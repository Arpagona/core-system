const list = document.querySelector("#missions");
const journal = document.querySelector("#journal");
const status = document.querySelector("#status");
const openCode = document.querySelector("#opencode");
const states = {
  pending: "En attente", queued: "En attente", created: "Créée", running: "En cours",
  completed: "Terminée", failed: "En échec", uncertain: "À vérifier",
  cancelled: "Annulée", unreadable: "Journal illisible",
};
let selected;

async function read(path) {
  const response = await fetch(path);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error);
  return data;
}

async function showLog(mission, button) {
  selected = mission.id;
  for (const row of list.querySelectorAll("button")) {
    row.setAttribute("aria-pressed", String(row === button));
  }
  journal.textContent = "Chargement…";
  try {
    const data = await read("/api/missions/" + encodeURIComponent(mission.id) + "/log");
    if (selected === mission.id) journal.textContent = data.log || "Journal vide.";
  } catch (error) {
    if (selected === mission.id) journal.textContent = error.message;
  }
}

async function refresh() {
  status.textContent = "Chargement…";
  try {
    const missions = await read("/api/missions");
    list.replaceChildren();
    status.textContent = missions.length ? "" : "Aucune mission enregistrée.";
    for (const mission of missions) {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = mission.goal || mission.id;
      button.setAttribute("aria-pressed", "false");
      const state = document.createElement("small");
      state.textContent = (states[mission.state] || mission.state)
        + (mission.truncated ? " · dernière ligne tronquée" : "");
      button.append(state);
      button.addEventListener("click", () => showLog(mission, button));
      item.append(button);
      list.append(item);
      if (selected === mission.id) showLog(mission, button);
    }
    if (!missions.some((mission) => mission.id === selected)) {
      selected = undefined;
      journal.textContent = "Sélectionne une mission pour consulter son journal.";
    }
  } catch (error) {
    status.textContent = error.message;
  }
  try {
    const result = await read("/api/opencode");
    openCode.textContent = result.available ? "OpenCode · Détecté" : "OpenCode · Non détecté";
  } catch {
    openCode.textContent = "OpenCode · Statut indisponible";
  }
}

document.querySelector("#refresh").addEventListener("click", refresh);
refresh();
