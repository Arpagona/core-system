# Sécurité de l'atelier

Données synthétiques seulement ; aucun secret, jeton ou donnée client dans Git, CI ou logs. CI : token contents:read, sans secret ni pull_request_target ; une PR peut néanmoins modifier son propre workflow, donc ce n'est pas un verrou contre un acteur privilégié. Les scanners de ce lot sont ciblés et ne garantissent pas l'absence de secrets. Le contrôle Cargo bloque toute dépendance externe actuellement ; il ne constitue pas un audit CVE. Guardian déterministe prévu au lot 2 ; pas de code privé transmis à un modèle externe additionnel.

Protections main : non disponibles lors de l'inventaire initial (403). Pas d'anti-merge garanti ; procédure humaine indispensable. Aucun déploiement ou permission accordée dans ce lot.
