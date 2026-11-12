# Protocole de suivi vivant des agents — ARPAGONA

**Version proposée — 12 novembre 2026.** Source de vérité pour la **destination produit** : [docs/ROADMAP-PRODUIT.md](ROADMAP-PRODUIT.md), charte modifiable uniquement sur demande et validation explicites du porteur du produit. Source pour **l'exécution courante** : [GitHub issue #45 — journal vivant](https://github.com/Arpagona/core-system/issues/45).

## À chaque démarrage ou reprise
1. Lire AGENTS.md, la charte produit, ce protocole, le journal #45 et les PR/commits qui concernent la mission.
2. Vérifier l'état réellement fusionné/déployé. Ne pas déduire le succès d'un simple texte de PR ou d'un test simulé.
3. Identifier une **prochaine action concrète** permise, son objectif et ses critères de preuve.

## À chaque action significative et fin de session
1. Ajouter un **commentaire daté à l'issue #45** : session/agent, objectif, action tentée, résultat (terminé, partiel, échec, non vérifié), preuve SHA/PR/tests, obstacle, alternatives essayées et prochaine étape.
2. Actualiser le **tableau de bord instantané** dans le corps de l'issue en réconciliant le dernier état avec les faits GitHub ; ne pas effacer l'historique des commentaires. Avant une édition concurrente, relire la dernière version pour éviter d'effacer une autre mise à jour.
3. Au démarrage d'une autre session, lire ce journal avant d'entreprendre l'action suivante. Si l'état est incohérent, expliquer la divergence et la corriger dans le journal.
4. Si GitHub est indisponible, conserver localement les entrées horodatées puis synchroniser dès l'accès rétabli ; **ne pas prétendre que GitHub est à jour sans confirmation de publication**.

## Invariants
- Les agents **ne modifient jamais** docs/ROADMAP-PRODUIT.md. Ils déposent leurs idées d'évolution comme suggestions dans le journal.
- Ne pas confondre charte produit, décisions d'architecture, backlog de travail, et audit des preuves.
- Le journal doit dire : **ce qui vient d'être fait**, **ce qui est fait**, **ce qui reste**, **le problème rencontré**, **ce qui sera tenté ensuite**, et **sur quelle preuve on s'appuie**.
- L'actualisation « live » veut dire à chaque événement significatif confirmé, pas après chaque jeton de dialogue.
- La limite de coût, d'autorité et de sécurité prime sur la persévérance.
- Ce fichier n'établit **pas à lui seul** de verrouillage GitHub. Avec le compte actuel et main non protégée, un agent disposant d'écriture pourrait techniquement toucher à la charte. Séparer l'identité de service, réduire ses permissions et instaurer les protections appropriées est indispensable avant de promettre une impossibilité technique.
