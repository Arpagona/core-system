# ADR 0003 — workspace expérimental jetable

Date : 2026-11-10. Statut : proposition dans PR 1, accord des trois non recueilli.

Contexte : vérifier le passage d'un contrat entre deux unités sans anticiper l'architecture produit. Options : workspace vide ou deux crates synthétiques. Proposition : deux crates sous experiments/, sans réseau ni dépendance externe ; crates/ reste réservé. Conséquence : permet de prouver localement une rupture mais ne valide ni un contrat produit ni l'architecture. Toute évolution de CI et du workspace requiert accord explicite des trois avant intégration.
