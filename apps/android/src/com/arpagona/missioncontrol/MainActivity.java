package com.arpagona.missioncontrol;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.view.WindowInsets;
import android.Manifest;
import android.content.pm.PackageManager;
import android.media.MediaRecorder;
import android.util.Base64;
import android.webkit.JavascriptInterface;
import android.webkit.CookieManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;

/**
 * Enveloppe Mission Control : deux environnements derrière le même tunnel WireGuard.
 *  - Atlas : banc de test ARPAGONA (port 8700), où se fait la connexion (session de 90 jours).
 *  - GONA  : Mission Control personnel du Ryzen (port 8710), ouvert par la même session via le pont signé.
 * Même hôte, donc mêmes cookies : une seule connexion, aucune reconnexion à la bascule.
 */
public class MainActivity extends Activity {
    static final String HOTE = "https://10.68.100.1";
    static final String[] URLS = { HOTE + ":8700/", HOTE + ":8710/" };
    static final String[] NOMS = { "Atlas", "GONA" };
    static final int ATLAS = 0, GONA = 1;

    private WebView web;
    private SharedPreferences prefs;
    private int env = ATLAS;
    private final java.util.Set<Long> apkAttendus = java.util.Collections.synchronizedSet(new java.util.HashSet<Long>());

    /** Fin de téléchargement d'un APK demandé par l'appli : ouvre directement l'installateur (comme Telegram). */
    private final android.content.BroadcastReceiver finTelechargement = new android.content.BroadcastReceiver() {
        @Override
        public void onReceive(android.content.Context c, Intent i) {
            long id = i.getLongExtra(android.app.DownloadManager.EXTRA_DOWNLOAD_ID, -1);
            if (!apkAttendus.remove(id)) return;
            try {
                android.app.DownloadManager dm = (android.app.DownloadManager) getSystemService(DOWNLOAD_SERVICE);
                android.database.Cursor q = dm.query(new android.app.DownloadManager.Query().setFilterById(id));
                boolean ok = q.moveToFirst() && q.getInt(q.getColumnIndexOrThrow(android.app.DownloadManager.COLUMN_STATUS)) == android.app.DownloadManager.STATUS_SUCCESSFUL;
                q.close();
                Uri u = dm.getUriForDownloadedFile(id);
                if (!ok || u == null) return;
                Intent v = new Intent(Intent.ACTION_VIEW);
                v.setDataAndType(u, "application/vnd.android.package-archive");
                v.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(v);
            } catch (Exception e) {
                android.widget.Toast.makeText(MainActivity.this, "Ouvre le fichier dans Téléchargements pour l'installer", android.widget.Toast.LENGTH_LONG).show();
            }
        }
    };
    private android.webkit.ValueCallback<Uri[]> choixFichier;

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req != 7 || choixFichier == null) return;
        Uri[] r = (res == RESULT_OK && data != null && data.getData() != null) ? new Uri[] { data.getData() } : null;
        choixFichier.onReceiveValue(r);
        choixFichier = null;
    }

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(Color.BLACK);
        getWindow().setNavigationBarColor(Color.BLACK);
        getWindow().getDecorView().setSystemUiVisibility(0);
        prefs = getSharedPreferences("mission-control", MODE_PRIVATE);
        env = prefs.getInt("env", ATLAS) == GONA ? GONA : ATLAS;

        web = new WebView(this);
        web.setBackgroundColor(Color.parseColor("#0f172a"));
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(true);   // lecture des fichiers choisis par l'utilisateur (content://)
        s.setMediaPlaybackRequiresUserGesture(false);   // réponses vocales de GONA
        web.addJavascriptInterface(new Micro(), "AndroidMic");
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED)
            requestPermissions(new String[] { Manifest.permission.RECORD_AUDIO }, 1);
        CookieManager.getInstance().setAcceptCookie(true);
        android.content.IntentFilter fin = new android.content.IntentFilter(android.app.DownloadManager.ACTION_DOWNLOAD_COMPLETE);
        if (android.os.Build.VERSION.SDK_INT >= 33) registerReceiver(finTelechargement, fin, RECEIVER_EXPORTED);
        else registerReceiver(finTelechargement, fin);
        // Fichiers envoyés par l'agent (APK, PDF, ZIP…) : téléchargement Android avec la session de l'appli.
        web.setDownloadListener((url, ua, disp, mime, len) -> {
            try {
                android.app.DownloadManager.Request r = new android.app.DownloadManager.Request(Uri.parse(url));
                r.addRequestHeader("Cookie", CookieManager.getInstance().getCookie(url));
                r.addRequestHeader("X-Gona", "1");
                r.addRequestHeader("X-Arpagona", "1");
                String nom = android.webkit.URLUtil.guessFileName(url, disp, mime);
                r.setTitle(nom);
                r.setMimeType(mime);
                r.setNotificationVisibility(android.app.DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                r.setDestinationInExternalPublicDir(android.os.Environment.DIRECTORY_DOWNLOADS, nom);
                long id = ((android.app.DownloadManager) getSystemService(DOWNLOAD_SERVICE)).enqueue(r);
                if (nom.toLowerCase().endsWith(".apk")) apkAttendus.add(id);
                android.widget.Toast.makeText(this, "Téléchargement : " + nom, android.widget.Toast.LENGTH_SHORT).show();
            } catch (Exception e) {
                android.widget.Toast.makeText(this, "Téléchargement impossible", android.widget.Toast.LENGTH_LONG).show();
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            // Bouton 📎 : sélecteur de fichiers Android (galerie, documents), sans permission particulière.
            @Override
            public boolean onShowFileChooser(WebView v, android.webkit.ValueCallback<Uri[]> cb, FileChooserParams p) {
                if (choixFichier != null) choixFichier.onReceiveValue(null);
                choixFichier = cb;
                try {
                    Intent i = new Intent(Intent.ACTION_GET_CONTENT);
                    i.addCategory(Intent.CATEGORY_OPENABLE);
                    i.setType("*/*");
                    i.putExtra(Intent.EXTRA_MIME_TYPES, new String[] { "image/*", "application/pdf", "text/*", "application/json" });
                    startActivityForResult(Intent.createChooser(i, "Joindre un fichier"), 7);
                } catch (Exception e) {
                    choixFichier = null;
                    cb.onReceiveValue(null);
                    return false;
                }
                return true;
            }
        });
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                Uri u = req.getUrl();
                if ("arpagona".equals(u.getScheme())) {
                    if ("basculer".equals(u.getHost())) basculer(); else ouvrir();
                    return true;
                }
                // Les deux environnements restent dans l'appli ; le lien « ⇄ » de la page ne recharge pas deux fois.
                for (int i = 0; i < URLS.length; i++) {
                    if (URLS[i].startsWith(u.getScheme() + "://" + u.getAuthority() + "/")) {
                        if (i != env) { choisir(i, true); return true; }
                        return false;
                    }
                }
                // Liens externes : ouverts dans le navigateur du téléphone, jamais dans l'appli.
                try { startActivity(new Intent(Intent.ACTION_VIEW, u)); } catch (Exception ignored) { }
                return true;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest req, WebResourceError err) {
                if (req.isForMainFrame()) view.loadDataWithBaseURL("arpagona://hors-ligne/", horsLigne(), "text/html", "utf-8", null);
            }
        });

        FrameLayout racine = new FrameLayout(this);
        racine.addView(web, new FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        racine.setBackgroundColor(Color.BLACK);
        racine.setOnApplyWindowInsetsListener((v, ins) -> {
            v.setPadding(ins.getSystemWindowInsetLeft(), ins.getSystemWindowInsetTop(),
                ins.getSystemWindowInsetRight(), ins.getSystemWindowInsetBottom());
            return ins;
        });
        setContentView(racine);
        racine.requestApplyInsets();
        if (state != null) web.restoreState(state); else ouvrir();
    }

    private void basculer() {
        choisir(1 - env, true);
    }

    private void choisir(int cible, boolean charger) {
        env = cible;
        prefs.edit().putInt("env", env).apply();
        if (charger) ouvrir();
    }

    /** Vérifie en 5 s que l'environnement répond (tunnel actif) avant de charger ; sinon page claire. */
    private void ouvrir() {
        final int cible = env;
        web.loadDataWithBaseURL(null, chargement(), "text/html", "utf-8", null);
        new Thread(() -> {
            boolean ok;
            final boolean[] code401 = { false };
            try {
                java.net.HttpURLConnection c = (java.net.HttpURLConnection) new java.net.URL(URLS[cible] + "api/me").openConnection();
                String ck = CookieManager.getInstance().getCookie(URLS[cible]);
                if (ck != null) c.setRequestProperty("Cookie", ck);
                c.setConnectTimeout(5000);
                c.setReadTimeout(5000);
                int code = c.getResponseCode();
                c.disconnect();
                // 200 = connecté, 401 = joignable mais pas connecté : dans les deux cas on affiche la page.
                ok = code == 200 || code == 401;
                code401[0] = code == 401;
            } catch (Exception e) {
                ok = false;
            }
            final boolean joignable = ok;
            runOnUiThread(() -> {
                if (cible != env) return; // l'utilisateur a rebasculé entre-temps
                if (joignable && cible == GONA && code401[0]) { choisir(ATLAS, true); return; }
                if (joignable) web.loadUrl(URLS[cible]);
                else web.loadDataWithBaseURL("arpagona://hors-ligne/", horsLigne(), "text/html", "utf-8", null);
            });
        }).start();
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        web.saveState(out);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        try { unregisterReceiver(finTelechargement); } catch (Exception ignored) { }
    }

    @Override
    protected void onPause() {
        super.onPause();
        CookieManager.getInstance().flush();
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack(); else super.onBackPressed();
    }

    /** Micro natif : le WebView en HTTP n'expose pas getUserMedia. Enregistre en AAC/MP4, rend le fichier en base64. */
    class Micro {
        private MediaRecorder rec;
        private java.io.File fichier;

        @JavascriptInterface
        public synchronized boolean start() {
            if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                runOnUiThread(() -> requestPermissions(new String[] { Manifest.permission.RECORD_AUDIO }, 1));
                return false;
            }
            try {
                liberer();
                fichier = java.io.File.createTempFile("voix", ".m4a", getCacheDir());
                rec = new MediaRecorder();
                rec.setAudioSource(MediaRecorder.AudioSource.MIC);
                rec.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4);
                rec.setAudioEncoder(MediaRecorder.AudioEncoder.AAC);
                rec.setAudioSamplingRate(16000);
                rec.setAudioEncodingBitRate(48000);
                rec.setOutputFile(fichier.getAbsolutePath());
                rec.prepare();
                rec.start();
                return true;
            } catch (Exception e) {
                liberer();
                return false;
            }
        }

        @JavascriptInterface
        public synchronized String stop() {
            try {
                if (rec == null) return "";
                try { rec.stop(); } catch (RuntimeException tropCourt) { return ""; }
                byte[] b = java.nio.file.Files.readAllBytes(fichier.toPath());
                return Base64.encodeToString(b, Base64.NO_WRAP);
            } catch (Exception e) {
                return "";
            } finally {
                liberer();
            }
        }

        private void liberer() {
            try { if (rec != null) rec.release(); } catch (Exception ignored) { }
            rec = null;
            if (fichier != null) { fichier.delete(); fichier = null; }
        }
    }

    private String horsLigne() {
        String autre = NOMS[1 - env];
        String aide = env == GONA
            ? "GONA est joignable seulement si le Ryzen est allumé et son tunnel actif. Vous pouvez revenir sur Atlas."
            : "Vérifiez que le tunnel WireGuard « Arpagona » est actif, puis réessayez.";
        return "<!doctype html><html lang='fr'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            + "<style>body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0f172a;color:#f3f5fc;"
            + "font-family:sans-serif;text-align:center;padding:24px;box-sizing:border-box}h1{font-size:22px}p{color:#b1bdd0;line-height:1.5}"
            + "a{display:inline-block;margin:16px 6px 0;padding:12px 20px;border-radius:10px;background:#4cd7f6;color:#0f172a;text-decoration:none;font-weight:bold}"
            + "a.s{background:#334155;color:#f3f5fc}</style></head>"
            + "<body><div><h1>" + NOMS[env] + " ne répond pas</h1><p>" + aide + "</p>"
            + "<a href='arpagona://reessayer'>Réessayer</a><a class='s' href='arpagona://basculer'>Aller sur " + autre + "</a></div></body></html>";
    }

    private String chargement() {
        return "<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'></head>"
            + "<body style='margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0f172a;color:#b1bdd0;font-family:sans-serif'>"
            + "Connexion à " + NOMS[env] + "…</body></html>";
    }
}
