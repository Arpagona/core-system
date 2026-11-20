"use strict";
// Markdown minimal, sûr : tout le texte est échappé avant d'ajouter nos balises.
(function (root) {
  const ENTITIES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  const MEDIA = /MEDIA:((?:\/|~\/)[^\s<>"']+?\.(?:png|jpe?g|gif|webp|bmp))/gi;
  const esc = s => String(s).replace(/[&<>"']/g, c => ENTITIES[c]);

  function inlineText(text) {
    const media = [];
    let s = String(text).replace(MEDIA, (_, p) => {
      media.push(p);
      return "\u0000M" + (media.length - 1) + "\u0000";
    });
    s = esc(s);
    s = s.replace(/\u0000M(\d+)\u0000/g, (_, i) =>
      '<img class="msg-media" src="/api/media?path=' + encodeURIComponent(media[+i]) + '" alt="" loading="lazy">');
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/~~([^~]+)~~/g, "<del>$1</del>");
    s = s.replace(/(^|[\s(])\*([^*\n]+)\*(?=$|[\s).,!?:;])/g, "$1<em>$2</em>");
    s = s.replace(/(^|[\s(])_([^_\n]+)_(?=$|[\s).,!?:;])/g, "$1<em>$2</em>");
    return s;
  }

  function inline(text) {
    const codes = [];
    const masked = String(text).replace(/`([^`]*)`/g, (_, c) => {
      codes.push(c); return "\u0000C" + (codes.length - 1) + "\u0000";
    });
    return inlineText(masked).replace(/\u0000C(\d+)\u0000/g,
      (_, i) => "<code>" + esc(codes[+i]) + "</code>");
  }

  function renderMarkdown(source) {
    if (source == null) return "";
    const lines = String(source).replace(/\r\n?/g, "\n").split("\n");
    const out = [];
    let para = [];
    let i = 0;
    const flush = () => {
      if (!para.length) return;
      out.push("<p>" + para.map(inline).join("<br>") + "</p>");
      para = [];
    };
    while (i < lines.length) {
      const line = lines[i];
      const fence = /^\s*```/.exec(line);
      if (fence) {
        flush();
        i++;
        const code = [];
        while (i < lines.length && !/^\s*```/.test(lines[i])) code.push(lines[i++]);
        if (i < lines.length) i++;
        out.push("<pre><code>" + esc(code.join("\n")) + "</code></pre>");
        continue;
      }
      if (!line.trim()) {
        flush();
        i++;
        continue;
      }
      const heading = /^(#{1,6})\s+(.*)$/.exec(line);
      if (heading) {
        flush();
        const n = heading[1].length;
        out.push("<h" + n + ">" + inline(heading[2]) + "</h" + n + ">");
        i++;
        continue;
      }
      if (/^\s*(?:---+|\*\*\*+)\s*$/.test(line)) {
        flush();
        out.push("<hr>");
        i++;
        continue;
      }
      if (/^\s*>/.test(line)) {
        flush();
        const quote = [];
        while (i < lines.length && /^\s*>/.test(lines[i])) {
          quote.push(lines[i].replace(/^\s*>\s?/, ""));
          i++;
        }
        out.push("<blockquote>" + quote.map(inline).join("<br>") + "</blockquote>");
        continue;
      }
      const bullet = /^\s*([-*+]|\d+\.)\s+/.exec(line);
      if (bullet) {
        flush();
        const ordered = /\d/.test(bullet[1]);
        const items = [];
        while (i < lines.length) {
          const item = /^\s*([-*+]|\d+\.)\s+(.*)$/.exec(lines[i]);
          if (!item) break;
          items.push("<li>" + inline(item[2]) + "</li>");
          i++;
        }
        const tag = ordered ? "ol" : "ul";
        out.push("<" + tag + ">" + items.join("") + "</" + tag + ">");
        continue;
      }
      para.push(line);
      i++;
    }
    flush();
    return out.join("");
  }

  root.renderMarkdown = renderMarkdown;
  root.MC = root.MC || {};
  root.MC.renderMarkdown = renderMarkdown;
  if (typeof module !== "undefined" && module.exports) module.exports = { renderMarkdown };
})(typeof window !== "undefined" ? window : globalThis);
