// Horloge du bandeau + croix de fermeture (visible seulement dans le kiosque iMac).
(function () {
  var c = document.getElementById("clock");
  function tick() {
    var d = new Date();
    c.textContent = d.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" }) +
      " · " + d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  }
  tick(); setInterval(tick, 10000);
  var x = document.getElementById("kiosk-close");
  if (location.port === "18710") {
    x.hidden = false;
    x.addEventListener("click", function () {
      if (!confirm("Fermer Agent Core et revenir au bureau ?")) return;
      fetch("/api/kiosk/close", { method: "POST", headers: { "X-Gona": "1", "Content-Type": "application/json" }, body: "{}" });
    });
  }
})();
