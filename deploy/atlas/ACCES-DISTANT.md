# Accès distant au banc (WireGuard)

Statut : en service sur la VM `agentcore-dev` depuis le 22/11/2026. Banc de test uniquement, données fictives.

## Principe

```
Poste du contributeur ──WireGuard (UDP 51820, chiffré)──► box ──redirection──► VM agentcore-dev (wg0 10.68.100.1)
                                                                               autorisé : TCP 8700 Mission Control, TCP 22 SSH
                                                                               refusé : tout le reste, aucun routage vers le LAN
```

- Le tunnel se termine sur la VM, pas sur l'hôte ni sur le routeur. Le routage IP de la VM est coupé et la table `arpagona_wg` rejette tout transit : le réseau local est injoignable depuis le tunnel.
- Chaque contributeur génère sa propre paire de clés ; il ne transmet que ses clés **publiques**.
- Mission Control reste en HTTP, mais dans le tunnel chiffré.
- SSH : compte personnel, clé acceptée seulement depuis l'adresse du tunnel du contributeur, sans sudo, sans redirection de port, journaux système en lecture.

## Côté contributeur

1. Installer WireGuard : https://www.wireguard.com/install/ (Linux : paquet `wireguard-tools` ; Windows et macOS : application officielle).
2. Générer la paire de clés WireGuard **sur son poste** :
   - Linux / macOS : `wg genkey | tee wg-arpagona.key | wg pubkey > wg-arpagona.pub` (garder `wg-arpagona.key` privé).
   - Application Windows ou macOS : « Ajouter un tunnel vide » ; la clé publique s'affiche.
3. Générer une clé SSH si besoin : `ssh-keygen -t ed25519 -f ~/.ssh/arpagona_banc`.
4. Envoyer à l'administrateur les deux clés **publiques** : WireGuard (une ligne de 44 caractères) et SSH (`~/.ssh/arpagona_banc.pub`).
5. Importer la configuration reçue, y coller sa clé privée WireGuard, activer le tunnel.
6. Vérifier :
   - Mission Control : http://10.68.100.1:8700 (identifiants transmis par canal privé).
   - SSH : `ssh -i ~/.ssh/arpagona_banc <login>@10.68.100.1`.

Le tunnel ne route que l'adresse 10.68.100.1 : le reste du trafic du poste ne passe pas par le banc.

## Côté administrateur (sur la VM, en root)

```sh
S=/opt/arpagona/current/deploy/atlas/acces-wireguard.sh
bash $S install <ip-publique>                       # une fois ; rejouable
bash $S add-peer mael 10.68.100.2 '<clé publique wg>'
bash $S add-ssh-user mael 10.68.100.2 '<clé publique ssh>'
bash $S status
bash $S remove-peer mael ; bash $S remove-ssh-user mael   # révocation immédiate
bash $S uninstall                                         # coupe le tunnel
```

Sur la box (et le routeur intermédiaire s'il y a double NAT) : rediriger UDP 51820 vers 192.168.68.240.

Cartes de démonstration (fictives, sans affectation) : `bash /opt/arpagona/current/deploy/atlas/demo-kanban.sh`.

Compte Mission Control : `python3 -m arpagona_api.manage add-user|set-password|del-user <login> --password-stdin`, en tant que `arpagona-api`, avec `ARPAGONA_DB=/var/lib/arpagona-api/arpagona.db`.

## Preuves (22/11/2026, pair d'essai isolé dans un espace réseau dédié)

- Via le tunnel : Mission Control 200, SSH ouvert, ping VM OK.
- Fermés via le tunnel : Hermès 8642, passerelle Kanban 8701, Hindsight 18897, PostgreSQL 5432, ancienne console 8765.
- Injoignables via le tunnel : Atlas (8006, 22, ping), routeur, poste Ryzen.
- Compte SSH d'essai : pas de sudo, journaux lisibles ; secrets (`.env` Hermès, jetons API et Kanban, clé SSH `agentcore`, base) illisibles ; redirection de port refusée ; même clé refusée depuis le LAN.
- Pair et compte d'essai supprimés après le test.

## Limites

- Les journaux système lisibles contiennent les traces des services du banc (conversations de test incluses).
- Le code de `/opt/arpagona` est lisible (c'est le dépôt).
- IP publique du foyer possiblement dynamique : si elle change, mettre à jour `Endpoint` chez le contributeur.
- Pas de HTTPS : acceptable dans le tunnel, obligatoire avant tout client.
