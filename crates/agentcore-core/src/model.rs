//! Adaptateurs du port modèle (C-03) : OpenAI-compatible (réel) et scripté (tests).

use agentcore_types::{
    FinishReason, Message, ModelError, ModelPort, ModelRequest, ModelResponse, Role, ToolCall,
    Usage,
};
use serde_json::{json, Value};
use std::sync::Mutex;
use std::time::Duration;

/// Adaptateur `/chat/completions` avec appels d'outils.
pub struct OpenAiCompatible {
    pub base_url: String,
    pub model: String,
    api_key: String,
    agent: ureq::Agent,
}

impl OpenAiCompatible {
    pub fn new(base_url: &str, model: &str, api_key: String, timeout_s: u64) -> Self {
        let agent: ureq::Agent = ureq::Agent::config_builder()
            .timeout_global(Some(Duration::from_secs(timeout_s)))
            .http_status_as_error(false)
            .build()
            .into();
        Self {
            base_url: base_url.trim_end_matches('/').to_string(),
            model: model.to_string(),
            api_key,
            agent,
        }
    }
}

fn role(r: Role) -> &'static str {
    match r {
        Role::System => "system",
        Role::User => "user",
        Role::Assistant => "assistant",
        Role::Tool => "tool",
    }
}

pub fn to_wire(m: &Message) -> Value {
    let mut v = json!({"role": role(m.role), "content": m.content});
    if !m.tool_calls.is_empty() {
        v["tool_calls"] = m
            .tool_calls
            .iter()
            .map(|c| json!({"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments.to_string()}}))
            .collect();
    }
    if let Some(id) = &m.tool_call_id {
        v["tool_call_id"] = json!(id);
    }
    v
}

pub fn parse_response(body: &Value) -> Result<ModelResponse, ModelError> {
    let bad = |m: &str| ModelError::InvalidResponse {
        message: m.to_string(),
    };
    let choice = body
        .get("choices")
        .and_then(|c| c.get(0))
        .ok_or_else(|| bad("champ choices absent"))?;
    let msg = choice.get("message").ok_or_else(|| bad("message absent"))?;
    let text = msg
        .get("content")
        .and_then(Value::as_str)
        .filter(|s| !s.trim().is_empty())
        .map(str::to_string);
    let mut tool_calls = Vec::new();
    if let Some(calls) = msg.get("tool_calls").and_then(Value::as_array) {
        for c in calls {
            let id = c
                .get("id")
                .and_then(Value::as_str)
                .ok_or_else(|| bad("tool_call sans id"))?;
            let f = c
                .get("function")
                .ok_or_else(|| bad("tool_call sans function"))?;
            let name = f
                .get("name")
                .and_then(Value::as_str)
                .ok_or_else(|| bad("function sans nom"))?;
            let raw = f.get("arguments").and_then(Value::as_str).unwrap_or("{}");
            // Arguments non JSON : transmis tels quels, l'outil les refusera proprement.
            let arguments = serde_json::from_str(if raw.trim().is_empty() { "{}" } else { raw })
                .unwrap_or_else(|_| json!({"_raw_invalide": raw}));
            tool_calls.push(ToolCall {
                id: id.to_string(),
                name: name.to_string(),
                arguments,
            });
        }
    }
    let usage = body.get("usage");
    let get = |k: &str| {
        usage
            .and_then(|u| u.get(k))
            .and_then(Value::as_u64)
            .unwrap_or(0)
    };
    let finish = match choice.get("finish_reason").and_then(Value::as_str) {
        Some("stop") => FinishReason::Stop,
        Some("tool_calls") => FinishReason::ToolCalls,
        Some("length") => FinishReason::Length,
        _ => FinishReason::Other,
    };
    Ok(ModelResponse {
        text,
        tool_calls,
        usage: Usage {
            input_tokens: get("prompt_tokens"),
            output_tokens: get("completion_tokens"),
        },
        finish,
    })
}

impl ModelPort for OpenAiCompatible {
    fn complete(&self, req: &ModelRequest) -> Result<ModelResponse, ModelError> {
        let tools: Vec<Value> = req
            .tools
            .iter()
            .map(|t| json!({"type":"function","function":{"name":t.name,"description":t.description,"parameters":t.parameters}}))
            .collect();
        let body = json!({
            "model": self.model,
            "messages": req.messages.iter().map(to_wire).collect::<Vec<_>>(),
            "tools": tools,
            "tool_choice": "auto",
            "max_tokens": req.max_output_tokens,
        });
        let url = format!("{}/chat/completions", self.base_url);
        let resp = self
            .agent
            .post(&url)
            .header("Authorization", &format!("Bearer {}", self.api_key))
            .header("Content-Type", "application/json")
            .send(body.to_string().as_bytes());
        let mut resp = match resp {
            Ok(r) => r,
            Err(ureq::Error::Timeout(_)) => return Err(ModelError::Timeout),
            Err(e) => {
                return Err(ModelError::Transport {
                    message: e.to_string(),
                })
            }
        };
        let status = resp.status().as_u16();
        let text = resp
            .body_mut()
            .with_config()
            .limit(16 * 1024 * 1024)
            .read_to_string()
            .map_err(|e| match e {
                ureq::Error::Timeout(_) => ModelError::Timeout,
                e => ModelError::Transport {
                    message: e.to_string(),
                },
            })?;
        match status {
            200..=299 => {}
            401 | 403 => return Err(ModelError::Auth),
            429 => return Err(ModelError::RateLimited),
            s => {
                let mut message: String = text.chars().take(300).collect();
                message = message.replace(&self.api_key, "***");
                return Err(ModelError::Provider { status: s, message });
            }
        }
        let v: Value = serde_json::from_str(&text).map_err(|e| ModelError::InvalidResponse {
            message: format!("JSON invalide : {e}"),
        })?;
        parse_response(&v)
    }
}

/// Modèle scripté pour les tests : renvoie les réponses dans l'ordre.
pub struct ScriptedModel {
    script: Mutex<Vec<Result<ModelResponse, ModelError>>>,
    pub calls: Mutex<u32>,
}

impl ScriptedModel {
    pub fn new(mut script: Vec<Result<ModelResponse, ModelError>>) -> Self {
        script.reverse();
        Self {
            script: Mutex::new(script),
            calls: Mutex::new(0),
        }
    }
}

impl ModelPort for ScriptedModel {
    fn complete(&self, _req: &ModelRequest) -> Result<ModelResponse, ModelError> {
        *self.calls.lock().expect("verrou") += 1;
        self.script
            .lock()
            .expect("verrou")
            .pop()
            .unwrap_or(Err(ModelError::InvalidResponse {
                message: "script épuisé".into(),
            }))
    }
}
