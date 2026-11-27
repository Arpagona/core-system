# Agent Core Android — 0.11 TLS

Sources de l'enveloppe ARPAGONA, désormais versionnées dans le dépôt canonique. Aucun secret embarqué. La clé de signature reste hors dépôt (`~/.local/share/arpagona/android`).

- Même package et signature que 0.10 : mise à jour, pas nouvelle application.
- HTTPS uniquement, CA privée publique embarquée et limitée à deux IP du banc. Aucun contournement d'erreur de certificat ni confiance globale en toutes les autorités utilisateur.
- `bash build.sh` : Android SDK35, build-tools35, JDK17. Toute erreur javac arrête la compilation.
- Ressources/manifest : tests `tests/dev/test_android_tls.py`.
- Le certificat est celui du banc local, pas une configuration distribuable à des clients de production. Une rotation de CA nécessite une nouvelle version.
- Build signé et vérifié ne prouve pas le parcours sur le téléphone physique. Pièces jointes : DownloadManager est un service système ; sa confiance TLS doit être vérifiée séparément du WebView. Ne jamais corriger ce problème par un bypass TLS.
