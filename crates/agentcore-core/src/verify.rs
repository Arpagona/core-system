//! Vérification déterministe du livrable (sans LLM). Ne juge pas la qualité.

use agentcore_types::{DeliverableReport, Event, EventKind, MissionSpec, ToolOutcome};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

/// Fichiers d'entrée lus avec succès pendant la mission (chemins canoniques).
pub fn inputs_read(spec: &MissionSpec, events: &[Event]) -> Vec<PathBuf> {
    let mut tool_of: BTreeMap<&str, &str> = BTreeMap::new();
    let roots: Vec<PathBuf> = spec
        .input_dirs
        .iter()
        .filter_map(|d| d.canonicalize().ok())
        .collect();
    let mut out = Vec::new();
    for ev in events {
        match &ev.kind {
            EventKind::ToolStarted { call_id, tool, .. } => {
                tool_of.insert(call_id, tool);
            }
            EventKind::ToolFinished {
                call_id,
                outcome: ToolOutcome::Ok { output },
            } if tool_of.get(call_id.as_str()) == Some(&"read_file") => {
                if let Some(p) = output.get("path").and_then(|v| v.as_str()) {
                    let p = PathBuf::from(p);
                    if roots.iter().any(|r| p.starts_with(r)) && !out.contains(&p) {
                        out.push(p);
                    }
                }
            }
            _ => {}
        }
    }
    out
}

fn normalize(p: &str) -> &str {
    p.trim_start_matches("./")
}

pub fn verify_deliverable(
    spec: &MissionSpec,
    declared: &str,
    events: &[Event],
) -> DeliverableReport {
    let d = &spec.deliverable;
    let mut problems = Vec::new();
    let mut bytes = 0;
    let declared_rel = Path::new(declared)
        .strip_prefix(&spec.workspace)
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_else(|_| declared.to_string());
    if normalize(&declared_rel) != normalize(&d.path) {
        problems.push(format!(
            "livrable déclaré « {declared} » différent du livrable attendu « {} »",
            d.path
        ));
    }
    let path = spec.workspace.join(&d.path);
    match std::fs::symlink_metadata(&path) {
        Err(_) => problems.push(format!("fichier « {} » absent du workspace", d.path)),
        Ok(m) if m.file_type().is_symlink() => {
            problems.push("le livrable est un lien symbolique".into())
        }
        Ok(m) if !m.is_file() => problems.push("le livrable n'est pas un fichier".into()),
        Ok(m) => {
            bytes = m.len();
            if bytes < d.min_bytes {
                problems.push(format!(
                    "livrable trop court : {bytes} < {} octets",
                    d.min_bytes
                ));
            }
            if bytes > d.max_bytes {
                problems.push(format!(
                    "livrable trop long : {bytes} > {} octets",
                    d.max_bytes
                ));
            }
            match std::fs::read(&path).map(String::from_utf8) {
                Ok(Ok(text)) => {
                    if d.must_cite_inputs {
                        let read = inputs_read(spec, events);
                        if read.is_empty() {
                            problems.push("aucun document d'entrée n'a été lu".into());
                        }
                        for p in read {
                            let name = p
                                .file_name()
                                .map(|n| n.to_string_lossy().to_string())
                                .unwrap_or_default();
                            if !text.contains(&name) {
                                problems.push(format!("document lu non cité : {name}"));
                            }
                        }
                    }
                }
                _ => problems.push("livrable illisible ou non UTF-8".into()),
            }
        }
    }
    DeliverableReport {
        path: d.path.clone(),
        ok: problems.is_empty(),
        bytes,
        problems,
    }
}
