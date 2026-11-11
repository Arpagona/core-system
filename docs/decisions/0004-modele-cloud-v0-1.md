# ADR 0004 — Fournisseur de modèle de la v0.1

**Date :** 10 novembre 2026
**Statut :** principe (option A), fournisseur, modèle et plafonds décidés par Thibaud le 10/11/2026 ; relecture de Maël et Stéphane encore requise
**Correction du 10/11/2026 :** la version initiale présentait à tort `opencode-go` / `deepseek-v4.1-flash` comme route approuvée.
**Actualisation du 11/11/2026 :** après la correction ci-dessus, Thibaud a choisi le 10/11 `opencode-go` / `deepseek-v4.1-flash` pour le défaut de la préversion et accepté 0,50 USD par mission et 20 USD par 24 heures ; l'implémentation utilise une fenêtre glissante. L'interprétation du terme « quotidien » reste à confirmer. Cette décision individuelle ne vaut pas accord collectif ; revue de Maël et Stéphane attendue.
**Référence :** `docs/PLAN-NOYAU.md`, section 5.3 ; décision consignée dans la carte `t_066af63e`.

## Contexte

Le noyau agentique sera installé sur une machine virtuelle du serveur Atlas. Le routeur de modèles local du poste de travail n'écoute qu'en boucle locale (`127.0.0.1:8080`, vLLM sur `127.0.0.1:8022`) : il n'est donc pas joignable depuis cette VM sans exposer un service sur le réseau local.

## Options examinées

| Option | Avantage | Inconvénient |
|---|---|---|
| A. API cloud OpenAI-compatible | immédiat, aucune surface réseau ajoutée | coût par mission, code transmis à un tiers |
| B. Exposer le routeur local sur le LAN | souveraineté, coût marginal nul | nouvelle surface d'attaque, décision de sécurité lourde |
| C. Passerelle dédiée sur Atlas | isolement correct | brique supplémentaire à maintenir |

## Décision

Option **A** sur le principe : API cloud OpenAI-compatible, configurable (`base_url`, `model`, `api_key_env`). La clé provient d'une variable d'environnement, jamais du dépôt.

**Décision complémentaire de Thibaud (10/11/2026, soir) :**

| Élément | Valeur |
|---|---|
| Fournisseur / passerelle | `opencode-go` — `https://opencode.ai/zen/go/v1` (OpenAI-compatible) |
| Modèle par défaut | `deepseek-v4.1-flash` |
| Plafond par mission | 0,50 $ estimés (`max_cost_microusd = 500_000`) |
| Plafond quotidien | 20 $ estimés sur 24 h glissantes, toutes missions (`max_daily_cost_microusd = 20_000_000`) — interprétation de « plafond quotidien » à confirmer |

Précisions techniques constatées : la passerelle exige l'en-tête `x-opencode-session` (configurable, valeur = identifiant de mission). Le coût est **estimé** à partir de tarifs configurés prudents (0,30 $ / M tokens en entrée, 1,20 $ / M en sortie), pas facturé ; le contrôle est strict (coût engagé + pire cas de l'appel suivant). Clé : actuellement la clé opencode existante, copiée dans la VM de test hors dépôt ; une clé dédiée au projet reste recommandée.

Cette décision reste à relire par Maël et Stéphane ; elle ne change pas le contrat `ModelPort`.

**Précision 11/11 :** pour la préversion, route `opencode-go` / `deepseek-v4.1-flash` et plafonds ci-dessus choisis par Thibaud. Le plafond global de développement reste à préciser, ainsi que la confirmation de la fenêtre quotidienne. Revue collective toujours requise.

## Justification

- décision explicite de Thibaud le 10/11/2026 ;
- aucune exposition réseau supplémentaire sur le poste de travail ;
- réversible : le noyau dépend d'un port `ModelPort`, pas d'un fournisseur.

## Conséquences

- le contenu des missions transite vers un fournisseur externe : **aucune donnée client réelle** en v0.1 ;
- le coût et la latence doivent être mesurés et journalisés par mission ;
- délais et nombre de tentatives bornés obligatoires ;
- un adaptateur local pourra être ajouté plus tard sans modifier les contrats du noyau.

## Limites

Cette décision ne traite ni la confidentialité contractuelle avec le fournisseur, ni l'hébergement, ni la conservation des données. Ces points restent hors périmètre de la v0.1 et devront être tranchés avant tout usage sur données client.
