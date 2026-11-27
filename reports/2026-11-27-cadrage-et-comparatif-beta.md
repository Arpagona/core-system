# Agent Core — cadrage et comparatif vérifié

27 novembre 2026 — lot 0 de la roadmap. Recherche et rédaction directes par GONA, sans sous-agent.

## Conclusion produit

Ne pas essayer de reconstruire Cognite ni de gagner une course aux connecteurs. La proposition à prouver est un **copilote accompagné pour petite équipe industrielle**, qui mène un travail jusqu'au livrable, conserve les sources et rend les validations simples. Cette différenciation est une hypothèse commerciale à tester, pas un avantage acquis.

Le contrat de beta reste : donner une mission, suivre son état réel, retrouver le livrable, décider sur une action externe précise, puis vérifier son résultat. Chaque écran doit servir ce parcours.

## Sources officielles consultées le 27/11/2026

- Cognite : https://www.cognite.com/en/product/atlas ; documentation trouvée : https://docs.cognite.com/cdf/atlas_ai . L'ancienne URL `/en/products/atlas-ai` renvoie 404 : ne plus la citer comme source consultée.
- Microsoft : https://www.microsoft.com/en-us/microsoft-copilot/microsoft-copilot-studio . La variante `/pricing` de cette URL renvoie 404 : aucun tarif actuel vérifié ici.
- Dust : https://dust.tt/ et https://dust.tt/pricing . La page de tarifs décrit les crédits, les plans et les déploiements ; aucun prix de siège lisible dans l'extraction. Aucun ancien prix mensuel n'est repris comme fait actuel.

Il s'agit de fonctionnalités annoncées par les éditeurs, pas de produits exercés par GONA. Aucun gain de temps marketing n'est repris comme preuve indépendante.

## Cognite Atlas AI

**Faits de la source :** contexte industriel fondé sur un graphe reliant capteurs, maintenance, spécifications et historique d'actifs ; réponses sourcées ; exécution de workflows ; capitalisation de savoir-faire. La documentation présente construction, validation, traces et confirmations d'outils.

**Conséquence pour nous :** c'est le repère pour la traçabilité et les résultats métier industriels, pas le périmètre à copier pour une beta de petite équipe. Une base OT/IT industrielle complète, la simulation et le multi-site sont hors de notre chantier actuel.

**Inconnus :** prix applicable à notre cible, coût de déploiement, délai réel d'intégration, adéquation à une petite PME et expérience française. Une page anglaise ne prouve pas que le français est absent.

## Microsoft Copilot Studio

**Faits de la source :** création sans code d'agents et workflows, voix et conversation, connecteurs et MCP, automatisation, évaluations, canaux de publication et gestion Dev/Test/Prod avec gates d'approbation et traces.

**Conséquence pour nous :** la gouvernance et l'évaluation ne sont pas une exclusivité ARPAGONA. Si la cible est déjà très équipée Microsoft, comparer d'abord le coût et l'effort d'intégration réels plutôt que prétendre qu'elle aurait besoin d'une autre plateforme.

**Inconnus :** facturation effective pour notre parcours de référence, administration nécessaire, licences et coûts des services associés. Aucune estimation de coût total n'est présentée comme vérifiée.

## Dust

**Faits des sources :** agents reliés aux connaissances et outils d'entreprise ; collaboration et revue humaine ; permissions ; journaux et mesure de l'usage. La page Enterprise mentionne résidence UE/US, déploiement single-tenant, rétention et SLA.

**Rectification importante :** « instance dédiée » ou « contrôle humain » ne peuvent pas être présentés comme des fonctions que Dust n'offre pas. Résidence UE ne signifie pas déploiement sur site.

**Conséquence pour nous :** c'est un concurrent de référence plus proche pour le travail quotidien d'équipe. Notre valeur éventuelle repose sur l'accompagnement, le cas industriel livré et la simplicité d'exploitation démontrée, pas sur une liste de fonctions génériques.

**Inconnus :** limites pratiques des actions approuvées, coût du scénario de référence, conditions exactes d'un hébergement client et ergonomie comparée en test.

## Contrat honnête pour Agent Core

1. Une réservation budgétaire protège l'admission de nouveaux travaux ; elle ne limite pas à elle seule la facture d'un appel fournisseur déjà parti. Tant que cette borne n'est pas appliquée par le moteur ou le fournisseur, ne pas annoncer de plafond financier strict.
2. Un coût manquant ou invalide reste inconnu. Il n'est pas gratuit.
3. Une perte de réponse SMTP ou de soumission moteur n'est pas une preuve d'absence d'effet. Pas de réessai automatique aveugle.
4. Un test d'API ou un APK installé ne prouve pas le parcours rendu sur le téléphone.
5. Un partage de mémoire entre comptes n'est pas une preuve d'isolation entre deux entreprises.
6. Cinq jours d'usage servent à déclarer la beta réussie, pas à dater artificiellement son ouverture. Les portes de sécurité restent préalables à l'ouverture.

## Décisions d'exécution issues du cadrage

- Aucun connecteur, moteur, service ou nouvel écran par défaut.
- Priorité aux réservations atomiques, coûts inconnus, échéances et reprise contrôlée.
- Maintenir les critères de la roadmap ; les ambiguïtés du CDC sont tracées dans la matrice, pas supprimées.
- Le chantier actuel ne modifie pas la feuille de route produit protégée. La PR sera soumise aux règles de revue humaine du dépôt ; une CI verte n'est pas une approbation humaine.
