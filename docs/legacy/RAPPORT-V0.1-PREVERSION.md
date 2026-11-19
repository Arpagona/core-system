# Agent Core v0.1 — rapport de préversion (11/11/2026)

**Version installée dans agentcore-dev (192.168.68.240) :** `0.1.0+6d20ef8e488d` (branche `spike/v0.1-noyau`, PR #14). Le code du binaire est identique à `07d0f9fc` ; seul le script de recette a changé.
**Statut :** tous les critères fonctionnels v0.1 sont démontrés dans la VM avec le vrai modèle. **Réception non prononcée** : contrats M0 et règle de dépendances acceptés par Thibaud seul (accord de Maël et Stéphane manquant) ; aucune fusion.
**Modèle :** opencode-go / deepseek-v4.1-flash. Plafonds : 0,50 $ / mission, 20 $ / 24 h glissantes (ADR 0004, commit `9f0045a`).

## Critères v0.1 → preuve
| Exigence | Preuve (VM, vrai modèle sauf mention) |
|---|---|
| Mission CLI → synthèse vérifiée | R1 PASS ; démo m-20261110-195146-58feac (12 314 octets, 0,0096 $) |
| Persistance après redémarrage | reboot VM : nouveau boot_id, 15 missions identiques, 24 empreintes SHA-256 identiques ; mission terminée non réexécutée |
| Interruption sans rejeu d'effet incertain | reboot **forcé** pendant l'appel modèle 3 → `Running` → `resume` → Completed, 1 seule écriture (m-20261111-062916-4bcef8) ; R8 kill -9 PASS ; R9 écriture incertaine → code 3, pas de rejeu, résolution humaine (coupure simulée par troncature d'un journal réel) |
| Refus hors périmètre | R2 PASS : le modèle a tenté de lire une annexe réelle hors périmètre → `REFUSÉ (perimetre-fichiers)`, refus signalé dans le livrable. Écriture hors périmètre : non tentée par le vrai modèle, prouvée seulement par les tests à modèle scripté |
| Limites durée / itérations / coût | R5, R4, R3 PASS (arrêt à 0,0080 $ pour un plafond de 0,02 $) ; plafond quotidien : test automatisé uniquement |
| Erreurs sans fausse réussite | R6 clé invalide → Failed/Auth, aucun livrable ; R7 entrée illisible refusée avant création |
| Installable / réversible | `install.sh` (sauvegarde préalable), `rollback.sh`, 3 installations successives réussies |

Recette `recette.sh` du 11/11 : **11 PASS, 0 FAIL, 0 non concluant** (`~/recette/20261111T063124Z/verdicts.txt` dans la VM).

## Tests automatisés
`cargo test --workspace` : 27 tests verts (13 de contrat, 13 de scénario à modèle scripté, 1 d'atelier). CI GitHub verte (rust, guardian, docs, documentation) sur les PR #12, #13 et #14.

## Limites connues
- Après une coupure, une mission reste `Running` jusqu'à `agentcore mission resume ID` : pas de reprise automatique (choix de sûreté, pas de démon).
- Coût **estimé** sur tarifs prudents configurés, pas facturé ; consommation réelle de l'abonnement opencode-go non vérifiée.
- Clé : clé opencode d'Hermes copiée dans `/etc/agentcore/api_key` (root:agentcore 0640) ; clé dédiée recommandée.
- Un fournisseur, 4 outils, pas de démon ni d'API ; Linux uniquement ; vérification du livrable structurelle (taille, citations), pas qualitative.

## Relancer soi-même
    ssh agentcore@192.168.68.240
    agentcore version
    agentcore mission run --input /opt/agentcore/current/demo --goal "Synthétise ce dossier pour un rendez-vous commercial."
    agentcore mission list ; agentcore mission status ID ; agentcore mission log ID ; agentcore mission resume ID
    /opt/agentcore/current/recette.sh          # recette complète, ~6 min, < 0,15 $
Retour arrière : `sudo /opt/agentcore/current/rollback.sh` ; sauvegardes dans `/var/backups/agentcore/`.
