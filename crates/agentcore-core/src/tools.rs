//! Outils intégrés v0.1 (C-04) : list_dir, read_file, write_file, finish.

use crate::policy::{resolve, Access};
use agentcore_types::{Effect, Tool, ToolContext, ToolErrorKind, ToolOutcome, ToolSpec};
use serde_json::{json, Value};
use std::fs;
use std::io::Write;

pub const MAX_READ: usize = 256 * 1024;
pub const MAX_WRITE: usize = 1024 * 1024;
const MAX_ENTRIES: usize = 500;

fn err(kind: ToolErrorKind, message: impl Into<String>) -> ToolOutcome {
    ToolOutcome::Err {
        kind,
        message: message.into(),
    }
}

fn path_arg(args: &Value) -> Result<&str, ToolOutcome> {
    args.get("path").and_then(Value::as_str).ok_or_else(|| {
        err(
            ToolErrorKind::InvalidArguments,
            "argument « path » (texte) requis",
        )
    })
}

pub struct ListDir;
impl Tool for ListDir {
    fn spec(&self) -> ToolSpec {
        ToolSpec {
            name: "list_dir".into(),
            description: "Liste le contenu d'un dossier d'entrée (chemin absolu fourni dans la mission) ou du workspace (chemin relatif, « . » pour la racine).".into(),
            parameters: json!({"type":"object","properties":{"path":{"type":"string"}},"required":["path"],"additionalProperties":false}),
            effect: Effect::ReadOnly,
        }
    }
    fn execute(&self, args: &Value, ctx: &ToolContext) -> ToolOutcome {
        let raw = match path_arg(args) {
            Ok(p) => p,
            Err(e) => return e,
        };
        let p = match resolve(raw, Access::Read, &ctx.input_dirs, &ctx.workspace) {
            Ok(p) => p,
            Err(m) => return err(ToolErrorKind::Denied, m),
        };
        let rd = match fs::read_dir(&p) {
            Ok(r) => r,
            Err(e) => return err(ToolErrorKind::Io, e.to_string()),
        };
        let mut entries = Vec::new();
        for e in rd.flatten() {
            let Ok(meta) = e.metadata() else { continue };
            entries.push(json!({
                "name": e.file_name().to_string_lossy(),
                "path": p.join(e.file_name()).to_string_lossy(),
                "kind": if meta.is_dir() { "dir" } else { "file" },
                "bytes": meta.len(),
            }));
        }
        entries.sort_by(|a, b| a["name"].as_str().cmp(&b["name"].as_str()));
        let truncated = entries.len() > MAX_ENTRIES;
        entries.truncate(MAX_ENTRIES);
        ToolOutcome::Ok {
            output: json!({"path": p.to_string_lossy(), "entries": entries, "truncated": truncated}),
        }
    }
}

pub struct ReadFile;
impl Tool for ReadFile {
    fn spec(&self) -> ToolSpec {
        ToolSpec {
            name: "read_file".into(),
            description: format!(
                "Lit un fichier texte UTF-8 (au plus {} Kio, tronqué au-delà).",
                MAX_READ / 1024
            ),
            parameters: json!({"type":"object","properties":{"path":{"type":"string"}},"required":["path"],"additionalProperties":false}),
            effect: Effect::ReadOnly,
        }
    }
    fn execute(&self, args: &Value, ctx: &ToolContext) -> ToolOutcome {
        let raw = match path_arg(args) {
            Ok(p) => p,
            Err(e) => return e,
        };
        let p = match resolve(raw, Access::Read, &ctx.input_dirs, &ctx.workspace) {
            Ok(p) => p,
            Err(m) => return err(ToolErrorKind::Denied, m),
        };
        if !p.is_file() {
            return err(ToolErrorKind::NotFound, format!("pas un fichier : {raw}"));
        }
        let bytes = match fs::read(&p) {
            Ok(b) => b,
            Err(e) => return err(ToolErrorKind::Io, e.to_string()),
        };
        let total = bytes.len();
        let mut cut = total.min(MAX_READ);
        while cut > 0 && cut < total && std::str::from_utf8(&bytes[..cut]).is_err() {
            cut -= 1;
        }
        match std::str::from_utf8(&bytes[..cut]) {
            Ok(text) => ToolOutcome::Ok {
                output: json!({"path": p.to_string_lossy(), "bytes": total, "truncated": cut < total, "content": text}),
            },
            Err(_) => err(ToolErrorKind::InvalidArguments, "fichier non UTF-8"),
        }
    }
}

pub struct WriteFile;
impl Tool for WriteFile {
    fn spec(&self) -> ToolSpec {
        ToolSpec {
            name: "write_file".into(),
            description: format!("Écrit (ou remplace) un fichier texte dans le workspace, chemin relatif. Au plus {} Kio.", MAX_WRITE / 1024),
            parameters: json!({"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"],"additionalProperties":false}),
            effect: Effect::WorkspaceWrite,
        }
    }
    fn execute(&self, args: &Value, ctx: &ToolContext) -> ToolOutcome {
        let raw = match path_arg(args) {
            Ok(p) => p,
            Err(e) => return e,
        };
        let Some(content) = args.get("content").and_then(Value::as_str) else {
            return err(
                ToolErrorKind::InvalidArguments,
                "argument « content » (texte) requis",
            );
        };
        if content.len() > MAX_WRITE {
            return err(
                ToolErrorKind::TooLarge,
                format!("contenu > {} octets", MAX_WRITE),
            );
        }
        // Contrôle refait au moment de l'effet.
        let p = match resolve(raw, Access::Write, &ctx.input_dirs, &ctx.workspace) {
            Ok(p) => p,
            Err(m) => return err(ToolErrorKind::Denied, m),
        };
        let Some(parent) = p.parent() else {
            return err(ToolErrorKind::InvalidArguments, "chemin sans parent");
        };
        if let Err(e) = fs::create_dir_all(parent) {
            return err(ToolErrorKind::Io, e.to_string());
        }
        // Écriture atomique : fichier temporaire exclusif puis renommage (ne suit pas les liens).
        let tmp = parent.join(format!(".agentcore-tmp-{}", std::process::id()));
        let res = (|| -> std::io::Result<()> {
            let _ = fs::remove_file(&tmp);
            let mut f = fs::OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(&tmp)?;
            f.write_all(content.as_bytes())?;
            f.sync_all()?;
            fs::rename(&tmp, &p)?;
            fs::File::open(parent)?.sync_all()
        })();
        match res {
            Ok(()) => ToolOutcome::Ok {
                output: json!({"path": p.to_string_lossy(), "bytes": content.len()}),
            },
            Err(e) => {
                let _ = fs::remove_file(&tmp);
                err(ToolErrorKind::Io, e.to_string())
            }
        }
    }
}

/// Pseudo-outil de fin : le noyau vérifie le livrable avant de conclure.
pub struct Finish;
impl Tool for Finish {
    fn spec(&self) -> ToolSpec {
        ToolSpec {
            name: "finish".into(),
            description:
                "Déclare la mission terminée. À appeler seul, après avoir écrit le livrable.".into(),
            parameters: json!({"type":"object","properties":{"deliverable":{"type":"string","description":"chemin relatif du livrable dans le workspace"},"summary":{"type":"string","description":"compte rendu bref et factuel"}},"required":["deliverable","summary"],"additionalProperties":false}),
            effect: Effect::ReadOnly,
        }
    }
    fn execute(&self, args: &Value, _ctx: &ToolContext) -> ToolOutcome {
        match (
            args.get("deliverable").and_then(Value::as_str),
            args.get("summary").and_then(Value::as_str),
        ) {
            (Some(d), Some(s)) => ToolOutcome::Ok {
                output: json!({"deliverable": d, "summary": s}),
            },
            _ => err(
                ToolErrorKind::InvalidArguments,
                "« deliverable » et « summary » requis",
            ),
        }
    }
}

pub fn registry() -> Vec<Box<dyn Tool>> {
    vec![
        Box::new(ListDir),
        Box::new(ReadFile),
        Box::new(WriteFile),
        Box::new(Finish),
    ]
}
