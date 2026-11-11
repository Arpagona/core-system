//! Tests d'intégration du noyau avec un modèle scripté (aucun réseau).
//! Ils ne remplacent pas la démonstration avec un vrai modèle cloud.

use agentcore_core::journal::{self, Journal};
use agentcore_core::model::ScriptedModel;
use agentcore_core::policy::DefaultPolicy;
use agentcore_core::runner::{RunConfig, Runner};
use agentcore_core::{create_mission, tools};
use agentcore_types::*;
use serde_json::json;
use std::path::{Path, PathBuf};

struct Env {
    _tmp: TempDir,
    state: PathBuf,
    input: PathBuf,
    outside: PathBuf,
}

struct TempDir(PathBuf);
impl Drop for TempDir {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

fn env() -> Env {
    let base = std::env::temp_dir().join(format!(
        "agentcore-test-{}-{}",
        std::process::id(),
        agentcore_core::new_mission_id().0
    ));
    let input = base.join("dossier");
    let outside = base.join("secret");
    std::fs::create_dir_all(&input).unwrap();
    std::fs::create_dir_all(&outside).unwrap();
    std::fs::write(input.join("a.md"), "Document A : le client veut 50 pièces.").unwrap();
    std::fs::write(input.join("b.md"), "Document B : délai de 3 semaines.").unwrap();
    std::fs::write(outside.join("cle.txt"), "NE PAS LIRE").unwrap();
    Env {
        state: base.join("etat"),
        input,
        outside,
        _tmp: TempDir(base),
    }
}

fn reply(calls: Vec<(&str, &str, serde_json::Value)>) -> Result<ModelResponse, ModelError> {
    Ok(ModelResponse {
        text: None,
        tool_calls: calls
            .into_iter()
            .map(|(id, name, arguments)| ToolCall {
                id: id.into(),
                name: name.into(),
                arguments,
            })
            .collect(),
        usage: Usage {
            input_tokens: 1000,
            output_tokens: 100,
        },
        finish: FinishReason::ToolCalls,
    })
}

fn synthese() -> String {
    format!(
        "# Synthèse\n\n- `a.md` : le client veut 50 pièces.\n- `b.md` : délai de 3 semaines.\n\n{}",
        "Aucune autre information. ".repeat(10)
    )
}

fn happy_script(e: &Env) -> Vec<Result<ModelResponse, ModelError>> {
    let a = e.input.join("a.md").to_string_lossy().to_string();
    let b = e.input.join("b.md").to_string_lossy().to_string();
    vec![
        reply(vec![("c1", "list_dir", json!({"path": e.input}))]),
        reply(vec![
            ("c2", "read_file", json!({"path": a})),
            ("c3", "read_file", json!({"path": b})),
        ]),
        reply(vec![(
            "c4",
            "write_file",
            json!({"path": "synthese.md", "content": synthese()}),
        )]),
        reply(vec![(
            "c5",
            "finish",
            json!({"deliverable": "synthese.md", "summary": "2 documents synthétisés"}),
        )]),
    ]
}

fn run(
    e: &Env,
    j: &mut Journal,
    script: Vec<Result<ModelResponse, ModelError>>,
) -> (MissionState, u32) {
    let model = ScriptedModel::new(script);
    let cfg = RunConfig {
        price_input_per_mtok: 1_000_000,
        price_output_per_mtok: 2_000_000,
        retry_delays: vec![std::time::Duration::from_millis(1); 2],
        ..RunConfig::default()
    };
    let runner = Runner {
        model: &model,
        policy: &DefaultPolicy,
        tools: tools::registry(),
        cfg: &cfg,
    };
    let _ = e;
    let out = runner.run(j).unwrap();
    let calls = *model.calls.lock().unwrap();
    (out.state, calls)
}

fn mission(e: &Env, limits: Limits) -> Journal {
    create_mission(
        &e.state,
        "Synthétise le dossier",
        std::slice::from_ref(&e.input),
        "synthese.md",
        limits,
    )
    .unwrap()
}

fn id_of(j: &Journal) -> MissionId {
    j.projection().unwrap().spec.unwrap().id
}

fn denials(j: &Journal) -> Vec<String> {
    j.events
        .iter()
        .filter_map(|ev| match &ev.kind {
            EventKind::PolicyDecided {
                decision: Decision::Deny { reason, .. },
                ..
            } => Some(reason.clone()),
            _ => None,
        })
        .collect()
}

#[test]
fn scenario_nominal_complete_et_verifie() {
    let e = env();
    let mut j = mission(&e, Limits::default());
    let (state, calls) = run(&e, &mut j, happy_script(&e));
    assert_eq!(state, MissionState::Completed);
    assert_eq!(calls, 4);
    let p = j.projection().unwrap();
    assert_eq!(p.cost_microusd, 4 * (1000 + 200));
    let ws = p.spec.unwrap().workspace;
    assert!(std::fs::read_to_string(ws.join("synthese.md"))
        .unwrap()
        .contains("a.md"));
}

#[test]
fn persistance_apres_redemarrage() {
    let e = env();
    let mut j = mission(&e, Limits::default());
    let id = id_of(&j);
    run(&e, &mut j, happy_script(&e));
    drop(j);
    let (_, p, truncated) = journal::load(&journal::mission_dir(&e.state, &id)).unwrap();
    assert_eq!(p.state, MissionState::Completed);
    assert!(!truncated);
    // Une mission terminée n'est jamais réexécutée.
    let mut j = Journal::reopen(&e.state, &id).unwrap();
    let (state, calls) = run(&e, &mut j, vec![]);
    assert_eq!((state, calls), (MissionState::Completed, 0));
}

#[test]
fn acces_hors_perimetre_refuses_sans_effet() {
    let e = env();
    let mut j = mission(&e, Limits::default());
    let ws = j.projection().unwrap().spec.unwrap().workspace;
    std::os::unix::fs::symlink(&e.outside, ws.join("lien")).unwrap();
    let mut script = vec![reply(vec![
        (
            "x1",
            "read_file",
            json!({"path": e.outside.join("cle.txt")}),
        ),
        (
            "x2",
            "read_file",
            json!({"path": format!("{}/../secret/cle.txt", e.input.display())}),
        ),
        (
            "x3",
            "write_file",
            json!({"path": e.outside.join("pirate.txt"), "content": "x"}),
        ),
        (
            "x4",
            "write_file",
            json!({"path": "lien/pirate.txt", "content": "x"}),
        ),
        ("x5", "read_file", json!({"path": "lien/cle.txt"})),
        ("x6", "shell", json!({"cmd": "cat /etc/passwd"})),
        (
            "x7",
            "write_file",
            json!({"path": "../evasion.txt", "content": "x"}),
        ),
    ])];
    script.extend(happy_script(&e));
    let (state, _) = run(&e, &mut j, script);
    assert_eq!(state, MissionState::Completed);
    assert_eq!(denials(&j).len(), 7, "{:?}", denials(&j));
    assert!(!e.outside.join("pirate.txt").exists());
    assert!(!ws.parent().unwrap().join("evasion.txt").exists());
    // Aucun ToolStarted pour les appels refusés.
    assert!(!j.events.iter().any(
        |ev| matches!(&ev.kind, EventKind::ToolStarted { call_id, .. } if call_id.starts_with('x'))
    ));
}

#[test]
fn erreur_modele_echoue_sans_inventer_de_succes() {
    let e = env();
    let mut j = mission(&e, Limits::default());
    let (state, calls) = run(&e, &mut j, vec![Err(ModelError::Auth)]);
    assert_eq!(state, MissionState::Failed);
    assert_eq!(calls, 1, "Auth ne doit pas être retenté");
    let p = j.projection().unwrap();
    assert!(matches!(
        p.reason,
        Some(FailureReason::Model {
            error: ModelError::Auth
        })
    ));
}

#[test]
fn erreur_transitoire_retentee_deux_fois_au_plus() {
    let e = env();
    let mut j = mission(&e, Limits::default());
    let (state, calls) = run(
        &e,
        &mut j,
        vec![
            Err(ModelError::Timeout),
            Err(ModelError::Timeout),
            Err(ModelError::Timeout),
        ],
    );
    assert_eq!(state, MissionState::Failed);
    assert_eq!(calls, 3);
}

#[test]
fn finish_sans_livrable_valide_est_refuse() {
    let e = env();
    let mut j = mission(
        &e,
        Limits {
            max_iterations: 3,
            ..Limits::default()
        },
    );
    let a = e.input.join("a.md").to_string_lossy().to_string();
    let script = vec![
        reply(vec![("c1", "read_file", json!({"path": a}))]),
        reply(vec![(
            "c2",
            "write_file",
            json!({"path": "synthese.md", "content": "trop court"}),
        )]),
        reply(vec![(
            "c3",
            "finish",
            json!({"deliverable": "synthese.md", "summary": "fini"}),
        )]),
    ];
    let (state, _) = run(&e, &mut j, script);
    assert_eq!(state, MissionState::Failed);
    let p = j.projection().unwrap();
    match p.reason {
        Some(FailureReason::DeliverableRejected { problems }) => {
            assert!(
                problems.iter().any(|m| m.contains("trop court")),
                "{problems:?}"
            );
            assert!(problems.iter().any(|m| m.contains("a.md")), "{problems:?}");
        }
        r => panic!("raison inattendue {r:?}"),
    }
}

#[test]
fn sans_finish_la_mission_echoue() {
    let e = env();
    let mut j = mission(&e, Limits::default());
    let text = || {
        Ok(ModelResponse {
            text: Some("J'ai fini.".into()),
            tool_calls: vec![],
            usage: Usage::default(),
            finish: FinishReason::Stop,
        })
    };
    let (state, _) = run(&e, &mut j, vec![text(), text()]);
    assert_eq!(state, MissionState::Failed);
    assert_eq!(
        j.projection().unwrap().reason,
        Some(FailureReason::NoFinish)
    );
}

fn limit_reason(j: &Journal) -> Option<LimitKind> {
    match j.projection().unwrap().reason {
        Some(FailureReason::LimitExceeded { limit }) => Some(limit),
        _ => None,
    }
}

#[test]
fn limites_iterations_outils_tokens_cout_duree() {
    let e = env();
    let mut j = mission(
        &e,
        Limits {
            max_iterations: 2,
            ..Limits::default()
        },
    );
    run(&e, &mut j, happy_script(&e));
    assert_eq!(limit_reason(&j), Some(LimitKind::Iterations));

    let mut j = mission(
        &e,
        Limits {
            max_tool_calls: 2,
            ..Limits::default()
        },
    );
    run(&e, &mut j, happy_script(&e));
    assert_eq!(limit_reason(&j), Some(LimitKind::ToolCalls));

    let mut j = mission(
        &e,
        Limits {
            max_total_tokens: 2000,
            ..Limits::default()
        },
    );
    run(&e, &mut j, happy_script(&e));
    assert_eq!(limit_reason(&j), Some(LimitKind::Tokens));

    let mut j = mission(
        &e,
        Limits {
            max_cost_microusd: 12_000,
            ..Limits::default()
        },
    );
    // Plafond strict : avant chaque appel, coût engagé + pire cas (1,5 × dernière taille en entrée
    // + 4096 tokens de sortie) ≤ plafond. Appel scripté = 1200 µ$ ; pire cas suivant = 9842 µ$.
    // 1200 + 9842 ≤ 12000 → 2e appel ; 2400 + 9842 > 12000 → arrêt.
    let (_, calls) = run(&e, &mut j, happy_script(&e));
    assert_eq!(limit_reason(&j), Some(LimitKind::Cost));
    assert_eq!(calls, 2, "arrêt avant un appel qui pourrait dépasser");
    assert!(j.projection().unwrap().cost_microusd <= 12_000);

    let mut j = mission(
        &e,
        Limits {
            max_wall_seconds: 0,
            ..Limits::default()
        },
    );
    let (_, calls) = run(&e, &mut j, happy_script(&e));
    assert_eq!(limit_reason(&j), Some(LimitKind::WallTime));
    assert_eq!(calls, 0);
}

/// Simule un crash entre ToolStarted et ToolFinished en tronquant le journal.
fn crash_after_started(e: &Env, id: &MissionId, tool: &str) {
    let path = journal::mission_dir(&e.state, id).join("journal.jsonl");
    let text = std::fs::read_to_string(&path).unwrap();
    let mut kept = String::new();
    for line in text.lines() {
        kept.push_str(line);
        kept.push('\n');
        if line.contains("\"tool_started\"") && line.contains(&format!("\"tool\":\"{tool}\"")) {
            break;
        }
    }
    // Ligne partielle comme lors d'une coupure pendant l'écriture.
    kept.push_str("{\"v\":1,\"mission\":\"");
    std::fs::write(path, kept).unwrap();
}

#[test]
fn interruption_pendant_ecriture_incertaine_sans_rejeu() {
    let e = env();
    let mut j = mission(&e, Limits::default());
    let id = id_of(&j);
    run(&e, &mut j, happy_script(&e));
    drop(j);
    crash_after_started(&e, &id, "write_file");
    let mut j = Journal::reopen(&e.state, &id).unwrap();
    let (state, calls) = run(&e, &mut j, happy_script(&e));
    assert_eq!(state, MissionState::Uncertain);
    assert_eq!(calls, 0, "aucun appel ni rejeu");
    let starts = j
        .events
        .iter()
        .filter(
            |ev| matches!(&ev.kind, EventKind::ToolStarted { tool, .. } if tool == "write_file"),
        )
        .count();
    assert_eq!(starts, 1);
    // Décision humaine « effet non réalisé » puis reprise jusqu'au bout.
    j.append(EventKind::Resolved {
        call_id: "c4".into(),
        by: "test".into(),
        resolution: Resolution::NotDone,
    })
    .unwrap();
    let script = vec![
        reply(vec![(
            "c6",
            "write_file",
            json!({"path": "synthese.md", "content": synthese()}),
        )]),
        reply(vec![(
            "c7",
            "finish",
            json!({"deliverable": "synthese.md", "summary": "repris"}),
        )]),
    ];
    let (state, calls) = run(&e, &mut j, script);
    assert_eq!((state, calls), (MissionState::Completed, 2));
    assert!(journal::mission_dir(&e.state, &id)
        .read_dir()
        .unwrap()
        .flatten()
        .any(|f| f
            .file_name()
            .to_string_lossy()
            .starts_with("journal.truncated")));
}

#[test]
fn reprise_apres_coupure_d_un_caractere_utf8() {
    let e = env();
    let j = mission(&e, Limits::default());
    let id = id_of(&j);
    let dir = j.dir.clone();
    drop(j);

    let path = dir.join("journal.jsonl");
    let original = std::fs::read(&path).unwrap();
    let fragment = b"{\"text\":\"\xc3";
    std::fs::write(&path, [original.as_slice(), fragment].concat()).unwrap();

    let (_, projection, truncated) = journal::load(&dir).unwrap();
    assert!(truncated);
    assert_eq!(projection.last_seq, 1);
    let mut j = Journal::reopen(&e.state, &id).unwrap();
    assert_eq!(std::fs::read(&path).unwrap(), original);
    let archive = dir
        .read_dir()
        .unwrap()
        .map(|entry| entry.unwrap())
        .find(|entry| {
            entry
                .file_name()
                .to_string_lossy()
                .starts_with("journal.truncated.")
        })
        .unwrap();
    assert_eq!(std::fs::read(archive.path()).unwrap(), fragment);
    j.append(EventKind::MissionStarted { attempt: 1 }).unwrap();
    let (_, projection, truncated) = journal::load(&dir).unwrap();
    assert!(!truncated);
    assert_eq!(projection.last_seq, 2);
}

#[test]
fn ligne_complete_utf8_invalide_bloque_la_reprise() {
    let e = env();
    let j = mission(&e, Limits::default());
    let id = id_of(&j);
    let dir = j.dir.clone();
    drop(j);

    let path = dir.join("journal.jsonl");
    let mut original = std::fs::read(&path).unwrap();
    original.extend_from_slice(b"{\"text\":\"\xc3\n");
    std::fs::write(&path, &original).unwrap();

    assert!(matches!(
        journal::load(&dir),
        Err(journal::StoreError::Journal(_))
    ));
    assert!(matches!(
        Journal::reopen(&e.state, &id),
        Err(journal::StoreError::Journal(_))
    ));
    assert_eq!(std::fs::read(&path).unwrap(), original);
}

#[test]
fn interruption_pendant_lecture_rejouee() {
    let e = env();
    let mut j = mission(&e, Limits::default());
    let id = id_of(&j);
    run(&e, &mut j, happy_script(&e));
    drop(j);
    crash_after_started(&e, &id, "read_file");
    let mut j = Journal::reopen(&e.state, &id).unwrap();
    // Reprise : c2 est rejouée (lecture), c3 exécutée, puis le modèle poursuit.
    let script = happy_script(&e).split_off(2);
    let (state, calls) = run(&e, &mut j, script);
    assert_eq!(state, MissionState::Completed);
    assert_eq!(calls, 2);
    assert_eq!(j.projection().unwrap().attempts, 2);
}

#[test]
fn verrou_empeche_deux_processus_sur_la_meme_mission() {
    let e = env();
    let j = mission(&e, Limits::default());
    let id = id_of(&j);
    assert!(matches!(
        Journal::reopen(&e.state, &id),
        Err(journal::StoreError::Locked)
    ));
}

#[test]
fn entrees_recouvrant_l_etat_refusees() {
    let e = env();
    std::fs::create_dir_all(&e.state).unwrap();
    let r = create_mission(
        &e.state,
        "x",
        std::slice::from_ref(&e.state),
        "synthese.md",
        Limits::default(),
    );
    assert!(r.is_err());
    let r = create_mission(
        &e.state,
        "x",
        std::slice::from_ref(&e.input),
        "../x.md",
        Limits::default(),
    );
    assert!(r.is_err());
    let _ = Path::new("/");
}

#[test]
fn plafond_quotidien_arrete_la_mission() {
    let e = env();
    let mut j = mission(&e, Limits::default());
    let model = ScriptedModel::new(happy_script(&e));
    let cfg = RunConfig {
        price_input_per_mtok: 1_000_000,
        price_output_per_mtok: 2_000_000,
        daily_remaining_microusd: Some(12_000),
        ..RunConfig::default()
    };
    let runner = Runner {
        model: &model,
        policy: &DefaultPolicy,
        tools: tools::registry(),
        cfg: &cfg,
    };
    let out = runner.run(&mut j).unwrap();
    assert_eq!(out.state, MissionState::Failed);
    assert_eq!(*model.calls.lock().unwrap(), 2);
    assert_eq!(
        j.projection().unwrap().summary.as_deref(),
        Some("plafond quotidien de dépenses atteint")
    );
    assert_eq!(agentcore_core::spent_since(&e.state, 0), 2400);
}
