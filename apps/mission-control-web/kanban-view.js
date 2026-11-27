"use strict";
// Présentation seulement : aucun changement de statut ou de droit ici.
const KanbanView = (() => {
  const labels = {triage:"À trier",todo:"À faire",ready:"Prête",running:"En cours",blocked:"Bloquée",scheduled:"Planifiée",review:"À vérifier",done:"Terminée"};
  const fold = value => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("fr").trim();
  function filter(tasks, {scope="all", login="", query="", showDone=false}={}) {
    const words = fold(query).split(/\s+/).filter(Boolean);
    return tasks.filter(card => {
      if (card.status === "archived" || (!showDone && card.status === "done")) return false;
      if (scope === "mine" && card.assignee !== login) return false;
      if (scope === "unassigned" && card.assignee) return false;
      const text = fold([card.title, card.body, card.assignee, card.id].join(" "));
      return words.every(word => text.includes(word));
    });
  }
  function order(tasks) {
    const rank = {blocked:0,review:1,running:2,ready:3,triage:4,todo:4,scheduled:5,done:6};
    return [...tasks].sort((a,b) => (Number(b.priority)||0)-(Number(a.priority)||0) || (rank[a.status]??7)-(rank[b.status]??7));
  }
  return {filter,order,fold,label:status=>labels[status] || status || "État inconnu"};
})();
if (typeof module !== "undefined" && module.exports) module.exports = KanbanView;
