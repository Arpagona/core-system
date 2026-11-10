//! ARPAGONA Agent Core — noyau v0.1 (SPIKE sur contrats M0 proposés, non approuvés).

pub mod journal;
pub mod model;
pub mod policy;
pub mod runner;
pub mod tools;
pub mod verify;

use agentcore_types::*;
use std::collections::BTreeMap;
use std::io::Read;
use std::path::{Path, PathBuf};

pub const VERSION: &str = env!("CARGO_PKG_VERSION");
pub const COMMIT: &str = match option_env!("AGENTCORE_COMMIT") {
    Some(c) => c,
    None => "inconnu",
};

/// Configuration minimale `clé = valeur` (sous-ensemble TOML : chaînes entre guillemets et entiers).
#[derive(Debug, Clone)]
pub struct Config {
    pub state_dir: PathBuf,
    pub base_url: String,
    pub model: String,
    pub api_key_env: String,
    /// Nom d'un en-tête d'affinité envoyé avec l'identifiant de mission (vide = aucun).
    pub session_header: String,
    /// Fichier contenant la clé (une ligne), utilisé si la variable `api_key_env` est absente.
    pub api_key_file: String,
    pub price_input_per_mtok_microusd: u64,
    pub price_output_per_mtok_microusd: u64,
    pub request_timeout_s: u64,
    pub max_output_tokens: u32,
    /// Plafond de dépenses estimées sur 24 h glissantes, toutes missions (micro-dollars).
    pub max_daily_cost_microusd: u64,
    pub limits: Limits,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            state_dir: PathBuf::from("/var/lib/agentcore"),
            base_url: String::new(),
            model: String::new(),
            api_key_env: "AGENTCORE_API_KEY".into(),
            session_header: String::new(),
            api_key_file: String::new(),
            price_input_per_mtok_microusd: 0,
            price_output_per_mtok_microusd: 0,
            request_timeout_s: 120,
            max_output_tokens: 4096,
            max_daily_cost_microusd: 20_000_000,
            limits: Limits::default(),
        }
    }
}

impl Config {
    pub fn parse(text: &str) -> Result<Self, String> {
        let mut kv = BTreeMap::new();
        for (n, line) in text.lines().enumerate() {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') || line.starts_with('[') {
                continue;
            }
            let (k, v) = line
                .split_once('=')
                .ok_or(format!("ligne {} : « clé = valeur » attendu", n + 1))?;
            let v = v.trim();
            let v = v.split(" #").next().unwrap_or(v).trim();
            let v = v
                .strip_prefix('"')
                .and_then(|s| s.strip_suffix('"'))
                .unwrap_or(v);
            kv.insert(k.trim().to_string(), v.to_string());
        }
        let mut c = Self::default();
        let num = |k: &str, d: u64| -> Result<u64, String> {
            kv.get(k).map_or(Ok(d), |v| {
                v.replace('_', "")
                    .parse()
                    .map_err(|_| format!("{k} : entier attendu"))
            })
        };
        if let Some(v) = kv.get("state_dir") {
            c.state_dir = PathBuf::from(v);
        }
        if let Some(v) = kv.get("base_url") {
            c.base_url = v.clone();
        }
        if let Some(v) = kv.get("model") {
            c.model = v.clone();
        }
        if let Some(v) = kv.get("api_key_env") {
            c.api_key_env = v.clone();
        }
        if let Some(v) = kv.get("api_key_file") {
            c.api_key_file = v.clone();
        }
        if let Some(v) = kv.get("session_header") {
            c.session_header = v.clone();
        }
        c.price_input_per_mtok_microusd = num("price_input_per_mtok_microusd", 0)?;
        c.price_output_per_mtok_microusd = num("price_output_per_mtok_microusd", 0)?;
        c.request_timeout_s = num("request_timeout_s", 120)?;
        c.max_output_tokens = num("max_output_tokens", 4096)? as u32;
        c.max_daily_cost_microusd = num("max_daily_cost_microusd", 20_000_000)?;
        let d = Limits::default();
        c.limits = Limits {
            max_iterations: num("max_iterations", d.max_iterations as u64)? as u32,
            max_tool_calls: num("max_tool_calls", d.max_tool_calls as u64)? as u32,
            max_wall_seconds: num("max_wall_seconds", d.max_wall_seconds)?,
            max_total_tokens: num("max_total_tokens", d.max_total_tokens)?,
            max_cost_microusd: num("max_cost_microusd", d.max_cost_microusd)?,
        };
        Ok(c)
    }
}

/// Identifiant `m-AAAAMMJJ-HHMMSS-xxxxxx` (UTC + aléa système).
pub fn new_mission_id() -> MissionId {
    let ms = journal::now_ms();
    let secs = (ms / 1000) as i64;
    let (days, rem) = (secs.div_euclid(86_400), secs.rem_euclid(86_400));
    // Jours depuis 1970 → date civile (algorithme de H. Hinnant).
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = yoe + era * 400 + i64::from(m <= 2);
    let mut rnd = [0u8; 3];
    let _ = std::fs::File::open("/dev/urandom").and_then(|mut f| f.read_exact(&mut rnd));
    MissionId(format!(
        "m-{y:04}{m:02}{d:02}-{:02}{:02}{:02}-{:02x}{:02x}{:02x}",
        rem / 3600,
        rem % 3600 / 60,
        rem % 60,
        rnd[0],
        rnd[1],
        rnd[2]
    ))
}

/// Crée une mission : validation des entrées, journal (MissionCreated) et workspace.
pub fn create_mission(
    state_dir: &Path,
    goal: &str,
    inputs: &[PathBuf],
    deliverable: &str,
    limits: Limits,
) -> Result<journal::Journal, String> {
    if goal.trim().is_empty() || goal.chars().count() > 4000 {
        return Err("objectif vide ou > 4000 caractères".into());
    }
    if inputs.is_empty() {
        return Err("au moins un dossier d'entrée (--input) est requis".into());
    }
    if deliverable.is_empty() || deliverable.contains("..") || Path::new(deliverable).is_absolute()
    {
        return Err("le livrable doit être un chemin relatif simple".into());
    }
    let mut input_dirs = Vec::new();
    for i in inputs {
        let c = i
            .canonicalize()
            .map_err(|e| format!("dossier d'entrée {} : {e}", i.display()))?;
        if !c.is_dir() {
            return Err(format!("{} n'est pas un dossier", c.display()));
        }
        input_dirs.push(c);
    }
    let missions = state_dir.join("missions");
    std::fs::create_dir_all(&missions).map_err(|e| format!("{}: {e}", missions.display()))?;
    let missions = missions.canonicalize().map_err(|e| e.to_string())?;
    if input_dirs
        .iter()
        .any(|d| d.starts_with(&missions) || missions.starts_with(d))
    {
        return Err("un dossier d'entrée ne peut pas recouvrir le répertoire d'état".into());
    }
    let id = new_mission_id();
    let spec = MissionSpec {
        id: id.clone(),
        goal: goal.to_string(),
        input_dirs,
        workspace: missions.join(&id.0).join("workspace"),
        tools: tools::registry().iter().map(|t| t.spec().name).collect(),
        limits,
        deliverable: DeliverableSpec {
            path: deliverable.to_string(),
            min_bytes: 200,
            max_bytes: 200_000,
            must_cite_inputs: true,
        },
    };
    let ws = spec.workspace.clone();
    let j = journal::Journal::create(state_dir, EventKind::MissionCreated { spec }, &id)
        .map_err(|e| e.to_string())?;
    std::fs::create_dir(&ws).map_err(|e| e.to_string())?;
    Ok(j)
}

/// Rapport final lisible par machine (C-07).
pub fn report_json(proj: &Projection, events: &[Event], model: &str) -> serde_json::Value {
    let spec = proj.spec.as_ref();
    let check = events.iter().rev().find_map(|e| match &e.kind {
        EventKind::DeliverableChecked { report } => Some(report.clone()),
        _ => None,
    });
    let denials: Vec<_> = events
        .iter()
        .filter_map(|e| match &e.kind {
            EventKind::PolicyDecided {
                tool,
                decision: Decision::Deny { rule, reason },
                ..
            } => Some(serde_json::json!({"tool": tool, "rule": rule, "reason": reason})),
            _ => None,
        })
        .collect();
    let first = events.first().map(|e| e.at_ms).unwrap_or(0);
    let last = events.last().map(|e| e.at_ms).unwrap_or(0);
    serde_json::json!({
        "mission": spec.map(|s| s.id.0.clone()),
        "state": proj.state,
        "reason": proj.reason,
        "summary": proj.summary,
        "deliverable": spec.map(|s| s.workspace.join(&s.deliverable.path)),
        "verification": check,
        "attempts": proj.attempts,
        "iterations": proj.iterations,
        "tool_calls": proj.tool_calls,
        "denials": denials,
        "uncertain": proj.uncertain.iter().map(|u| &u.call_id).collect::<Vec<_>>(),
        "usage": proj.usage,
        "estimated_cost_usd": proj.cost_microusd as f64 / 1e6,
        "elapsed_s": (last.saturating_sub(first)) as f64 / 1000.0,
        "model": model,
        "version": format!("{VERSION}+{COMMIT}"),
        "note": "coût estimé à partir des tarifs configurés, pas une facture",
    })
}

fn cut(s: &str, n: usize) -> String {
    let one: String = s.split_whitespace().collect::<Vec<_>>().join(" ");
    if one.chars().count() > n {
        format!("{}…", one.chars().take(n).collect::<String>())
    } else {
        one
    }
}

/// Description courte d'un événement, sans contenu de fichier ni secret.
pub fn describe(k: &EventKind) -> String {
    match k {
        EventKind::MissionCreated { spec } => format!("mission créée : {}", cut(&spec.goal, 80)),
        EventKind::MissionStarted { attempt } => format!("exécution n° {attempt}"),
        EventKind::ModelCalled { iteration } => format!("appel modèle n° {iteration}"),
        EventKind::ModelReplied {
            usage,
            tool_calls,
            text,
            ..
        } => {
            let calls: Vec<String> = tool_calls
                .iter()
                .map(|c| match c.arguments.get("path").and_then(|p| p.as_str()) {
                    Some(p) => format!("{}({})", c.name, cut(p, 60)),
                    None => c.name.clone(),
                })
                .collect();
            format!(
                "réponse modèle ({} + {} tokens) → {}",
                usage.input_tokens,
                usage.output_tokens,
                if calls.is_empty() {
                    format!("texte : {}", cut(text.as_deref().unwrap_or(""), 80))
                } else {
                    calls.join(", ")
                }
            )
        }
        EventKind::ModelFailed { error, .. } => format!("ÉCHEC modèle : {error:?}"),
        EventKind::PolicyDecided { tool, decision, .. } => match decision {
            Decision::Allow { rule } => format!("autorisé {tool} ({rule})"),
            Decision::Deny { rule, reason } => format!("REFUSÉ {tool} ({rule}) : {reason}"),
        },
        EventKind::ToolStarted { tool, effect, .. } => format!("début {tool} [{effect:?}]"),
        EventKind::ToolFinished { outcome, .. } => match outcome {
            ToolOutcome::Ok { .. } => "fin outil : ok".into(),
            ToolOutcome::Err { kind, message } => {
                format!("fin outil : ERREUR {kind:?} : {}", cut(message, 100))
            }
        },
        EventKind::DeliverableChecked { report } => {
            if report.ok {
                format!(
                    "livrable vérifié : {} ({} octets)",
                    report.path, report.bytes
                )
            } else {
                format!("livrable REFUSÉ : {}", report.problems.join(" ; "))
            }
        }
        EventKind::Resolved {
            call_id,
            by,
            resolution,
        } => format!("résolution humaine {call_id} par {by} : {resolution:?}"),
        EventKind::MissionEnded { state, reason, .. } => format!(
            "FIN : {state:?} {}",
            reason
                .as_ref()
                .map(|r| format!("{r:?}"))
                .unwrap_or_default()
        ),
    }
}

/// Coût estimé dépensé depuis `since_ms`, toutes missions confondues (journaux lisibles uniquement).
pub fn spent_since(state_dir: &Path, since_ms: u64) -> u64 {
    let Ok(rd) = std::fs::read_dir(state_dir.join("missions")) else {
        return 0;
    };
    let mut total = 0;
    for e in rd.flatten() {
        let Ok(text) = std::fs::read_to_string(e.path().join("journal.jsonl")) else {
            continue;
        };
        for line in text.lines() {
            if let Ok(ev) = serde_json::from_str::<Event>(line) {
                if let EventKind::ModelReplied { cost_microusd, .. } = ev.kind {
                    if ev.at_ms >= since_ms {
                        total += cost_microusd;
                    }
                }
            }
        }
    }
    total
}
