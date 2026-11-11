//! Politique d'autorisation (C-05) et résolution des chemins, refaite au moment de l'effet.

use agentcore_types::{Decision, Effect, MissionSpec, Policy, ToolCall};
use std::path::{Component, Path, PathBuf};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Access {
    Read,
    Write,
}

/// Résout un chemin demandé par le modèle et vérifie qu'il reste dans le périmètre.
///
/// - chemin relatif : relatif au workspace ;
/// - aucun composant `..` accepté ;
/// - lecture : chemin canonique (liens résolus) sous un dossier d'entrée ou le workspace ;
/// - écriture : ancêtre existant canonique sous le workspace, cible non symbolique.
pub fn resolve(
    raw: &str,
    access: Access,
    input_dirs: &[PathBuf],
    workspace: &Path,
) -> Result<PathBuf, String> {
    if raw.is_empty() || raw.contains('\0') {
        return Err("chemin vide ou invalide".into());
    }
    let p = Path::new(raw);
    if p.components().any(|c| matches!(c, Component::ParentDir)) {
        return Err("composant « .. » interdit".into());
    }
    let joined = if p.is_absolute() {
        p.to_path_buf()
    } else {
        workspace.join(p)
    };
    let ws = workspace
        .canonicalize()
        .map_err(|e| format!("workspace inaccessible : {e}"))?;
    match access {
        Access::Read => {
            let c = joined
                .canonicalize()
                .map_err(|_| format!("introuvable : {raw}"))?;
            let mut roots = vec![ws];
            for d in input_dirs {
                if let Ok(cd) = d.canonicalize() {
                    roots.push(cd);
                }
            }
            if roots.iter().any(|r| c.starts_with(r)) {
                Ok(c)
            } else {
                Err(format!("lecture hors périmètre autorisé : {raw}"))
            }
        }
        Access::Write => {
            if !joined.starts_with(workspace) && !joined.starts_with(&ws) {
                return Err(format!("écriture hors workspace : {raw}"));
            }
            if let Ok(meta) = std::fs::symlink_metadata(&joined) {
                if meta.file_type().is_symlink() {
                    return Err("la cible est un lien symbolique".into());
                }
                if meta.is_dir() {
                    return Err("la cible est un dossier".into());
                }
            }
            // Ancêtre existant le plus proche, canonisé.
            let mut anc = joined.parent().map(Path::to_path_buf);
            while let Some(a) = anc.clone() {
                if a.exists() {
                    break;
                }
                anc = a.parent().map(Path::to_path_buf);
            }
            let anc = anc.ok_or("aucun ancêtre existant")?;
            let canc = anc
                .canonicalize()
                .map_err(|e| format!("ancêtre inaccessible : {e}"))?;
            if !canc.starts_with(&ws) {
                return Err(format!("écriture hors workspace (lien sortant) : {raw}"));
            }
            let rest = joined
                .strip_prefix(&anc)
                .map_err(|_| "chemin incohérent".to_string())?;
            Ok(canc.join(rest))
        }
    }
}

/// Politique v0.1 : refus par défaut, outils de la mission uniquement, chemins bornés.
pub struct DefaultPolicy;

impl Policy for DefaultPolicy {
    fn decide(&self, spec: &MissionSpec, call: &ToolCall, effect: Effect) -> Decision {
        if !spec.tools.iter().any(|t| t == &call.name) {
            return Decision::Deny {
                rule: "outil-non-autorise".into(),
                reason: format!("outil « {} » non autorisé pour cette mission", call.name),
            };
        }
        let path = call.arguments.get("path").and_then(|v| v.as_str());
        let access = match effect {
            Effect::ReadOnly => Access::Read,
            Effect::WorkspaceWrite => Access::Write,
        };
        match (call.name.as_str(), path) {
            ("finish", _) => Decision::Allow {
                rule: "fin-de-mission".into(),
            },
            (_, None) => Decision::Deny {
                rule: "argument-path-requis".into(),
                reason: "argument « path » manquant".into(),
            },
            (_, Some(p)) => match resolve(p, access, &spec.input_dirs, &spec.workspace) {
                Ok(_) => Decision::Allow {
                    rule: match access {
                        Access::Read => "lecture-perimetre".into(),
                        Access::Write => "ecriture-workspace".into(),
                    },
                },
                Err(reason) => Decision::Deny {
                    rule: "perimetre-fichiers".into(),
                    reason,
                },
            },
        }
    }
}
