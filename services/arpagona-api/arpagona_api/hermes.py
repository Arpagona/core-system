"""Client minimal du serveur API d'Hermès Agent (routes /v1/runs), en boucle locale."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Iterator

TERMINAL = {"completed", "failed", "cancelled"}


class HermesError(Exception):
    pass


class HermesClient:
    def __init__(self, base_url: str, api_key: str, timeout_s: float = 30.0, stream_timeout_s: float = 600.0):
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._timeout = timeout_s
        self._stream_timeout = stream_timeout_s

    def _request(self, method: str, path: str, body: dict | None = None, headers: dict | None = None,
                 timeout: float | None = None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self._base + path, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self._key}")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        for name, value in (headers or {}).items():
            req.add_header(name, value)
        try:
            return urllib.request.urlopen(req, timeout=timeout or self._timeout)
        except urllib.error.HTTPError as exc:
            raise HermesError(f"moteur : HTTP {exc.code}") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise HermesError("moteur injoignable") from exc

    def start_run(self, text: str, session_id: str, idempotency_key: str, instructions: str | None = None) -> str:
        body = {"input": text, "session_id": session_id}
        if instructions:
            body["instructions"] = instructions
        with self._request("POST", "/v1/runs", body, {"Idempotency-Key": idempotency_key}) as resp:
            return json.loads(resp.read())["run_id"]

    def run_status(self, run_id: str) -> dict:
        with self._request("GET", f"/v1/runs/{run_id}") as resp:
            return json.loads(resp.read())

    def events(self, run_id: str) -> Iterator[dict]:
        """Événements SSE d'une exécution, jusqu'à la fermeture du flux par le moteur."""
        try:
            with self._request("GET", f"/v1/runs/{run_id}/events", timeout=self._stream_timeout) as resp:
                for raw in resp:
                    line = raw.decode("utf-8", "replace").rstrip("\r\n")
                    if line.startswith("data:"):
                        try:
                            yield json.loads(line[5:].strip())
                        except json.JSONDecodeError:
                            continue
        except OSError as exc:
            raise HermesError("flux du moteur interrompu") from exc
