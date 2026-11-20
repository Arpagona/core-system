# Parité Telegram — Mission Control

Branche : `feat/telegram-parity`  
Worktree : `/home/thibaud/projects/gona-mission-control-parity`  
Production : `/home/thibaud/projects/gona-mission-control` — non modifiée pendant le chantier.

## Résultat

Le chat Mission Control utilise désormais le flux natif du gateway Hermes : streaming des tokens, progression des outils, boutons d'approbation/clarify, `/model`, `/reasoning`, `/stop`, menu de commandes et rendu Markdown avec images `MEDIA:`. Le polling reste le repli automatique si le flux SSE tombe.

## Parité fonction par fonction

| Fonction Telegram | Mission Control | Statut | Détail |
|---|---|---|---|
| Réponse affichée au fil de l'eau | SSE `GET /api/stream?id=…` | Fait | `gateway_live.py` s'abonne via `session.resume` + flux d'événements, `server.py` relaie en `text/event-stream`, avec heartbeat. |
| « GONA écrit… » | Événement `writing` puis `delta` | Fait | Bulle de streaming avec curseur ; le libellé « GONA travaille… » est aussi utilisé pendant l'envoi. |
| Progression des outils | `tool.start` / `tool.complete` | Fait | Ligne outil + aperçu court (40 caractères max), même niveau de détail que le profil Telegram, sans args ni résultats. |
| Reprise après coupure SSE | `EventSource` + polling | Fait | Reconnexion automatique ; repli sur `/api/channel/messages` toutes les 5 s après erreur. |
| Markdown | `web/markdown.js` | Fait | Titres, listes, citations, code inline/bloc, gras, italique, barré, liens `http(s)`. Échappement HTML systématique, pas de HTML brut. |
| Images `MEDIA:/chemin` | `GET /api/media?path=…` | Fait | Images PNG/JPEG/GIF/WebP/BMP, extension et racine autorisées, taille max 12 Mo, noms sensibles refusés. |
| Menu `/` cliquable | `GET /api/commands` + menu | Fait | `/status /model /reasoning /stop /new /restart /help`, filtrage à la frappe, Tab/Entrée/clic. |
| `/model` | Boutons fournisseur/modèle | Fait | Données `model.options`, changement par la commande native `/model <id>`, confirmation si requise. |
| `/reasoning` | Boutons low/medium/high/xhigh/reset | Fait | Niveaux exposés par `/api/command` et état courant affiché. |
| Clarify | Cartes de choix + RPC natif | Fait (code + tests) | `clarify.respond(session_id, execution_generation, prompt_id, answer)`. Pas de clarify réel observé pendant la capture. |
| Approbations | Boutons Approuver/Refuser | Fait (code + tests) | `approval.respond(session_id, execution_generation, prompt_id, choice)`, choix limités à `once/deny/session/always`. Pas d'approbation réelle observée pendant la capture. |
| `/stop` | `session.interrupt` | Fait | Bouton Stop + commande native, lié à la génération du tour courant. |
| Voix, Kanban, portail de décision | Routes existantes | Fait | Aucune route ni interaction modifiée ; tests de non-régression verts. |

## Architecture

```text
Navigateur
  ├─ EventSource /api/stream?id=<session>
  │    └─ server.py → gateway_live.py (op=stream)
  │         └─ hermes_cli.gateway_client → session.resume()
  │              ├─ session.info()
  │              └─ events.get() → sanitize_event() → JSONL → SSE
  ├─ POST /api/control/respond → gateway_live.py (op=respond)
  │    └─ approval.respond / clarify.respond
  ├─ POST /api/command → serveur local → session.interrupt via gateway_live.py
  └─ GET /api/media?path=… → image locale contrôlée
```

Le flux SSE est composé d'événements JSON, un par ligne :

```text
data: {"type":"snapshot","session":"…","running":false,"info":{…}}

data: {"type":"writing"}
data: {"type":"delta","text":"Bonjour"}
data: {"type":"tool","name":"terminal","preview":"…"}
data: {"type":"tool_done","name":"terminal","is_error":false}
data: {"type":"control","prompt":{"kind":"approval","choices":["once","deny"],…}}
data: {"type":"complete","status":"complete","text":"…"}
```

Types relayés : `snapshot`, `ready`, `writing`, `delta`, `tool`, `tool_done`, `control`, `control_settled`, `info`, `notice`, `complete`, `gap`.

## Format réel des événements observés

Capture en lecture seule via `session.events.since(session_id, last_sequence=0, replay_epoch=…)`, le 20 novembre 2026. Les frames du gateway contiennent :

```text
session.info        payload : api_mode, archived, credential_hint, desktop_protocol,
                              fast, last_active_at, lazy, model, profile_id,
                              profile_name, reasoning_effort, reasoning_effort_wire,
                              service_tier, source, started_at, title, tool_count, yolo

message.start       payload : {}

message.delta       payload : offset, segment, text, turn_id

message.complete    payload : admission_id, content, outcome, persisted_turn, status, text
                              status = complete | interrupted | error

agent.step          payload : iteration

tool.start          payload : args, context, name, tool_call_id, tool_id, tool_name

tool.complete       payload : args, context, is_error, name, result, tool_call_id,
                              tool_id, tool_name
```

Frames avec `admission_id`, `authority_epoch`, `execution_generation`, `replay_epoch`, `seq`, `session_id`, `type`. Les événements d'approbation/clarify suivent le même enveloppement avec un payload de la forme :

```text
approval.request    {kind, prompt_id, execution_generation, command, description, choices, timeout_s?}
clarify.request     {kind, prompt_id, execution_generation, question, choices, multi_select, timeout_s?}
```

`session.resume` ne renvoie qu'un `info` minimal (`desktop_protocol`). L'adaptateur appelle donc `session.info` pour obtenir le modèle, le raisonnement, le titre et `yolo`.

## Sécurité

- Aucun `prompt.submit`, `session.mutate`, interrupt ou reset n'est exécuté pendant la capture.
- L'adaptateur ne transmet jamais `args` ni `result` d'outil : seulement le nom et un aperçu de `context` (ou d'un champ texte autorisé), tronqué à 40 caractères.
- Les motifs de secrets sont redactés : `*api_key`, `*token`, `secret`, `password`, `Authorization`, `Bearer …`, `sk-…`.
- Le snapshot ne contient pas les messages historiques ; l'historique reste servi par la route existante.
- `/api/media` n'accepte que des fichiers image existants, sous des racines autorisées, et refuse les noms de credentials (`.env`, `token`, clés SSH, etc.).
- Les erreurs du sous-processus ne sont jamais renvoyées au navigateur ; aucun secret n'est journalisé.
- `gateway_live.py` valide strictement les ops et les champs de contrôle ; les champs inconnus sont rejetés.

## Tests

Commande :

```text
python3 -m unittest discover -s tests -v
```

Sortie exacte du 20 novembre 2026 :

```text
test_items_and_decide_idempotent (test_gate.GateTest.test_items_and_decide_idempotent) ... ok
test_refuse_bad_input (test_gate.GateTest.test_refuse_bad_input) ... ok
test_approval_and_clarify_prompts (test_gateway_live.GatewayLiveTests.test_approval_and_clarify_prompts) ... ok
test_authorization_and_long_tokens (test_gateway_live.GatewayLiveTests.test_authorization_and_long_tokens) ... ok
test_delta_and_writing (test_gateway_live.GatewayLiveTests.test_delta_and_writing) ... ok
test_real_capture_fixture (test_gateway_live.GatewayLiveTests.test_real_capture_fixture) ... ok
test_snapshot_redacts_prompt_and_hides_messages (test_gateway_live.GatewayLiveTests.test_snapshot_redacts_prompt_and_hides_messages) ... ok
test_tool_never_exposes_args (test_gateway_live.GatewayLiveTests.test_tool_never_exposes_args) ... ok
test_validate_rejects_injection (test_gateway_live.GatewayLiveTests.test_validate_rejects_injection) ... ok
test_escapes_html (test_markdown.MarkdownTests.test_escapes_html) ... ok
test_markdown_blocks_and_links (test_markdown.MarkdownTests.test_markdown_blocks_and_links) ... ok
test_media_path_is_encoded (test_markdown.MarkdownTests.test_media_path_is_encoded) ... ok
test_rejects_javascript_links (test_markdown.MarkdownTests.test_rejects_javascript_links) ... ok
test_ask_script_list_and_decide_fixture_only (test_server.AlphaTests.test_ask_script_list_and_decide_fixture_only) ... ok
test_auth_and_brand (test_server.AlphaTests.test_auth_and_brand) ... ok
test_backend_failure_does_not_leak (test_server.AlphaTests.test_backend_failure_does_not_leak) ... ok
test_chat_bridge_same_session_fixture_only (test_server.AlphaTests.test_chat_bridge_same_session_fixture_only) ... ok
test_commands_and_native_stop (test_server.AlphaTests.test_commands_and_native_stop) ... ok
test_control_respond_forwards_only_allowed_fields (test_server.AlphaTests.test_control_respond_forwards_only_allowed_fields) ... ok
test_create_mock_cli_no_assignee (test_server.AlphaTests.test_create_mock_cli_no_assignee) ... ok
test_csrf (test_server.AlphaTests.test_csrf) ... ok
test_forbid_existing_mutations (test_server.AlphaTests.test_forbid_existing_mutations) ... ok
test_login_logout (test_server.AlphaTests.test_login_logout) ... ok
test_media_allowlist_and_content_type (test_server.AlphaTests.test_media_allowlist_and_content_type) ... ok
test_read_connection_is_mode_ro (test_server.AlphaTests.test_read_connection_is_mode_ro) ... ok
test_read_only_cards (test_server.AlphaTests.test_read_only_cards) ... ok
test_real_snapshot_count (test_server.AlphaTests.test_real_snapshot_count) ... ok
test_sse_relays_sanitized_lines (test_server.AlphaTests.test_sse_relays_sanitized_lines) ... ok

----------------------------------------------------------------------
Ran 28 tests in 7.752s

OK
```

Vérifications complémentaires : `node --check web/app.js`, `node --check web/markdown.js`, `python3 -m py_compile server.py gateway_live.py` — OK.

Smoke réel sur le port `8719` (jamais la production) :

```text
/api/me                 200
/api/commands           200
/api/channel/messages   200, 57 messages
/api/stream             200, text/event-stream; charset=utf-8
snapshot                running=false, model=claude-opus-5-5, reasoning=medium
/api/command /status    200, model=claude-opus-5-5, reasoning=medium
/api/command /reasoning 200, levels=low,medium,high,xhigh,reset
/api/command /model     200, 9 fournisseurs
```

Le code `124` observé en fin de smoke est le timeout volontaire du serveur de test.

## Déploiement

Aucune migration de données ni changement de schéma. Le déploiement consiste à remplacer le code puis à redémarrer le service utilisateur qui sert Mission Control.

1. Fusionner ou cherry-picker le commit de `feat/telegram-parity` dans le checkout de production `/home/thibaud/projects/gona-mission-control`.
2. Vérifier que `gateway_live.py` est présent à côté de `server.py`, ainsi que `web/markdown.js`.
3. Redémarrer le service de production :
   ```bash
   systemctl --user restart arpagona-mission-control-alpha.service
   ```
4. Vérifier le service et le journal :
   ```bash
   systemctl --user status arpagona-mission-control-alpha.service
   journalctl --user -u arpagona-mission-control-alpha.service -n 50 --no-pager
   ```
5. Ouvrir Mission Control, vérifier `/status`, puis un tour réel : streaming, ligne d'outil, Stop, `/model` et `/reasoning`.
6. Si le gateway est indisponible, le chat doit continuer en polling ; le SSE se reconnecte seul.

Le service de production est `arpagona-mission-control-alpha.service` (`WorkingDirectory=/home/thibaud/projects/gona-mission-control`, `server.py`, port par défaut `8710`). Le service `gona-mission-control-ui.service` sur `8790` est l'ancien backend, pas la cible de ce déploiement.

## Retour arrière

Pas de données migrées : le rollback est un retour de code suivi d'un redémarrage.

1. Revenir au commit précédent le chantier (ou `git revert` du commit de fusion) dans le checkout de production.
2. Redémarrer `arpagona-mission-control-alpha.service`.
3. Vérifier que la page et `/api/channel/messages` répondent à nouveau.

Le polling existant reste le filet de sécurité : une panne du flux SSE ne bloque pas l'envoi des messages ni l'historique. Les routes voix, Kanban et décision n'ont pas été modifiées.
