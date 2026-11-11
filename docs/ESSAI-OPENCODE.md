# Essai OpenCode dans Mission Control

L’onglet **OpenCode** envoie un exercice fixe à un modèle de test. L’exercice consiste à corriger la formule du prix total. La console affiche le diff proposé et les résultats de trois vérifications déterministes. La proposition est évaluée avec un ensemble fermé d’opérateurs et n’est jamais exécutée comme du code. Le résultat reste consultable jusqu’au prochain essai ou au redémarrage de la console.

## Essai sur une VM dédiée

Préparer une VM Linux de test avec bubblewrap, un binaire OpenCode autonome compatible avec la configuration de permissions V1, et un compte dédié. Configurer une clé de test avec un plafond fournisseur dans l’environnement du compte. La console ne transmet que cette variable au processus OpenCode. La limite de 90 secondes borne l’exécution locale. La tarification relève du compte de test chez le fournisseur. [CLI OpenCode](https://opencode.ai/docs/cli) · [Permissions V1](https://docs.opencode.ai/docs/permissions/)

Lancer une instance de test sur un port libre, depuis la branche de cette PR.

```sh
python3 web/console.py --port 8766 \
  --agentcore /usr/local/bin/agentcore \
  --opencode-bin /chemin/vers/opencode \
  --opencode-model fournisseur/modèle \
  --opencode-key-env FOURNISSEUR_API_KEY
```

Depuis l’iMac, relier le navigateur à la console de test.

```sh
ssh -N -L 8766:127.0.0.1:8766 utilisateur@serveur
```

Ouvrir [Mission Control](http://127.0.0.1:8766/), puis **OpenCode** et **Lancer l’essai**. Le processus démarre avec un espace de travail éphémère, des outils OpenCode refusés et des montages système en lecture seule. Il utilise le réseau de la VM pour joindre le fournisseur. Réserver cette VM aux essais et utiliser un compte de test dédié. Le service Mission Control existant peut continuer à tourner sur son port habituel. L’unité systemd du serveur de test interdit les espaces de noms nécessaires à bubblewrap et ne convient donc pas à cet essai.

Le prochain jalon consistera à remplacer cet exercice fixe par une copie de dépôt de test autorisée, puis à recueillir un patch et les sorties d’une commande de test définie par l’opérateur.

## Vérification reproductible

Le test local utilise le vrai binaire OpenCode et un serveur fournisseur fictif. Il vérifie que l’action HTTP renvoie un diff correct, que les trois vérifications passent et qu’un seul appel modèle part sur le scénario nominal, sans outil déclaré. La console donne un titre fixe à la session pour éviter l’appel auxiliaire de génération de titre.

```sh
python3 tests/opencode_lab.py
python3 tests/opencode_smoke.py /chemin/vers/opencode
```

Essai vérifié avec OpenCode 1.19.5. L’essai sur la VM avec le fournisseur choisi reste distinct. [Publication OpenCode 1.19.5](https://github.com/anomalyco/opencode/releases/tag/v1.19.5)
