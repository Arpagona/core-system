# Proposition d’amendement M0 — budget des appels modèle

Statut : proposition à valider collectivement par Thibaud, Maël et Stéphane ; non implémentée. Le correctif de parsing associé ne garantit pas un plafond de dépenses et ne comptabilise pas un coût inconnu.

## Contrat proposé

1. Avant chaque appel susceptible d'atteindre le fournisseur, créer une réservation durable, identifiée par `call_id` unique, avec mission, période, devise, tarifs versionnés et borne de coût calculée à partir de limites d'entrée et de sortie effectivement imposées. Admission et réservation doivent être une transaction atomique sur le budget global partagé, incluant dépenses réglées et réservations actives/incertaines. Sans borne fiable imposable, refuser l'appel si un plafond strict est exigé.
2. Persister avant envoi l'état de l'appel et sa réservation ; après crash, considérer comme incertain tout appel pouvant avoir été envoyé. Annuler la réservation seulement si l'absence d'envoi est démontrée. Aucun retry automatique après résultat incertain (timeout, transport après envoi possible, réponse invalide ou usage manquant). Un éventuel retry après refus pré-envoi démontré exige une nouvelle admission et une identité distincte ; idempotence fournisseur à spécifier et vérifier avant toute exception.
3. Sur réponse et usage valides, régler une seule fois, de manière atomique et idempotente par `call_id`, les montants connus et libérer le reliquat. Si usage/coût est inconnu, conserver la réservation et marquer l'appel incertain ; ne jamais enregistrer zéro par défaut. Un dépassement de la borne déclarée bloque les admissions et déclenche une alerte : le contrat dépend aussi du respect des limites et tarifs par le fournisseur.
4. Réconciliation durable : récupérer usage/facture fournisseur par identifiant quand disponible, ou demander une résolution humaine auditée ; enregistrer preuve, acteur, décision et ajustement idempotent. Sans preuve, conserver l'incertitude et les fonds réservés ; expliciter la politique de période, taux et écarts de facture.

## Impacts et décisions

| Sujet | Migration / compatibilité | Décisions à valider : Thibaud, Maël, Stéphane |
|---|---|---|
| Événements et contrats modèle | Versionner schémas et états, conserver lecture historique ; ancien coût inconnu non reconstructible automatiquement | États, preuves pré-envoi, identifiant et politique d'idempotence fournisseur |
| Budget global | Stockage transactionnel commun et admission interprocessus ; snapshot quotidien existant insuffisant | Périmètre global, période/fuseau, devise, tarifs, limites imposables et échec fermé |
| Réservations et crash | Migration durable/versionnée ; anciens appels en vol à classer incertains, sans inventer de montants | Borne réservée, maintien et règles de libération, traitement des historiques incomplets |
| Réconciliation | Interface/écritures auditables, compatibilité fournisseur variable ; pas de résolution automatique sans preuve | Sources de preuve, autorité humaine, écarts, absence de facture, politique de déblocage |
| Retry et clients | Comportement et contrats publics potentiellement incompatibles ; révision des tests et des consommateurs | Cas démontrablement pré-envoi, exceptions éventuelles et stratégie de transition |

Critères avant adoption : tests offline multi-processus d'admission concurrente, crash à chaque transition, reprise sans rejeu incertain, règlement/réconciliation idempotents et migration d'historiques. Ces critères restent à implémenter et vérifier.
