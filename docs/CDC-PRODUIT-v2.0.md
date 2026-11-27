# ARPAGONA Agent Core — Cahier des charges produit

**Référence :** ARP-PROD-CDC-002
**Version :** 2.0 — 27 novembre 2026
**Remplace :** ARP-DEV-CDC-001 v1.1 (11/11/2026, caduc — voir §1)
**Commanditaire :** Thibaud, ARPAGONA
**Rédaction :** GONA (profil `gpt5`)
**Statut :** proposition à valider par Thibaud. Les décisions marquées **[À VALIDER]** ne sont pas engageantes.
**Périmètre du document :** le produit vendu au client et sa beta. Pas l'atelier de développement, pas le marketing.

---

## 0. Résumé exécutif

**Ce qu'on vend.** Un copilote de direction pour PME industrielle française. Il lit le contexte de l'entreprise, prépare des livrables (relance, devis, compte rendu, plan d'action), et **ne fait rien d'irréversible sans un clic humain**. Chaque action laisse une trace vérifiable.

**Ce qu'on ne vend pas.** Une plateforme de données industrielles, un moteur agentique, un chatbot généraliste.

**Pourquoi maintenant.** Les grands acteurs industriels (Cognite, Palantir) vendent des plateformes de données à des groupes, sur devis, avec des mois d'intégration. Une PME de 20 à 200 personnes n'a ni les données structurées, ni l'équipe, ni le budget. Elle a un dirigeant qui perd des engagements dans WhatsApp, un carnet de commandes dans un tableur et aucune trace de ses décisions.

**La beta.** Interne : Thibaud et Maël, données fictives, banc Atlas. Elle est réussie quand les 12 portes du §12 sont franchies avec preuve outil, pas quand la démo plaît.

**Écarts constatés au 27/11/2026** (détail et preuves dans `reports/2026-11-27-audit-beta-agent-core.md`) : le produit savait converser, suivre un Kanban, mémoriser des engagements et préparer des brouillons ; il ne savait pas **envoyer**, n'affichait **ni missions ni journal**, n'avait **aucun plafond de dépense** et tournait en **HTTP**. Missions, journal, rôles, export, envoi courriel, plafond et voix sont depuis implémentés et testés localement ; TLS, isolation à deux instances, sauvegarde/restauration et mémoire d'équipe restent à prouver sur le banc.

---

## 1. Rectification du cahier des charges précédent

Le document `ARP-DEV-CDC-001` v1.1 reste dans `docs/legacy/` comme archive. Il est **caduc** pour trois raisons, vérifiées le 27/11/2026 :

| Point du CDC v1.1 | Ce qui était écrit | Réalité constatée | Décision |
|---|---|---|---|
| §2 décision 3 | Noyau agentique **Rust-first**, atelier `cargo` | ADR 0007 (12/11, accepté le 19/11) : surcouche du Hermès Agent officiel en Python. Le noyau Rust n'a jamais été déployé. | Rust archivé. Aucune réintroduction sans nouvel ADR. |
| §1.2 et §15 | Livrable = **atelier GitHub** à trois co-concepteurs, Guardian, HTML généré | L'atelier existe (`core-system`), mais le produit est développé par Thibaud + GONA. Guardian n'est plus une porte technique. | Le CDC produit remplace le CDC atelier. Le workflow GitHub (branche, PR, CI) est conservé. |
| §16 | Amélioration continue du noyau par anneaux | Sans objet : le moteur est Hermès, épinglé. La boucle d'auto-amélioration n'est pas un besoin client. | Retiré du périmètre produit. Reste une pratique interne. |

**Ce qui est conservé du v1.1, et reste valable :** Markdown = source de vérité ; une instance par client ; aucun effet externe sans validation humaine ; séparation stricte entre environnement de test et production ; documentation honnête des limites ; rien n'est déclaré conforme sans preuve.

**Ce qui manquait purement et simplement :** le client, le parcours d'achat, la beta, le prix, les critères de sortie, la concurrence.

---

## 2. Problème client

Une PME industrielle française de 20 à 200 personnes, avec un dirigeant ou un directeur commercial qui :

1. **Perd des engagements.** « Je te rappelle lundi » est dit, puis oublié. Personne ne tient le registre.
2. **Recommence chaque semaine.** Comptes rendus, relances, devis : le contexte est reconstruit à la main à chaque fois.
3. **N'a aucune preuve.** En cas de litige ou d'audit client, aucune trace de qui a décidé quoi, quand, sur quelle base.
4. **Ne peut pas confier d'action à une IA.** Elle a peur — à raison — qu'un outil envoie un message faux à un client.

**Coût du problème, ordre de grandeur à vérifier chez le premier client :** une affaire perdue par relance oubliée vaut 5 000 à 50 000 €. Deux heures par semaine de reconstruction de contexte valent 4 000 à 8 000 € par an.

---

## 3. Positionnement et concurrence

### 3.1 Le paysage, constaté le 27/11/2026

| Acteur | Ce qu'il fait | Pour qui | Modèle | Ce qu'il ne fait pas |
|---|---|---|---|---|
| **Cognite Atlas AI** | Agents construits sur un graphe de connaissances industriel (capteurs, ordres de travail, specs, historique d'actifs) ; workbench low-code ; bac à sable d'exécution de code ; évaluations et traces ; confirmations d'outils côté API. | Groupes industriels, énergie, pharma, process. | Entreprise, sur devis, non publié. | Pas de PME sans données structurées. Pas de mise en service en jours. Pas de français métier. |
| **Palantir AIP / Foundry** | Ontologie d'entreprise + agents gouvernés. | Grands comptes, défense, industrie. | Enterprise, sur devis. | Même barrière d'entrée. |
| **Microsoft Copilot Studio / Agent 365** | Agents low-code dans Microsoft 365, gouvernance Entra/Purview. | Entreprises déjà Microsoft. | Par siège et par message. | Suppose l'écosystème M365 ; pas de livrable métier clé en main. |
| **LangGraph / LangSmith, CrewAI** | Framework et observabilité pour développeurs. | Équipes techniques. | Open source + plateforme. | Ce n'est pas un produit fini ; il faut une équipe pour l'exploiter. |
| **Dust, Lindy, assistants PME** | Assistants no-code connectés aux outils SaaS. | Startups, services. | Abonnement mensuel. | Généralistes, orientés tâches, pas de preuve d'approbation ni d'instance dédiée. |
| **ARPAGONA Agent Core** | Copilote de direction métier, instance dédiée, mémoire d'équipe, approbation humaine probante, français. | PME industrielle FR. | Abonnement + mise en service. | Pas de graphe de données industriel, pas d'intégration automate/ERP en beta. |

### 3.2 Notre place

Nous ne gagnons pas sur la donnée. **Nous gagnons sur la décision.**

Trois différences défendables :

1. **La preuve.** Toute action externe exige une approbation liée à une empreinte du contenu. Si le contenu change après approbation, l'envoi est refusé. Cognite confirme des appels d'outils ; nous garantissons que **le texte exact approuvé** est celui qui part.
2. **L'instance dédiée.** Fichiers, mémoire, journaux, secrets et modèle séparés par client. Pas de mutualisation. Argument direct face aux plateformes multi-tenant pour un dirigeant qui confie ses marges à un outil.
3. **Le délai.** Mise en service en jours, sans projet d'intégration de données. L'agent travaille sur ce que la PME a déjà : courriels, documents, tableur, réunions.

**Ce que Cognite fait mieux, et qu'il faut dire au client :** ingestion de données industrielles à grande échelle, graphe d'actifs, connecteurs OT, certifications, évaluations d'agents outillées. Nous ne prétendons pas les remplacer. Nous adressons la couche décision, au-dessus de la donnée qu'ils n'ont pas.

### 3.3 Message de vente (à tester)

> « Votre copilote prépare. Vous décidez. Tout est tracé. »
> Trois promesses : rien ne part sans vous ; vous retrouvez chaque engagement ; la mémoire reste chez vous.

---

## 4. Principes produit

1. **L'humain décide.** Aucun effet externe (courriel, publication, paiement, écriture chez un tiers) sans approbation explicite, liée au contenu exact.
2. **La preuve avant la promesse.** Une fonction non vérifiée n'est pas annoncée. Une limite connue est écrite dans l'interface, pas cachée.
3. **Simple avant puissant.** Trois questions auxquelles l'écran doit répondre : *que dois-je décider ? qu'est-ce qui a été fait ? qu'est-ce qui arrive ?* Si un écran ne répond à aucune, il est supprimé.
4. **Une instance par client.** L'isolation est structurelle, pas applicative.
5. **Le client ne voit jamais Hermès.** Ni shell, ni dashboard, ni clé, ni journal technique. Marque blanche ARPAGONA.
6. **Français métier.** Le vocabulaire est celui du dirigeant : affaire, relance, engagement, compte rendu. Pas celui de l'ingénierie agentique.

---

## 5. Utilisateurs de la beta

| Persona | Rôle | Ce qu'il doit pouvoir faire | Ce qu'il ne doit pas pouvoir faire |
|---|---|---|---|
| **Thibaud** — dirigeant ARPAGONA | Admin d'instance | Tout, y compris créer un compte, voir le journal, arrêter l'instance | Envoyer sans approbation (même lui) |
| **Maël** — associé, cas industriels | Membre | Converser, créer et traiter des cartes dont il est responsable, approuver **ses** brouillons, lire les engagements de l'équipe | Approuver un brouillon de Thibaud, modifier les comptes, voir les secrets |
| **Client pilote (post-beta)** | Membre | Idem Maël, sur son instance | Sortir de son instance |

**Décision beta :** deux comptes réels, sur une seule instance, avec des données **fictives** (entreprise « Dupont Industrie », 200 supports). Aucune donnée client réelle. Cette règle est une porte de sortie (§12, B-11).

---

## 6. Exigences fonctionnelles

Chaque exigence a un identifiant stable, un critère d'acceptation mesurable et un état. L'état est tenu dans `reports/` par audit daté, jamais dans ce document.

### 6.1 Conversation et missions

**F-01 — Conversation persistante.**
Une conversation par compte, conservée entre les visites, avec historique et reprise.
*Acceptation :* fermer l'onglet, rouvrir, l'historique est identique ; après redémarrage du service, l'historique est identique.

**F-02 — Missions visibles.**
Toute demande qui déclenche un travail de plus d'une étape crée une **mission** : identifiant, titre, statut (`en cours`, `à valider`, `terminée`, `échouée`, `arrêtée`), étapes, résultat, durée, coût, lien vers le fil de conversation.
*Acceptation :* une demande « prépare la relance Dupont » produit une mission visible dans l'onglet Missions, avec son résultat, en moins de 10 s après la fin du travail ; une mission interrompue apparaît `arrêtée`, jamais `terminée`.

**F-03 — Arrêt d'une mission.**
Le client peut arrêter une mission en cours. L'arrêt est immédiat et ne rejoue aucun effet.
*Acceptation :* bouton Arrêter → statut `arrêtée` en moins de 2 s ; aucun nouvel appel modèle après l'arrêt ; journal à l'appui.

**F-04 — Voix.**
Dictée dans le champ de saisie et lecture des réponses, sans quitter le navigateur.
*Acceptation :* sur Chrome desktop et Android, dicter « prépare la relance Dupont » produit le texte attendu ; la lecture d'une réponse fonctionne ; si le navigateur ne supporte pas, le bouton est masqué et le texte reste utilisable.
*Limite assumée et affichée :* la dictée utilise le service de reconnaissance du navigateur (Chrome peut traiter l'audio sur son service). ARPAGONA ne reçoit ni ne conserve aucun fichier audio. La lecture utilise les voix du système.

### 6.2 Décision et effets externes

**F-05 — Brouillon et empreinte.**
L'agent produit un brouillon (destinataire, objet, corps). Une empreinte SHA-256 du contenu est calculée côté serveur.
*Acceptation :* l'empreinte change si un caractère du corps change ; elle est recalculée au moment de l'envoi.

**F-06 — Approbation liée au contenu.**
Approuver un brouillon autorise **ce contenu exact**, une seule fois.
*Acceptation :* modifier le corps après approbation → envoi refusé, journalisé ; réutiliser une approbation → refusé ; approuver un brouillon d'un autre compte → refusé (403).

**F-07 — Envoi courriel après approbation.**
Un seul canal sortant en beta : le courriel. Envoi par SMTP, avec journal (horodatage, compte, destinataire, empreinte, identifiant de message).
*Acceptation :* brouillon approuvé → courriel reçu dans une boîte de contrôle, en moins de 60 s ; sans approbation → aucun courriel et une trace de refus ; échec SMTP → statut `échec`, message lisible, aucune reprise silencieuse.

**F-08 — Aucun autre canal.**
Agenda, Drive, publication, paiement : hors beta. L'interface ne propose aucun bouton inactif.

### 6.3 Mémoire et engagements

**F-09 — Engagements datés.**
Un engagement est une décision datée : client, objet, décision, échéance, source, niveau de confiance.
*Acceptation :* « relance Dupont lundi » crée un engagement avec la bonne date et le bon fuseau ; l'échéance passée déclenche la préparation d'un brouillon, jamais un envoi.

**F-10 — Mémoire d'équipe.**
Un fait durable confié par un compte est restitué à l'autre compte de la même instance, avec sa source.
*Acceptation :* Maël dit « le client Dupont exige un devis à 30 jours » ; Thibaud demande « quelles sont les conditions Dupont ? » → réponse exacte, avec la mention de la source. Latence < 10 s.

**F-11 — Oubli.**
Un admin peut supprimer un fait de mémoire et le retrouver absent.
*Acceptation :* suppression → question de contrôle → le fait n'apparaît plus ; journal de suppression conservé.

### 6.4 Travail partagé

**F-12 — Kanban avec responsabilité.**
Cartes visibles par l'équipe ; seul le responsable décide (terminer, bloquer, archiver) ; une carte sans responsable ne se décide pas.
*Acceptation :* Maël tente de terminer une carte de Thibaud → 403 lisible ; commenter reste ouvert ; une carte créée depuis l'interface ne déclenche aucun agent.

**F-13 — Journal d'audit lisible par le client.**
Onglet Journal : les 200 derniers événements (connexion, décision, envoi, refus, changement de compte), horodatés, sans secret.
*Acceptation :* chaque approbation et chaque refus d'envoi y figure ; aucun mot de passe, jeton ou clé n'y figure (test par recherche de motifs).

**F-14 — Portabilité.**
L'admin exporte conversations, engagements, brouillons et journal en un fichier unique (JSON ou ZIP).
*Acceptation :* export produit un fichier lisible, réimportable dans une instance neuve à l'identique pour les données métier.

### 6.5 Accès

**F-15 — Comptes et rôles.**
Deux rôles : admin (comptes, export, journal complet, mémoire) et membre (travail courant).
*Acceptation :* un membre ne peut ni créer de compte, ni changer un mot de passe, ni exporter ; tentative → 403 journalisé.

**F-16 — Multi-appareils.**
Ordinateur et mobile ; sur mobile, la conversation d'abord.
*Acceptation :* mêmes données sur Ryzen, iMac et Android ; aucune fonction critique réservée au desktop.

---

## 7. Exigences non fonctionnelles

**N-01 — TLS obligatoire.** HTTPS sur toute écoute réseau, redirection HTTP → HTTPS, cookie `Secure`, `HttpOnly`, `SameSite=Strict`, HSTS. *Acceptation :* `curl http://` redirige ; un certificat valide est présenté ; le cookie porte `Secure` ; test externe : 401 sans session.

**N-02 — Isolation par instance.** Deux instances fictives ne partagent ni fichiers, ni base, ni mémoire, ni journaux. *Acceptation :* script `nouvelle-instance <client>` ; tests croisés négatifs : un compte de A ne lit rien de B (API, mémoire, fichiers, journaux) ; procédure d'effacement testée.

**N-03 — Plafond de dépense.** Plafond par mission et par jour, appliqué côté serveur. Une exécution déjà lancée n'est pas coupée (le moteur ne publie pas le coût en cours de route) : son dépassement est enregistré et signalé ; aucune nouvelle mission n'est admise tant que le plafond journalier est atteint.
*Acceptation :* mission à 5 $ → coût enregistré, mission marquée « plafond dépassé », mission suivante refusée en 429 avec message lisible ; valeurs configurables sans redéploiement (`ARPAGONA_MAX_MISSION_USD`, `ARPAGONA_MAX_DAY_USD`).

**N-04 — Sauvegarde et restauration.** Sauvegarde quotidienne chiffrée, hors de l'hôte, rétention 30 jours. *Acceptation :* restauration complète sur instance neuve, chronométrée, < 30 min, avec vérification des données métier.

**N-05 — Conformité RGPD.** Registre des traitements, minimisation, durée de conservation par catégorie, procédure d'effacement, liste des sous-traitants (hébergeur, fournisseur de modèle), information claire que l'utilisateur parle à une IA. *Acceptation :* document `docs/conformite/RGPD.md` complet ; effacement d'un compte testé ; aucune donnée réelle sans base légale.

**N-06 — Journalisation sans secret.** Aucun mot de passe, jeton, clé ou contenu de `.env` dans les journaux. *Acceptation :* test automatisé par motifs sur 1 000 lignes ; zéro correspondance.

**N-07 — Performance.** Premier jeton de réponse < 3 s ; page < 1 s sur LAN ; liste Kanban < 500 ms pour 200 cartes. *Acceptation :* mesure répétée 10 fois, médiane et p95 consignées.

**N-08 — Disponibilité beta.** 99 % sur les heures ouvrées, redémarrage automatique, sonde de santé. *Acceptation :* arrêt forcé du service → reprise < 30 s ; sonde externe alerte après 2 échecs.

**N-09 — Mise à jour et retour arrière.** Mise à jour sans perte de données, retour arrière documenté et testé. *Acceptation :* mise à jour puis retour arrière exécutés sur le banc, données intactes.

**N-10 — Restriction des outils de l'agent.** En beta cliente, l'agent n'a pas de terminal ni d'accès réseau arbitraire ; liste d'outils explicite. *Acceptation :* `politique-outils.sh` appliqué ; tentative d'outil interdit → refus journalisé.

**N-11 — Accessibilité de base.** Contraste, navigation clavier, zoom 200 %, libellés ARIA sur les actions. *Acceptation :* parcours complet au clavier ; contraste ≥ 4,5:1 sur le texte.

**N-12 — Documentation client.** Guide de 2 pages (démarrer, approuver, engagements, limites) et guide admin (comptes, sauvegarde, incidents). *Acceptation :* un utilisateur nouveau réalise le parcours sans aide en moins de 10 min.

---

## 8. Périmètre de la beta

### 8.1 Dedans

Chat persistant, missions visibles et arrêtables, brouillons + approbation par empreinte, **envoi courriel**, engagements datés, mémoire d'équipe, oubli, Kanban avec responsabilité, journal d'audit, comptes et rôles, export, voix navigateur, mobile, TLS, isolation démontrée à deux instances, plafond de dépense, sauvegarde/restauration, supervision.

### 8.2 Dehors, explicitement

Autres connecteurs (agenda, Drive, ERP, PDM) ; agents autonomes en tâche de fond sans validation ; auto-modification du système ; multi-tenant en libre-service ; facturation en ligne ; SSO ; application App Store/Play Store ; fine-tuning ; évaluation automatique de la qualité des réponses par un juge modèle ; téléphonie.

Chaque élément dehors est **écrit dans l'interface** comme « non disponible en beta ». Pas de bouton mort.

---

## 9. Architecture beta

Inchangée sur le fond, car validée par ADR 0007 et 0008 :

```
Navigateur (web, PWA)  ──HTTPS──▶  Caddy / reverse proxy
                                        │
                                        ▼
                          API ARPAGONA (Python, 127.0.0.1:8700)
                    comptes · sessions · missions · engagements
                    brouillons · approbations · envoi · audit
                           │                        │
                  ┌────────┴────────┐        ┌──────┴───────┐
                  ▼                 ▼        ▼              ▼
        Hermes Agent API      Pont Kanban   SMTP        Hindsight
        (v0.23.1 épinglé)     (liste        (1 canal)   (mémoire)
        127.0.0.1:8642        blanche)
```

**Décisions d'architecture pour la beta :**

- **A-01** Le moteur reste Hermès officiel épinglé, sans fork. Tout le code ARPAGONA vit hors de son arbre.
- **A-02** L'envoi courriel est implémenté **dans l'API ARPAGONA**, pas dans un outil Hermès. L'agent ne peut pas envoyer : il ne dispose d'aucun outil d'envoi. C'est la garantie structurelle du §4.1.
- **A-03** L'approbation est vérifiée au moment de l'envoi par recalcul d'empreinte, en transaction, avec passage à `envoye` avant l'appel SMTP puis `echec` si SMTP échoue — pas de rejeu automatique.
- **A-04** Les missions sont une table de l'API, alimentée par les exécutions Hermès (`run_id`). Pas d'ordonnanceur nouveau.
- **A-05** Le plafond de dépense est calculé côté API à partir de l'usage retourné par Hermès ; si l'usage est absent, la mission est marquée `coût inconnu` et le plafond journalier s'applique en mode prudent (arrêt après N missions non mesurées).
- **A-06** TLS par proxy inverse sur la même machine, certificat Let's Encrypt si un nom de domaine est disponible, sinon autorité locale ARPAGONA installée sur les appareils de l'équipe.

---

## 10. Modèle de données (ajouts beta)

```sql
missions(id, user_id, conversation_id, run_id, title, status,
         started_at, ended_at, steps_json, result, cost_usd, stop_reason)
mission_events(id, mission_id, ts, kind, detail)          -- traçabilité d'exécution
drafts(... , approved_fingerprint, approved_by, approved_at, sent_message_id)
audit(...)                                                -- existant, exposé en lecture
users(... , role TEXT CHECK(role IN ('admin','membre')))
```

Règles : `status` en liste fermée ; suppression logique seulement ; aucune donnée métier supprimée sans export préalable.

---

## 11. UX — trois écrans, pas dix

| Écran | Question à laquelle il répond | Contenu |
|---|---|---|
| **Conversation** | Que dois-je décider maintenant ? | Fil, brouillons en attente mis en avant, bouton Arrêter, dictée |
| **Travail** | Où en est ce qui est lancé ? | Missions en cours, Kanban, engagements à venir |
| **Preuves** | Qu'est-ce qui a été fait, par qui ? | Journal, brouillons envoyés, export |

Règles : une action principale par écran ; le nombre de clics pour approuver un brouillon ≤ 2 ; aucune notification rouge sans action possible ; les limites affichées en clair (bandeau « beta — données fictives »).

---

## 12. Portes de sortie beta

La beta est déclarée réussie quand **les 12 portes** sont franchies, chacune avec une preuve outil citée dans le rapport de recette. Pas de « validé à l'œil ».

| # | Porte | Preuve exigée |
|---|---|---|
| B-01 | 20 parcours scénarisés verts sur le banc (chat, mission, approbation, refus, Kanban, engagement, mémoire, arrêt) | rapport de recette horodaté, 20/20 |
| B-02 | Deux instances fictives, zéro fuite croisée | tests négatifs API + mémoire + fichiers + journaux |
| B-03 | Envoi courriel réel après approbation, refus sans approbation | courriel reçu + journal + test d'empreinte modifiée |
| B-04 | Plafond de dépense actif | mission au-delà du plafond marquée, mission suivante refusée en 429, journal |
| B-05 | Restauration complète < 30 min | chronométrage + vérification des données |
| B-06 | TLS valide sur l'accès équipe, cookie `Secure` | capture + en-têtes + test externe |
| B-07 | Mémoire d'équipe restituée entre deux comptes | question de contrôle, réponse exacte, source citée |
| B-08 | Journal d'audit complet et sans secret | 200 événements relus, recherche de motifs = 0 |
| B-09 | Aucun bouton mort, aucune promesse fausse dans l'interface | revue écran par écran |
| B-10 | Guide client testé par un utilisateur nouveau | parcours < 10 min sans aide |
| B-11 | Aucune donnée réelle sur le banc | inventaire des comptes et fichiers |
| B-12 | 5 jours d'usage réel par Thibaud et Maël, ≥ 10 missions utiles, 0 incident critique | journal d'usage + décision écrite |

**Règle d'arrêt :** si une porte échoue, la beta n'est pas annoncée. On corrige ou on retire la promesse correspondante de l'interface.

---

## 13. Risques et limites connues

| Risque | Effet | Parade |
|---|---|---|
| Le moteur Hermès change et casse l'intégration | indisponibilité | version épinglée + test de non-régression avant toute montée |
| Le modèle cloud coûte plus que prévu | marge négative | plafond N-03 + mesure par mission + alerte |
| L'agent produit un texte faux mais crédible | perte de confiance | approbation humaine obligatoire, sources affichées, pas d'envoi automatique |
| Fuite entre comptes | rupture de confidentialité | isolation par instance (N-02), test négatif à chaque version |
| Dépendance à une seule personne (Thibaud) | rupture de service | documentation admin, procédures de reprise, Maël formé |
| Fournisseur de modèle hors UE | conformité | clause contractuelle, minimisation, option modèle local documentée |
| Promesse commerciale en avance sur le produit | réputation | ce document fait foi ; l'interface dit ce qui n'est pas disponible |

---

## 14. Modèle économique — hypothèse à valider

**[À VALIDER]** Aucun prix n'est engagé. Hypothèse de travail pour tester trois prospects :

- Mise en service : 2 500 € (instance, comptes, mémoire initiale, formation 2 h).
- Abonnement : 490 €/mois par instance, jusqu'à 5 utilisateurs.
- Coût variable : 15 à 40 €/mois de modèle pour un usage réel (à mesurer, pas à supposer).
- Marge cible : > 70 % après la première année.

Critère de passage GA : trois clients payants, churn nul sur 3 mois, coût variable mesuré sous 10 % du prix.

---

## 15. Après la beta (GA) — non engagé

Ordre proposé, à réévaluer avec les retours : connecteur agenda, connecteur documents/Drive, tableau de bord dirigeant (engagements à risque), import de fichiers métier, évaluation de qualité des réponses, second canal sortant, offre multi-site.

---

## 16. Gouvernance documentaire

- Ce document est la **source de vérité produit**. Il remplace tout CDC antérieur.
- Chaque changement de périmètre = une modification de ce fichier + un ADR si structurant.
- L'état d'avancement vit dans `reports/AAAAMMJJ-audit-beta-agent-core.md`, jamais ici.
- Une exigence retirée est barrée avec sa date et sa raison. On ne réécrit pas l'histoire.
- Langue : français. Les identifiants techniques restent en anglais.

---

## Historique

| Version | Date | Changement |
|---|---|---|
| 2.0 | 27/11/2026 | Première version produit. Remplace ARP-DEV-CDC-001 v1.1. Ajoute client, concurrence, beta, portes de sortie, sécurité, économie. |
