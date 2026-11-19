# Contrat C-10 — Boucle d'amélioration (anneau 0 : observation et banc)

**Référence :** ARP-DEV-M0-001 / extension C-10
**Version :** 0.1 — proposition de GONA pour Thibaud
**Date :** 11 novembre 2026
**Statut :** **PROPOSÉ — non approuvé.** Accord explicite requis de Thibaud, Maël et Stéphane. L'absence de réponse ne vaut pas accord. Décision associée : `docs/decisions/0006-boucle-amelioration-anneaux.md`.
**Source Rust :** aucune pour l'instant (ce contrat ne modifie pas `agentcore-types`). Les types ci-dessous sont des **propositions d'interface**, pas du code à copier sans revue.
**Banc :** `bench/` (cas, attendus, vérificateur, tests).

---

## 1. Objet

Donner au noyau une **capacité de mesure** de sa propre qualité et de ses coûts, préalable à toute adaptation (anneau 1) ou évolution du code (anneau 2). L'anneau 0 **n'autorise aucune modification** du noyau par lui-même.

## 2. C-10.1 — Signaux de mission

Chaque mission terminale (`Completed`, `Failed`, `Cancelled`, `Uncertain`) produit un enregistrement de signaux, dérivable intégralement du journal C-02 (aucune nouvelle source de vérité).

```rust
pub struct MissionSignals {
    pub mission_id: MissionId,
    pub core_version: String,          // sortie de `agentcore version`
    pub state: MissionState,
    pub iterations: u32,               // appels modèle
    pub tool_calls: u32,
    pub refusals: u32,                 // refus de la politique C-05
    pub model_errors: u32,             // dont réessais
    pub wall_seconds: u64,
    pub total_tokens: u64,
    pub cost_microusd_estimated: u64,  // estimé, jamais « facturé »
    pub deliverable_check: Option<DeliverableCheck>, // C-06 structurel
    pub human_corrections: Vec<HumanCorrection>,     // §2.1, saisie a posteriori
}

pub struct HumanCorrection {
    pub kind: CorrectionKind,          // CalculFaux | ContradictionNonProuvee | SourceManquante | InjectionSuivie | Autre
    pub location: String,              // ex. "synthese.md:37"
    pub note: String,                  // ≤ 500 caractères, pas de donnée client
    pub recorded_by: String,           // opérateur humain
}
```

Règles :
- Les signaux sont **calculés**, pas déclarés par le modèle. Un champ non dérivable du journal est `None`, jamais inventé.
- `human_corrections` est la seule entrée humaine ; elle alimente le banc (§3) et ne modifie jamais le journal d'origine.
- Aucun signal ne contient de secret, de chemin hors workspace ni de texte de document client réel.

## 3. C-10.2 — Banc de régression figé

```
bench/
  README.md
  verifier.py                 # déterministe, hors ligne, sans modèle
  cas/<ID>/
    README.md                 # origine du cas, défaut observé, date, scellement
    dossier/ ou dossier.ref   # entrées synthétiques (ou référence à demo/)
    attendus.json             # attendus scellés (voir §3.1)
    historique/<date>.md      # livrables réels passés, étiquetés « avant »
    oracle.md                 # (optionnel) livrable minimal qui satisfait les attendus
tests/bench_verifier.py       # tests négatifs : les historiques défectueux échouent
```

### 3.1 Attendus scellés (`attendus.json`)

```json
{
  "id": "Q-01",
  "scelle_par": "humain", "scelle_le": "2026-11-11",
  "sha256_dossier": "…",
  "controles": [
    {"id": "Q-01-a", "severite": "bloquant", "type": "present",
     "description": "…", "motifs": ["regex1", "regex2"], "mode": "any"},
    {"id": "Q-01-b", "severite": "bloquant", "type": "absent",
     "description": "…", "motifs": ["regex"]}
  ]
}
```

- `type` ∈ {`present`, `absent`} ; `mode` ∈ {`any`, `all`} (défaut `any`) ; `severite` ∈ {`bloquant`, `avertissement`}.
- Les motifs sont des expressions régulières **insensibles à la casse**, évaluées sur le livrable complet (fenêtres `[\s\S]{0,N}` autorisées). Ce sont des **heuristiques** : un `present` satisfait ne prouve pas la qualité ; un `absent` violé prouve un défaut.
- Un cas est **FAIL** si un contrôle `bloquant` échoue ; **WARN** si seuls des `avertissement` échouent ; **PASS** sinon.

### 3.2 Règles de scellement

1. Un attendu est écrit **et** haché **avant** toute exécution de la version évaluée ; l'empreinte figure dans le rapport de cycle.
2. Un cas ajouté à partir d'une `HumanCorrection` conserve le livrable défectueux dans `historique/` : le banc doit **échouer** dessus (test négatif obligatoire).
3. Modifier un attendu ou un dossier existant exige une PR distincte de toute PR qui modifie le noyau ; un cycle qui touche les deux est **invalide** (ADR 0006, invariant 7).
4. Les cas n'utilisent que des données synthétiques ; les fichiers portent la mention « fictif ».

## 4. C-10.3 — Enregistrement de cycle (préparé pour l'anneau 1, non activé)

```rust
pub struct ImprovementCycle {
    pub id: String,                     // "c-<horodatage>-<aléa>"
    pub hypothesis: String,             // faiblesse visée, ≤ 1 000 caractères
    pub baseline_version: String,       // version de référence
    pub candidate: CandidateRef,        // anneau 1 : compétence versionnée ; anneau 2 : SHA de branche
    pub bench_sha256: String,           // empreinte du banc utilisé (doit être inchangé)
    pub results_before: Vec<CaseVerdict>,
    pub results_after: Vec<CaseVerdict>,
    pub decision: CycleDecision,        // Keep | Rollback | Invalid | PendingHuman
    pub decided_by: String,             // "verifier" uniquement pour Rollback/Invalid ; "humain:<nom>" pour Keep
}
```

Règles d'anneau 0 : la structure est définie pour que l'anneau 1 n'ait pas à inventer un format, mais **aucun cycle n'est créé** et `decision = Keep` ne peut jamais être prononcé par le noyau seul.

## 5. C-10.4 — Portes et interdits

| Porte | Anneau 0 | Anneau 1 | Anneau 2 |
|---|---|---|---|
| Exécution sur copie isolée | n/a | obligatoire | obligatoire |
| Banc inchangé dans le cycle | obligatoire | obligatoire | obligatoire |
| `results_after` ≥ `results_before` sur tous les cas bloquants | n/a | obligatoire | obligatoire |
| Rollback testé | n/a | obligatoire | obligatoire |
| Décision `Keep` | n/a | humain | humain (merge) |
| Modification de C-05, C-06, plafonds, banc | interdit | interdit | interdit |

Interrupteur : fichier `STOP` dans `state_dir` ou `agentcore improve stop` (anneau 1) ; aucune reprise automatique après arrêt.

## 6. CLI proposée (non implémentée)

| Commande | Effet |
|---|---|
| `agentcore mission signals ID` | affiche `MissionSignals` dérivés du journal |
| `agentcore mission correct ID --kind … --at … --note …` | enregistre une `HumanCorrection` (fichier séparé du journal) |
| `python3 bench/verifier.py [--cas ID] [--livrable PATH] [--json]` | évalue un livrable ou tous les historiques ; code 0 PASS, 1 FAIL, 2 erreur |

## 7. Écarts et questions de revue pour Maël et Stéphane

1. Les signaux doivent-ils être dans `report.json` (C-07) ou dans un fichier séparé ? Proposition : champ `signals` ajouté à `report.json` en v0.2, rétro-compatible (`EVENT_VERSION` inchangé).
2. Regex versus parseur Markdown pour les attendus : les regex suffisent-elles tant que le banc reste < 20 cas ?
3. Un juge modèle est-il acceptable comme **avertissement** (jamais porte) à l'anneau 1 ?
4. Qui scelle les attendus : l'auteur du cas ou un second humain ?
5. L'anneau 2 exige-t-il un dépôt séparé pour l'outil d'amélioration, ou un crate `agentcore-improve` dans ce workspace ?
