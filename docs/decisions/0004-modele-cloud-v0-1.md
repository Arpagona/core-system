# ADR 0004 — Fournisseur de modèle de la v0.1

**Date :** 10 novembre 2026
**Statut :** option A et route de préversion choisies par Thibaud ; relecture de Maël et Stéphane encore requise
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
