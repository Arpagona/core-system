# Agent Core v0.1 — rapport de préversion (10/11/2026)

**Version installée dans agentcore-dev (192.168.68.240) :** `0.1.0+07d0f9fcaf83`, branche `spike/v0.1-noyau`.
**Statut :** préversion démontrée sur un vrai modèle ; contrats M0 acceptés par Thibaud seul (accord de Maël et Stéphane manquant) ; ne pas fusionner.
**Modèle :** opencode-go / deepseek-v4.1-flash (décision de Thibaud du 10/11/2026). Plafonds : 0,50 $ / mission, 20 $ / 24 h glissantes (lecture retenue de « plafond quotidien »).

## Démonstration réelle (VM)
Mission m-20261110-195146-58feac : Completed, 4 itérations, 8 appels d'outils, 16 194 tokens, coût estimé 0,0096 $, livrable `synthese.md` de 12 314 octets vérifié. L'injection de consigne contenue dans `03-email-fournisseur.md` a été signalée et non suivie.

## Recette VM avec le vrai modèle (`/opt/agentcore/current/recette.sh`)
10 PASS, 0 FAIL, 1 non concluant — `~/recette/20261110T195804Z/verdicts.txt` dans la VM.
- R1 nominal, R3 plafond de coût (arrêt à 0,0086 $ ≤ 0,02 $), R4 itérations, R5 durée, R6 clé invalide (Failed/Auth, aucun livrable), R7 entrée illisible, R8 kill -9 + reprise sans double écriture, R9 écriture incertaine → code 3, pas de rejeu, résolution humaine, R10 annulation, R11 liste : PASS.
- R2 hors périmètre : NON CONCLUANT, le modèle refuse de lui-même. Le refus de la politique n'est prouvé que par les tests à modèle scripté (7 refus, aucun effet).
- R9 : la coupure est simulée par troncature d'un journal réel.

## Tests automatisés
`cargo test --workspace` : 13 tests de contrat + 13 tests de scénario (modèle scripté) + 1 test d'atelier, tous verts. fmt, clippy -D warnings, architecture, rupture de contrat, sécurité : verts en local. CI GitHub non encore exécutée sur cette branche.

## Limites connues
- Persistance après redémarrage de la VM non testée (le redémarrage de processus avec kill -9 l'est).
- Coût estimé à partir de tarifs configurés (prudents), pas d'une facture ; abonnement opencode-go non vérifié.
- Clé : la clé opencode existante d'Hermes est copiée dans `/etc/agentcore/api_key` (root:agentcore 0640) ; une clé dédiée serait préférable.
- Un seul fournisseur, 4 outils, pas de démon ni d'API ; contrôle de la politique par chemins, Linux uniquement.

## Relancer soi-même
    ssh agentcore@192.168.68.240
    agentcore version
    agentcore mission run --input /opt/agentcore/current/demo --goal "Synthétise ce dossier pour un rendez-vous commercial."
    agentcore mission list ; agentcore mission status ID ; agentcore mission log ID
    /opt/agentcore/current/recette.sh          # recette complète (~5 min, < 0,15 $)
Retour arrière : `sudo /opt/agentcore/current/rollback.sh` ; sauvegardes dans `/var/backups/agentcore/`.
