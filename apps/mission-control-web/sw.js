"use strict";
// Service worker de l'application installable (PWA).
// Règle : aucune donnée de l'API n'est mise en cache. Seule une page « hors ligne »
// statique est gardée, pour afficher un message clair quand le tunnel est coupé.
const CACHE = "arpagona-mc-v1";
const OFFLINE = "/offline.html";
const SHELL = [OFFLINE, "/icon-192.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  // Seules les navigations (ouverture de page) ont un repli ; tout le reste passe directement au réseau.
  if (req.mode !== "navigate") return;
  event.respondWith(fetch(req).catch(() => caches.match(OFFLINE)));
});
