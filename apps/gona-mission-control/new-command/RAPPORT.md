# RAPPORT — `/new` depuis Mission Control

Commit Hermes de référence : `ae2a81ccc0` (sources en lecture seule).
Périmètre : prototype `mc-new`, sans installation ni redémarrage du gateway.

## 1. Mécanisme

1. Mission Control exécute `gateway_new.py` avec `{ "id": "<session physique>" }`.
2. Le client ouvre `$HERMES_HOME/mc-new-runtime/proof.sock` (AF_UNIX, 0700, `SO_PEERCRED`
   même UID) et obtient un proof à usage unique, lié à cet id, valable 30 s, non persisté.
3. Le client appelle le RPC `plugin.mc-new.mc.new` sur le gateway avec `session_id` + `local_proof`.
4. Le handler RPC consomme le proof, puis confie l'opération à la boucle du gateway
   (`run_coroutine_threadsafe`) sous le profil propriétaire de la session.
5. Le plugin vérifie le profil, l'id physique, la route vivante, le DM Telegram privé et la
   cible épinglée (`chat_id`, `user_id`, `thread_id`), puis exécute le chemin natif :
   - **session inactive** : `_handle_reset_command` (handler réel, aucun algorithme recopié) ;
   - **session occupée** : `dispatch_active_session_command(adapter, event, key, "new")`.
6. Le RPC ne renvoie `{ "ok": true, "new_session_id": ... }` qu'après avoir observé la
   rotation réelle du store. Toute exception ou rotation non observée renvoie `uncertain: true`.

Le plugin est fermé par défaut (`armed: false`) : sans activation explicite, le RPC répond
`not_armed` et aucun socket n'est créé.

## 2. Effet par effet — `/new` Telegram vs `mc-new`

| Effet du `/new` natif | Inactive | Occupée | Commentaire |
|---|---|---|---|
| Arrêt du tour propriétaire | reproduit | reproduit | `_handle_reset_command` / `_hm_stop_owner_turn` |
| Invalidation de génération, libération du slot | reproduit | reproduit | même handler |
| Nettoyage agent, éviction du cache | reproduit | reproduit | même handler |
| Effacement de l'état conversationnel + sécurité | reproduit | reproduit | `_clear_conversation_scope` |
| Interruption des délégations async | reproduit | reproduit | `interrupt_for_session` |
| Reset de l'état outils process | reproduit | reproduit | `_reset_process_scoped_tool_state` |
| Rotation + persistance du nouvel id | reproduit | reproduit | `async_session_store.reset_session` |
| Déplacement des wakes, suivi des followers | reproduit | reproduit | `move_route_wakes`, `paused_followers` |
| Hooks session (`session:end/reset`, plugins) | reproduit | reproduit | via le handler natif |
| Interruption du tour + raison RESET | — | reproduit | `_busy_new_command` → `_interrupt_and_clear_session` |
| Annulation du debounce / timer détenu | — | reproduit | `dispatch_active_session_command` |
| `cancel_session_processing` (release_guard=false) | — | reproduit | même dispatcher |
| Drain du message en attente (relancé après reset) | — | reproduit | `_drain_pending_after_session_command` |
| Bannière de confirmation envoyée dans Telegram | **non** | oui (via le dispatcher) | voir écarts |
| Confirmation destructive interactive (`Oui/Non`) | **non** | **non** | voir écarts |
| Admission gateway, burst gate, rate limits | **non** | **non** | le RPC a sa propre authorization + proof |
| Lobby de topic Telegram, injection de plugin en attente | **non** | **non** | court-circuit du routage idle natif |

Écarts assumés (prototype) :
- En inactive, le handler est appelé directement : pas de bannière Telegram et pas de
  confirmation destructive interactive. Le nouvel id est renvoyé à Mission Control, qui peut
  afficher son propre accusé. Si la confirmation est activée sur le profil, ce chemin ne la
  déclenche pas.
- En occupée, le dispatcher natif envoie la bannière `/new` dans Telegram (effet identique au
  `/new` natif, mais déclenché par Mission Control).
- Le proof local remplace l'acteur authentifié Telegram : la frontière de sécurité est l'UID
  local + le profil + la cible épinglée, pas l'identité du chat.

## 3. Tests

`run_tests.sh` neutralise le bootstrap/relaunch Hermes avec
`HERMES_DISABLE_LAZY_INSTALLS=1`, isole `HOME`, `HERMES_HOME`, `TMPDIR` sous
`.test-runtime/`, et utilise le Python du venv Hermes. Aucun paquet n'est installé.
Le proof AF_UNIX utilise `.test-runtime/proof-home` (limite de 108 octets).

Les tests occupés exercent le vrai `GatewayBusySessionMixin._busy_new_command`,
`_dispatch_busy_slash_command` et `GatewaySessionCommandsMixin._handle_reset_command`,
avec un adapter/runner factices et un `SessionStore` réel.

Sortie exacte de la dernière exécution (`sh run_tests.sh`) :

```
.......................                                                  [100%]
23 passed in 5.92s
```

## 4. Risques

- **API internes** : `gateway.run._gateway_runner_ref`, `runner._handle_reset_command`,
  `runner._adapter_for_source`, `runner._async_profile_scope_for_source`,
  `session_store.peek_session_id`, `dispatch_active_session_command`, plus les états
  `_active_sessions`, `_pending_messages`, `_text_debounce_store`. Tout changement Hermes
  peut casser le plugin ; le prototype est épinglé à `ae2a81ccc0`.
- **Verrou plugin** : le lock par session sérialise les RPC `mc-new` entre eux, pas l'ingress
  Telegram simultané. Le dispatcher natif garde la main sur l'annulation/drain.
- **Busy large** : un simple debounce ou un pending suffit à choisir le chemin occupé. C'est
  volontaire pour ne pas rejouer un texte détenu dans la nouvelle session, mais cela peut
  envoyer une bannière Telegram là où le `/new` natif aurait suivi un autre chemin.
- **Confirmation destructive** : non reproduite en inactive (voir écarts).
- **Pas de test intégré** : aucun gateway réel, aucune vraie session, aucun réseau n'a été
  utilisé (interdits du chantier). La validation sur le profil gpt5 reste à faire.
- **Sécurité** : tout processus du même UID peut demander un proof puis appeler le RPC. C'est
  la frontière locale annoncée ; le proof ne sert jamais d'authentification gateway.

## 5. Installation sur le profil gpt5

À faire hors de ce chantier, avec un redémarrage planifié du gateway (ne pas le faire ici) :

1. Copier le dossier `mc-new/` dans `$PROFILE/plugins/mc-new/` (`$PROFILE` = home du profil
   gpt5, celui qui contient son `config.yaml` et ses sessions).
2. Copier `gateway_new.py` vers l'emplacement d'exécution de Mission Control.
3. Déclarer le plugin dans `$PROFILE/config.yaml` :

   ```yaml
   plugins:
     enabled:
       - mc-new
     entries:
       mc-new:
         settings:
           armed: true
           target:
             chat_id: "<chat Telegram>"
             user_id: "<user Telegram>"
             thread_id: "<topic>"   # null si aucun topic
   ```

4. Redémarrer le gateway du profil gpt5 (hors périmètre de ce chantier) pour charger le
   plugin et créer `$PROFILE/mc-new-runtime/proof.sock`.
5. Appeler le client avec le Python du venv Hermes et `HERMES_HOME=$PROFILE` :

   ```sh
   printf '%s' '{"id":"<session physique>"}' \
     | HERMES_HOME="$PROFILE" PYTHONPATH="$HERMES_ROOT" \
       "$HERMES_ROOT/venv/bin/python" gateway_new.py
   ```

6. Vérifier sur un profil jetable : session inactive, puis session occupée (agent en cours),
   et contrôler l'id renvoyé, la disparition de l'ancien tour, le drain du pending et l'absence
   de rejeu.

## 6. Retour arrière

1. Repasser `armed` à `false` (le RPC répond `not_armed`, plus de création de proof).
2. Ou retirer `mc-new` de `plugins.enabled`.
3. Redémarrer le gateway pour décharger le plugin et fermer le socket.
4. Supprimer `$PROFILE/plugins/mc-new/` et, si souhaité, `$PROFILE/mc-new-runtime/`.
   Aucune table ni session Hermes n'est modifiée par l'installation elle-même.

## 7. Verdict

**PRÊT À ACTIVER : NON**

Le prototype est complet et couvert hors-ligne (23/23), y compris le chemin occupé natif.
Il n'est pas certifié pour une activation en production : aucun test intégré sur un gateway
réel n'a été possible dans ce chantier, et le plugin dépend d'API internes épinglées à
`ae2a81ccc0`. Condition de passage à OUI : smoke test encadré sur un profil gpt5 jetable,
session inactive puis occupée, avec vérification de l'id, du drain et des effets Telegram.
