# Audit beta — Agent Core / Mission Control

**Date :** 27/11/2026
**Référence :** audit d'écart contre `docs/CDC-PRODUIT-v2.0.md`
**Méthode :** lecture du code et des unités systemd, exécution des tests, appels HTTP réels sur les services en marche. Aucune conformité déclarée sans preuve citée.
**Verdict :** **non éligible à la beta en l'état.** 5 bloqueurs, 7 écarts majeurs, 5 écarts mineurs. Le socle est sain : 69 tests API verts, 26 tests de parcours verts.

---

## 1. Ce qui est vérifié et fonctionne

| Élément | Preuve du 27/11/2026 |
|---|---|
| API ARPAGONA : comptes, sessions, conversation, engagements, brouillons, Kanban, audit interne | `python3 -m unittest discover -s services/arpagona-api/tests` → **69 tests, OK** (55 s) |
| Parcours local complet (chat simulé, approbations, Kanban, équipe) | `python3 -m unittest discover -s tests/dev` → **26 tests, OK** (4,5 s) |
| Empreinte de brouillon : modification après approbation refusée | `store.decide_draft` → `contenu_modifie` → HTTP 409 ; test unitaire vert |
| Isolation des sessions par compte côté API (jeton d'agent lié à son propriétaire) | `_service_user` : `owner_of_token` + `user_for_hermes_session` ; test `test_agents_isolation` |
| Kanban : seul le responsable décide, commentaire ouvert à l'équipe | `_kanban` : 403 sur `complete/block/archive` d'une carte d'autrui |
| UI : 4 espaces (Conversation, Kanban, Approbations, Engagements), PWA, mobile | `apps/mission-control-web/index.html`, `manifest.webmanifest`, service worker |
| Services en marche | `arpagona-mission-control-alpha` (8710) : HTTP 200 ; `gona-mission-control-ui` (8790) : 401 sans jeton, normal |
| Non-envoi structurel | `_decide` : « aucun connecteur autorisé », note de livraison posée. L'agent n'a aucun outil d'envoi |

---

## 2. Bloqueurs beta

### B-1 — Aucun envoi courriel (F-05, F-06, F-07)
Le brouillon approuvé est **copié à la main**. Aucun code SMTP, aucun statut `envoye`, aucun identifiant de message.
**Écart :** le produit ne prouve pas sa promesse centrale. Un client ne paie pas pour un presse-papiers.
**Preuve :** `grep -ri smtp` → 0 résultat ; `_decide` force `non envoyé : aucun connecteur autorisé`.

### B-2 — Aucune mission visible ni arrêtable (F-02, F-03)
Il n'existe ni table `missions`, ni route `/api/missions`, ni onglet. Une demande longue se fond dans le fil de conversation : impossible de savoir ce qui tourne, ce qui a coûté quoi, ni d'arrêter.
**Écart :** le produit s'appelle Mission Control et n'a pas d'objet « mission ».
**Preuve :** `grep -rn "missions" services/arpagona-api apps/mission-control-web` → 0 résultat.

### B-3 — Aucun plafond de dépense (N-03)
Aucun compteur de coût, aucun arrêt. Le banc Atlas documente déjà : « aucun plafond de dépense n'est appliqué », ~12 500 jetons par exécution même pour un mot.
**Écart :** risque financier direct et non borné. Rédhibitoire pour une beta facturée.
**Preuve :** `deploy/atlas/README.md` §Limites 1 ; `grep -rn "cost\|budget"` → 0 dans l'API.

### B-4 — HTTP en clair, cookie non `Secure` (N-01)
Le script LAN écrit `ARPAGONA_COOKIE_SECURE=0` et ouvre le port 8700 en HTTP. Aucun proxy TLS dans le dépôt.
**Écart :** mots de passe et conversations en clair sur le réseau. Inacceptable dès qu'un deuxième utilisateur se connecte.
**Preuve :** `deploy/atlas/enable-mission-control-lan.sh:18` ; `ARPAGONA_COOKIE_SECURE` par défaut `0`.

### B-5 — Mémoire d'équipe non démontrée (F-10)
La recette M1 du 12/11 a échoué (contexte tronqué). Le correctif n'a pas été rejoué. L'ADR 0008 fonde pourtant l'argument « mémoire d'équipe ».
**Écart :** la fonction est annoncée, non prouvée.
**Preuve :** `docs/FEUILLE-DE-ROUTE.md`, ligne « Mémoire d'équipe Hindsight — partielle ».

---

## 3. Écarts majeurs

| ID | Écart | Preuve | Effet |
|---|---|---|---|
| M-1 | Journal d'audit non exposé au client (F-13) | table `audit` présente, aucune route `/api/audit`, aucun onglet | transparence promise, absente |
| M-2 | Pas de rôles admin/membre (F-15) | `users` sans colonne `role` | un membre peut tout, y compris gérer les comptes |
| M-3 | Pas d'export (F-14) | aucune route, aucun bouton | portabilité RGPD impossible |
| M-4 | Pas de voix (F-04) | `grep -ri "voice\|audio\|micro"` dans l'app web → 0 | exigence beta non tenue |
| M-5 | Isolation à deux instances non démontrée (N-02) | une seule instance existe ; script absent | argument de vente non prouvé |
| M-6 | Sauvegarde/restauration non testée (N-04) | pas de script de sauvegarde de l'instance | perte de données non bornée |
| M-7 | Outils de l'agent non restreints (N-10) | `deploy/atlas/README.md` §Limites 3 : terminal inclus | surface d'attaque inutile en beta |

## 4. Écarts mineurs

| ID | Écart | Effet |
|---|---|---|
| m-1 | Pas de sonde de santé supervisée (N-08) | panne silencieuse |
| m-2 | Pas de guide client ni admin (N-12) | adoption dépendante de Thibaud |
| m-3 | Accessibilité non vérifiée (N-11) | risque d'exclusion, non mesuré |
| m-4 | Performance non mesurée (N-07) | aucun repère |
| m-5 | Registre RGPD absent (N-05) | conformité non démontrable |

---

## 5. Ordre de traitement

| Rang | Chantier | Exigences | Effort | Dépendance |
|---|---|---|---|---|
| 1 | Missions visibles + arrêt + coût par mission | F-02, F-03, N-03 (socle de mesure) | 2 j | — |
| 2 | Envoi courriel avec approbation par empreinte | F-05, F-06, F-07 | 2 j | SMTP disponible |
| 3 | Journal d'audit + rôles + export | F-13, F-15, F-14 | 1 j | — |
| 4 | TLS + cookie `Secure` | N-01 | 0,5 j | nom de domaine ou CA locale |
| 5 | Voix navigateur | F-04 | 0,5 j | — |
| 6 | Deuxième instance + tests croisés négatifs | N-02 | 1,5 j | 1 à 3 |
| 7 | Sauvegarde/restauration + supervision | N-04, N-08 | 1 j | 1 |
| 8 | Mémoire d'équipe M1 rejouée | F-10 | 1 j | — |
| 9 | Restriction des outils | N-10 | 0,5 j | — |
| 10 | Guides + RGPD + accessibilité + perf | N-05, N-11, N-12 | 1,5 j | 1 à 7 |

**Chemin critique vers la beta :** 1 → 2 → 3 → 4 → 5 → 6. Les rangs 7 à 10 se parallélisent.

---

## 6. Décisions nécessaires

1. **SMTP réel.** Un compte d'envoi dédié est nécessaire (adresse, serveur, mot de passe d'application). Sans lui, l'envoi ne peut être prouvé qu'avec un serveur de capture local — insuffisant pour la porte B-03.
2. **Nom de domaine pour TLS.** `agentcore.arpagona.com` ou certificat d'autorité locale à installer sur les appareils de l'équipe.
3. **Point d'arrêt.** L'API Hermès permet-elle d'interrompre une exécution en cours (`/v1/runs/{id}/cancel`) ? À vérifier avant de promettre F-03 ; sinon l'arrêt se fait entre deux étapes.

---

## 7. Conclusion

Le socle est meilleur que son cahier des charges. Les cinq bloqueurs ne demandent pas de refonte : ils demandent du travail borné, dans l'ordre ci-dessus. Après les rangs 1 à 6, le produit peut être montré à Maël sans excuse. Après les rangs 1 à 10, il peut être montré à un client pilote.
