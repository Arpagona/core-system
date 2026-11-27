# Agent Core — itération 1 après validation de la roadmap

27 novembre 2026. Exécution directe GONA, sans sous-agent.
Branche : `fix/beta-budget-admission`. Issue : https://github.com/Arpagona/core-system/issues/74 .
Base : `13045c624f6c`. Le candidat n'est pas déployé et la beta n'est pas déclarée conforme.

## Livrables

- Matrice de réception : `reports/2026-11-27-matrice-reception-beta.md`. Identifiants du CDC extraits et comparés par programme : 40 critères, aucun identifiant manquant. Distinction ouverture interne / réussite de beta / production.
- Comparatif sourcé : `reports/2026-11-27-cadrage-et-comparatif-beta.md`. Sources officielles Cognite, Microsoft et Dust consultées ; les affirmations non prouvées d'exclusivité, de langue et de prix ne sont pas reprises comme faits.
- Garde d'admission persistante : `services/arpagona-api/arpagona_api/budget.py` et raccordements serveur/store. Procédure : `docs/BUDGET-ADMISSION.md`.
- CLI opérateur locale : `budget-status` et `budget-reconcile`, confirmation et preuve obligatoires, contrôle du rôle, transaction avec audit et relecture du reçu.

## Boucle rouge → correction → vérification

1. Baseline : 98 tests API OK, 75,464 s. ResourceWarnings présents.
2. Tests de registre avant implémentation : rouges, attribut/table de réserve absents.
3. Trois contrôles d'intégration ont reproduit de vraies non-conformités : réserve observée à zéro au départ du moteur ; coût NaN laissant démarrer un autre compte (HTTP 200 au lieu de 429) ; échéance lançant un moteur malgré un budget insuffisant.
4. Registre atomique dans la base existante, micro-USD, coût connu/inconnu distinct, conservation après réouverture et passage de journée. Tests avec deux connexions puis deux processus OS distincts : une admission, un refus. Aucun appel à un modèle dans ces tests.
5. Chat et échéances passent maintenant par la même réservation. Les échéances créent une mission et un message suivis ; un délai de surveillance ne signifie ni annulation ni remboursement.
6. La suite complète a révélé un conflit avec la reprise de conversation après HTTP 503. L'ancien comportement relançait sans preuve d'absence d'effet. Le test de passation est conservé et renforcé : refus tant que le coût reste inconnu, preuve synthétique du rejet avant création dans le faux moteur, rapprochement opérateur explicite, puis vérification originale de la passation.
7. Le parcours développeur a détecté que son simulateur n'exposait pas de coût. Correction du simulateur uniquement : coût zéro explicite parce qu'il n'appelle aucun fournisseur. Cette valeur n'est jamais utilisée par défaut pour le moteur réel. Le parcours existant relance → brouillon → approbation repasse sans suppression d'assertion.
8. L'interface distingue coût mesuré, réserves, inconnus et absence de garantie fournisseur. Les coûts invalides ne sont pas exportés dans la réponse missions comme NaN/Infinity. Les clés de réserve du chat servent également de clés d'idempotence envoyées au moteur.
9. Les coûts historiques manquants sont visibles et rapprochables explicitement ; ils ne sont pas initialisés à zéro. L'export conserve les réserves et l'allocation des nouveaux IDs tient compte de l'historique financier.

## Dernière exécution locale intégrée

- API : `python3 -m unittest discover -s tests` dans `services/arpagona-api` : **121 tests OK**, 86,428 s.
- Parcours développeur : `python3 -m unittest discover -s tests/dev` : **29 tests OK**, 4,057 s, incluant la vraie API, la passerelle et le plugin avec moteur explicitement simulé.
- Sur cette même branche, précédemment dans l'itération : passerelle Kanban **8 OK**, portier Hindsight **14 OK**, session-lifecycle **11 OK**. Leurs sources n'ont pas été modifiées depuis.
- Syntaxe JavaScript, compilation Python des plugins et outils listés en CI, syntaxe des deux scripts agents personnels, scan de motifs sensibles et `git diff --check` : verts.
- Des ResourceWarnings persistent (SQLite et HTTPError de tests), et le portier Hindsight a affiché des ConnectionResetError de sockets clientes pendant sa suite pourtant verte. Ce n'est PAS une preuve d'absence de fuite ou de logs propres. À corriger et vérifier séparément.

## Limite déterminante — conformité financière encore ouverte

La garde garantit l'admission atomique selon les coûts connus et réserves. Elle ne borne pas la consommation d'un fournisseur déjà lancé. Le champ API `plafond_fournisseur_garanti` vaut donc `false`.

Voies examinées : source du contrat `/v1/runs` et des options moteur effectivement installées sur Atlas ; documentation/recherche officielle Hermes ; contrôle d'admission persistant côté application et possibilité d'une borne fournisseur distincte. Les sources inspectées exposent notamment des options de modèle/itérations, pas une borne USD prouvée par run. Aucune limite de clé fournisseur n'a été modifiée et aucune route locale n'a été substituée silencieusement.

Ne pas déclarer N-03 strict validé avec ce seul correctif. Prochain test technique : identifier une borne effective moteur/fournisseur sur une route isolée, ou préparer un mode interne sans appels facturés dont le périmètre et l'absence de repli seraient réellement prouvés. Ne jamais couper l'accès utile en production au seul motif de faire passer une recette.

## Gouvernance et suite

Pas de modification de la feuille de route produit protégée ni d'affaiblissement du CDC. Les clarifications sont dans la matrice et la documentation du candidat.

Selon `AGENTS.md` et `CONTRIBUTING.md` : PR, CI verte, revue humaine requise avant merge. Pas d'auto-approbation. Cela n'empêche pas d'avancer les vérifications indépendantes des autres lots. Aucun service réel redémarré pour cet incrément ; aucun envoi SMTP ni paiement pendant cette itération.

Prochaines actions précises : soumettre le candidat ; poursuivre la recette visuelle HTTPS/multi-appareils et le diagnostic du téléchargement Android ; préparer la restauration isolée complète, sans assimiler une simple copie de SQLite à une restauration d'instance.
