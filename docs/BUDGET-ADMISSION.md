# Budget — contrat d'admission et procédure opérateur

## Ce que garantit ce candidat

- Une réservation est écrite dans la même base SQLite que les missions **avant** l'appel moteur, pour le chat comme pour les échéances.
- `BEGIN IMMEDIATE` protège le calcul et l'insertion entre connexions/processus. Un verrou Python seul ne suffirait pas.
- La somme des coûts connus et des réserves ne peut pas dépasser la limite d'admission au moment où un nouveau travail est accepté. Les réserves anciennes restent comptées après redémarrage et après 24 heures.
- Un coût inconnu, NaN, infini, négatif ou booléen ne devient pas zéro. Il bloque de nouveaux démarrages. La configuration de limites nulle, négative ou non finie est refusée, pas interprétée comme « illimité ».
- Les montants sont suivis en micro-USD. Coûts/réserves arrondis vers le haut, limite vers le bas.
- L'insertion et la clôture financière sont idempotentes ; une répétition ne rembourse pas la même consommation.
- Les coûts historiques ne disparaissent pas lors de l'introduction du registre ; les coûts historiques inconnus restent à rapprocher.
- L'export métier conserve les réserves. Cela ne vaut pas preuve de réimport complet.

## Ce que cela NE garantit PAS

La réservation n'est ni un devis du moteur, ni un plafond de facture. Le moteur actuel peut consommer plus que la réserve pendant une exécution. Aucun paramètre USD de coupure n'a été identifié dans le contrat `/v1/runs` inspecté sur le banc. Un arrêt demandé au moteur ne prouve pas la fin de facturation d'un appel distant déjà parti.

L'API expose donc `plafond_fournisseur_garanti: false` et l'interface l'indique. La porte financière stricte reste ouverte. Il faut prouver une borne appliquée au niveau moteur/fournisseur, ou proposer un mode de beta réellement borné, avant de prétendre le contraire. Aucun changement de clé, de fournisseur ou de facturation n'est réalisé par ce candidat.

Les limites courantes restent 0,50 USD de réserve par démarrage et 5 USD sur 24 h pour l'instance, pas par utilisateur. Il n'est pas proposé de relever ces limites.

## Reprise après erreur

Une erreur de soumission, même HTTP 503, ne prouve pas à travers un intermédiaire qu'aucune exécution n'a commencé. La réserve reste inconnue et aucun nouveau travail payant ne part automatiquement. Les commandes locales `/status`, `/help` et `/new` ne nécessitent pas de démarrer un modèle.

Les échéances utilisent le même registre et deviennent des missions suivies. Si le délai de surveillance expire, elles ne sont ni marquées terminées ni remboursées : le suivi visible pourra constater l'état réel du moteur ensuite. La politique de réessai/représentation des échéances différées et de leurs tentatives reste à recetter sur le banc.

## Rapprochement opérateur explicite

Ces commandes sont des outils d'administration **locale**, protégés par les droits d'accès à la base du service. `--operator` vérifie le rôle du compte et attribue l'audit ; ce n'est pas un nouveau mécanisme d'authentification distant.

Exemple sur Atlas, depuis un accès administrateur autorisé :

```sh
sudo -u arpagona-api env \
  PYTHONPATH=/opt/arpagona/current/services/arpagona-api \
  ARPAGONA_DB=/var/lib/arpagona-api/arpagona.db \
  python3 -m arpagona_api.manage budget-status --operator thibaud
```

Avant tout rapprochement :
1. Identifier le travail exact, vérifier sa fin ou une preuve de non-démarrage. Une simple coupure du client n'est pas une preuve.
2. Relever la consommation dans une source fiable du moteur/fournisseur. Ne jamais supposer un coût nul.
3. Conserver une référence de preuve, sans secret ni contenu client sensible. Les réserves actives ne se libèrent pas sur simple impression qu'un travail aurait échoué.
4. Effectuer le geste explicite, par exemple pour une fixture synthétique dont le coût zéro est effectivement prouvé :

```sh
# EXEMPLE FICTIF : remplacer la clé et la référence par les preuves vérifiées.
python3 -m arpagona_api.manage budget-reconcile CLE_DE_RECETTE \
  --operator thibaud --cost-usd 0 \
  --evidence 'Référence de preuve de la fixture sans appel fournisseur' --confirm
```

Sans `--confirm`, rien n'est changé. Un membre, une preuve vide, un montant invalide ou un rapprochement déjà effectué sont refusés. La modification et son audit forment une transaction. Le reçu relit la ligne modifiée. Le suivi automatique n'appelle jamais cette fonction.

`budget-status` donne aussi les clés `legacy-mission-<id>-<user_id>` des anciennes missions dont le coût manque. Une mission historique encore en cours ne peut pas être rapprochée comme terminée par ce raccourci. Un rapprochement historique accepté conserve le registre et met à jour son coût métier, sans double comptage.

## Déploiement et retour arrière

Candidat non déployé tant que la revue requise n'est pas acquise. Avant déploiement : sauvegarde SQLite cohérente, inventaire des anciennes missions aux coûts inconnus, vérification des limites et procédure opérateur prête. Ne jamais remplir ces coûts avec zéro pour débloquer l'interface.

Un rollback vers l'ancien code enlève la protection d'admission : ce n'est pas un état conforme. Conserver les écritures financières dans les sauvegardes et annoncer explicitement le mode dégradé. Ne pas supprimer les réservations pour faire passer une recette.
