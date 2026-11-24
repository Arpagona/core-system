import hashlib
import http.client
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import gate


class Upstream:
    def __init__(self):
        self.seen = []
        up = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                return

            def _all(self):
                n = int(self.headers.get("Content-Length") or 0)
                up.seen.append((self.command, self.path, self.headers.get("Authorization"), self.rfile.read(n)))
                body = json.dumps({"ok": True}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            do_GET = do_POST = do_PUT = do_DELETE = _all

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"


def start_gate(upstream_url, name, bank, token, team_bank=None):
    tenant = gate.Tenant(name, bank, hashlib.sha256(token.encode()).hexdigest(), team_bank)
    server = ThreadingHTTPServer(("127.0.0.1", 0), gate.make_handler(tenant, upstream_url, "cle-amont"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def call(server, method, path, token, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    conn.request(method, path, json.dumps(body) if body is not None else None, headers)
    status = conn.getresponse().status
    conn.close()
    return status


class GateTest(unittest.TestCase):
    def setUp(self):
        self.up = Upstream()
        self.mael = start_gate(self.up.url, "mael", "arpagona-mael", "jeton-mael")
        self.thibaud = start_gate(self.up.url, "thibaud", "arpagona-thibaud", "jeton-thibaud")

    def tearDown(self):
        for s in (self.mael, self.thibaud, self.up.server):
            s.shutdown()
            s.server_close()

    def test_sa_banque_passe_avec_la_cle_amont(self):
        self.assertEqual(call(self.mael, "POST", "/v1/default/banks/arpagona-mael/memories", "jeton-mael", {"items": []}), 200)
        method, path, auth, _ = self.up.seen[-1]
        self.assertEqual(auth, "Bearer cle-amont")  # la clé de l'utilisateur ne va jamais en amont, ni l'inverse
        self.assertEqual(path, "/v1/default/banks/arpagona-mael/memories")

    def test_banque_de_l_autre_refusee(self):
        before = len(self.up.seen)
        for path in ("/v1/default/banks/arpagona-thibaud/memories/recall",
                     "/v1/default/banks/arpagona-thibaud",
                     "/v1/default/banks/arpagona-mael-bis/memories",
                     "/v1/default/banks",
                     "/v1/default/banks/arpagona-mael/../arpagona-thibaud/memories",
                     "/v1/default/banks/arpagona-mael/%2e%2e/arpagona-thibaud/memories",
                     "/v1/default/banks//arpagona-thibaud/memories",
                     "/v1/default/banks/arpagona-mael%2f..%2farpagona-thibaud"):
            self.assertEqual(call(self.mael, "POST", path, "jeton-mael", {}), 403, path)
        self.assertEqual(len(self.up.seen), before)

    def test_jeton_de_l_autre_refuse(self):
        self.assertEqual(call(self.mael, "GET", "/v1/default/banks/arpagona-mael/stats", "jeton-thibaud"), 401)
        self.assertEqual(call(self.mael, "GET", "/v1/default/banks/arpagona-mael/stats", None), 401)
        self.assertEqual(call(self.thibaud, "GET", "/v1/default/banks/arpagona-mael/stats", "jeton-mael"), 401)
        self.assertEqual(self.up.seen, [])

    def test_banque_invalide_refusee_a_la_creation(self):
        with self.assertRaises(ValueError):
            gate.Tenant("x", "../autre", "00")

    def test_sante_sans_banque(self):
        self.assertEqual(call(self.mael, "GET", "/health", "jeton-mael"), 200)


TEAM = "arpagona-equipe"


class TeamZoneTest(unittest.TestCase):
    """Zone commune : banque d'équipe lisible et alimentable par les deux, banques personnelles toujours séparées."""

    def setUp(self):
        self.up = Upstream()
        self.mael = start_gate(self.up.url, "mael", "arpagona-mael", "jeton-mael", TEAM)
        self.thibaud = start_gate(self.up.url, "thibaud", "arpagona-thibaud", "jeton-thibaud", TEAM)

    def tearDown(self):
        for s in (self.mael, self.thibaud, self.up.server):
            s.shutdown()
            s.server_close()

    def retain(self, server, token, content, **extra):
        item = {"content": content, **extra}
        return call(server, "POST", f"/v1/default/banks/{TEAM}/memories", token, {"items": [item]})

    def test_les_deux_lisent_et_ecrivent_dans_l_equipe(self):
        self.assertEqual(self.retain(self.mael, "jeton-mael", "Le client Dupont préfère les devis sous 48 h."), 200)
        self.assertEqual(call(self.thibaud, "POST", f"/v1/default/banks/{TEAM}/memories/recall", "jeton-thibaud",
                              {"query": "Dupont"}), 200)
        self.assertEqual(self.retain(self.thibaud, "jeton-thibaud", "Dupont a signé le devis 2026-041."), 200)
        self.assertEqual(call(self.mael, "GET", f"/v1/default/banks/{TEAM}/stats", "jeton-mael"), 200)

    def test_auteur_impose_par_le_portier(self):
        # Maël tente de se faire passer pour Thibaud : la balise et les métadonnées sont écrasées.
        self.retain(self.mael, "jeton-mael", "Fait métier fictif.", tags=["auteur:thibaud", "client:dupont"],
                    metadata={"auteur": "thibaud", "source": "réunion du 24/11"})
        item = json.loads(self.up.seen[-1][3])["items"][0]
        self.assertEqual(sorted(item["tags"]), ["auteur:mael", "client:dupont", "zone:equipe"])
        self.assertEqual(item["metadata"]["auteur"], "mael")
        self.assertEqual(item["metadata"]["source"], "réunion du 24/11")  # la source déclarée est conservée
        self.retain(self.thibaud, "jeton-thibaud", "Autre fait.")
        item = json.loads(self.up.seen[-1][3])["items"][0]
        self.assertEqual(item["metadata"]["source"], "agent:thibaud")

    def test_equipe_ni_suppression_ni_configuration(self):
        before = len(self.up.seen)
        for method, path in (("DELETE", f"/v1/default/banks/{TEAM}"), ("DELETE", f"/v1/default/banks/{TEAM}/memories"),
                             ("PUT", f"/v1/default/banks/{TEAM}"), ("PATCH", f"/v1/default/banks/{TEAM}/config"),
                             ("POST", f"/v1/default/banks/{TEAM}/reflect"),
                             ("DELETE", f"/v1/default/banks/{TEAM}/documents/x")):
            self.assertEqual(call(self.mael, method, path, "jeton-mael", {}), 403, f"{method} {path}")
        self.assertEqual(len(self.up.seen), before)

    def test_ni_mail_entier_ni_secret_dans_l_equipe(self):
        before = len(self.up.seen)
        mail = "From: a@b.invalid\nTo: c@d.invalid\nSubject: devis\n\nBonjour"
        self.assertEqual(self.retain(self.mael, "jeton-mael", mail), 422)
        self.assertEqual(self.retain(self.mael, "jeton-mael", "mot de passe du client : abc"), 422)
        self.assertEqual(self.retain(self.mael, "jeton-mael", "clé API sk-abcdef123456"), 422)
        self.assertEqual(self.retain(self.mael, "jeton-mael", "x" * 2500), 422)
        self.assertEqual(self.retain(self.mael, "jeton-mael", ""), 422)
        self.assertEqual(call(self.mael, "POST", f"/v1/default/banks/{TEAM}/memories", "jeton-mael", {"items": []}), 422)
        self.assertEqual(len(self.up.seen), before)

    def test_banque_personnelle_de_l_autre_toujours_refusee(self):
        self.assertEqual(call(self.mael, "POST", "/v1/default/banks/arpagona-thibaud/memories/recall", "jeton-mael", {}), 403)
        self.assertEqual(call(self.mael, "GET", "/v1/default/banks", "jeton-mael"), 403)
        self.assertEqual(call(self.mael, "POST", f"/v1/default/banks/{TEAM}/../arpagona-thibaud/memories", "jeton-mael", {}), 403)
        self.assertEqual(call(self.thibaud, "GET", f"/v1/default/banks/{TEAM}/stats", "jeton-mael"), 401)

    def test_banque_personnelle_garde_tous_ses_droits(self):
        self.assertEqual(call(self.mael, "DELETE", "/v1/default/banks/arpagona-mael/documents/x", "jeton-mael", {}), 200)
        # Le dépôt personnel n'est ni filtré ni balisé : mails et préférences y restent possibles.
        call(self.mael, "POST", "/v1/default/banks/arpagona-mael/memories", "jeton-mael",
             {"items": [{"content": "From: a@b.invalid\nTo: c@d.invalid\nmot de passe"}]})
        self.assertNotIn("zone:equipe", self.up.seen[-1][3].decode())

    def test_banque_equipe_distincte_des_banques_personnelles(self):
        with self.assertRaises(ValueError):
            gate.Tenant("x", TEAM, "00", TEAM)


if __name__ == "__main__":
    unittest.main()
