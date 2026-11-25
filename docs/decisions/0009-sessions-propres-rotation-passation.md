# 0009 — Sessions propres : rotation paresseuse et passation

**Statut :** acceptée le 25/11/2026 (Thibaud).

## Contexte

Une conversation unique et sans fin coûte de plus en plus cher à chaque tour (tout l'historique
repart au modèle) et finit par embrouiller l'agent. Un `/new` manuel règle le problème, mais
l'utilisateur ne doit pas avoir à y penser. Couper au bout de 15 minutes de silence rendrait
l'agent amnésique au retour d'une pause café.

## Décision

Trois seuils, aucun minuteur :

1. **À chaque tour** : la mémoire retient les faits (Hindsight `auto_retain`). Rien à ajouter.
2. **Rotation** au *premier message* après 240 min sans message de l'utilisateur, ou après la
   frontière quotidienne de 4 h (heure de Paris). Jamais pendant une réponse en cours, jamais sur
   une commande `/`, jamais sur une conversation vide.
3. **Passation** : le premier tour de la nouvelle session reçoit un bloc de reprise déterministe
   (8 derniers échanges, 600 caractères chacun, 4 000 au total), sans appel LLM supplémentaire.
   Un `/new` manuel n'en reçoit pas : l'utilisateur a demandé un fil neuf.

L'affichage reste continu : l'ancienne session est montrée au-dessus de la nouvelle, avec un
séparateur discret.

## Mise en œuvre

| Surface | Où | Réglage |
| --- | --- | --- |
| API ARPAGONA (Mission Control client) | `services/arpagona-api` : rotation dans `/api/chat`, passation via `instructions` de `/v1/runs` | `ARPAGONA_SESSION_IDLE_MINUTES`, `ARPAGONA_SESSION_DAILY_HOUR` |
| Gateway Hermes (Telegram) | `plugins/session-lifecycle` : `pre_gateway_dispatch` + `pre_llm_call` | `plugins.entries.session-lifecycle.settings` |
| GONA Mission Control alpha | `apps/gona-mission-control` : rotation avant envoi (mode Telegram via `/new` natif ; mode api dans sa base) | réglages du plugin, ou `MC_SESSION_IDLE_MINUTES` / `MC_SESSION_DAILY_HOUR` |

`0` (minutes) ou `-1` (heure) désactive le seuil correspondant.

## Conséquences

- Coût par tour borné ; contexte propre ; historique intact en base.
- La passation est un extrait, pas un résumé : fidèle et gratuite, mais limitée aux derniers
  échanges. Un résumé LLM pourra la remplacer si l'usage montre un besoin.
- Le code de rotation du plugin reprend `hermes-session-reset-policy` (MIT), modifié pour compter
  l'activité depuis `state.db` (Telegram **et** Mission Control).
