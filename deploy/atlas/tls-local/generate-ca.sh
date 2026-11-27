#!/usr/bin/env bash
# Créer une CA et un certificat sans jamais écraser une identité existante.
set -euo pipefail
umask 077
[ "$#" -eq 1 ] || { echo "usage: $0 REPERTOIRE_INEXISTANT" >&2; exit 2; }
dir=$1
mkdir -m 700 -- "$dir" || { echo 'Répertoire déjà existant ou inaccessible ; arrêt.' >&2; exit 1; }
openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$dir/ca.key"
openssl req -x509 -new -sha256 -key "$dir/ca.key" -days 3650 -subj '/CN=ARPAGONA Local Root CA' -addext 'basicConstraints=critical,CA:TRUE,pathlen:0' -addext 'keyUsage=critical,keyCertSign,cRLSign' -out "$dir/ca.crt"
openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$dir/server.key"
openssl req -new -key "$dir/server.key" -subj '/CN=ARPAGONA local' -out "$dir/server.csr"
printf '%s\n' 'basicConstraints=critical,CA:FALSE' 'keyUsage=critical,digitalSignature' 'extendedKeyUsage=serverAuth' 'subjectAltName=IP:192.168.68.240,IP:10.68.100.1,IP:127.0.0.1,DNS:localhost' > "$dir/server.ext"
openssl x509 -req -in "$dir/server.csr" -CA "$dir/ca.crt" -CAkey "$dir/ca.key" -CAcreateserial -days 397 -sha256 -extfile "$dir/server.ext" -out "$dir/server.crt"
rm -- "$dir/server.csr" "$dir/server.ext" "$dir/ca.srl"
chmod 600 "$dir/ca.key" "$dir/server.key"
chmod 644 "$dir/ca.crt" "$dir/server.crt"
printf 'CA et certificat créés dans %s ; sauvegarder ca.key hors ligne, ne distribuer que ca.crt.\n' "$dir"
