# Banc de régression — contrat C-10, anneau 0

**Statut : PROPOSÉ, non approuvé à trois** (cf. `docs/decisions/0006-boucle-amelioration-anneaux.md`, `docs/contrats/C-10-BOUCLE-AMELIORATION.md`).

Ce banc mesure la **qualité des livrables** que la vérification structurelle (C-06) ne voit pas. Il est hors ligne, déterministe, sans modèle, et ne modifie rien : c'est un **instrument de mesure**, pas une boucle d'amélioration.

## Contenu

| Cas | Défaut observé (mission réelle) | Historique attendu | Oracle |
|---|---|---|---|
| `Q-01-calcul-derive` | réduction « 90 % » pour 2,5 j → 1 j (exact : 60 %) ; +8 % appliqué aux devis clients | FAIL (Q-01-a) + WARN (Q-01-f) | PASS |
| `Q-02-contradiction-non-prouvee` | « prix vs réserve de capacité » classé contradiction ; « commande » surinterprétée | FAIL (Q-02-e) + WARN (Q-02-f) | PASS |

Chaque cas : `README.md` (origine, scellement), `dossier/` ou `dossier.ref`, `attendus.json` (contrôles regex scellés + empreinte SHA-256 du dossier), `historique/` (livrables réels défectueux, étiquetés « avant »), `oracle.md` (livrable minimal rédigé à la main qui doit passer — il ne prouve pas qu'un modèle l'atteint).

## Utilisation

```
python3 bench/verifier.py                 # tous les cas : historiques (FAIL attendu) + oracles (PASS attendu)
python3 bench/verifier.py --cas Q-01-calcul-derive --livrable /chemin/synthese.md   # évaluer un candidat
python3 bench/verifier.py --json          # sortie machine (verdict, contrôles, empreintes)
python3 tests/bench_verifier.py           # tests négatifs du banc lui-même
```

Codes : `0` aucun FAIL (hors historiques), `1` FAIL, `2` banc incohérent (dossier modifié après scellement, attendus invalides).

## Règles

1. Attendus et dossiers sont **scellés** : toute modification exige une PR distincte de toute PR touchant le noyau.
2. Un nouveau cas part d'une `HumanCorrection` (C-10.1) et conserve le livrable défectueux dans `historique/` ; le test négatif est obligatoire.
3. Données synthétiques uniquement, marquées « fictif ». Aucun secret, aucun chemin de VM.
4. Les regex sont des heuristiques : un `present` satisfait ne prouve pas la qualité ; un `absent` violé prouve un défaut. Limite connue : une regex ne distingue pas une citation d'une affirmation (cf. Q-01-c).

## Comment produire un candidat (manuel, v0.1)

Dans la VM de test : `agentcore mission run --input <dossier du cas> --goal "<consigne>"`, puis rapatrier `workspace/synthese.md` et l'évaluer avec `--livrable`. Aucune automatisation n'est fournie à l'anneau 0.
