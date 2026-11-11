//! Journal append-only d'une mission (C-02) : une ligne JSON par événement, fsync à chaque écriture.

use agentcore_types::{
    decode_journal, project, Event, EventKind, MissionId, Projection, EVENT_VERSION,
};
use std::fs::{self, File, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

pub fn now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

#[derive(Debug)]
pub enum StoreError {
    Io(String),
    Journal(String),
    Locked,
    NotFound(String),
}

impl std::fmt::Display for StoreError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Io(m) => write!(f, "erreur d'entrée/sortie : {m}"),
            Self::Journal(m) => write!(f, "journal invalide : {m}"),
            Self::Locked => write!(
                f,
                "mission déjà en cours d'exécution par un autre processus"
            ),
            Self::NotFound(m) => write!(f, "mission introuvable : {m}"),
        }
    }
}

impl From<std::io::Error> for StoreError {
    fn from(e: std::io::Error) -> Self {
        Self::Io(e.to_string())
    }
}

/// Répertoire d'une mission sous le répertoire d'état.
pub fn mission_dir(state_dir: &Path, id: &MissionId) -> PathBuf {
    state_dir.join("missions").join(&id.0)
}

/// Lecture seule : événements et projection.
pub fn load(dir: &Path) -> Result<(Vec<Event>, Projection, bool), StoreError> {
    let path = dir.join("journal.jsonl");
    let text = fs::read_to_string(&path)
        .map_err(|e| StoreError::NotFound(format!("{} ({e})", path.display())))?;
    let decoded = decode_journal(&text).map_err(|e| StoreError::Journal(format!("{e:?}")))?;
    let proj = project(&decoded.events).map_err(|e| StoreError::Journal(format!("{e:?}")))?;
    Ok((decoded.events, proj, decoded.truncated_tail))
}

/// Journal ouvert en écriture, protégé par un verrou exclusif.
pub struct Journal {
    pub dir: PathBuf,
    mission: MissionId,
    file: File,
    seq: u64,
    _lock: File,
    pub events: Vec<Event>,
    /// Affiche chaque événement sur la sortie d'erreur (suivi en direct).
    pub echo: bool,
}

fn lock(dir: &Path) -> Result<File, StoreError> {
    let f = OpenOptions::new()
        .create(true)
        .truncate(false)
        .write(true)
        .open(dir.join("lock"))?;
    match f.try_lock() {
        Ok(()) => Ok(f),
        Err(std::fs::TryLockError::WouldBlock) => Err(StoreError::Locked),
        Err(std::fs::TryLockError::Error(e)) => Err(e.into()),
    }
}

impl Journal {
    /// Crée une mission neuve. Échoue si le répertoire existe déjà.
    pub fn create(
        state_dir: &Path,
        created: EventKind,
        id: &MissionId,
    ) -> Result<Self, StoreError> {
        let dir = mission_dir(state_dir, id);
        fs::create_dir_all(dir.parent().unwrap_or(state_dir))?;
        fs::create_dir(&dir)?;
        let lk = lock(&dir)?;
        let file = OpenOptions::new()
            .create_new(true)
            .append(true)
            .open(dir.join("journal.jsonl"))?;
        if let Some(parent) = dir.parent() {
            File::open(parent)?.sync_all()?;
        }
        let mut j = Self {
            dir,
            mission: id.clone(),
            file,
            seq: 0,
            _lock: lk,
            events: Vec::new(),
            echo: false,
        };
        j.append(created)?;
        Ok(j)
    }

    /// Rouvre une mission existante pour reprise. Une ligne finale tronquée est retirée.
    pub fn reopen(state_dir: &Path, id: &MissionId) -> Result<Self, StoreError> {
        let dir = mission_dir(state_dir, id);
        if !dir.is_dir() {
            return Err(StoreError::NotFound(id.0.clone()));
        }
        let lk = lock(&dir)?;
        let path = dir.join("journal.jsonl");
        let text = fs::read_to_string(&path)?;
        let decoded = decode_journal(&text).map_err(|e| StoreError::Journal(format!("{e:?}")))?;
        if decoded.truncated_tail {
            // Conserve la trace de la ligne tronquée hors du journal, puis la retire.
            let keep = text.rfind('\n').map(|i| i + 1).unwrap_or(0);
            fs::write(
                dir.join(format!("journal.truncated.{}", now_ms())),
                &text[keep..],
            )?;
            let f = OpenOptions::new().write(true).open(&path)?;
            f.set_len(keep as u64)?;
            f.sync_all()?;
        }
        let file = OpenOptions::new().append(true).open(&path)?;
        Ok(Self {
            dir,
            mission: id.clone(),
            file,
            seq: decoded.events.len() as u64,
            _lock: lk,
            events: decoded.events,
            echo: false,
        })
    }

    pub fn append(&mut self, kind: EventKind) -> Result<&Event, StoreError> {
        let ev = Event {
            v: EVENT_VERSION,
            mission: self.mission.clone(),
            seq: self.seq + 1,
            at_ms: now_ms(),
            kind,
        };
        let mut line = serde_json::to_string(&ev).map_err(|e| StoreError::Io(e.to_string()))?;
        line.push('\n');
        self.file.write_all(line.as_bytes())?;
        self.file.sync_data()?;
        self.seq += 1;
        if self.echo {
            eprintln!("  [{:>3}] {}", ev.seq, crate::describe(&ev.kind));
        }
        self.events.push(ev);
        Ok(self.events.last().expect("événement ajouté"))
    }

    pub fn projection(&self) -> Result<Projection, StoreError> {
        project(&self.events).map_err(|e| StoreError::Journal(format!("{e:?}")))
    }
}
