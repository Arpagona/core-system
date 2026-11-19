# Rapport lot 1 — 2026-11-10

Périmètre : atelier expérimental seulement ; pas de moteur agentique, production, permissions ou merge. Source CDC copiée à l'identique, SHA-256 `5642cd3ba2a97c90b2b0d6badf5221f211814975e77f9d1199f3003ffd3aa798`. Point de départ PR 1 : `c879be48cb1c1c95377bd80c9130a342b4ea7fab`. Résultats CI et SHA final : voir les checks de la PR et le handoff de la carte, qui sont les sources autoritatives après publication.

Deux crates jetables : un contrat et son consommateur ; `crates/` reste vide de code produit. Le script `tests/rupture_contrat.py` copie le workspace, provoque E0308 puis restaure la signature et relance les tests. L'échec local n'est pas une PR fautive visible. La CI construit un petit binaire identifié par commit, version et SHA-256 ; aucun déploiement ou Release.

Contrôles de sécurité limités : dépendances externes interdites par lecture du lockfile et recherche de quelques motifs secrets dans les fichiers suivis ; ni audit CVE ni détection exhaustive. CI read-only au niveau workflow ; aucun secret configuré par ce lot. Guardian absent. Revue des changements CI et architecture avec accord à trois obligatoire avant merge selon le processus.

ENFORCÉ : exécution des checks dans le workflow, sous réserve du résultat réel. PROCÉDURAL : ne pas merger sans CI, Guardian et revues prévues. NON DISPONIBLE : protection obligatoire de main selon inventaire initial ; non reconfigurée. Accès des trois non établis, environnement vierge non testé, aucune recette intégrale revendiquée. Lot 2 : Guardian déterministe, registre de modules et comparaison metadata, vue HTML et test de divergence. Lot 3 : exercice PR et correction, poste neuf, recette et éventuel test sur serveur autorisé.
