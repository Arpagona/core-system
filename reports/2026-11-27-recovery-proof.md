# Agent Core — lot sauvegarde / restauration, 27 novembre 2026

> Historique de l'arrêt initial. Le blocage décrit ci-dessous a depuis été réparé et la recette rejouée avec succès sur une nouvelle VM. Voir [la preuve de réparation](2026-11-27-recovery-repair.md). Cela ne déclare pas l'ensemble de la bêta conforme.

## Verdict

**NON VALIDÉ pour la restauration complète. La bêta n'est pas déclarée prête.**

La copie chiffrée hors hyperviseur est utilisable : le déchiffrement réel de la copie PC puis son transfert vers Atlas ont restitué exactement l'archive d'origine. La seconde tentative a restauré et démarré une VM neuve sans interfaces réseau. Le contrôle invité QGA a cependant échoué avant la comparaison des données et la validation des services. Un démarrage ne constitue pas une recette fonctionnelle.

## Livrables présents

Dans le worktree `/home/thibaud/projects/core-system-recovery`, branche `test/beta-recovery-proof` :

- `dev/restore_vm_proof.py` : contrôleur défensif, vérification SHA-256, refus d'une cible existante ou égale à la source, retrait des interfaces réseau avant premier démarrage, contrôle des services et des empreintes, procédure d'arrêt de la copie en fin d'exécution.
- `dev/recovery_data_manifest.py` : intégrité SQLite et empreintes agrégées des tables applicatives, y compris comptes et sessions. Aucune valeur d'authentification n'est imprimée.
- `dev/recovery_memory_manifest.py` : pagination vérifiée des documents et unités mémoire de chaque banque Hindsight, comptage et empreintes sans impression des textes.
- `tests/dev/test_restore_vm_proof.py` : **5 tests passants**, comprenant les refus d'écrasement, de lien symbolique, de mauvaise empreinte et de nom d'archive Proxmox invalide.

Cette branche n'est pas présentée comme une livraison fusionnée ou déployée. Les tests complets et la CI de cette nouvelle branche ne sont pas annoncés comme exécutés.

## Preuves acquises

- Archive chiffrée : `backup.vma.zst.age`, dans `/var/lib/vz/dump/agent-core-beta-20261127T111520Z/` sur Atlas.
- Copie PC : `~/.local/share/arpagona/agent-core-backups/20261127T111520Z/backup.vma.zst.age`.
- Le processus de copie vers l'iMac s'est terminé avec le code 0. Cela ne prouve pas une restauration depuis l'iMac.
- La chaîne réelle PC → déchiffrement `age` → réception Atlas a pris **639,766 secondes**.
- Données reçues : **7 511 490 921 octets**.
- SHA-256 du fichier déchiffré, comparé à l'original : `423d618c0112509473aca507a4c19987fe7f1e63eb75eb9a3b01e92e020f934d`.
- La configuration source contrôlée ne contenait aucun périphérique `hostpci`, `usb`, `virtiofs`, ni champ `args`, `hookscript` ou `cicustom`. Ses volumes étaient `local-lvm:vm-100-cloudinit` et `local-lvm:vm-100-disk-0`.
- Aucun arrêt de la VM source 100 n'est demandé par le contrôleur.

## Deux tentatives, sans masquer les échecs

### Première tentative — VM 101

Échec avant restauration des disques : Proxmox refuse le nom de staging `from-offhost.vma.zst` avec `couldn't determine archive info`.

Correction appliquée : conservation du nom original `vzdump-qemu-100-2026_11_27-12_15_21.vma.zst`, dans un sous-dossier séparé. Le contrôleur rejette désormais un nom non conforme et vérifie le VMID source indiqué dans le nom, avant création d'une VM. Les tests correspondants passent.

Le reçu privé `restore-receipt-101.json` indique une cible arrêtée et une source en marche. La VM 101 était alors un résidu vide de cette tentative. Aucune suppression de ce résidu n'est annoncée comme faite.

### Seconde tentative — VM 102

La restauration, le contrôle de configuration sans interfaces réseau, le démarrage et le ping de l'agent invité ont passé : l'exécution a atteint `guest(vmid, SETUP)`.

Échec du contrôle suivant : commande `qm guest exec 102 --timeout 300 ...`, **code 255**. La cause précise n'est pas établie. Ne pas attribuer ce code à un problème TLS, de base de données ou de service sans lire les diagnostics.

Le contrôleur comporte un `finally` qui demande l'arrêt de la copie et écrit un reçu. Le reçu exact de cette seconde tentative et l'état final des VM restent à relire : **ne pas annoncer leur vérification comme acquise**.

## Traces privées et reprise exacte

- Chaîne initiale PC : `/home/thibaud/.hermes/profiles/gpt5/cache/scratch/agent-core-recovery-chain-receipt.json`. Elle porte `passed: false` et `restore_exit_code: 1`.
- Atlas : `/var/lib/vz/dump/agent-core-beta-20261127T111520Z/restore-receipt-101.json` et `restore-receipt-102.json`.
- Archive déchiffrée reçue hors hôte puis renommée : `/var/lib/vz/dump/agent-core-beta-20261127T111520Z/offhost-retrieved/vzdump-qemu-100-2026_11_27-12_15_21.vma.zst`.
- Références privées : `expected-data.json`, `expected-memory.json`, `data_helper.py`, `memory_helper.py` dans ce même dossier Atlas.

Prochaine opération nécessaire : lire le reçu 102 et le diagnostic QGA ; confirmer l'arrêt de la copie et l'état de la source ; corriger le contrôle invité ; comparer réellement les données API/Kanban/Hindsight ; rejouer la recette et chronométrer la récupération complète. Ne jamais forcer la restauration sur une VM existante ni reconnecter le clone au LAN : il contient les identifiants de l'instance sauvegardée.

## Critères non acquis

- Intégrité des données **restaurées** comparée à la référence indépendante : non exécutée à ce stade.
- Services applicatifs de la copie : non validés.
- Récupération complète en moins de 30 minutes : non validée ; le temps de transfert seul ne suffit pas.
- Sauvegarde quotidienne, rétention et alertes : aucune activation annoncée.
- Deux clients indépendants et isolés : non testés par cet exercice de restauration d'une même instance.

Les limites de temps de l'exécution ont imposé un arrêt du diagnostic. Ce document est une continuité factuelle, pas une clôture de la mission ni une preuve d'ouverture de bêta.
