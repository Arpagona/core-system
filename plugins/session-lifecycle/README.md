# session-lifecycle — sessions propres, invisibles pour l'utilisateur

Plugin Hermes (gateway : Telegram, et Mission Control qui écrit dans la même session).

| Moment | Effet |
| --- | --- |
| Chaque tour | Hindsight retient déjà les faits (`auto_retain`) : rien à faire ici. |
| Premier message après `idle_minutes` sans message de l'utilisateur, ou après `daily_hour` | Rotation par le chemin natif du `/new`. Jamais pendant un tour en cours, jamais sur une commande `/`. |
| Premier tour de la nouvelle session | Bloc de reprise (8 derniers échanges, 600 car. chacun, 4 000 car. max) injecté dans le tour. Pas après un `/new` manuel. |

Aucun minuteur, aucun appel LLM supplémentaire. L'horloge est le dernier message *utilisateur* réel
dans `state.db` : Telegram et Mission Control comptent tous les deux.

## Installation (gateway multiplexé)

Le crochet `pre_gateway_dispatch` s'exécute avant la portée du profil : copier le plugin dans
`~/.hermes/plugins/` **et** dans `~/.hermes/profiles/<profil>/plugins/`, puis l'activer dans les deux
`config.yaml`. Il n'agit que pour les profils qui l'activent **et** portent un bloc `settings` explicite
(un profil qui l'active sans réglages, comme la racine, n'est jamais tourné) :

```yaml
plugins:
  enabled: [session-lifecycle]
  entries:
    session-lifecycle:
      settings:
        idle_minutes: 240   # 0 = désactivé
        daily_hour: 4       # heure locale ; -1 = désactivé
        handoff: true
```

Puis `systemctl --user reload hermes-gateway.service` (attend la fin du tour en cours).

## Traces (sans contenu)

`<profil>/session-lifecycle/rotations.jsonl` et `handoffs.jsonl`. Mission Control écrit aussi
`rotations.jsonl` (`"by": "mission-control"`) quand il tourne la session avant un envoi.

## Retour arrière

Retirer `session-lifecycle` de `plugins.enabled` (ou le mettre dans `disabled`) puis recharger le
gateway. Aucune donnée n'est supprimée.

## Tests

`python3 -m unittest discover -s plugins/session-lifecycle/tests -v` (stdlib + PyYAML).
