# Plan de développement — noyau agentique ARPAGONA

**Référence :** ARP-DEV-PLAN-001
**Version :** 0.1 — proposition de Thibaud
**Date :** 10 novembre 2026
**Statut :** proposition à valider à trois (Thibaud, Maël, Stéphane) avant tout développement dépendant des contrats
**Documents liés :** `ARP-DEV-CDC-001` v1.0 (atelier), cadrage Atelier v0.1, `docs/ARCHITECTURE.md`, `docs/INTERFACES.md`

---

## 1. Définition du produit

**Une application Linux autonome**, installée sur une machine virtuelle Debian, qui exécute des missions agentiques bornées : elle reçoit une mission, interroge un modèle, choisit des actions, les exécute sous contrôle, journalise tout, et peut être arrêtée puis reprise sans double effet.

Deux composants livrables :

| Composant | Rôle |
|---|---|
| `agentcored` | démon systemd : boucle agentique, journal, exécution, API locale |
| `agentcore` | CLI : soumettre une mission, suivre son état, approuver ou annuler |

**Ce n'est ni un fork ni une copie de Hermes ou d'OpenClaw.** On reprend des principes éprouvés : boucle courte, outils typés, permissions explicites, journal durable, reprise après crash. Le code est original et plus petit : c'est le principal avantage — un socle lisible, auditable et installable chez un client.

**Différenciateur recherché :** un noyau assez petit pour être audité en une journée, assez solide pour tourner chez un client sans nous, et assez générique pour porter plusieurs usages métier via des compétences.

## 2. Périmètre de la v0.1

### Inclus

- Une mission à la fois par instance, plusieurs en file ; durée bornée.
- Un fournisseur de modèle **OpenAI-compatible** (cloud ou serveur local), interface unique.
- Quatre outils réels : lecture de fichier, écriture bornée à un espace de travail, commande shell sur liste blanche, requête HTTP sur liste blanche.
- Politique d'autorisation par défaut refus, avec **validation humaine** pour les actions sensibles.
- Journal append-only et reprise après arrêt brutal sans rejouer un effet déjà produit.
- API HTTP locale (127.0.0.1), unité systemd durcie, sauvegarde et retour arrière.

### Explicitement exclu de la v0.1

Interface graphique, multi-utilisateur, multi-client, base vectorielle/RAG, MCP, navigateur automatisé, voix, auto-modification, place de marché de compétences, orchestration multi-agents, application mobile, connecteurs CAO/PDM/ERP.

**Règle de discipline :** toute idée hors périmètre part en annexe « v0.2+ », jamais dans la branche courante. C'est la leçon directe de GONA Core, où l'élargissement du cahier des charges a coûté plusieurs jours pour un usage non démontré.

## 3. Architecture cible

### 3.1 Crates

```
crates/
├── agentcore-types/     # structures partagées, sérialisation, versionnement des contrats
├── agentcore-core/      # machine à états de mission, boucle de décision
├── agentcore-model/     # port ModelPort + adaptateurs (OpenAI-compatible, faux modèle)
├── agentcore-tools/     # registre typé + outils intégrés
├── agentcore-policy/    # autorisation, budgets, périmètre d'action
├── agentcore-store/     # SQLite, journal append-only, reprise
├── agentcore-runtime/   # exécution, délais, annulation, concurrence
└── agentcore-api/       # HTTP local + CLI
bins/
├── agentcored/
└── agentcore/
```

**Règle de dépendance :** `types` ne dépend de rien ; `core` dépend de `types` et des traits, jamais d'un adaptateur concret ; `model`, `tools`, `store`, `api` sont des implémentations branchées au démarrage. Aucun cycle, aucune dépendance entre adaptateurs. Cette règle est vérifiable automatiquement (`cargo metadata`) et déjà outillée dans l'atelier.

### 3.2 Machine à états d'une mission

```
queued → running → waiting_approval → running → completed
              ↘ failed        ↘ cancelled        ↘ uncertain
```

Chaque transition est journalisée avec un identifiant d'événement. Une action ayant pu produire un effet externe sans accusé de réception aboutit à `uncertain` : **jamais de rejeu automatique**, une décision humaine est requise.

### 3.3 Journal

Table append-only : `mission_id`, `seq`, `type`, `payload`, `created_at`, `idempotency_key`. L'état de mission est une projection du journal, pas une donnée écrite séparément. C'est ce qui rend la reprise après crash démontrable plutôt que supposée.

## 4. Modèle de sûreté

| Contrôle | Règle v0.1 |
|---|---|
| Défaut | refus ; toute action est explicitement autorisée par une règle |
| Périmètre fichiers | racine de travail unique, chemins résolus, refus des liens sortants (`..`, symlinks) |
| Shell | liste blanche de commandes + arguments, pas de shell interactif, délai maximal |
| Réseau | liste blanche de domaines, sortie HTTP journalisée |
| Secrets | variables d'environnement ou fichier `0600`, jamais dans le journal ni dans le prompt |
| Budgets | tokens, nombre d'appels d'outils, durée murale, par mission ; dépassement = arrêt |
| Approbation | action marquée sensible → mission en `waiting_approval`, décision humaine tracée |
| Audit | toute décision de politique est journalisée avec sa règle et son motif |

**Ce que ce modèle ne garantit pas :** l'isolation entre clients (v0.1 mono-client), ni la résistance à un modèle malveillant, ni le confinement noyau. Le durcissement réel viendra avec systemd (ProtectSystem, ProtectHome, NoNewPrivileges, PrivateTmp, restrictions réseau) et sera testé, pas seulement déclaré.

## 5. Cible de déploiement : machine virtuelle sur Atlas

### 5.1 Constat mesuré le 10 novembre 2026

Atlas (`192.168.68.20`) est l'**hôte Proxmox** lui-même, pas une machine libre :

- Debian 13 (trixie), 8 processeurs, 31 Gio de RAM, 1 Gio utilisé ;
- racine `pve-root` 94 Gio, 6,1 Gio utilisés, **84 Gio disponibles** ;
- présence d'un iGPU Intel sur l'hôte (`card1`, `renderD128`) ;
- accès SSH opérationnel avec la clé `id_ed25519_atlas_gona` — **la clé `id_ed25519_atlas` référencée dans `~/.ssh/config` est refusée**, à corriger.

### 5.2 Machine virtuelle — **créée le 10 novembre 2026**

| Paramètre | Valeur réalisée |
|---|---|
| Hôte | Atlas, Proxmox VE 9.2.25, noyau 7.0.14-28-pve |
| VMID / nom | `100` / `agentcore-dev` |
| Type | VM KVM, image cloud Debian 13 (trixie) genericcloud |
| Système | Debian 13.7, noyau 6.12 cloud, sans bureau |
| Ressources | 4 vCPU, 8 Gio de RAM, 40 Gio (`local-lvm`, thin) |
| Réseau | `vmbr0`, **192.168.68.240/24**, passerelle et DNS 192.168.68.1 |
| Accès | SSH par clé uniquement (`gona-atlas`), utilisateur `agentcore`, `qemu-guest-agent` actif |
| Démarrage | `onboot=1`, ordre 10, délai 30 s |
| Point de reprise | snapshot `baseline-post-install` (installation propre) |

Contrôles effectués : image téléchargée avec somme SHA-512 vérifiée, VM démarrée, IP statique appliquée et testée après redémarrage, agent invité interrogeable depuis Proxmox, SSH opérationnel.

Consommation observée : disque de la VM 596 Mio utilisés sur 40 Gio. `local-lvm` dispose de 348 Gio libres ; aucune autre VM n'existe sur Atlas à cette date.

L'adresse .240 a été choisie hors de la plage dynamique constatée (.55 attribué en DHCP) ; à confirmer avec la configuration du routeur.

### 5.3 Accès au modèle — **principe validé le 10 novembre 2026, fournisseur non choisi**

**Principe retenu par Thibaud : démarrer avec un modèle cloud (option A).** Le fournisseur, le modèle précis et le budget **ne sont pas validés** (correction du 10/11/2026 : une version antérieure de ce document présentait à tort `opencode-go` / `deepseek-v4.1-flash` comme approuvé).

Le routeur local écoute sur `127.0.0.1:8080` (et vLLM sur `127.0.0.1:8022`) sur le poste de travail : une VM sur Atlas ne peut pas l'atteindre sans exposition réseau. Ce point est donc écarté pour la v0.1.

| Élément | Valeur retenue |
|---|---|
| Type d'accès | API cloud **OpenAI-compatible** |
| Fournisseur et modèle | **à décider** — candidats à comparer (dont `opencode-go`), aucun choix approuvé |
| Configuration | `base_url`, `model`, `api_key_env` dans `/etc/agentcore/config.toml` (`0600`), clé jamais dans Git |
| Coût | **plafond de dépenses à décider** ; budget par mission obligatoire : plafond d'appels et de tokens, arrêt propre au dépassement |
| Réversibilité | `ModelPort` unique ; un adaptateur local pourra être ajouté sans toucher au noyau |

Conséquences à assumer et à écrire dans l'ADR :

- le code des missions transite vers un fournisseur externe ; aucune donnée client réelle dans les prompts en v0.1 ;
- le coût par mission devient mesurable et doit être journalisé (tokens consommés par mission) ;
- la latence dépend du réseau : les délais et le retry borné ne sont pas optionnels ;
- la souveraineté locale reste une option future, pas un prérequis de la v0.1.

**Le noyau est identique dans les deux cas** : c'est précisément l'intérêt du port `ModelPort`.

### 5.4 Exploitation

Unité systemd durcie, utilisateur système dédié, `/var/lib/agentcore` pour l'état, `/etc/agentcore` pour la configuration `0600`, journal système, sauvegarde quotidienne de la base + journal, procédure de retour arrière versionnée. La VM n'a **aucun accès** aux données clients réelles en v0.1.

## 6. Jalons

Estimations en jours-homme, à trois en parallèle après validation des contrats. Total ≈ **18 j-h**, soit environ **3 semaines calendaires** hors validations.

| Jalon | Contenu | Livrable démontrable | Critère d'acceptation | Charge |
|---|---|---|---|---|
| **M0 — Socle** | crates réels, contrats C-01…C-07 figés, ADR, faux modèle déterministe | `agentcore mission --fake` sur mission synthétique | état de mission projeté depuis le journal ; tests de contrat verts ; aucun accès réseau | 2 j |
| **M1 — Boucle et reprise** | boucle de décision, store SQLite, arrêt/reprise | mission de 3 étapes, `kill -9` au milieu, reprise sans double effet | état `uncertain` correct, zéro rejeu d'effet, journal rejouable | 3 j |
| **M2 — Modèle réel** | adaptateur OpenAI-compatible, délais, retry borné, budgets | mission réelle sur un modèle choisi | réponse structurée valide, dépassement de budget arrêté proprement, erreur fournisseur non confondue avec succès | 2 j |
| **M3 — Outils et politique** | registre typé, 4 outils, défaut refus, approbation | tentative d'écriture hors espace de travail refusée ; action sensible bloquée en attente | refus journalisé avec motif ; approbation nécessaire avant effet ; 100 % des appels tracés | 4 j |
| **M4 — API et observabilité** | HTTP local, health, logs JSON, métriques minimales | `curl` soumet, suit et approuve une mission | aucune écoute hors boucle locale ; annulation effective sous 5 s | 2 j |
| **M5 — Packaging et VM** | binaire statique, unité systemd durcie, sauvegarde, retour arrière | installation reproductible sur la VM Atlas | installation sur VM vierge rejouée deux fois ; redémarrage hôte → service sain ; restauration testée | 2 j |
| **M6 — Premier usage borné** | un cas concret sur données synthétiques, évaluation | note structurée produite depuis un dossier d'entrée | résultat utile jugé par un humain ; limites écrites ; coût et latence mesurés | 3 j |

**Ordre imposé :** M0 bloque tout le reste. M1 et M2 peuvent avancer en parallèle sur des branches distinctes après M0. M3 dépend des contrats d'outils. M5 ne démarre pas avant M3, pour ne pas empaqueter un noyau non sûr.

### Répartition proposée (à confirmer par les intéressés)

- **Thibaud** : M0, M1, M2 — types, machine à états, boucle, port modèle.
- **Maël** : M3, M4 — outils, politique, API.
- **Stéphane** : M5, M6 — packaging, VM, cas d'usage et évaluation.

Chacun reste relecteur des autres : c'est le point où l'atelier se prouve.

## 7. Méthode de développement assistée par agents

1. **Une Issue par jalon**, avec périmètre, exclusions, critères d'acceptation et démonstration attendue.
2. **Une branche courte** (`feat/types-mission`), une PR liée à l'Issue. Jamais de commit direct sur `main`.
3. **L'agent lit `AGENTS.md`**, les contrats et l'ADR pertinent avant d'écrire. Il annonce la zone modifiée et les contrats impactés.
4. **Tests d'abord sur les contrats** : un contrat sans test de contrat ne rentre pas.
5. **Chaque PR contient la commande de démonstration** exécutée et son résultat, pas une affirmation.
6. **Aucun agent ne fusionne son propre travail** ; Guardian déterministe + relecture humaine.
7. **Budget d'agent borné par jalon** : si un agent tourne plus longtemps que prévu sur un jalon, on arrête et on découpe — l'échec se traite par le périmètre, pas par la persévérance.
8. **Une ADR par décision structurante** (fournisseur de modèle, format de journal, stratégie de reprise).

## 8. Stratégie de test

| Niveau | Contenu | Déterministe |
|---|---|---|
| Contrats | sérialisation, compatibilité, versions | oui |
| Boucle | faux modèle scripté : succès, refus, erreur, budget | oui |
| Politique | cas autorisés/refusés, chemins piégeux, arguments shell | oui |
| Reprise | crash à chaque étape, `uncertain`, non-rejeu | oui |
| Intégration réelle | un modèle réel, une mission complète | non — tracé et daté |
| Bout en bout VM | installation, systemd, redémarrage, sauvegarde | semi |

Aucun test de CI n'appelle un modèle payant. Les tests réels sont explicitement marqués et exécutés à la demande.

## 9. Risques et critères d'arrêt

| Risque | Réponse |
|---|---|
| Élargissement du périmètre | règle v0.2+ ; revue de périmètre à chaque fin de jalon |
| Sur-ingénierie (précédent GONA Core) | 7 crates maximum en v0.1, aucun mécanisme sans test qui échoue |
| Contrats instables | figés en M0, toute évolution = ADR + accord des trois |
| Modèle inaccessible depuis la VM | option A par défaut, décision tracée |
| Fausse impression de sécurité | durcissement systemd testé ; limites écrites dans le rapport |
| Dépendance à un fournisseur | `ModelPort` unique, adaptateurs interchangeables |
| Trois personnes, trois rythmes | jalons courts, démonstration obligatoire, pas de jalon ouvert plus d'une semaine |

**Critères d'arrêt (kill criteria) :** si à la fin de M3 le noyau ne termine pas une mission réelle de 5 étapes sur données synthétiques sans intervention, on arrête et on réévalue l'approche avant d'aller plus loin. Si le coût par mission dépasse un seuil convenu ou la latence dépasse 2 minutes pour une mission simple, on traite la performance avant M5.

## 10. Décisions ouvertes à trois

| # | Question | État |
|---|---|---|
| 1 | Fournisseur de modèle pour M2 | **principe acté le 10/11/2026** par Thibaud : cloud OpenAI-compatible, local en option future (ADR 0004). **Fournisseur, modèle précis et plafond de dépenses : non décidés** |
| 2 | Création de la VM sur Atlas | **réalisée le 10/11/2026** (VMID 100, `agentcore-dev`, 192.168.68.240) ; déploiement de test autorisé par Thibaud |
| 3 | Runtime des outils sensibles | proposition : shell sur liste blanche, jamais de shell libre |
| 4 | Niveau d'approbation humaine | proposition : toute écriture hors espace de travail + toute commande shell |
| 5 | Cas d'usage de M6 | à choisir : dossier technique client, ou préparation de devis |
| 6 | Licence du code | privé pour l'instant, décision distincte |
| 7 | Qui porte quel jalon | proposition section 6 |
| 8 | Critère de succès de la v0.1 | une mission réelle utile, jugée par un humain, reproductible |

## 11. ADR 0004 proposée — fournisseur de modèle de la v0.1

**Contexte.** Le noyau doit appeler un modèle depuis une VM Atlas ; le routeur local n'écoute qu'en boucle locale.

**Options.** (A) API cloud OpenAI-compatible. (B) Exposer le routeur local sur le LAN. (C) Passerelle sur Atlas.

**Décision.** Option A sur le principe. Adaptateur OpenAI-compatible configurable (`base_url`, `model`, `api_key_env`), clé par variable d'environnement. **Fournisseur, modèle et plafond de dépenses restent à décider.**

**Justification.** Décision de principe de Thibaud du 10/11/2026 ; pas de nouvelle surface d'attaque réseau ; réversible par le port `ModelPort`.

**Conséquences.** Code des missions transmis à un tiers (aucune donnée client réelle en v0.1) ; coût et latence à mesurer par mission ; délais et retry bornés obligatoires ; adjonction ultérieure d'un adaptateur local sans modification du noyau.

**Relecture requise.** Maël et Stéphane, avant M2.

## 12. Prochaine action

1. **Thibaud** : valider ou corriger ce plan, puis l'ouvrir en PR dans l'atelier (`docs/PLAN-NOYAU.md`) après revue de la PR nº 1.
2. **Modèle** : principe cloud OpenAI-compatible décidé (section 5.3, ADR 0004) ; **fournisseur, modèle et plafond de dépenses à décider avant M2**.
3. **M0** démarre dès que les contrats C-01…C-07 sont acceptés à trois ; le reste du plan n'attend pas la VM.
4. **VM Atlas** : créée (section 5.2) ; installation de versions de test autorisée par Thibaud, sauvegarde et retour arrière obligatoires.

---

*Plan de travail, non un engagement figé. Toute décision structurante sera datée, justifiée et versionnée en ADR.*
