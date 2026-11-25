# Rapport — badge « Sans responsable » sur le Kanban (24/11/2026, t_9cded92b)

## Surface cible (confirmée)
Dépôt `~/projects/gona-mission-control`, vue Kanban de `web/app.js` (`taskButton`, `renderKanban`), servie par `arpagona-mission-control-alpha` (:8710). Le service actif n'a PAS été redémarré : la modif est sur disque et sera visible au prochain redémarrage voulu.

## Règle
Badge texte « Sans responsable » (pastille violette + liseré gauche) si, et seulement si :
- `assignee` natif vide ;
- pas d'attente humaine (`waiting()` ou `block_kind === "needs_input"`, y compris les 6 cartes réelles `ready + needs_input`) ;
- statut ni `done` ni `archived` ;
- la carte n'est pas une ombrelle de `kanban_map.json` (sans responsable par choix : pas d'alerte).
Aucun nouveau statut Hermes. Lecture seule : aucune carte déplacée, assignée ou dispatchée. Distinct de l'ambre « needs-input » ; « en attente de déploiement » n'a pas de représentation dédiée dans l'UI actuelle : testé par une carte bloquée (`blocked`/`dependency`), assignée (pas de badge) et non assignée (badge).

## Preuves
- Instance isolée : port 8799, base SQLite fixture, profil/jeton temporaires (scratch), Chrome headless dédié (profil propre, port 9333). Chrome de Thibaud non touché, board réel non touché.
- `tests/e2e/unowned_badge_e2e.py` : 7 cartes × desktop (1280) + mobile (390) = 14/14 OK (non assignée → badge ; assignée, déploiement assigné, attente humaine, ombrelle, terminée → pas de badge ; bloquée non assignée → badge).
- Captures : `tests/e2e/kanban-desktop.png`, `tests/e2e/kanban-mobile.png`.
- Non-régression : `python3 -m unittest discover -s tests` → 46 OK ; `node --check web/app.js` OK.
- Note : sur la capture mobile pleine page, les colonnes se chevauchent (mise en page existante, hors périmètre) ; le badge reste lisible.

## Isolation de la tranche
`web/app.js` n'avait aucune modif préexistante. Fichiers de la tranche : `web/app.js` (+7/−1), bloc ajouté en fin de `web/alpha.css`, `tests/e2e/*`. Diff : `badge-sans-responsable-20261124.diff`. Modifs préexistantes (`server.py`, `web/index.html`, bandeau kiosque dans alpha.css, fichiers kiosk) intactes et non commitées. Rien commité, rien poussé.

## Données réelles (lecture seule)
Sur le board réel : 17 cartes non terminées, sans assignee et sans `needs_input` recevront le badge (hors ombrelles éventuelles) ; les 6 `ready + needs_input` sans assignee n'en reçoivent pas.
