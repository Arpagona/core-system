# Contrats minimaux M0 — scénario « synthèse de dossier »

**Référence :** ARP-DEV-M0-001
**Version :** 0.1 — proposition de GONA pour Thibaud
**Date :** 10 novembre 2026
**Statut :** **PROPOSÉ — non approuvé.** Accord explicite requis de Thibaud, Maël et Stéphane avant tout développement dépendant et avant intégration dans `main`. L'absence de réponse ne vaut pas accord.
**Source Rust :** `crates/agentcore-types/src/lib.rs` (identifiants `C-01` … `C-07` cités dans le code)
**Tests de contrat :** `crates/agentcore-types/tests/contrats.rs`

---

## 1. Scénario unique de la v0.1

> Depuis la CLI, l'opérateur donne une mission : *lire un dossier de documents synthétiques et produire une synthèse dans l'espace de travail de la mission*. Le noyau appelle un vrai modèle cloud, choisit et exécute les outils autorisés, vérifie le livrable et rend compte.

```
agentcore mission run --input ./dossier-synthetique --goal "Synthétise ces documents" 
  → mission créée (journal durable)
  → boucle : modèle → proposition d'outil → politique → exécution → résultat → modèle …
  → l'agent appelle `finish` avec le chemin du livrable
  → vérification déterministe du livrable
  → rapport : completed | failed | uncertain | cancelled, usage, coût estimé, erreurs
```

Tout ce qui ne sert pas ce scénario est **hors v0.1** (voir §9).

## 2. Découpage proposé (3 crates au lieu de 8)

| Crate | Rôle | Dépend de |
|---|---|---|
| `agentcore-types` | **contrats communs** C-01…C-07 : types, traits, erreurs | `serde`, `serde_json` |
| `agentcore-core` | boucle, politique, journal fichier, outils intégrés, adaptateur OpenAI-compatible | `agentcore-types`, client HTTP |
| `agentcore` (binaire) | CLI | `agentcore-core` |

Seul `agentcore-types` est un contrat commun. L'intérieur de `agentcore-core` reste libre (modules internes), ce qui évite de figer 8 frontières avant de savoir lesquelles tiennent. Le découpage du plan (§3.1, 8 crates) reste possible plus tard, par extraction.

## 3. C-01 — Mission

```rust
pub struct MissionSpec {
    pub id: MissionId,              // "m-<horodatage>-<aléa>", unique, jamais réutilisé
    pub goal: String,               // consigne opérateur, ≤ 4 000 caractères
    pub input_dirs: Vec<PathBuf>,   // lecture seule, chemins absolus canoniques
    pub workspace: PathBuf,         // seul endroit inscriptible, propre à la mission
    pub tools: Vec<String>,         // outils autorisés pour cette mission (sous-ensemble du registre)
    pub limits: Limits,             // C-06
    pub deliverable: DeliverableSpec,
}

pub struct DeliverableSpec {
    pub path: String,               // relatif au workspace, ex. "synthese.md"
    pub min_bytes: u64,             // ex. 200
    pub max_bytes: u64,             // ex. 200 000
    pub must_cite_inputs: bool,     // chaque document lu doit être cité par son nom
}

pub enum MissionState { Queued, Running, Completed, Failed, Cancelled, Uncertain }
```

Règles :
- `Completed` **uniquement** si le modèle a appelé `finish` **et** la vérification déterministe du livrable (§8) a réussi.
- Tout dépassement de limite → `Failed` avec `FailureReason::LimitExceeded(...)`.
- `Uncertain` : un effet a pu se produire sans résultat journalisé ; aucune reprise automatique (C-02).
- États terminaux : `Completed`, `Failed`, `Cancelled`. `Uncertain` attend une décision humaine.

## 4. C-02 — Journal et reprise

Journal **append-only** par mission : `<état>/missions/<id>/journal.jsonl`, une ligne JSON par événement, `fsync` après chaque écriture. L'état de mission est une **projection** du journal ; il n'est stocké nulle part ailleurs.

```rust
pub struct Event { pub v: u32 /* = 1 */, pub mission: MissionId, pub seq: u64, pub at_ms: u64, pub kind: EventKind }

pub enum EventKind {
    MissionCreated { spec: MissionSpec },
    MissionStarted { attempt: u32 },          // nouvelle exécution du processus (1, 2, …)
    ModelCalled { iteration: u32 },
    ModelReplied { iteration: u32, usage: Usage, tool_calls: Vec<ToolCall>, text: Option<String> },
    ModelFailed { iteration: u32, error: ModelError },
    PolicyDecided { call_id: String, decision: Decision },
    ToolStarted { call_id: String, tool: String, effect: Effect },   // écrit AVANT l'effet
    ToolFinished { call_id: String, outcome: ToolOutcome },          // écrit APRÈS l'effet
    DeliverableChecked { report: DeliverableReport },
    Resolved { call_id: String, by: String, resolution: Resolution }, // décision humaine sur un incertain
    MissionEnded { state: MissionState, reason: Option<FailureReason>, summary: Option<String> },
}
```

**Règle de reprise (cœur du contrat) :**

| Dernier état d'un appel | Effet `ReadOnly` | Effet `WorkspaceWrite` |
|---|---|---|
| `ToolStarted` sans `ToolFinished` | réexécution autorisée (sans effet) | **`Uncertain`, aucun rejeu** |
| `ToolFinished` présent | jamais réexécuté ; résultat relu du journal | idem |

- `agentcore mission resume <id>` reprend une mission non terminale ; le contexte modèle est reconstruit depuis le journal.
- `agentcore mission resolve <id> --call <call_id> --as done|not-done` trace la décision humaine puis permet la reprise.
- Un verrou exclusif sur le répertoire de mission interdit deux processus sur la même mission.
- Une ligne finale tronquée (crash pendant l'écriture) est ignorée et signalée ; toute autre ligne invalide arrête la reprise (journal corrompu, pas de devinette).

## 5. C-03 — Port modèle

```rust
pub trait ModelPort {
    fn complete(&self, req: &ModelRequest) -> Result<ModelResponse, ModelError>;
}
pub struct ModelRequest { pub messages: Vec<Message>, pub tools: Vec<ToolSpec>, pub max_output_tokens: u32 }
pub struct ModelResponse { pub text: Option<String>, pub tool_calls: Vec<ToolCall>, pub usage: Usage, pub finish: FinishReason }
pub struct ToolCall { pub id: String, pub name: String, pub arguments: serde_json::Value }
pub struct Usage { pub input_tokens: u64, pub output_tokens: u64 }
pub enum ModelError { Timeout, Transport(String), Auth, RateLimited, Provider { status: u16, message: String }, InvalidResponse(String) }
```

- Appel bloquant avec délai. Chaque itération déclenche au plus un envoi, même après une erreur transitoire. L’adaptateur HTTP ne suit pas les redirections.
- À la reprise, un appel sans résultat journalisé clôture la mission en échec avec une cause indiquant que la facturation est inconnue. Si l’erreur a déjà été journalisée, la clôture conserve cette erreur.
- Avant l’envoi, le journal enregistre une réservation estimée. Le compteur des 24 heures la remplace par le coût calculé à partir de l’usage si une réponse est reçue. Il conserve la réservation dans la fenêtre de 24 heures si l’usage manque. Le rapport signale un coût incomplet et présente la réservation à part. Les anciens appels sans réservation restent lisibles et signalés comme incomplets lorsque leur résultat manque. L’adaptateur cloud requiert les compteurs d’entrée et de sortie, y compris lorsque le fournisseur indique explicitement zéro.
- Une proposition du modèle **n'autorise rien** : elle passe toujours par C-05.
- Adaptateurs v0.1 : OpenAI-compatible (`/chat/completions` avec `tools`), et `ScriptedModel` réservé aux tests.

## 6. C-04 — Outils

```rust
pub enum Effect { ReadOnly, WorkspaceWrite }
pub struct ToolSpec { pub name: String, pub description: String, pub parameters: serde_json::Value /* JSON Schema */, pub effect: Effect }
pub trait Tool {
    fn spec(&self) -> ToolSpec;
    fn execute(&self, args: &serde_json::Value, ctx: &ToolContext) -> ToolOutcome;
}
pub enum ToolOutcome { Ok { output: serde_json::Value }, Err { kind: ToolErrorKind, message: String } }
pub enum ToolErrorKind { InvalidArguments, NotFound, Denied, TooLarge, Io, Timeout }
```

Outils v0.1 (quatre, tous nécessaires au scénario) :

| Outil | Effet | Rôle |
|---|---|---|
| `list_dir` | ReadOnly | lister un dossier d'entrée ou le workspace |
| `read_file` | ReadOnly | lire un fichier texte (≤ 256 Kio, tronqué au-delà avec indication) |
| `write_file` | WorkspaceWrite | écrire un fichier dans le workspace (≤ 1 Mio), écriture atomique (fichier temporaire + renommage) |
| `finish` | ReadOnly | déclarer la fin : `{ "deliverable": "synthese.md", "summary": "…" }` |

Une erreur d'outil est un `ToolOutcome::Err` renvoyé au modèle, **jamais** un succès.

## 7. C-05 — Politique d'autorisation

```rust
pub enum Decision { Allow { rule: String }, Deny { rule: String, reason: String } }
pub trait Policy { fn decide(&self, spec: &MissionSpec, call: &ToolCall, effect: Effect) -> Decision; }
```

- **Refus par défaut** : outil absent de `spec.tools` → `Deny`.
- Chemins : canonisés ; lecture autorisée seulement sous `input_dirs` ∪ `workspace` ; écriture seulement sous `workspace`. Refus de `..` sortant, des chemins absolus hors périmètre et des liens symboliques sortants.
- La vérification est **refaite au moment de l'effet** par l'outil (ouverture sans suivre les liens), pas seulement lors de la décision.
- Un `Deny` produit **zéro invocation** et est journalisé avec règle et motif ; le refus est renvoyé au modèle comme erreur d'outil.

## 8. C-06 — Limites et C-07 — Rapport / CLI

```rust
pub struct Limits {
    pub max_iterations: u32,       // appels modèle, défaut 20
    pub max_tool_calls: u32,       // défaut 60
    pub max_wall_seconds: u64,     // durée cumulée sur toutes les tentatives, défaut 600
    pub max_total_tokens: u64,     // entrée + sortie, défaut 200 000
    pub max_cost_microusd: u64,    // coût estimé, défaut 500 000 (= 0,50 $) — À VALIDER
}
pub enum FailureReason { LimitExceeded(LimitKind), Model(ModelError), DeliverableRejected(Vec<String>), NoFinish, Internal(String) }
```

- Le coût est **estimé** à partir des tarifs configurés (`price_input_per_mtok`, `price_output_per_mtok`) ; il est journalisé par appel. Ce n'est pas une facture : le rapport le dit.
- Les limites sont vérifiées **avant** chaque appel modèle et chaque appel d'outil.

**Vérification du livrable** (déterministe, sans LLM) : le fichier existe dans le workspace, n'est pas un lien, UTF-8, taille dans `[min_bytes, max_bytes]`, et, si `must_cite_inputs`, cite le nom de chaque fichier d'entrée lu. Elle ne juge pas la qualité : c'est le rôle de l'humain.

**CLI (C-07)** :

| Commande | Effet |
|---|---|
| `agentcore mission run --input DIR [--input DIR] --goal TEXTE [--deliverable synthese.md]` | crée et exécute |
| `agentcore mission list` / `status ID` / `log ID` | lecture du journal |
| `agentcore mission resume ID` | reprise |
| `agentcore mission resolve ID --call CALL --as done\|not-done` | décision humaine sur un incertain |
| `agentcore mission cancel ID` | état `Cancelled` |
| `agentcore version` | version, commit, configuration effective sans secret |

Codes de sortie : `0` completed, `2` failed, `3` uncertain, `4` cancelled, `1` erreur interne / usage. Le rapport final (texte + `report.json` dans le répertoire de mission) contient état, raison, chemin du livrable, résultat de vérification, itérations, appels d'outils, tokens, coût estimé, durée et version.

**Configuration** : `/etc/agentcore/config.toml` (ou `--config`) : `state_dir`, `base_url`, `model`, `api_key_env`, tarifs, délais, limites par défaut. La clé est lue dans l'environnement (fichier `EnvironmentFile` `0600` hors dépôt), jamais journalisée ni envoyée au modèle.

## 9. Écarts assumés par rapport à `PLAN-NOYAU.md`

| Plan | Proposition M0 | Raison |
|---|---|---|
| 8 crates | 3 crates, 1 seul contrat commun | ne pas construire la plateforme d'avance |
| démon `agentcored` + API HTTP | CLI au premier plan, pas de démon | scénario demandé = CLI ; démon en v0.2 |
| SQLite | JSONL append-only + `fsync` | moins de dépendances, lisible, suffisant mono-mission |
| shell et HTTP sur liste blanche, approbation humaine | absents | inutiles au scénario ; aucune action sensible donc pas d'approbation ; v0.2 |
| `waiting_approval` | remplacé par `Uncertain` + `resolve` | seule décision humaine nécessaire en v0.1 |

## 10. Tests de contrat associés

1. Un `Deny` produit zéro invocation d'outil.
2. Écriture hors workspace, `..`, lien symbolique sortant → refus journalisé.
3. `ToolStarted` WorkspaceWrite sans `ToolFinished` → projection `Uncertain`, aucun rejeu.
4. `ToolStarted` ReadOnly sans `ToolFinished` → réexécution autorisée.
5. Erreur modèle ou d'outil ≠ succès ; mission sans `finish` → `Failed(NoFinish)`.
6. Livrable absent / trop court / sans citation → `Failed(DeliverableRejected)`.
7. Chaque limite dépassée → `Failed(LimitExceeded)` et arrêt avant l'appel suivant.
8. Sérialisation stable des événements (`v = 1`) ; ligne finale tronquée tolérée, ligne interne corrompue refusée.

## 11. Questions de revue pour Maël et Stéphane

1. Le découpage 3 crates / 1 contrat commun vous convient-il ?
2. JSONL plutôt que SQLite pour la v0.1 ?
3. La règle de reprise du §4 est-elle suffisante (ReadOnly rejouable, écriture → incertain) ?
4. Report du démon, du shell, du HTTP et de l'approbation en v0.2 ?
5. Dépendances externes acceptées : `serde`, `serde_json`, un client HTTPS (`ureq` + `rustls`) — ce qui modifie `scripts/security_checks.py` et la CI (`cargo fetch --locked` avant les étapes hors ligne).
