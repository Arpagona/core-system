# Feuille de route — ARPAGONA Core System

Mise à jour : 22 novembre 2026. Statut : **proposition de travail**, à discuter entre Thibaud, Maël et Stéphane. Les lots ne sont pas des engagements.

## Le produit en une phrase

Une surcouche d'Hermès Agent officiel (ADR 0007) qui donne à une PME un copilote : il prépare, l'humain décide. Une instance par client (ADR 0008).

## État vérifié au 22/11/2026

| Brique | État | Preuve |
|---|---|---|
| Mission Control web (chat, Kanban, approbations, engagements) | fonctionne | recette navigateur LAN 19/11 ; parcours local 22/11 |
| API ARPAGONA (comptes, sessions, engagements, brouillons, empreinte, audit) | fonctionne | 31 tests unitaires |
| Passerelle Kanban (liste blanche sur `hermes kanban`) | fonctionne | 7 tests + parcours local |
| Plugin `arpagona-core` (3 outils, aucun envoi) | fonctionne | recette banc 12/11 ; parcours local 22/11 |
| Poste développeur en une commande | fonctionne | `tests/dev`, Python 3.10 à 3.14 |
| Banc Atlas (VM `agentcore-dev`, Hermès v0.23.1, Hindsight) | en service, accès LAN de test | recette 29/30 le 12/11 ; à rejouer |
| Mémoire d'équipe Hindsight | partielle | M0 vert, M1 en échec le 12/11 (contexte tronqué, correctif non rejoué) |

## Limites à dire à tout interlocuteur

- Banc de test. Aucune donnée client réelle.
- HTTP sur le réseau local, cookie non `Secure`. HTTPS obligatoire avant tout client.
- Aucun envoi : un brouillon approuvé se copie à la main.
- Une seule instance existe. L'isolation entre deux clients n'est pas démontrée.
- Pas de plafond de dépense côté Hermès : limite chez le fournisseur du modèle.

## Lots proposés

Durées indicatives. Chaque lot = une Issue, une branche, une PR relue par un autre humain.

| Lot | Contenu | Critère d'acceptation | Pilote proposé |
|---|---|---|---|
| 1. Démo synthétique | scénario PME « 200 supports », répétition chronométrée sur le banc, captures de repli | parcours complet enregistré avec horodatage et coût | Thibaud |
| 2. Accès et secrets | HTTPS (proxy ou tunnel), cookie `Secure`, inventaire et rotation des secrets | test externe : 401 sans session, TLS valide, aucun secret lisible | Thibaud |
| 3. Deux instances clients | script paramétré `nouvelle-instance <client>` : compte système, ports, secrets, base, banque Hindsight | deux clients fictifs ; tests croisés négatifs mémoire, fichiers, API ; procédure d'effacement | Maël |
| 4. Mémoire d'équipe | rejouer M1 sur banque neuve avec le budget élargi | second compte restitue les faits ; mesure de latence | à répartir |
| 5. Exploitation | sauvegarde chiffrée hors hôte, restauration testée, rétention, oubli | restauration réelle chronométrée | à répartir |
| 6. Premier connecteur d'envoi | courriel après approbation explicite, journalisé | aucun envoi sans approbation ; test d'empreinte modifiée | après lots 2 et 3 |

## Décisions ouvertes

- Premier cas client cible (commercial, documents industriels, autre).
- Mode d'arbitrage à trois en cas de désaccord.
- Licence et éventuelle ouverture du code.
- Protection technique de `main` (offre GitHub).
