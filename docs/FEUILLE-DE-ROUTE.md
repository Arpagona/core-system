# Feuille de route — ARPAGONA Core System

Mise à jour : 22 novembre 2026. Statut : **proposition de travail**, à discuter entre Thibaud, Maël et Stéphane. Les lots ne sont pas des engagements.

## Le produit en une phrase

Une surcouche d'Hermès Agent officiel (ADR 0007) qui donne à une PME un copilote : il prépare, l'humain décide. Une instance par client (ADR 0008).

## État vérifié au 22/11/2026

| Brique | État | Preuve |
|---|---|---|
| Mission Control web (chat, missions, Kanban, approbations, engagements, journal) | fonctionne | tests API 83 ; parcours local 26 ; recette navigateur à rejouer après déploiement |
| API ARPAGONA (comptes, rôles, sessions, missions, engagements, brouillons, envoi, empreinte, audit, export) | fonctionne | 83 tests unitaires |
| Envoi courriel après approbation | codé et testé, **non prouvé en réel** | faux SMTP vert ; remise réelle à faire sur le banc |
| Plafonds de dépense (mission et jour) | fonctionne | tests : dépassement signalé, mission suivante refusée |
| Passerelle Kanban (liste blanche sur `hermes kanban`) | fonctionne | 7 tests + parcours local |
| Plugin `arpagona-core` (3 outils, aucun envoi) | fonctionne | recette banc 12/11 ; parcours local 22/11 |
| Poste développeur en une commande | fonctionne | `tests/dev`, Python 3.10 à 3.14 |
| Banc Atlas (VM `agentcore-dev`, Hermès v0.23.1, Hindsight) | en service, accès LAN de test | recette 29/30 le 12/11 ; à rejouer |
| Mémoire d'équipe Hindsight | partielle | M0 vert, M1 en échec le 12/11 (contexte tronqué, correctif non rejoué) |

## Limites à dire à tout interlocuteur

- Banc de test. Aucune donnée client réelle.
- HTTP sur le réseau local, cookie non `Secure`. HTTPS obligatoire avant tout client.
- L'envoi courriel n'est pas encore prouvé en conditions réelles (SMTP à configurer).
- Une seule instance existe. L'isolation entre deux clients n'est pas démontrée.
- Sauvegarde/restauration de l'instance non testées.
- Le plafond de dépense n'interrompt pas une exécution déjà lancée ; il bloque la suivante.

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
