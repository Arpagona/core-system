#!/usr/bin/env bash
# Remplit le Kanban du banc avec quelques cartes de démonstration (données fictives, aucune affectation :
# aucun agent n'est déclenché). Rejouable : clés d'idempotence. Retrait : archiver les cartes [DEMO].
# Usage (sur la VM, en root) : bash demo-kanban.sh
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "à lancer en root" >&2; exit 1; }
h() { sudo -u hermes-arpagona -H bash -lc "export PATH=\$HOME/.local/bin:\$PATH; $(printf '%q ' hermes kanban "$@")"; }
id_de() { h create "$@" --created-by demo --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])'; }

A=$(id_de "[DEMO] Dupont Mécanique — préparer l'offre pilote 4 semaines" --idempotency-key demo-offre \
  --body "Client fictif. Objectif : offre d'une page, périmètre limité au contrôle des plans entrants (série 50-500 pièces).")
B=$(id_de "[DEMO] Plan P-1042 — vérifier les cotes critiques" --idempotency-key demo-p1042 \
  --body "Plan fictif. Trois cotes à contrôler : Ø12 H7, entraxe 48 ±0,05, planéité 0,02.")
C=$(id_de "[DEMO] Devis 2026-041 — relancer le client" --idempotency-key demo-devis \
  --body "Devis fictif de 200 supports. Relance prévue sous 48 h, brouillon à valider avant envoi.")
D=$(id_de "[DEMO] Facture fournisseur F-7781 — rapprocher de la commande" --idempotency-key demo-facture \
  --body "Facture fictive. Écart de 3 pièces entre bon de livraison et facture.")
E=$(id_de "[DEMO] Mettre en place le modèle de fiche client" --idempotency-key demo-fiche \
  --body "Gabarit fictif : raison sociale, contact achats, matières, volumes annuels.")

h comment "$B" "Cote d'entraxe hors tolérance sur la vue de détail B : à confirmer avec le bureau d'études." >/dev/null
h block "$D" "En attente du bon de livraison signé." >/dev/null || true
h complete "$E" --result "Modèle validé." >/dev/null || true
h list
