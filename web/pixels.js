// Sprites pixel art dessinés en SVG à partir de grilles de caractères (aucune image externe).
"use strict";

const PAL = {
  p: "#a78bfa", P: "#7552d6", q: "#5b46a8", o: "#ff9b43", O: "#c96a1f", g: "#4fd88b",
  G: "#2b9c62", w: "#f4f1fa", W: "#c9c2e6", k: "#0d0d20", K: "#1e1d3a", s: "#f2c39b",
  S: "#d69a70", h: "#6b3f2a", b: "#5f7cff", B: "#3c4fb8", y: "#ffd166", m: "#a8a0c9",
  n: "#393657", r: "#ff6b6b", c: "#8be9fd", t: "#2a2848", l: "#6e5bb8",
};

const SPRITES = {
  logo: [
    "....oooo....",
    "...oooooo...",
    "...ooOOoo...",
    "..ooo..ooo..",
    "..oo....oo..",
    ".ooo....ooo.",
    ".oooooooooo.",
    ".oooooooooo.",
    "ooo......ooo",
    "oo........oo",
    "oo........oo",
    "OO........OO",
  ],
  home: [
    "....pp....",
    "...pppp...",
    "..pppppp..",
    ".pppppppp.",
    "pppppppppp",
    ".pp....pp.",
    ".pp.pp.pp.",
    ".pp.pp.pp.",
    ".pp.pp.pp.",
    ".pppppppp.",
  ],
  chat: [
    ".pppppppp.",
    "pppppppppp",
    "pp......pp",
    "pp.p.p.ppp",
    "pp......pp",
    "pppppppppp",
    ".pppppppp.",
    "..pp......",
    ".pp.......",
    "..........",
  ],
  target: [
    "..pppppp..",
    ".pp....pp.",
    "pp..pp..pp",
    "p..p..p..p",
    "p.p.oo.p.p",
    "p.p.oo.p.p",
    "p..p..p..p",
    "pp..pp..pp",
    ".pp....pp.",
    "..pppppp..",
  ],
  cubes: [
    "...oooo...",
    "...oOOo...",
    "...oOOo...",
    "...oooo...",
    "..........",
    "oooo.oooo.",
    "oOOo.oOOo.",
    "oOOo.oOOo.",
    "oooo.oooo.",
    "..........",
  ],
  moon: [
    "...ppp...y",
    "..ppp...yyy",
    ".ppp.....y",
    ".pp.......",
    "ppp.......",
    "ppp.......",
    "ppp......p",
    ".ppp....pp",
    "..pppppppp",
    "...pppppp.",
  ],
  shield: [
    "pppppppppp",
    "pgggggggpp",
    "pg......gp",
    "pg....g.gp",
    "pg...g..gp",
    "pgg.g..ggp",
    ".pg.g.ggp.",
    ".pgg..gpp.",
    "..pgggpp..",
    "...pppp...",
  ],
  check: [
    "pppppppppp",
    "p........p",
    "p.......gp",
    "p......gg.",
    "p.g...gg.p",
    "p.gg.gg..p",
    "p..ggg...p",
    "p...g....p",
    "p........p",
    "pppppppppp",
  ],
  checkO: [
    "oooooooooo",
    "o........o",
    "o.......wo",
    "o......ww.",
    "o.w...ww.o",
    "o.ww.ww..o",
    "o..www...o",
    "o...w....o",
    "o........o",
    "oooooooooo",
  ],
  bars: [
    "........pp",
    "........pp",
    ".....pp.pp",
    ".....pp.pp",
    "..pp.pp.pp",
    "..pp.pp.pp",
    "..pp.pp.pp",
    "pp.......",
    "pppppppppp",
    "..........",
  ],
  chip: [
    ".p.p.p.p..",
    "pppppppppp",
    ".pPPPPPPp.",
    "ppPwwwwPpp",
    ".pPwPPwPp.",
    "ppPwPPwPpp",
    ".pPwwwwPp.",
    "ppPPPPPPpp",
    "pppppppppp",
    ".p.p.p.p..",
  ],
  gear: [
    "....pp....",
    ".p.pppp.p.",
    "..pppppp..",
    ".ppp..ppp.",
    "ppp....ppp",
    "ppp....ppp",
    ".ppp..ppp.",
    "..pppppp..",
    ".p.pppp.p.",
    "....pp....",
  ],
  bell: [
    "....ww....",
    "...wwww...",
    "..wwwwww..",
    "..wwwwww..",
    "..wwwwww..",
    ".wwwwwwww.",
    "wwwwwwwwww",
    "..........",
    "....ww....",
    "..........",
  ],
  help: [
    "..wwwwww..",
    ".ww....ww.",
    ".ww....ww.",
    "......ww..",
    ".....ww...",
    "....ww....",
    "....ww....",
    "..........",
    "....ww....",
    "....ww....",
  ],
  user: [
    "...wwww...",
    "..w....w..",
    "..w....w..",
    "..w....w..",
    "...wwww...",
    "..........",
    ".wwwwwwww.",
    "w........w",
    "w........w",
    "wwwwwwwwww",
  ],
  term: [
    "..........",
    "pp........",
    ".pp.......",
    "..pp......",
    ".pp.......",
    "pp........",
    "..........",
    "....pppppp",
    "..........",
    "..........",
  ],
  play: [
    ".pp.......",
    ".pppp.....",
    ".pppppp...",
    ".pppppppp.",
    ".pppppppp.",
    ".pppppp...",
    ".pppp.....",
    ".pp.......",
  ],
  playG: [
    "..gggggg..",
    ".g......g.",
    "g..gg....g",
    "g..gggg..g",
    "g..ggggg.g",
    "g..gggg..g",
    "g..gg....g",
    ".g......g.",
    "..gggggg..",
  ],
  pencil: [
    "......ww..",
    ".....wwww.",
    "....wwww..",
    "...wwww...",
    "..wwww....",
    ".wwww.....",
    "www.......",
    "ww........",
  ],
  cross: [
    "ww....ww",
    "www..www",
    ".wwwwww.",
    "..wwww..",
    "..wwww..",
    ".wwwwww.",
    "www..www",
    "ww....ww",
  ],
  send: [
    "ww........",
    "wwww......",
    ".wwwwww...",
    ".wwwwwwww.",
    ".wwwwwwww.",
    ".wwwwww...",
    "wwww......",
    "ww........",
  ],
  plus: [
    "...ww...",
    "...ww...",
    "...ww...",
    "wwwwwwww",
    "wwwwwwww",
    "...ww...",
    "...ww...",
    "...ww...",
  ],
  pulse: [
    "..........",
    "....p.....",
    "....p.....",
    "...p.p..p.",
    "pppp.p.p.p",
    ".....p.p..",
    "......p...",
    "......p...",
    "..........",
  ],
  dots: [
    "ww", "ww", "..", "..", "ww", "ww", "..", "..", "ww", "ww",
  ],
  ok: [
    "........g",
    ".......gg",
    "......gg.",
    "g....gg..",
    "gg..gg...",
    ".gggg....",
    "..gg.....",
  ],
  ko: [
    "r.....r",
    "rr...rr",
    ".rr.rr.",
    "..rrr..",
    ".rr.rr.",
    "rr...rr",
    "r.....r",
  ],
  ring: [
    "..mmmmm..",
    ".m.....m.",
    "m.......m",
    "m.......m",
    "m.......m",
    "m.......m",
    "m.......m",
    ".m.....m.",
    "..mmmmm..",
  ],
  arrow: [
    "mm....",
    ".mm...",
    "..mm..",
    "...mm.",
    "..mm..",
    ".mm...",
    "mm....",
  ],
  robot: [
    ".......oo.......",
    ".......oo.......",
    "........w.......",
    "...wwwwwwwwww...",
    "..wWWWWWWWWWWw..",
    "..wWkkkkkkkkWw..",
    "..wWkcckkcckWw..",
    "..wWkcckkcckWw..",
    "..wWkkkkkkkkWw..",
    "..wWkkgggggkWw..",
    "..wWWWWWWWWWWw..",
    "...wwwwwwwwww...",
    ".....pppppp.....",
    "...pppppppppp...",
    "..ppPPppppPPpp..",
    "..pp.pppppp.pp..",
  ],
  person: [
    ".....hhhhhh.....",
    "....hhhhhhhh....",
    "...hhhhhhhhhh...",
    "...hhssssssh....",
    "...hssssssssh...",
    "...ssksssskss...",
    "...ssssssssss...",
    "...sssssSssss...",
    "....ssSSSSss....",
    ".....ssssss.....",
    "......ssss......",
    "...bbbbbbbbbb...",
    "..bbbbBBBBbbbb..",
    ".bbbbbbBBbbbbbb.",
    ".bbbbbbBBbbbbbb.",
    ".bbbbbbbbbbbbbb.",
  ],
};

function svgFromGrid(rows, scale, extra) {
  const h = rows.length;
  const w = Math.max(...rows.map((r) => r.length));
  let rects = "";
  rows.forEach((row, y) => {
    let x = 0;
    while (x < row.length) {
      const ch = row[x];
      if (ch === "." || !PAL[ch]) { x += 1; continue; }
      let end = x;
      while (end + 1 < row.length && row[end + 1] === ch) end += 1;
      rects += `<rect x="${x}" y="${y}" width="${end - x + 1}" height="1" fill="${PAL[ch]}"/>`;
      x = end + 1;
    }
  });
  const width = scale ? w * scale : "100%";
  const height = scale ? h * scale : "100%";
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" width="${width}" height="${height}" shape-rendering="crispEdges" aria-hidden="true" ${extra || ""}>${rects}</svg>`;
}

// Décor : montagnes violettes sous un soleil orange (barre latérale).
function mountainsScene() {
  const W = 64, H = 34, g = [];
  for (let y = 0; y < H; y += 1) g.push(Array(W).fill("."));
  const set = (x, y, c) => { if (x >= 0 && x < W && y >= 0 && y < H) g[y][x] = c; };
  [[8, 3], [22, 6], [40, 2], [55, 7], [3, 11], [60, 13], [30, 9]].forEach(([x, y]) => set(x, y, "W"));
  const cx = 44, cy = 13, r = 7;
  for (let y = -r; y <= r; y += 1) for (let x = -r; x <= r; x += 1) {
    if (x * x + y * y <= r * r) set(cx + x, cy + y, y > 3 ? "O" : "o");
  }
  const ridge = (peaks, color, shade) => {
    for (let x = 0; x < W; x += 1) {
      let top = H;
      for (const [px, py, slope] of peaks) top = Math.min(top, py + Math.floor(Math.abs(x - px) / slope));
      for (let y = Math.max(0, top); y < H; y += 1) set(x, y, (x + y) % 7 === 0 && y > top + 1 ? shade : color);
    }
  };
  ridge([[12, 14, 1], [36, 18, 1.4], [60, 15, 1.1]], "l", "P");
  ridge([[4, 22, 1.2], [26, 20, 1], [50, 23, 1.3]], "P", "q");
  ridge([[16, 28, 1.5], [44, 27, 1.6], [64, 29, 2]], "q", "K");
  return svgFromGrid(g.map((r) => r.join("")), 0, 'preserveAspectRatio="xMidYMax slice"');
}

// Décor : le robot Agent Core sur une plateforme herbeuse, avec un écran « A ».
function robotScene() {
  const W = 96, H = 40, g = [];
  for (let y = 0; y < H; y += 1) g.push(Array(W).fill("."));
  const set = (x, y, c) => { if (x >= 0 && x < W && y >= 0 && y < H) g[y][x] = c; };
  const blit = (rows, ox, oy) => rows.forEach((row, y) => [...row].forEach((ch, x) => { if (ch !== ".") set(ox + x, oy + y, ch); }));
  for (let x = 6; x < 90; x += 1) {
    const top = 31 + (x < 12 || x > 84 ? 1 : 0);
    for (let y = top; y < H; y += 1) set(x, y, y === top ? "g" : y < top + 2 ? "G" : (x * 3 + y) % 9 === 0 ? "l" : (x + y) % 4 ? "t" : "K");
  }
  const tree = (ox, oy, s) => {
    for (let y = 0; y < s; y += 1) for (let x = -s + y; x <= s - y; x += 1) set(ox + x, oy - s + y * 2, "G");
    for (let y = 0; y < s; y += 1) for (let x = -s + y + 1; x <= s - y - 1; x += 1) set(ox + x, oy - s + y * 2 + 1, y % 2 ? "g" : "G");
    for (let y = oy + s - 1; y < 31; y += 1) set(ox, y, "h");
  };
  tree(80, 14, 6); tree(70, 20, 4);
  [[14, 29], [18, 30], [60, 29], [64, 30], [88, 29]].forEach(([x, y]) => { set(x, y, "g"); set(x + 1, y, "G"); set(x, y + 1, "G"); });
  blit(SPRITES.robot, 28, 13);
  for (let x = 30; x < 42; x += 1) set(x, 29, "p");
  // écran avec « A »
  for (let y = 15; y < 30; y += 1) for (let x = 48; x < 64; x += 1) set(x, y, y === 15 || y === 29 || x === 48 || x === 63 ? "n" : "K");
  blit(SPRITES.logo.map((r) => r.slice(0, 12)), 50, 16);
  for (let x = 54; x < 58; x += 1) set(x, 30, "n");
  return svgFromGrid(g.map((r) => r.join("")), 0, 'preserveAspectRatio="xMidYMax meet"');
}

function paintSprites(root) {
  for (const el of (root || document).querySelectorAll("[data-px]")) {
    const name = el.dataset.px;
    if (el.dataset.painted === name) continue;
    const scale = Number(el.dataset.scale || 2);
    if (name === "scene-mountains") el.innerHTML = mountainsScene();
    else if (name === "scene-robot") el.innerHTML = robotScene();
    else if (SPRITES[name]) el.innerHTML = svgFromGrid(SPRITES[name], scale);
    el.dataset.painted = name;
  }
}

window.Pixels = { paintSprites, svgFromGrid, SPRITES };
