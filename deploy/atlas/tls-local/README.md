# HTTPS local — banc Agent Core

Décision Thibaud 27/11 : autorité locale maintenant, sans domaine public ni exposition Internet.

## Topologie
- Ports réseau existants : Atlas `https://192.168.68.240:8700/` (LAN) et `https://10.68.100.1:8700/` (WireGuard).
- Pont personnel GONA `https://10.68.100.1:8710/` seulement pour le pair Thibaud `.3`.
- Même pare-feu, aucun port additionnel. L'API écoute désormais uniquement `127.0.0.1:8700`, derrière nginx autonome. Le nginx système n'est jamais démarré (pas de port 80).
- Une requête HTTP initiale aux anciens ports est redirigée vers HTTPS par nginx (code interne 497 → 308). Ne jamais saisir un mot de passe avant d'avoir validé HTTPS.
- SSE sans buffering, délai lecture 900 s ; pièces jointes GONA conservées. Cookies marqués Secure/HttpOnly/SameSite=Strict à la frontière.
- Certificat signé par CA privée ARPAGONA, SAN IP du LAN/WireGuard et localhost, validité serveur 397 jours. Clés 0600, répertoire 0700. Ne distribuer QUE ca.crt, jamais ca.key/server.key.

## Installation (après PR/CI/merge)
`sudo bash /opt/arpagona/current/deploy/atlas/tls-local/install.sh`
Sauvegarde privée horodatée dans `/var/backups/arpagona-tls/` ; en cas d'erreur de bascule, rollback automatique. L'installateur refuse un drop-in TLS préexistant : pas de réécriture silencieuse.

## Clients — installation de confiance indispensable
- Le certificat public `/etc/arpagona-tls/ca.crt` doit être ajouté à la confiance sur chaque appareil. `curl --cacert ca.crt` prouve la chaîne, pas la confiance du navigateur.
- Linux : administrateur, copie dans `/usr/local/share/ca-certificates/arpagona-local.crt`, puis `update-ca-certificates`. Chrome peut nécessiter import dans son gestionnaire de certificats et relance.
- Android : installer le certificat CA via Paramètres / Sécurité / identifiants ; le WebView doit explicitement accepter les autorités utilisateur ou embarquer le certificat public pour ce seul hôte. Ne jamais ajouter `onReceivedSslError.proceed()`.
- Tant que la confiance client n'est pas vérifiée, ne pas annoncer le parcours téléphone/iMac validé. Aucun contournement d'erreur TLS.
- Les accès SSH loopback existants sont chiffrés par SSH ; ils ne prouvent pas l'affichage sur les appareils.

## Contrôles
`openssl verify -CAfile ca.crt server.crt` ; SAN IPv4 LAN et WireGuard ; permissions clés.
`curl --cacert ca.crt https://192.168.68.240:8700/api/health` → 200 ; `/api/me` sans session → 401.
`curl -I http://192.168.68.240:8700/` → 308 HTTPS.
Connexion avec compte synthétique → cookie Secure ; aucune écoute API sur `0.0.0.0` ; pas de port80 ; pont GONA fonctionnel via TLS depuis le pair autorisé.

## Retour arrière
`sudo bash /opt/arpagona/current/deploy/atlas/tls-local/rollback.sh /var/backups/arpagona-tls/<horodatage>`
Arrête/désactive le proxy, retire son unité/drop-in, redémarre l'API dans son ancien mode, restaure état enabled/active du relais. CA et sauvegardes sont conservées. Retour HTTP = repli temporaire privé, pas conformité beta.
