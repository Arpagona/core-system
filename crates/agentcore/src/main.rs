//! CLI `agentcore` (C-07).

use agentcore_core::journal::{self, Journal};
use agentcore_core::model::OpenAiCompatible;
use agentcore_core::policy::DefaultPolicy;
use agentcore_core::runner::{RunConfig, Runner};
use agentcore_core::{report_json, Config, COMMIT, VERSION};
use agentcore_types::*;
use std::path::PathBuf;
use std::process::ExitCode;

/// Écrit sur la sortie standard ; un tube fermé (`| head`) termine proprement au lieu de paniquer.
macro_rules! out {
    ($($t:tt)*) => {{
        use std::io::Write;
        if let Err(e) = writeln!(std::io::stdout(), $($t)*) {
            if e.kind() == std::io::ErrorKind::BrokenPipe {
                std::process::exit(0);
            }
        }
    }};
}

const USAGE: &str = "agentcore — ARPAGONA Agent Core v0.1 (préversion)

USAGE
  agentcore [--config FICHIER] mission run --input DOSSIER [--input DOSSIER…] --goal TEXTE [--deliverable synthese.md]
  agentcore [--config FICHIER] mission list [--json]
  agentcore [--config FICHIER] mission status ID
  agentcore [--config FICHIER] mission log ID
  agentcore [--config FICHIER] mission resume ID
  agentcore [--config FICHIER] mission resolve ID --call APPEL --as done|not-done [--by NOM]
  agentcore [--config FICHIER] mission cancel ID
  agentcore [--config FICHIER] version

Configuration : --config, sinon $AGENTCORE_CONFIG, sinon /etc/agentcore/config.toml.
Codes de sortie : 0 terminée, 2 échec, 3 incertaine, 4 annulée, 1 erreur d'usage ou interne.";

fn fail(msg: impl std::fmt::Display) -> ExitCode {
    eprintln!("erreur : {msg}");
    ExitCode::from(1)
}

fn take(args: &mut Vec<String>, flag: &str) -> Option<String> {
    let i = args.iter().position(|a| a == flag)?;
    if i + 1 >= args.len() {
        return None;
    }
    let v = args.remove(i + 1);
    args.remove(i);
    Some(v)
}

fn take_all(args: &mut Vec<String>, flag: &str) -> Vec<String> {
    let mut out = Vec::new();
    while let Some(v) = take(args, flag) {
        out.push(v);
    }
    out
}

fn load_config(path: Option<String>) -> Result<(Config, String), String> {
    let path = path
        .or_else(|| std::env::var("AGENTCORE_CONFIG").ok())
        .unwrap_or_else(|| "/etc/agentcore/config.toml".into());
    let text = std::fs::read_to_string(&path).map_err(|e| format!("configuration {path} : {e}"))?;
    Ok((Config::parse(&text)?, path))
}

/// Clé : variable d'environnement, sinon fichier dédié. Jamais affichée ni journalisée.
fn api_key(cfg: &Config) -> Option<String> {
    std::env::var(&cfg.api_key_env)
        .ok()
        .map(|k| k.trim().to_string())
        .filter(|k| !k.is_empty())
        .or_else(|| {
            if cfg.api_key_file.is_empty() {
                return None;
            }
            std::fs::read_to_string(&cfg.api_key_file)
                .ok()
                .map(|k| k.trim().to_string())
                .filter(|k| !k.is_empty())
        })
}

fn model_of(cfg: &Config, mission: Option<&MissionId>) -> Result<OpenAiCompatible, String> {
    if cfg.base_url.is_empty() || cfg.model.is_empty() {
        return Err("base_url et model doivent être configurés".into());
    }
    let key = api_key(cfg).ok_or(format!(
        "clé absente : variable {} non définie et fichier « {} » illisible ou vide",
        cfg.api_key_env, cfg.api_key_file
    ))?;
    Ok(OpenAiCompatible::new(
        &cfg.base_url,
        &cfg.model,
        key,
        cfg.request_timeout_s,
        mission
            .filter(|_| !cfg.session_header.is_empty())
            .map(|id| (cfg.session_header.clone(), format!("agentcore-{id}"))),
    ))
}

fn print_report(cfg: &Config, id: &MissionId) -> Result<MissionState, String> {
    let dir = journal::mission_dir(&cfg.state_dir, id);
    let (events, proj, truncated) = journal::load(&dir).map_err(|e| e.to_string())?;
    let r = report_json(&proj, &events, &cfg.model);
    let _ = std::fs::write(
        dir.join("report.json"),
        serde_json::to_string_pretty(&r).unwrap_or_default(),
    );
    out!("mission       : {id}");
    out!("état          : {:?}", proj.state);
    if let Some(reason) = &proj.reason {
        out!("raison        : {reason:?}");
    }
    if let Some(s) = &proj.summary {
        out!("compte rendu  : {s}");
    }
    if let Some(spec) = &proj.spec {
        let p = spec.workspace.join(&spec.deliverable.path);
        out!(
            "livrable      : {} ({})",
            p.display(),
            if p.is_file() { "présent" } else { "absent" }
        );
    }
    if let Some(v) = r.get("verification").filter(|v| !v.is_null()) {
        out!("vérification  : {v}");
    }
    out!(
        "consommation  : {} itérations, {} appels d'outil, {} tokens (entrée {}, sortie {}), coût estimé {:.4} $",
        proj.iterations,
        proj.tool_calls,
        proj.usage.total(),
        proj.usage.input_tokens,
        proj.usage.output_tokens,
        proj.cost_microusd as f64 / 1e6
    );
    if let Some(d) = r
        .get("denials")
        .and_then(|d| d.as_array())
        .filter(|d| !d.is_empty())
    {
        out!("refus         : {}", d.len());
    }
    if !proj.uncertain.is_empty() {
        for u in &proj.uncertain {
            out!(
                "INCERTAIN     : appel {} ({}) commencé sans résultat → vérifier puis `agentcore mission resolve {id} --call {} --as done|not-done`",
                u.call_id, u.tool, u.call_id
            );
        }
    }
    if truncated {
        out!("journal       : dernière ligne tronquée ignorée");
    }
    out!("tentatives    : {}", proj.attempts);
    out!("rapport       : {}", dir.join("report.json").display());
    Ok(proj.state)
}

fn daily_remaining(cfg: &Config) -> Result<u64, String> {
    let since = agentcore_core::journal::now_ms().saturating_sub(24 * 3600 * 1000);
    let spent = agentcore_core::spent_since(&cfg.state_dir, since);
    if spent >= cfg.max_daily_cost_microusd {
        return Err(format!(
            "plafond quotidien atteint : {:.4} $ dépensés sur 24 h pour {:.2} $ autorisés",
            spent as f64 / 1e6,
            cfg.max_daily_cost_microusd as f64 / 1e6
        ));
    }
    Ok(cfg.max_daily_cost_microusd - spent)
}

fn execute(cfg: &Config, j: &mut Journal) -> Result<MissionState, String> {
    let id = j.projection().ok().and_then(|p| p.spec).map(|s| s.id);
    let model = model_of(cfg, id.as_ref())?;
    let remaining = daily_remaining(cfg)?;
    let run_cfg = RunConfig {
        price_input_per_mtok: cfg.price_input_per_mtok_microusd,
        price_output_per_mtok: cfg.price_output_per_mtok_microusd,
        max_output_tokens: cfg.max_output_tokens,
        daily_remaining_microusd: Some(remaining),
        ..RunConfig::default()
    };
    let runner = Runner {
        model: &model,
        policy: &DefaultPolicy,
        tools: agentcore_core::tools::registry(),
        cfg: &run_cfg,
    };
    j.echo = true;
    let out = runner.run(j).map_err(|e| e.to_string())?;
    if let Some(n) = out.note {
        eprintln!("  note : {n}");
    }
    Ok(out.state)
}

fn code(state: MissionState) -> ExitCode {
    ExitCode::from(state.exit_code() as u8)
}

fn main() -> ExitCode {
    let mut args: Vec<String> = std::env::args().skip(1).collect();
    if args.is_empty() || args.iter().any(|a| a == "-h" || a == "--help") {
        out!("{USAGE}");
        return ExitCode::SUCCESS;
    }
    let config_path = take(&mut args, "--config");
    if args.first().map(String::as_str) == Some("version") {
        out!("agentcore {VERSION}+{COMMIT}");
        if let Ok((cfg, path)) = load_config(config_path) {
            out!(
                "configuration : {path}\nétat : {}\nplafonds : {:.2} $ / mission, {:.2} $ / 24 h\nmodèle : {} @ {}\nclé : variable {} ou fichier dédié ({})",
                cfg.state_dir.display(),
                cfg.limits.max_cost_microusd as f64 / 1e6,
                cfg.max_daily_cost_microusd as f64 / 1e6,
                cfg.model,
                cfg.base_url,
                cfg.api_key_env,
                if api_key(&cfg).is_some() {
                    "disponible"
                } else {
                    "INDISPONIBLE"
                }
            );
        }
        return ExitCode::SUCCESS;
    }
    if args.first().map(String::as_str) != Some("mission") || args.len() < 2 {
        return fail(format!("commande inconnue\n\n{USAGE}"));
    }
    let (cfg, _) = match load_config(config_path) {
        Ok(c) => c,
        Err(e) => return fail(e),
    };
    let sub = args[1].clone();
    let mut rest: Vec<String> = args[2..].to_vec();
    let id_arg = |rest: &Vec<String>| rest.first().map(|s| MissionId(s.clone()));
    match sub.as_str() {
        "run" => {
            let inputs: Vec<PathBuf> = take_all(&mut rest, "--input")
                .into_iter()
                .map(PathBuf::from)
                .collect();
            let Some(goal) = take(&mut rest, "--goal") else {
                return fail("--goal requis");
            };
            let deliverable =
                take(&mut rest, "--deliverable").unwrap_or_else(|| "synthese.md".into());
            if !rest.is_empty() {
                return fail(format!("arguments inattendus : {rest:?}"));
            }
            // Vérifier configuration et budget quotidien AVANT de créer la mission.
            if let Err(e) = model_of(&cfg, None)
                .map(|_| ())
                .and_then(|_| daily_remaining(&cfg).map(|_| ()))
            {
                return fail(e);
            }
            let mut j = match agentcore_core::create_mission(
                &cfg.state_dir,
                &goal,
                &inputs,
                &deliverable,
                cfg.limits.clone(),
            ) {
                Ok(j) => j,
                Err(e) => return fail(e),
            };
            let id = j
                .projection()
                .ok()
                .and_then(|p| p.spec)
                .map(|s| s.id)
                .expect("mission créée");
            eprintln!("mission {id} — modèle {} — suivi :", cfg.model);
            if let Err(e) = execute(&cfg, &mut j) {
                eprintln!("erreur pendant l'exécution : {e}");
            }
            drop(j);
            match print_report(&cfg, &id) {
                Ok(s) => code(s),
                Err(e) => fail(e),
            }
        }
        "resume" => {
            let Some(id) = id_arg(&rest) else {
                return fail("ID requis");
            };
            let mut j = match Journal::reopen(&cfg.state_dir, &id) {
                Ok(j) => j,
                Err(e) => return fail(e),
            };
            eprintln!("reprise de {id} — suivi :");
            if let Err(e) = execute(&cfg, &mut j) {
                eprintln!("erreur pendant l'exécution : {e}");
            }
            drop(j);
            match print_report(&cfg, &id) {
                Ok(s) => code(s),
                Err(e) => fail(e),
            }
        }
        "status" => {
            let Some(id) = id_arg(&rest) else {
                return fail("ID requis");
            };
            match print_report(&cfg, &id) {
                Ok(s) => code(s),
                Err(e) => fail(e),
            }
        }
        "log" => {
            let Some(id) = id_arg(&rest) else {
                return fail("ID requis");
            };
            match journal::load(&journal::mission_dir(&cfg.state_dir, &id)) {
                Ok((events, _, _)) => {
                    for e in events {
                        out!(
                            "[{:>3}] {} {}",
                            e.seq,
                            e.at_ms,
                            agentcore_core::describe(&e.kind)
                        );
                    }
                    ExitCode::SUCCESS
                }
                Err(e) => fail(e),
            }
        }
        "list" => {
            let dir = cfg.state_dir.join("missions");
            let mut ids: Vec<String> = std::fs::read_dir(&dir)
                .map(|r| {
                    r.flatten()
                        .map(|e| e.file_name().to_string_lossy().to_string())
                        .collect()
                })
                .unwrap_or_default();
            ids.sort();
            if rest == ["--json"] {
                let missions: Vec<_> = ids
                    .iter()
                    .rev()
                    .map(|id| match journal::load(&dir.join(id)) {
                        Ok((_, projection, truncated)) => serde_json::json!({
                            "id": id,
                            "state": projection.state,
                            "goal": projection.spec.map(|spec| spec.goal),
                            "truncated": truncated,
                        }),
                        Err(_) => serde_json::json!({"id": id, "state": "unreadable"}),
                    })
                    .collect();
                out!("{}", serde_json::json!(missions));
                return ExitCode::SUCCESS;
            }
            for id in ids {
                match journal::load(&dir.join(&id)) {
                    Ok((_, p, _)) => out!(
                        "{id}  {:<10}  {}",
                        format!("{:?}", p.state),
                        p.spec
                            .map(|s| s.goal.chars().take(60).collect::<String>())
                            .unwrap_or_default()
                    ),
                    Err(e) => out!("{id}  ILLISIBLE  {e}"),
                }
            }
            ExitCode::SUCCESS
        }
        "resolve" => {
            let Some(id) = id_arg(&rest) else {
                return fail("ID requis");
            };
            let (Some(call), Some(r)) = (take(&mut rest, "--call"), take(&mut rest, "--as")) else {
                return fail("--call et --as done|not-done requis");
            };
            let by = take(&mut rest, "--by")
                .unwrap_or_else(|| std::env::var("USER").unwrap_or_else(|_| "operateur".into()));
            let resolution = match r.as_str() {
                "done" => Resolution::Done,
                "not-done" => Resolution::NotDone,
                _ => return fail("--as doit valoir done ou not-done"),
            };
            let mut j = match Journal::reopen(&cfg.state_dir, &id) {
                Ok(j) => j,
                Err(e) => return fail(e),
            };
            let p = match j.projection() {
                Ok(p) => p,
                Err(e) => return fail(e),
            };
            if !p.uncertain.iter().any(|u| u.call_id == call) {
                return fail(format!(
                    "aucun appel incertain « {call} » dans cette mission"
                ));
            }
            if let Err(e) = j.append(EventKind::Resolved {
                call_id: call,
                by,
                resolution,
            }) {
                return fail(e);
            }
            out!("résolution enregistrée ; reprendre avec : agentcore mission resume {id}");
            ExitCode::SUCCESS
        }
        "cancel" => {
            let Some(id) = id_arg(&rest) else {
                return fail("ID requis");
            };
            match Journal::reopen(&cfg.state_dir, &id) {
                Ok(mut j) => {
                    let p = match j.projection() {
                        Ok(p) => p,
                        Err(e) => return fail(e),
                    };
                    if p.state.is_terminal() {
                        return fail(format!("mission déjà terminée ({:?})", p.state));
                    }
                    if let Err(e) = j.append(EventKind::MissionEnded {
                        state: MissionState::Cancelled,
                        reason: None,
                        summary: Some("annulée par l'opérateur".into()),
                    }) {
                        return fail(e);
                    }
                    out!("mission {id} annulée");
                    ExitCode::from(4)
                }
                Err(journal::StoreError::Locked) => {
                    let f = journal::mission_dir(&cfg.state_dir, &id).join("cancel.request");
                    match std::fs::write(&f, b"cancel\n") {
                        Ok(()) => {
                            out!("mission en cours : demande d'annulation déposée, prise en compte avant l'étape suivante");
                            ExitCode::SUCCESS
                        }
                        Err(e) => fail(e),
                    }
                }
                Err(e) => fail(e),
            }
        }
        _ => fail(format!("sous-commande inconnue « {sub} »\n\n{USAGE}")),
    }
}
