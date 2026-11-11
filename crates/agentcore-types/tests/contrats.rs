//! Tests de contrat C-01 … C-07 (portée : types et projection du journal).
use agentcore_types::*;
use serde_json::json;
use std::path::PathBuf;

fn spec() -> MissionSpec {
    MissionSpec {
        id: MissionId("m-test".into()),
        goal: "Synthétise".into(),
        input_dirs: vec![PathBuf::from("/in")],
        workspace: PathBuf::from("/ws"),
        tools: vec!["read_file".into(), "write_file".into(), "finish".into()],
        limits: Limits::default(),
        deliverable: DeliverableSpec {
            path: "synthese.md".into(),
            min_bytes: 10,
            max_bytes: 1000,
            must_cite_inputs: true,
        },
    }
}

fn ev(seq: u64, kind: EventKind) -> Event {
    Event {
        v: EVENT_VERSION,
        mission: MissionId("m-test".into()),
        seq,
        at_ms: seq,
        kind,
    }
}

fn base() -> Vec<Event> {
    vec![
        ev(1, EventKind::MissionCreated { spec: spec() }),
        ev(2, EventKind::MissionStarted { attempt: 1 }),
    ]
}

fn started(seq: u64, id: &str, tool: &str, effect: Effect) -> Event {
    ev(
        seq,
        EventKind::ToolStarted {
            call_id: id.into(),
            tool: tool.into(),
            effect,
        },
    )
}

#[test]
fn c02_ecriture_commencee_sans_resultat_est_incertaine_sans_rejeu() {
    let mut e = base();
    e.push(started(3, "c1", "write_file", Effect::WorkspaceWrite));
    let p = project(&e).unwrap();
    assert_eq!(p.state, MissionState::Uncertain);
    assert_eq!(p.uncertain.len(), 1);
    assert!(p.replayable.is_empty());
    assert_eq!(p.state.exit_code(), 3);
}

#[test]
fn c02_lecture_commencee_sans_resultat_est_rejouable() {
    let mut e = base();
    e.push(started(3, "c1", "read_file", Effect::ReadOnly));
    let p = project(&e).unwrap();
    assert_eq!(p.state, MissionState::Running);
    assert_eq!(p.replayable.len(), 1);
    assert!(p.uncertain.is_empty());
}

#[test]
fn c02_resolution_humaine_leve_l_incertitude() {
    let mut e = base();
    e.push(started(3, "c1", "write_file", Effect::WorkspaceWrite));
    e.push(ev(
        4,
        EventKind::Resolved {
            call_id: "c1".into(),
            by: "thibaud".into(),
            resolution: Resolution::NotDone,
        },
    ));
    let p = project(&e).unwrap();
    assert_eq!(p.state, MissionState::Running);
    assert!(p.uncertain.is_empty());
}

#[test]
fn c02_effet_termine_n_est_pas_rejoue() {
    let mut e = base();
    e.push(started(3, "c1", "write_file", Effect::WorkspaceWrite));
    e.push(ev(
        4,
        EventKind::ToolFinished {
            call_id: "c1".into(),
            outcome: ToolOutcome::Ok {
                output: json!({"bytes": 3}),
            },
        },
    ));
    let p = project(&e).unwrap();
    assert!(p.uncertain.is_empty() && p.replayable.is_empty());
    assert!(p.finished_calls["c1"].is_ok());
}

#[test]
fn c02_ligne_finale_tronquee_toleree_ligne_interne_refusee() {
    let lines: Vec<String> = base()
        .iter()
        .map(|e| serde_json::to_string(e).unwrap())
        .collect();
    let ok = format!("{}\n{}\n{{\"v\":1,\"miss", lines[0], lines[1]);
    let d = decode_journal(&ok).unwrap();
    assert!(d.truncated_tail);
    assert_eq!(d.events.len(), 2);
    let bad = format!("{}\n{{casse}}\n{}\n", lines[0], lines[1]);
    assert_eq!(decode_journal(&bad), Err(JournalError::Corrupt { line: 2 }));
}

#[test]
fn c02_sequence_et_version_controlees() {
    let mut e = base();
    e[1].seq = 5;
    let text: String = e
        .iter()
        .map(|e| serde_json::to_string(e).unwrap() + "\n")
        .collect();
    assert!(matches!(
        decode_journal(&text),
        Err(JournalError::Sequence { .. })
    ));
    let mut e = base();
    e[1].v = 2;
    let text: String = e
        .iter()
        .map(|e| serde_json::to_string(e).unwrap() + "\n")
        .collect();
    assert_eq!(
        decode_journal(&text),
        Err(JournalError::Version { found: 2 })
    );
}

#[test]
fn c02_premier_evenement_doit_creer_la_mission() {
    let e = vec![ev(1, EventKind::MissionStarted { attempt: 1 })];
    assert_eq!(project(&e), Err(JournalError::MissingCreation));
}

#[test]
fn c02_format_evenement_stable() {
    let e = ev(
        2,
        EventKind::PolicyDecided {
            call_id: "c1".into(),
            tool: "write_file".into(),
            decision: Decision::Deny {
                rule: "workspace-only".into(),
                reason: "hors périmètre".into(),
            },
        },
    );
    let v = serde_json::to_value(&e).unwrap();
    assert_eq!(
        v,
        json!({"v":1,"mission":"m-test","seq":2,"at_ms":2,"kind":{"type":"policy_decided","call_id":"c1","tool":"write_file","decision":{"decision":"deny","rule":"workspace-only","reason":"hors périmètre"}}})
    );
}

#[test]
fn c03_erreurs_retentables_bornees_aux_transitoires() {
    assert!(ModelError::Timeout.is_retryable());
    assert!(ModelError::RateLimited.is_retryable());
    assert!(ModelError::Provider {
        status: 503,
        message: String::new()
    }
    .is_retryable());
    assert!(!ModelError::Auth.is_retryable());
    assert!(!ModelError::Provider {
        status: 400,
        message: String::new()
    }
    .is_retryable());
    assert!(!ModelError::InvalidResponse {
        message: String::new()
    }
    .is_retryable());
}

#[test]
fn c04_erreur_d_outil_n_est_pas_un_succes() {
    let o = ToolOutcome::Err {
        kind: ToolErrorKind::Denied,
        message: "x".into(),
    };
    assert!(!o.is_ok());
}

#[test]
fn c05_refus_par_defaut_ne_produit_aucune_invocation() {
    struct DenyAll;
    impl Policy for DenyAll {
        fn decide(&self, _: &MissionSpec, _: &ToolCall, _: Effect) -> Decision {
            Decision::Deny {
                rule: "default".into(),
                reason: "refus par défaut".into(),
            }
        }
    }
    struct Counting(std::cell::Cell<u32>);
    impl Tool for Counting {
        fn spec(&self) -> ToolSpec {
            ToolSpec {
                name: "write_file".into(),
                description: String::new(),
                parameters: json!({}),
                effect: Effect::WorkspaceWrite,
            }
        }
        fn execute(&self, _: &serde_json::Value, _: &ToolContext) -> ToolOutcome {
            self.0.set(self.0.get() + 1);
            ToolOutcome::Ok {
                output: json!(null),
            }
        }
    }
    let tool = Counting(std::cell::Cell::new(0));
    let call = ToolCall {
        id: "c1".into(),
        name: "write_file".into(),
        arguments: json!({}),
    };
    // Règle de contrat : on n'invoque que sur Allow.
    let d = DenyAll.decide(&spec(), &call, tool.spec().effect);
    if d.is_allow() {
        tool.execute(
            &call.arguments,
            &ToolContext {
                input_dirs: vec![],
                workspace: "/ws".into(),
            },
        );
    }
    assert_eq!(tool.0.get(), 0);
}

#[test]
fn c01_c07_etats_terminaux_et_codes_de_sortie() {
    assert!(MissionState::Completed.is_terminal());
    assert!(!MissionState::Uncertain.is_terminal());
    assert_eq!(MissionState::Completed.exit_code(), 0);
    assert_eq!(MissionState::Failed.exit_code(), 2);
    assert_eq!(MissionState::Cancelled.exit_code(), 4);
}

#[test]
fn c06_limites_par_defaut() {
    let l = Limits::default();
    assert_eq!(l.max_iterations, 20);
    assert_eq!(l.max_cost_microusd, 500_000);
}
