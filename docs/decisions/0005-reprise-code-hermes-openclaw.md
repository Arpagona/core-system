# ADR 0005 — Reprise de code de Hermes Agent et OpenClaw

**Date :** 10 novembre 2026
**Statut :** REMPLACÉ/HISTORIQUE par ADR 0007

## Contexte

Le CDC et `AGENTS.md` excluent toute copie de Hermes ou d'OpenClaw. Thibaud souhaite pouvoir reprendre des parties de leur code pour accélérer le noyau Rust.

Licences vérifiées le 10/11/2026 via l'API GitHub : `NousResearch/hermes-agent` **MIT** (Python), `openclaw/openclaw` **MIT** (TypeScript). La MIT autorise la reprise, y compris dans un produit privé, à condition de conserver l'avis de copyright et de licence.

## Proposition

1. Reprise autorisée **uniquement** depuis ces deux projets, sous MIT.
2. Toute reprise ou traduction substantielle en Rust est tracée dans `THIRD_PARTY.md` : projet, fichier, commit d'origine, nature (copie / traduction / inspiration), fichier de destination ; l'avis MIT d'origine est reproduit.
3. Les textes repris (prompts, schémas d'outils) restent soumis aux mêmes tests et à la même revue que le code original.
4. Aucune reprise depuis l'ancien `Arpagona/Agent-core`, `arpagona-core-one` ou GONA Core sans décision distincte.

## Conséquences

Gain de temps sur des mécanismes éprouvés (boucle d'appel d'outils, formats de messages) ; obligation de traçabilité ; la mention « ni fork ni copie » du plan devient « ni fork ; reprises ponctuelles tracées ».

## État au 10/11/2026

Le code M0 proposé ne contient aucune reprise : il est écrit pour ce dépôt.
