# Utiliser le Kanban au quotidien — prototype ergonomique

**État : proposition testée sur la branche `feat/kanban-ergonomie`, pas encore intégrée ni activée sur Atlas.** L’interface commune demande l’accord explicite de Thibaud, Maël et Stéphane. Issue : [#78](https://github.com/Arpagona/core-system/issues/78).

## Le minimum utile

- **Une carte = un résultat livrable**, pas une conversation ni un sujet indéfini.
- Titre : un verbe et un objet. Description : résultat attendu, critère de réussite, prochaine action.
- **Un responsable** pour décider. Les collègues voient et commentent ; ils ne terminent pas une carte à sa place.
- Routine conseillée, non imposée : ouvrir **Mes cartes**, choisir au plus trois priorités ; consulter **Équipe** pour coordonner. Le nombre de travaux en cours n’est pas limité automatiquement.
- Si une carte bloque : donner la cause et ce qui permettra de reprendre. Ne pas écrire seulement « bloqué ».
- Avant de terminer : joindre la preuve ou le lien vers le résultat dans un commentaire. Ce contrôle reste humain ; le bouton ne vérifie pas lui-même le livrable.

## Ce que permet ce premier lot

- **Onglet Kanban** sur grand écran comme sur téléphone. Sur ordinateur, il ouvre le tableau en pleine largeur. La conversation garde son aperçu sur grand écran.
- **Équipe / Mes cartes / Sans responsable** : filtres immédiats, sans déplacer ni réaffecter de carte.
- Recherche par titre, responsable ou identifiant, sans tenir compte des accents et de la casse. Plusieurs mots doivent tous être présents. Le corps participe aussi si la liste du backend le fournit ; ce n’est pas une recherche intégrale garantie.
- **Tableau / Liste** : liste par défaut au chargement sur petit écran. En liste, les priorités numériques les plus hautes passent d’abord, puis les blocages, cartes à vérifier et travaux en cours. Le tri ne modifie aucune priorité métier.
- Les cartes terminées sont masquées par défaut, retrouvables avec **Afficher les terminées**. Ce n’est pas un archivage. Les archives ne sont pas affichées dans ce lot.
- Les états métier restent inchangés. Les badges distinguent notamment une carte bloquée d’une carte planifiée.
- Une carte sans responsable peut être prise en charge explicitement. La création propose les membres de l’équipe configurée, même sans carte existante.
- Les actions de détail restent celles du backend : commenter, prendre en charge une carte non affectée et, pour le responsable autorisé, terminer, bloquer/débloquer ou archiver. Bloquer est proposé pour les états `ready` et `running` ; ce n’est pas un déplacement libre entre colonnes.
- Un blocage demande une cause non vide. Son dernier motif est affiché depuis l’événement `blocked` du Kanban, lorsqu’il est disponible.
- Actualisation : conserve les filtres et le focus quand les cartes n’ont pas changé. En cas de panne, les dernières cartes restent lisibles avec un avertissement d’ancienneté.
- Déconnexion : efface la sélection, les cartes affichées et les brouillons de formulaire. Ce lot n’ajoute aucun stockage persistant de cartes ou de filtres dans le navigateur.
- Session expirée en cours d’usage : retour à l’écran de connexion avec un message clair, au lieu d’un tableau figé qui refuse silencieusement les actions.
- **Mise à jour sans manipuler l’appareil** : `GET /api/health` publie une empreinte courte des fichiers d’interface (`ui`). Un client déjà ouvert (application Android, onglet de bureau) compare cette empreinte au retour au premier plan et toutes les cinq minutes, puis se recharge si un déploiement a changé l’interface. Sans cela, une application laissée ouverte continuait d’afficher l’ancienne version après une mise à jour du serveur.
- Sur petit écran, la croix de fermeture reste accessible pendant le défilement d’un détail long.
- Message d’état vide utile : tableau vide, tout terminé, ou filtres trop étroits donnent trois consignes différentes.

## Contrat proposé

`GET /api/health` ajoute **`ui`** : douze caractères hexadécimaux, empreinte des fichiers `index.html`, `app.js`, `kanban-view.js`, `style.css`. Aucune donnée métier, aucun secret ; le calcul est mis en cache sur la date et la taille des fichiers.

`GET /api/me` ajoute **`team: string[]`** : identifiants des membres configurés pour l’instance, uniquement si le compte courant en fait partie. Une session absente reste `401` ; un compte non configuré reçoit une liste vide. Aucun jeton, URL moteur ou détail privé n’est exposé.

Le client utilise cette liste pour le sélecteur de responsable. Pour compatibilité avec une ancienne API, il peut reprendre les responsables déjà visibles et le compte courant. Ce repli ne découvre pas un collègue sans carte : l’ajout API évite cette limite sur la version proposée.

Aucune nouvelle opération de passerelle. Aucun changement des règles d’autorisation, des états persistés, de la base métier, de la mémoire ou du déclenchement des agents. Le contrat et l’interface restent **à discuter et valider collectivement** avant intégration.

## Reproduire la démo sans données réelles

Depuis la racine du dépôt, premier terminal :

```sh
python3 dev/kanban_ergonomie_fixture.py
ARPAGONA_AGENTS_FILE="$PWD/.local/kanban-ergonomie/agents.json" \
  python3 dev/lancer.py --port 18800 --moteur-port 18842 --kanban-port 18801 \
  --data "$PWD/.local/kanban-ergonomie"
```

La démo écoute uniquement en boucle locale. Compte fictif : `demo`, mot de passe public de développement `demo-arpagona-2026`. Pour rejouer, `python3 dev/kanban_ergonomie_fixture.py --reset` remet seulement les cartes de cette démo reconnue à leur état initial. Un répertoire existant sans marqueur de démo est refusé.

Chrome avec son CDP local sur 9223, second terminal :

```sh
node --test tests/ui/kanban-view.test.cjs
node tests/ui/kanban-browser.cjs .local/kanban-browser-proof
```

Recherche de défauts sur cas limites, sur un second jeu de données séparé (port 18810) :

```sh
python3 dev/kanban_ergonomie_fixture.py --set adversarial --data "$PWD/.local/kanban-adversarial"
ARPAGONA_AGENTS_FILE="$PWD/.local/kanban-adversarial/agents.json" \
  python3 dev/lancer.py --port 18810 --moteur-port 18852 --kanban-port 18811 \
  --data "$PWD/.local/kanban-adversarial"
node tests/ui/kanban-adversarial.cjs .local/kanban-adversarial
```

Preuve que ces tests détectent bien les régressions : on casse volontairement huit règles protégées et la suite doit échouer à chaque fois.

```sh
python3 dev/kanban_ergonomie_fixture.py --set adversarial --data "$PWD/.local/kanban-adversarial" --reset
python3 tests/ui/mutation-check.py .local/mutation.json
```

Réinitialiser le jeu avant chaque rejeu : les scénarios créent et terminent des cartes fictives.

Node 22+ et Chrome sont requis pour la recette navigateur. Le script utilise un contexte navigateur isolé et un hôte `.localhost` distinct ; il ne remplace pas les cookies des sessions habituelles. Les tests JavaScript unitaires sont aussi lancés par `tests/dev/test_kanban_presentation.py` lorsque Node est présent.

**Portée de la preuve :** vrai navigateur (1440×1000, 390×844, 320×568), API et passerelle réelles ; CLI Kanban et moteur simulés, données synthétiques. La CLI simulée refuse désormais les mêmes transitions que le noyau natif (blocage seulement depuis `ready`/`running`, motif vide refusé, motif recopié en commentaire `BLOCKED: …`). Le petit écran est une émulation 390 × 844, pas un essai sur un téléphone physique. Cette recette ne remplace pas les essais iMac/Android authentifiés et déployés du jalon bêta.

## Hors de ce lot

Pas de nouvelle architecture, de glisser-déposer des statuts, d’édition de description existante, de synchronisation automatique d’autres suivis, de nouvelle autonomie, de modification de cartes métier réelles ni de déploiement. Les migrations et droits restent inchangés. Retour arrière proposé : remettre les fichiers applicatifs de la version précédente, sans restaurer la base ; cela reste à vérifier lors du futur déploiement.
