//! Contrats communs M0 d'ARPAGONA Agent Core (C-01 … C-07).
//!
//! STATUT : PROPOSÉ, non approuvé à trois. Voir `docs/contrats/M0-CONTRATS.md`.
//! Toute modification publique de ce fichier est une modification de contrat commun.

use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeMap;
use std::path::PathBuf;

/// Version du format d'événement (C-02).
pub const EVENT_VERSION: u32 = 1;

// ---------------------------------------------------------------- C-01 Mission

/// Identifiant de mission, unique et jamais réutilisé.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct MissionId(pub String);

impl std::fmt::Display for MissionId {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

/// C-01 : description complète et figée d'une mission.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MissionSpec {
    pub id: MissionId,
    pub goal: String,
    /// Dossiers en lecture seule (chemins absolus canoniques).
    pub input_dirs: Vec<PathBuf>,
    /// Seul répertoire inscriptible.
    pub workspace: PathBuf,
    /// Outils autorisés pour cette mission.
    pub tools: Vec<String>,
    pub limits: Limits,
    pub deliverable: DeliverableSpec,
}

/// C-01 : attentes vérifiables sur le livrable.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DeliverableSpec {
    /// Chemin relatif au workspace.
    pub path: String,
    pub min_bytes: u64,
    pub max_bytes: u64,
    pub must_cite_inputs: bool,
}

/// C-01 : états de mission.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MissionState {
    Queued,
    Running,
    Completed,
    Failed,
    Cancelled,
    Uncertain,
}

impl MissionState {
    pub fn is_terminal(self) -> bool {
        matches!(self, Self::Completed | Self::Failed | Self::Cancelled)
    }
    /// Code de sortie CLI (C-07).
    pub fn exit_code(self) -> i32 {
        match self {
            Self::Completed => 0,
            Self::Failed => 2,
            Self::Uncertain => 3,
            Self::Cancelled => 4,
            Self::Queued | Self::Running => 1,
        }
    }
}

// ---------------------------------------------------------------- C-03 Modèle

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Role {
    System,
    User,
    Assistant,
    Tool,
}

/// Message de conversation transmis au modèle.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Message {
    pub role: Role,
    pub content: Option<String>,
    /// Appels d'outil proposés (rôle assistant).
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub tool_calls: Vec<ToolCall>,
    /// Appel auquel répond ce message (rôle tool).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tool_call_id: Option<String>,
}

/// Proposition d'appel d'outil émise par le modèle. N'autorise rien (C-05).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ToolCall {
    pub id: String,
    pub name: String,
    pub arguments: Value,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct Usage {
    pub input_tokens: u64,
    pub output_tokens: u64,
}

impl Usage {
    pub fn total(&self) -> u64 {
        self.input_tokens + self.output_tokens
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FinishReason {
    Stop,
    ToolCalls,
    Length,
    Other,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ModelRequest {
    pub messages: Vec<Message>,
    pub tools: Vec<ToolSpec>,
    pub max_output_tokens: u32,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ModelResponse {
    pub text: Option<String>,
    pub tool_calls: Vec<ToolCall>,
    pub usage: Usage,
    pub finish: FinishReason,
}

/// C-03 : erreurs du fournisseur, jamais confondues avec une réponse.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", tag = "type")]
pub enum ModelError {
    Timeout,
    Transport { message: String },
    Auth,
    RateLimited,
    Provider { status: u16, message: String },
    InvalidResponse { message: String },
}

impl ModelError {
    /// Indique une erreur transitoire. Le noyau ne retente pas les appels modèle.
    pub fn is_retryable(&self) -> bool {
        matches!(
            self,
            Self::Timeout | Self::Transport { .. } | Self::RateLimited
        ) || matches!(self, Self::Provider { status, .. } if *status >= 500)
    }
}

/// C-03 : port unique vers un modèle de langage.
pub trait ModelPort {
    fn complete(&self, req: &ModelRequest) -> Result<ModelResponse, ModelError>;
}

// ---------------------------------------------------------------- C-04 Outils

/// Classe d'effet d'un outil : détermine la règle de reprise (C-02).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Effect {
    ReadOnly,
    WorkspaceWrite,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ToolSpec {
    pub name: String,
    pub description: String,
    /// Schéma JSON des paramètres.
    pub parameters: Value,
    pub effect: Effect,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ToolErrorKind {
    InvalidArguments,
    NotFound,
    Denied,
    TooLarge,
    Io,
    Timeout,
}

/// C-04 : résultat d'outil. Une erreur n'est jamais un succès.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", tag = "status")]
pub enum ToolOutcome {
    Ok {
        output: Value,
    },
    Err {
        kind: ToolErrorKind,
        message: String,
    },
}

impl ToolOutcome {
    pub fn is_ok(&self) -> bool {
        matches!(self, Self::Ok { .. })
    }
}

/// Contexte d'exécution fourni par le noyau à l'outil.
#[derive(Debug, Clone)]
pub struct ToolContext {
    pub input_dirs: Vec<PathBuf>,
    pub workspace: PathBuf,
}

/// C-04 : outil exécutable.
pub trait Tool {
    fn spec(&self) -> ToolSpec;
    fn execute(&self, args: &Value, ctx: &ToolContext) -> ToolOutcome;
}

// ---------------------------------------------------------------- C-05 Politique

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", tag = "decision")]
pub enum Decision {
    Allow { rule: String },
    Deny { rule: String, reason: String },
}

impl Decision {
    pub fn is_allow(&self) -> bool {
        matches!(self, Self::Allow { .. })
    }
}

/// C-05 : refus par défaut ; une décision est requise avant tout effet.
pub trait Policy {
    fn decide(&self, spec: &MissionSpec, call: &ToolCall, effect: Effect) -> Decision;
}

// ---------------------------------------------------------------- C-06 Limites

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Limits {
    pub max_iterations: u32,
    pub max_tool_calls: u32,
    pub max_wall_seconds: u64,
    pub max_total_tokens: u64,
    /// Coût estimé maximal, en micro-dollars.
    pub max_cost_microusd: u64,
}

impl Default for Limits {
    fn default() -> Self {
        Self {
            max_iterations: 20,
            max_tool_calls: 60,
            max_wall_seconds: 600,
            max_total_tokens: 200_000,
            max_cost_microusd: 500_000,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LimitKind {
    Iterations,
    ToolCalls,
    WallTime,
    Tokens,
    Cost,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", tag = "type")]
pub enum FailureReason {
    LimitExceeded { limit: LimitKind },
    Model { error: ModelError },
    DeliverableRejected { problems: Vec<String> },
    NoFinish,
    Internal { message: String },
}

// ---------------------------------------------------------------- C-02 Journal

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Resolution {
    /// L'humain constate que l'effet a eu lieu.
    Done,
    /// L'humain constate que l'effet n'a pas eu lieu.
    NotDone,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DeliverableReport {
    pub path: String,
    pub ok: bool,
    pub bytes: u64,
    pub problems: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", tag = "type")]
pub enum EventKind {
    MissionCreated {
        spec: MissionSpec,
    },
    MissionStarted {
        attempt: u32,
    },
    ModelCalled {
        iteration: u32,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        reserved_cost_microusd: Option<u64>,
    },
    ModelReplied {
        iteration: u32,
        usage: Usage,
        cost_microusd: u64,
        text: Option<String>,
        tool_calls: Vec<ToolCall>,
    },
    ModelFailed {
        iteration: u32,
        error: ModelError,
    },
    PolicyDecided {
        call_id: String,
        tool: String,
        decision: Decision,
    },
    /// Écrit et synchronisé AVANT l'effet.
    ToolStarted {
        call_id: String,
        tool: String,
        effect: Effect,
    },
    /// Écrit APRÈS l'effet.
    ToolFinished {
        call_id: String,
        outcome: ToolOutcome,
    },
    DeliverableChecked {
        report: DeliverableReport,
    },
    Resolved {
        call_id: String,
        by: String,
        resolution: Resolution,
    },
    MissionEnded {
        state: MissionState,
        reason: Option<FailureReason>,
        summary: Option<String>,
    },
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Event {
    pub v: u32,
    pub mission: MissionId,
    pub seq: u64,
    pub at_ms: u64,
    pub kind: EventKind,
}

/// Appel d'outil dont l'issue n'est pas journalisée.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PendingCall {
    pub call_id: String,
    pub tool: String,
    pub effect: Effect,
}

/// C-02 : état projeté depuis le journal, seule source de l'état.
#[derive(Debug, Clone, PartialEq)]
pub struct Projection {
    pub spec: Option<MissionSpec>,
    pub state: MissionState,
    pub attempts: u32,
    pub iterations: u32,
    pub tool_calls: u32,
    pub usage: Usage,
    pub cost_microusd: u64,
    /// Effets d'écriture commencés sans résultat ni résolution : bloquent la reprise.
    pub uncertain: Vec<PendingCall>,
    /// Lectures commencées sans résultat : réexécutables.
    pub replayable: Vec<PendingCall>,
    pub finished_calls: BTreeMap<String, ToolOutcome>,
    pub reason: Option<FailureReason>,
    pub summary: Option<String>,
    pub last_seq: u64,
}

/// Erreurs de lecture du journal.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum JournalError {
    /// Ligne invalide qui n'est pas la dernière : journal corrompu.
    Corrupt { line: usize },
    /// Numéro de séquence non contigu.
    Sequence { expected: u64, found: u64 },
    /// Version d'événement inconnue.
    Version { found: u32 },
    /// Premier événement différent de `MissionCreated`.
    MissingCreation,
}

/// Résultat du décodage d'un journal JSONL.
#[derive(Debug, Clone, PartialEq)]
pub struct DecodedJournal {
    pub events: Vec<Event>,
    /// Vrai si une dernière ligne tronquée a été ignorée.
    pub truncated_tail: bool,
}

/// C-02 : décode un journal JSONL. Seule une dernière ligne invalide est tolérée.
pub fn decode_journal(text: &str) -> Result<DecodedJournal, JournalError> {
    let lines: Vec<&str> = text.split('\n').collect();
    let mut events = Vec::new();
    let mut truncated_tail = false;
    let last_non_empty = lines.iter().rposition(|l| !l.trim().is_empty());
    for (i, line) in lines.iter().enumerate() {
        if line.trim().is_empty() {
            continue;
        }
        match serde_json::from_str::<Event>(line) {
            Ok(ev) => {
                if ev.v != EVENT_VERSION {
                    return Err(JournalError::Version { found: ev.v });
                }
                let expected = events.len() as u64 + 1;
                if ev.seq != expected {
                    return Err(JournalError::Sequence {
                        expected,
                        found: ev.seq,
                    });
                }
                events.push(ev);
            }
            Err(_) if Some(i) == last_non_empty && !text.ends_with('\n') => {
                truncated_tail = true;
            }
            Err(_) => return Err(JournalError::Corrupt { line: i + 1 }),
        }
    }
    Ok(DecodedJournal {
        events,
        truncated_tail,
    })
}

/// C-02 : projette l'état d'une mission depuis ses événements.
pub fn project(events: &[Event]) -> Result<Projection, JournalError> {
    let mut p = Projection {
        spec: None,
        state: MissionState::Queued,
        attempts: 0,
        iterations: 0,
        tool_calls: 0,
        usage: Usage::default(),
        cost_microusd: 0,
        uncertain: Vec::new(),
        replayable: Vec::new(),
        finished_calls: BTreeMap::new(),
        reason: None,
        summary: None,
        last_seq: 0,
    };
    let mut started: BTreeMap<String, PendingCall> = BTreeMap::new();
    let mut resolved: BTreeMap<String, Resolution> = BTreeMap::new();
    for (i, ev) in events.iter().enumerate() {
        p.last_seq = ev.seq;
        match &ev.kind {
            EventKind::MissionCreated { spec } if i == 0 => p.spec = Some(spec.clone()),
            _ if i == 0 => return Err(JournalError::MissingCreation),
            EventKind::MissionCreated { .. } => return Err(JournalError::Corrupt { line: i + 1 }),
            EventKind::MissionStarted { attempt } => {
                p.attempts = *attempt;
                if !p.state.is_terminal() {
                    p.state = MissionState::Running;
                }
            }
            EventKind::ModelCalled { iteration, .. } => p.iterations = p.iterations.max(*iteration),
            EventKind::ModelReplied {
                usage,
                cost_microusd,
                ..
            } => {
                p.usage.input_tokens += usage.input_tokens;
                p.usage.output_tokens += usage.output_tokens;
                p.cost_microusd += cost_microusd;
            }
            EventKind::ModelFailed { .. } | EventKind::PolicyDecided { .. } => {}
            EventKind::ToolStarted {
                call_id,
                tool,
                effect,
            } => {
                p.tool_calls += 1;
                started.insert(
                    call_id.clone(),
                    PendingCall {
                        call_id: call_id.clone(),
                        tool: tool.clone(),
                        effect: *effect,
                    },
                );
            }
            EventKind::ToolFinished { call_id, outcome } => {
                started.remove(call_id);
                p.finished_calls.insert(call_id.clone(), outcome.clone());
            }
            EventKind::DeliverableChecked { .. } => {}
            EventKind::Resolved {
                call_id,
                resolution,
                ..
            } => {
                started.remove(call_id);
                resolved.insert(call_id.clone(), *resolution);
            }
            EventKind::MissionEnded {
                state,
                reason,
                summary,
            } => {
                p.state = *state;
                p.reason = reason.clone();
                p.summary = summary.clone();
            }
        }
    }
    if p.spec.is_none() {
        return Err(JournalError::MissingCreation);
    }
    for call in started.into_values() {
        match call.effect {
            Effect::ReadOnly => p.replayable.push(call),
            Effect::WorkspaceWrite => p.uncertain.push(call),
        }
    }
    if !p.uncertain.is_empty() && !p.state.is_terminal() {
        p.state = MissionState::Uncertain;
    }
    Ok(p)
}
