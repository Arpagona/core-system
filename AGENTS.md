# Règles communes aux agents

Lire README.md, CONTRIBUTING.md et les ADR pertinents avant modification.

- Une Issue, une branche dédiée et une PR par chantier ; pas de travail direct sur main.
- Documenter les changements de contrat ; tests et documentation accompagnent le code. Les décisions contestées nécessitent une revue humaine.
- Ne jamais approuver ou fusionner seul son propre travail ; la CI ne remplace pas la revue humaine.
- Aucun secret ni donnée client dans Git, CI ou revue IA ; données synthétiques par défaut.
- Courriels en brouillon ; aucun effet externe, déploiement de production, permission ou engagement sans validation humaine appropriée.
- Ne pas présenter une proposition comme une décision ni inventer un accord.

Validation locale : voir `.github/workflows/ci.yml` ; parcours complet sans clé : `python3 -m unittest discover -s tests/dev`. Démarrage : `docs/DEMARRAGE-DEVELOPPEUR.md`.
- Python : bibliothèque standard seulement (décision du 12/11) ; ajouter une dépendance demande une discussion.
