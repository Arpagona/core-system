# Flux de collaboration

Issue (besoin, périmètre, exclusions, pilote et critères), branche dédiée, commits locaux, push vers branche, PR liée à l'Issue. Le merge intègre à main ; deploy installe un artefact : ce sont des opérations distinctes. Guardian intervient avant merge, non avant chaque commit.

| Changement | Processus de revue convenu |
|---|---|
| Interne sans impact interface | CI + Guardian indépendant + autre co-concepteur |
| Contrat intermodule, format partagé, API publique | CI + Guardian + accord explicite des trois ; actualiser INTERFACES et tests |
| Architecture, sécurité, permissions agents, CI, Guardian, déploiement | CI + Guardian + accord explicite des trois ; ADR obligatoire |
| Éditorial pur | contrôles adaptés + revue légère |
| Production / données client | décision humaine distincte ; hors mandat |

Guardian n'est pas encore disponible. Aucun auteur n'approuve seul son travail. En désaccord : suspendre, exposer options et critères mesurables, comparer des prototypes si utile et laisser les trois co-concepteurs décider. Coordonner avant fusion deux PR touchant une interface. Détecter les signatures et changements de fichiers sensibles ne remplace pas une revue. Les règles ci-dessus sont procédurales, pas des protections techniques vérifiées.

## Nommage des branches (proposition de simulation)

Préfixer la branche par le type de changement (`feat/`, `docs/`, `fix/`) et par le chantier ; ne jamais travailler sur main. Cette convention est proposée, pas approuvée.
