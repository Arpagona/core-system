"""Plugin arpagona-equipe : la zone COMMUNE de l'entreprise, à destination explicite.

Deux outils de mémoire d'équipe (Hindsight, banque commune, via le portier) et trois outils de
dossiers clients (répertoire commun lisible et modifiable par les deux agents et les humains habilités).

Règles :
- L'écriture dans le commun n'a lieu que par ces outils : destination explicite. La mémoire
  automatique de l'agent reste dans SA banque personnelle (par défaut, en cas de doute : privé).
- Le portier impose l'auteur du fait et refuse mails entiers et secrets (voir services/hindsight-gate).
- Dossiers clients : chemins relatifs seulement, aucun « .. », aucun lien symbolique rencontré sur le
  chemin, aucune sortie de la racine ; fichiers créés en 0660 et dossiers en 2770 (groupe d'équipe).
"""
from __future__ import annotations

import json
import os
import re
import stat
import urllib.error
import urllib.request
from pathlib import Path

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,100}$")
MAX_FILE = 200 * 1024
MAX_LIST = 200


class EquipeError(Exception):
    pass


# --- dossiers clients --------------------------------------------------------
def _root() -> Path:
    raw = os.environ.get("ARPAGONA_CLIENTS_DIR", "").strip()
    if not raw:
        raise EquipeError("dossier clients non configuré (ARPAGONA_CLIENTS_DIR absent)")
    return Path(raw)


def safe_path(rel: str, *, must_exist: bool) -> Path:
    """Chemin sûr sous la racine : relatif, sans « .. », sans lien symbolique, sans nom étrange."""
    if not isinstance(rel, str) or "\x00" in rel or rel.startswith("/") or "\\" in rel:
        raise EquipeError("chemin invalide : relatif, sans « \\ »")
    parts = [p for p in rel.split("/") if p not in ("", ".")]
    for part in parts:
        if part == ".." or not NAME_RE.match(part) or part.startswith("."):
            raise EquipeError(f"nom de chemin refusé : {part!r}")
    root = _root()
    if root.is_symlink() or not root.is_dir():
        raise EquipeError("racine des dossiers clients invalide")
    current = root
    for part in parts:
        current = current / part
        try:
            mode = os.lstat(current).st_mode
        except FileNotFoundError:
            if must_exist:
                raise EquipeError("introuvable") from None
            continue
        if stat.S_ISLNK(mode):
            raise EquipeError("lien symbolique refusé")
    return current


def _ensure_dirs(path: Path) -> None:
    root = _root()
    missing = []
    probe = path
    while probe != root and not probe.exists():
        missing.append(probe)
        probe = probe.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o2770)
        os.chmod(directory, 0o2770)  # le masque du processus ne doit pas fermer le groupe


def clients_list(args: dict, **_kw) -> str:
    try:
        target = safe_path(str(args.get("chemin", "")), must_exist=True)
        if not target.is_dir():
            raise EquipeError("ce n'est pas un dossier")
        rows = []
        for entry in sorted(target.iterdir(), key=lambda p: p.name)[:MAX_LIST]:
            if entry.name.startswith(".") or entry.is_symlink():
                continue
            rows.append({"nom": entry.name, "type": "dossier" if entry.is_dir() else "fichier",
                         "taille": entry.stat().st_size if entry.is_file() else None})
        return json.dumps({"chemin": str(args.get("chemin", "")) or "/", "entrees": rows}, ensure_ascii=False)
    except (EquipeError, OSError) as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def clients_read(args: dict, **_kw) -> str:
    try:
        target = safe_path(str(args.get("chemin", "")), must_exist=True)
        fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise EquipeError("ce n'est pas un fichier")
            data = handle.read(MAX_FILE + 1)
        if len(data) > MAX_FILE:
            raise EquipeError("fichier trop grand")
        return json.dumps({"chemin": args.get("chemin"), "contenu": data.decode("utf-8", "replace")},
                          ensure_ascii=False)
    except (EquipeError, OSError) as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def clients_write(args: dict, **_kw) -> str:
    content = args.get("contenu")
    if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_FILE:
        return json.dumps({"error": "contenu invalide ou trop grand"})
    append = bool(args.get("ajouter", False))
    try:
        rel = str(args.get("chemin", ""))
        if not [p for p in rel.split("/") if p not in ("", ".")]:
            raise EquipeError("chemin de fichier requis")
        target = safe_path(rel, must_exist=False)
        _ensure_dirs(target.parent)
        if target.parent.is_symlink() or os.path.lexists(target) and target.is_symlink():
            raise EquipeError("lien symbolique refusé")
        flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | (os.O_APPEND if append else os.O_TRUNC)
        fd = os.open(target, flags, 0o660)
        with os.fdopen(fd, "wb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise EquipeError("ce n'est pas un fichier")
            st = os.fstat(handle.fileno())
            if stat.S_IMODE(st.st_mode) != 0o660 and st.st_uid == os.geteuid():
                # Fichier créé par ce compte : le masque du service ne doit pas fermer le groupe d'équipe.
                # Le fichier d'un collègue reste tel quel (groupe d'équipe + ACL par défaut du dossier).
                os.fchmod(handle.fileno(), 0o660)
            handle.write(content.encode("utf-8"))
        return json.dumps({"chemin": rel, "ecrit": len(content.encode("utf-8")), "mode": "ajout" if append else "remplacement"})
    except (EquipeError, OSError) as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


# --- mémoire d'équipe ------------------------------------------------------------
def _gate(path: str, body: dict) -> tuple[int, dict]:
    base = os.environ.get("ARPAGONA_TEAM_MEMORY_URL", "").rstrip("/")
    bank = os.environ.get("ARPAGONA_TEAM_BANK", "")
    token = os.environ.get("HINDSIGHT_API_KEY", "")
    if not (base and bank and token):
        raise EquipeError("mémoire d'équipe non configurée")
    req = urllib.request.Request(f"{base}/v1/default/banks/{bank}/{path}", data=json.dumps(body).encode(),
                                 method="POST", headers={"Content-Type": "application/json",
                                                         "Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read() or b"{}")
        except ValueError:
            detail = {}
        return exc.code, detail
    except (OSError, ValueError) as exc:
        raise EquipeError(f"mémoire d'équipe injoignable : {exc}") from exc


def team_remember(args: dict, **_kw) -> str:
    fact = str(args.get("fait", "")).strip()
    source = str(args.get("source", "")).strip()
    if not fact or not source:
        return json.dumps({"error": "« fait » et « source » sont obligatoires (d'où vient ce fait ?)"}, ensure_ascii=False)
    item = {"content": fact, "context": "fait métier d'équipe", "metadata": {"source": source[:300]}}
    if str(args.get("id", "")).strip():
        item["document_id"] = str(args["id"]).strip()[:120]
    try:
        status, result = _gate("memories", {"items": [item], "async": False})
    except EquipeError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)
    if status != 200:
        return json.dumps({"error": f"refusé par le portier (HTTP {status})", "detail": result.get("error", "")},
                          ensure_ascii=False)
    return json.dumps({"statut": "enregistré dans la mémoire d'équipe", "zone": "equipe"}, ensure_ascii=False)


def team_recall(args: dict, **_kw) -> str:
    query = str(args.get("requete", "")).strip()
    if not query:
        return json.dumps({"error": "« requete » obligatoire"}, ensure_ascii=False)
    try:
        status, result = _gate("memories/recall", {"query": query[:1000], "max_tokens": 2000,
                                                  "types": ["world", "experience"]})
    except EquipeError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)
    if status != 200:
        return json.dumps({"error": f"refusé par le portier (HTTP {status})"}, ensure_ascii=False)
    rows = []
    # Seuls les faits d'origine sont rendus : les « observations » (synthèses automatiques) perdent l'auteur et la source.
    for hit in [h for h in (result.get("results") or []) if h.get("type") != "observation"][:10]:
        meta = hit.get("metadata") or {}
        rows.append({"fait": hit.get("text", ""), "auteur": meta.get("auteur", ""), "source": meta.get("source", ""),
                     "tags": hit.get("tags", [])})
    return json.dumps({"zone": "equipe", "resultats": rows}, ensure_ascii=False)


SCHEMAS = {
    "arpagona_equipe_memoire_ecrire": {
        "name": "arpagona_equipe_memoire_ecrire",
        "description": ("Enregistre UN fait métier dans la mémoire d'ÉQUIPE (lue par tous les collègues). "
                        "Réservé aux faits d'entreprise : clients, projets, décisions. Jamais de mail entier, de secret, "
                        "de préférence ou de fait privé : ceux-là restent dans ta mémoire personnelle (par défaut). "
                        "L'auteur est ajouté automatiquement ; indique la source du fait."),
        "parameters": {"type": "object", "properties": {
            "fait": {"type": "string", "description": "Un fait métier court (une à trois phrases)"},
            "source": {"type": "string", "description": "D'où vient le fait (réunion, document, échange client…)"},
            "id": {"type": "string", "description": "Identifiant stable facultatif (mise à jour d'un même fait)"}},
            "required": ["fait", "source"]}},
    "arpagona_equipe_memoire_chercher": {
        "name": "arpagona_equipe_memoire_chercher",
        "description": "Cherche dans la mémoire d'ÉQUIPE (faits métier de toute l'entreprise, avec auteur et source).",
        "parameters": {"type": "object", "properties": {"requete": {"type": "string"}}, "required": ["requete"]}},
    "arpagona_clients_lister": {
        "name": "arpagona_clients_lister",
        "description": "Liste un dossier de l'espace COMMUN des dossiers clients (racine si « chemin » est vide).",
        "parameters": {"type": "object", "properties": {"chemin": {"type": "string"}}}},
    "arpagona_clients_lire": {
        "name": "arpagona_clients_lire",
        "description": "Lit un fichier de l'espace commun des dossiers clients (chemin relatif).",
        "parameters": {"type": "object", "properties": {"chemin": {"type": "string"}}, "required": ["chemin"]}},
    "arpagona_clients_ecrire": {
        "name": "arpagona_clients_ecrire",
        "description": ("Crée, remplace ou complète un fichier dans l'espace COMMUN des dossiers clients. "
                        "Visible et modifiable par tes collègues : n'y mets ni secret ni contenu privé."),
        "parameters": {"type": "object", "properties": {
            "chemin": {"type": "string", "description": "Ex. dupont/fiche.md"},
            "contenu": {"type": "string"},
            "ajouter": {"type": "boolean", "description": "true : ajoute à la fin au lieu de remplacer"}},
            "required": ["chemin", "contenu"]}},
}
HANDLERS = {"arpagona_equipe_memoire_ecrire": team_remember, "arpagona_equipe_memoire_chercher": team_recall,
            "arpagona_clients_lister": clients_list, "arpagona_clients_lire": clients_read,
            "arpagona_clients_ecrire": clients_write}


def register(ctx) -> None:
    for name, schema in SCHEMAS.items():
        ctx.register_tool(name=name, toolset="arpagona", schema=schema, handler=HANDLERS[name],
                          description=schema["description"][:120])
