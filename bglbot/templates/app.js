(async function(){
  "use strict";
  const DATA = await fetch("graph.json", {cache: "no-cache"}).then(r => r.json());
  const nodesById = new Map(DATA.nodes.map(n => [n.id, n]));

  const PARTY_COLORS = {
    "SPÖ": "#ff4d5a", "ÖVP": "#3fd0c9", "FPÖ": "#4d8dff", "Grüne": "#7ed957",
    "GRÜNE": "#7ed957", "NEOS": "#ff6ec7", "KPÖ": "#c0504d", "Bierpartei": "#c8a04a",
    "Liste Burgenland": "#b48ead"
  };
  const SENTI_RGB = {
    feindselig: "255,86,86", negativ: "255,150,94", gemischt: "214,178,70",
    positiv: "86,214,140", neutral: "159,182,204"
  };
  const SENTI_LABEL = {
    feindselig: "feindselig", negativ: "negativ", gemischt: "gemischt",
    positiv: "freundlich", neutral: "sachlich"
  };
  const CATEGORY_COLORS = {
    politik:"#ff8a5c", verwaltung:"#6cc4a1", sicherheit:"#7ea6f0", wirtschaft:"#d9c06b",
    justiz:"#b08bd9", kirche:"#c9b7a0", bildung:"#8fd3f4", gesundheit:"#f28ba8",
    sport:"#9ad36b", organisation:"#a9b4c2", kultur:"#e0a3ff", sonstiges:"#9aa7b4"
  };
  // Cluster-Farben: kräftig, aber unterscheidbar; greift nur im Modus "Cluster".
  const COMMUNITY_COLORS = ["#4da3ff", "#ff6b6b", "#3fd0c9", "#f7b32b", "#9b7ede",
                            "#6cc4a1", "#ff9f68", "#7ed957", "#ff6ec7", "#c8a04a",
                            "#8fd3f4", "#c0504d", "#b48ead", "#a9b4c2"];
  function colorOf(n){
    if (state.colorMode === "community"){
      return n.community != null
        ? COMMUNITY_COLORS[n.community % COMMUNITY_COLORS.length]
        : "#3a4552";
    }
    if (n.party && PARTY_COLORS[n.party]) return PARTY_COLORS[n.party];
    return CATEGORY_COLORS[n.role_category] || "#7f8fa1";
  }

  const state = {
    minWeight: 1,
    minArticles: "solid",
    showLabels: true,
    showIsolated: false,
    evidenceOnly: true,
    colorMode: "party",
    parties: new Set(DATA.parties),
    query: "",
    selected: null,
    hover: null,
    hoverEdge: null,
    matches: null,         // Set von IDs, wenn eine Suche aktiv ist
    sentiFilter: "all",
    toneFilter: "all",
    yearFrom: 2019,
    yearTo: 2026
  };

  // ---------- Layout (Kraftsimulation) ----------
  const W = () => canvas.clientWidth, H = () => canvas.clientHeight;
  let view = {x:0, y:0, k:1};
  const nodes = DATA.nodes.map(n => ({...n, x:0, y:0, vx:0, vy:0, r:0, visible:true, fixed:false}));
  const nodeIndex = new Map(nodes.map(n => [n.id, n]));
  nodes.forEach(n => { n.r = Math.min(42, 5 + Math.sqrt(n.articles) * 3.2 + Math.min(9, n.mentions * 0.35)); });

  const edges = DATA.edges.map(e => ({...e, visible:true}));

  function initLayout(){
    const R = Math.min(W(), H()) * 0.42;
    nodes.forEach((n,i) => {
      const a = (i / nodes.length) * Math.PI * 2;
      const rr = R * (0.35 + 0.65 * ((i * 37) % 100) / 100);
      n.x = Math.cos(a) * rr + (Math.random()-0.5)*30;
      n.y = Math.sin(a) * rr + (Math.random()-0.5)*30;
    });
  }

  function simulate(iterations){
    // Barnes-Hut über d3-force: stabil und O(n log n) statt O(n²). Die Kanten
    // werden kopiert, weil forceLink source/target in Knotenobjekte umwandelt
    // und das übrige Programm die IDs erwartet.
    if (window.d3 && d3.forceSimulation){
      const links = edges.map(e => ({source: e.source, target: e.target,
                                     weight: e.weight || 1}));
      const sim = d3.forceSimulation(nodes)
        .force("link", d3.forceLink(links).id(d => d.id)
          .distance(e => 42 + (e.source.r || 5) + (e.target.r || 5))
          .strength(e => Math.min(0.9, 0.3 + 0.08 * Math.min(8, e.weight))))
        .force("charge", d3.forceManyBody().strength(-95).distanceMax(620))
        .force("center", d3.forceCenter(0, 0))
        .force("collide", d3.forceCollide(d => (d.r || 5) + 2).strength(1).iterations(2))
        .stop();
      sim.alpha(1).alphaDecay(0.022);
      for (let i = 0; i < iterations; i++) sim.tick();
      sim.stop();
      nodes.forEach(nd => {
        if (!Number.isFinite(nd.x) || !Number.isFinite(nd.y)){
          const angle = Math.random() * Math.PI * 2, radius = 200 + Math.random() * 900;
          nd.x = Math.cos(angle) * radius; nd.y = Math.sin(angle) * radius;
        }
        nd.vx = 0; nd.vy = 0;
      });
      separate();
      return;
    }

    const n = nodes.length;
    // Bei großen Netzwerken weniger Iterationen und Nachbarschafts-Gitter statt
    // Alles-mit-allem (sonst blockiert der erste Aufbau den Browser).
    const GX = 190, MAXD2 = 640000;   // 800 px Reichweite
    // Bei vielen Knoten mehr Abstoßung, sonst verklumpt alles in der Mitte.
    const spread = Math.min(3.2, Math.max(1, n / 550));
    for (let it=0; it<iterations; it++){
      const alpha = Math.max(0.02, 1 - it/iterations);
      const grid = new Map();
      for (const nd of nodes){
        const key = Math.floor(nd.x/GX) + ":" + Math.floor(nd.y/GX);
        const bucket = grid.get(key);
        if (bucket) bucket.push(nd); else grid.set(key, [nd]);
      }
      for (let i=0;i<n;i++){
        const a = nodes[i];
        let fx = 0, fy = 0;
        const cx = Math.floor(a.x/GX), cy = Math.floor(a.y/GX);
        for (let gx=cx-2; gx<=cx+2; gx++){
          for (let gy=cy-2; gy<=cy+2; gy++){
            const bucket = grid.get(gx + ":" + gy);
            if (!bucket) continue;
            for (const b of bucket){
              if (b === a) continue;
              let dx = a.x-b.x, dy = a.y-b.y;
              let d2 = dx*dx + dy*dy;
              if (d2 > MAXD2) continue;
              if (d2 < 1) { dx = Math.random()-0.5; dy = Math.random()-0.5; d2 = 1; }
              const d = Math.sqrt(d2);
              const rep = 1400 * spread * alpha / d2;
              fx += (dx/d) * rep; fy += (dy/d) * rep;
            }
          }
        }
        fx -= a.x * 0.012 * alpha; fy -= a.y * 0.012 * alpha;
        // Begrenzen: Bei vielen Nachbarn summieren sich die Kräfte sonst zu
        // Werten, die das Layout auseinandertreiben (Positionen bis 1e12).
        const FMAX = 80;
        fx = Math.max(-FMAX, Math.min(FMAX, fx));
        fy = Math.max(-FMAX, Math.min(FMAX, fy));
        a.vx = (a.vx + fx) * 0.82; a.vy = (a.vy + fy) * 0.82;
      }
      edges.forEach(e => {
        const a = nodeIndex.get(e.source), b = nodeIndex.get(e.target);
        if (!a || !b) return;
        const dx = b.x-a.x, dy = b.y-a.y;
        const d = Math.sqrt(dx*dx+dy*dy) || 1;
        const rest = 70 + (a.r + b.r) * 1.6;
        const f = (d - rest) * 0.012 * Math.min(3, 1 + Math.log(1+e.weight)) * alpha;
        const ux = dx/d, uy = dy/d;
        a.vx += ux*f; a.vy += uy*f;
        b.vx -= ux*f; b.vy -= uy*f;
      });
      nodes.forEach(nd => {
        if (nd.fixed) { nd.vx = nd.vy = 0; return; }
        const vmax = 30;
        nd.vx = Math.max(-vmax, Math.min(vmax, nd.vx));
        nd.vy = Math.max(-vmax, Math.min(vmax, nd.vy));
        nd.x += nd.vx; nd.y += nd.vy;
        if (!Number.isFinite(nd.x) || !Number.isFinite(nd.y)){
          const a0 = Math.random() * Math.PI * 2, r0 = 200 + Math.random() * 900;
          nd.x = Math.cos(a0) * r0; nd.y = Math.sin(a0) * r0; nd.vx = nd.vy = 0;
        }
        const LIMIT = 6000;
        nd.x = Math.max(-LIMIT, Math.min(LIMIT, nd.x));
        nd.y = Math.max(-LIMIT, Math.min(LIMIT, nd.y));
      });
    }
  }

  // Überlappungen hart auflösen: d3.forceCollide arbeitet iterativ und lässt
  // bei sehr unterschiedlichen Radien Restüberlappungen zurück.
  function separate(passes = 90){
    const CELL = 150;
    for (let pass = 0; pass < passes; pass++){
      const grid = new Map();
      for (const nd of nodes){
        const key = Math.floor(nd.x/CELL) + ":" + Math.floor(nd.y/CELL);
        const bucket = grid.get(key);
        if (bucket) bucket.push(nd); else grid.set(key, [nd]);
      }
      let moved = 0;
      for (const a of nodes){
        const cx = Math.floor(a.x/CELL), cy = Math.floor(a.y/CELL);
        for (let gx = cx-1; gx <= cx+1; gx++){
          for (let gy = cy-1; gy <= cy+1; gy++){
            const bucket = grid.get(gx + ":" + gy);
            if (!bucket) continue;
            for (const b of bucket){
              if (b === a) continue;
              let dx = b.x - a.x, dy = b.y - a.y;
              let d = Math.hypot(dx, dy);
              const min = (a.r || 5) + (b.r || 5) + 2;
              if (d >= min) continue;
              if (d < 0.01){ dx = Math.random() - 0.5; dy = Math.random() - 0.5; d = 0.01; }
              const push = (min - d) / 2 + 0.1;
              const ux = dx / d, uy = dy / d;
              a.x -= ux * push; a.y -= uy * push;
              b.x += ux * push; b.y += uy * push;
              moved++;
            }
          }
        }
      }
      if (!moved) break;
    }
  }

  // ---------- Rendering ----------
  const canvas = document.getElementById("graph");
  const ctx = canvas.getContext("2d");
  const tooltip = document.getElementById("tooltip");

  function resize(){
    const dpr = window.devicePixelRatio || 1;
    canvas.width = canvas.clientWidth * dpr;
    canvas.height = canvas.clientHeight * dpr;
    ctx.setTransform(dpr,0,0,dpr,0,0);
  }
  window.addEventListener("resize", () => { resize(); draw(); });

  function toScreen(p){ return {x: p.x*view.k + view.x, y: p.y*view.k + view.y}; }
  function toWorld(sx, sy){ return {x: (sx - view.x)/view.k, y: (sy - view.y)/view.k}; }

  function visibleNodes(){
    return nodes.filter(n => n.visible);
  }
  function visibleEdges(){
    const vis = new Set(visibleNodes().map(n => n.id));
    return edges.filter(e => e.visible && vis.has(e.source) && vis.has(e.target));
  }

  function draw(){
    const placedLabels = [];
    const w = W(), h = H();
    ctx.clearRect(0,0,w,h);
    const highlight = new Set();
    if (state.selected){
      highlight.add(state.selected);
      visibleEdges().forEach(e => {
        if (e.source === state.selected) highlight.add(e.target);
        if (e.target === state.selected) highlight.add(e.source);
      });
    }
    const vEdges = visibleEdges();
    const matches = state.matches;
    const dim = state.selected ? 0.18 : 1;

    vEdges.forEach(e => {
      const a = nodeIndex.get(e.source), b = nodeIndex.get(e.target);
      if (!a || !b) return;
      const pa = toScreen(a), pb = toScreen(b);
      const on = state.selected && (e.source === state.selected || e.target === state.selected);
      const hov = state.hoverEdge === e;
      ctx.beginPath();
      ctx.moveTo(pa.x, pa.y); ctx.lineTo(pb.x, pb.y);
      const sentiLabel = (e.sentiment && e.sentiment.label) || "neutral";
      const rgb = SENTI_RGB[sentiLabel] || SENTI_RGB.neutral;
      const strong = sentiLabel !== "neutral";
      const alphaBase = strong ? 0.55 : Math.min(0.55, 0.12 + ((e.strength ?? 0) * 0.08));
      let alpha = hov ? 0.95 : on ? 0.8 : alphaBase * dim;
      if (matches && !(matches.has(e.source) && matches.has(e.target))) alpha *= 0.25;
      ctx.strokeStyle = hov ? "#ffffff" : on ? "#8fc7ff" : "rgba(" + rgb + "," + alpha.toFixed(2) + ")";
      const strength = (e.strength ?? 0) || 0;
      const visual = strength * 0.3 + Math.min(6, e.weight) * 0.08;
      ctx.lineWidth = hov ? 2.6 : on ? Math.min(5, 0.7 + visual * 1.4)
                                    : Math.max(0.5, Math.min(2.6, 0.35 + visual));
      ctx.stroke();
    });

    nodes.forEach(n => {
      if (!n.visible) return;
      const p = toScreen(n);
      const r = Math.max(2.5, n.r * view.k);
      const isSel = state.selected === n.id;
      const isHover = state.hover === n;
      const inHighlight = !state.selected || highlight.has(n.id);
      const inQuery = !matches || matches.has(n.id);
      ctx.beginPath();
      ctx.arc(p.x, p.y, r, 0, Math.PI*2);
      ctx.fillStyle = colorOf(n);
      ctx.globalAlpha = (inHighlight ? 1 : 0.25) * (inQuery ? 1 : 0.16);
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.lineWidth = isSel || isHover ? 2.4 : 1;
      ctx.strokeStyle = isSel ? "#ffffff" : isHover ? "#cfe6ff" : "rgba(0,0,0,.45)";
      ctx.stroke();

      if (state.showLabels && (view.k > 0.55 || isSel || isHover || n.articles >= 3)) {
        const fs = Math.max(10, Math.min(15, 11*Math.sqrt(view.k)));
        ctx.font = (isSel?"600 ":"400 ") + fs + "px 'Segoe UI',sans-serif";
        ctx.textAlign = "center"; ctx.textBaseline = "top";
        const label = n.name + (n.party ? " · " + n.party : "");
        ctx.fillStyle = "rgba(8,12,18,.75)";
        const tw = ctx.measureText(label).width;
        ctx.fillRect(p.x - tw/2 - 3, p.y + r + 2, tw + 6, fs + 3);
        ctx.fillStyle = inHighlight ? "#e9f1fa" : "rgba(200,215,230,.45)";
        ctx.fillText(label, p.x, p.y + r + 3);
      }
    });
  }

  // ---------- Interaktion ----------
  let dragging = null, panning = null, movedSinceDown = 0;

  function hitNode(sx, sy){
    const vis = visibleNodes().slice().sort((a,b)=>b.r-a.r);
    for (const n of vis){
      const p = toScreen(n);
      const r = Math.max(3.5, n.r * view.k) + 3;
      if ((sx-p.x)**2 + (sy-p.y)**2 <= r*r) return n;
    }
    return null;
  }

  function hitEdge(sx, sy){
    let best = null, bestD = 6;
    visibleEdges().forEach(e => {
      const a = nodeIndex.get(e.source), b = nodeIndex.get(e.target);
      if (!a || !b) return;
      const pa = toScreen(a), pb = toScreen(b);
      const vx = pb.x-pa.x, vy = pb.y-pa.y;
      const len2 = vx*vx+vy*vy;
      let t = len2 ? ((sx-pa.x)*vx + (sy-pa.y)*vy)/len2 : 0;
      t = Math.max(0, Math.min(1, t));
      const cx = pa.x + t*vx, cy = pa.y + t*vy;
      const d = Math.hypot(sx-cx, sy-cy);
      if (d < bestD){ bestD = d; best = e; }
    });
    return best;
  }

  function pointer(e){
    const rect = canvas.getBoundingClientRect();
    return {x: e.clientX - rect.left, y: e.clientY - rect.top};
  }

  canvas.addEventListener("mousedown", e => {
    const p = pointer(e);
    movedSinceDown = 0;
    const n = hitNode(p.x, p.y);
    if (n){
      dragging = n; n.fixed = true;
      canvas.classList.add("dragging");
    } else {
      panning = {x: p.x - view.x, y: p.y - view.y};
    }
  });

  canvas.addEventListener("mousemove", e => {
    const p = pointer(e);
    if (dragging){
      const w = toWorld(p.x, p.y);
      movedSinceDown += Math.abs(w.x - dragging.x) + Math.abs(w.y - dragging.y);
      dragging.x = w.x; dragging.y = w.y;
      draw();
      return;
    }
    if (panning){ view.x = p.x - panning.x; view.y = p.y - panning.y; draw(); return; }

    const n = hitNode(p.x, p.y);
    state.hover = n ? n.id : null;
    state.hoverEdge = n ? null : hitEdge(p.x, p.y);
    canvas.style.cursor = n ? "pointer" : state.hoverEdge ? "pointer" : "grab";
    if (n){
      showTooltip(p, `<b>${esc(n.name)}</b><br>${esc(n.role||"Funktion unbekannt")}${n.party?" · "+esc(n.party):""}<br><span style="color:#8b98a5">${n.articles} Artikel · ${n.degree} Beziehungen</span>`);
    } else if (state.hoverEdge){
      const e2 = state.hoverEdge;
      const a = nodeIndex.get(e2.source), b = nodeIndex.get(e2.target);
      const sl = (e2.sentiment && e2.sentiment.label) || "neutral";
      showTooltip(p, `<b>${esc(a.name)} ↔ ${esc(b.name)}</b><br><span style="color:rgb(${SENTI_RGB[sl]})">${esc(SENTI_LABEL[sl] || sl)}</span><br><span style="color:#8b98a5">Stärke ${e2.strength ?? "–"} · ${e2.weight} gemeinsame Artikel · ${e2.sentences} gemeinsame Sätze</span>`);
    } else {
      hideTooltip();
    }
    draw();
  });

  function endDrag(){
    if (dragging){ dragging.fixed = false; dragging.vx = dragging.vy = 0; dragging = null; }
    panning = null;
    canvas.classList.remove("dragging");
  }
  canvas.addEventListener("mouseup", e => {
    const p = pointer(e);
    const n = hitNode(p.x, p.y);
    if (movedSinceDown < 4){
      if (n) selectNode(n.id);
      else {
        const ed = hitEdge(p.x, p.y);
        if (ed) showEdge(ed); else clearSelection();
      }
    }
    endDrag();
  });
  canvas.addEventListener("mouseleave", () => { endDrag(); hideTooltip(); state.hover=null; state.hoverEdge=null; draw(); });

  canvas.addEventListener("wheel", e => {
    e.preventDefault();
    const p = pointer(e);
    const w = toWorld(p.x, p.y);
    const factor = Math.exp(-e.deltaY * 0.0015);
    view.k = Math.max(0.15, Math.min(4, view.k * factor));
    view.x = p.x - w.x * view.k;
    view.y = p.y - w.y * view.k;
    draw();
  }, {passive:false});

  function showTooltip(p, html){
    tooltip.innerHTML = html;
    tooltip.classList.add("on");
    const wrap = canvas.getBoundingClientRect();
    tooltip.style.left = Math.min(wrap.width-290, p.x+14) + "px";
    tooltip.style.top = Math.max(4, p.y-10) + "px";
  }
  function hideTooltip(){ tooltip.classList.remove("on"); }
  function shorten(text, limit){
    if (!text || text.length <= limit) return text || "";
    const cut = text.slice(0, limit);
    const stop = Math.max(cut.lastIndexOf(". "), cut.lastIndexOf("! "), cut.lastIndexOf("? "));
    return (stop > limit * 0.5 ? cut.slice(0, stop + 1) : cut.trim()) + " …";
  }

  function esc(s){
    return String(s==null?"":s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  }

  // ---------- Detailpanel ----------
  const detail = document.getElementById("detail");

  function selectNode(id){
    state.selected = id;
    const n = nodeIndex.get(id);
    if (!n){ clearSelection(); return; }
    const partners = edges
      .filter(e => e.source === id || e.target === id)
      .map(e => ({other: nodeIndex.get(e.source === id ? e.target : e.source), e}))
      .sort((a,b) => b.e.weight - a.e.weight)
      .slice(0, 12);

    const roles = (n.roles||[]).map(r => `<span class="badge">${esc(r.label)} <span style="color:#8b98a5">${r.count}×</span></span>`).join("");
    const arts = (n.article_list||[]).slice(0, 25).map(a =>
      `<a class="article" href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.title)}
        <small>${esc(a.date)} · ${esc(a.category||"")}</small></a>`).join("");

    detail.innerHTML = `
      <h2>${esc(n.name)}</h2>
      <div class="sub">${esc(n.role || "Funktion im Korpus nicht erkannt")}${n.role_context ? " · " + esc(n.role_context) : ""}</div>
      <div>${n.party ? `<span class="badge" style="border-color:${colorOf(n)};color:${colorOf(n)}">${esc(n.party)}</span>` : ""}
           <span class="badge">${n.articles} Artikel</span>
           <span class="badge">${n.mentions} Nennungen</span>
           <span class="badge">Grad ${n.degree}</span>
           <span class="badge">Konfidenz ${esc(n.confidence)}</span>
           ${n.conflict_edges ? `<span class="badge" style="border-color:rgb(255,120,90);color:rgb(255,150,120)">${n.conflict_edges} konfliktäre Kanten</span>` : ""}
           ${n.positive_edges ? `<span class="badge" style="border-color:rgb(86,214,140);color:rgb(86,214,140)">${n.positive_edges} freundschaftliche</span>` : ""}</div>
      ${roles ? `<h3>Weitere erkannte Funktionen</h3><div>${roles}</div>` : ""}
      ${n.wikidata && n.wikidata.offices && n.wikidata.offices.length ? `
        <h3>Ämter (Wikidata)</h3>
        <div class="hint">${n.wikidata.offices.slice(0, 6).map(o => esc(o.label) + (o.start || o.end ? ` (${esc(o.start || "?")}–${esc(o.end || "heute")})` : "")).join("<br>")}</div>
        ${n.wikidata.birth ? `<div class="hint" style="margin-top:4px">geboren ${esc(n.wikidata.birth)}</div>` : ""}
      ` : ""}
      ${n.wikipedia ? `
        <h3>Wikipedia</h3>
        ${n.wikipedia.description ? `<div class="sub" style="margin:-4px 0 8px">${esc(n.wikipedia.description)}</div>` : ""}
        <div style="display:flex;gap:11px;align-items:flex-start">
          ${n.wikipedia.thumbnail ? `<img src="${esc(n.wikipedia.thumbnail)}" alt="" referrerpolicy="no-referrer"
              style="width:84px;border-radius:6px;flex:none;border:1px solid var(--line)">` : ""}
          <div style="font-size:12.5px;color:#cfd8e3;line-height:1.45">
            ${esc(shorten(n.wikipedia.extract, 560))}
            <div style="margin-top:7px"><a href="${esc(n.wikipedia.url)}" target="_blank" rel="noopener"
              style="color:var(--accent)">→ ${esc(n.wikipedia.title)}</a></div>
          </div>
        </div>
      ` : ""}
      ${(n.tone && n.tone.label && n.tone.label !== "zu wenig Belege") ? `
        <h3>Tonlage im Korpus</h3>
        <div><span class="badge" style="border-color:${n.tone.score < 0 ? "rgb(255,150,120)" : "rgb(86,214,140)"};
              color:${n.tone.score < 0 ? "rgb(255,150,120)" : "rgb(86,214,140)"}">${esc(n.tone.label)}</span>
          <span class="badge">${n.tone.critical} kritische Belege</span>
          <span class="badge">${n.tone.praising} zustimmende</span></div>
        ${n.tone.parties && n.tone.parties.length ? `<div class="hint">Kritik richtet sich gegen:
          ${n.tone.parties.map(p => esc(p.party) + " (" + p.count + ")").join(", ")}</div>` : ""}
        ${(n.tone.examples || []).map(ex => `<blockquote>${esc(ex.sentence)}
          <div class="hint" style="margin-top:5px">${esc(ex.article)} · ${esc(ex.date)}${ex.cues && ex.cues.length ? " · " + esc(ex.cues.join(", ")) : ""}</div></blockquote>`).join("")}
      ` : ""}
      ${n.aliases && n.aliases.length ? `<h3>Frühere Namen</h3><div class="hint">${n.aliases.map(a => {
          const span = [a.from, a.to].filter(Boolean).map(d => String(d).slice(0, 7)).join(" – ");
          return esc(a.name) + (span ? ` <span style="color:#6b7885">(${esc(span)})</span>` : "");
        }).join("<br>")}</div>` : ""}
      ${n.variants && n.variants.length > 1 ? `<h3>Schreibweisen</h3><div class="hint">${n.variants.map(esc).join(" · ")}</div>` : ""}
      <h3>Beziehungen (${partners.length})</h3>
      ${partners.map(({other,e}) => other ? `<div class="row" data-goto="${esc(other.id)}">
          <span class="n">${esc(other.name)}${other.party ? ` <span style="color:${colorOf(other)}">·</span>` : ""}</span>
          <span class="c">${e.weight} Art. / ${e.sentences} Sätze</span></div>` : "").join("") || `<div class="hint">Keine gemeinsamen Artikel.</div>`}
      <h3>Artikel (${(n.article_list||[]).length})</h3>
      <div style="max-height:210px;overflow:auto">${arts}</div>
      <div class="hint" style="margin-top:10px">Erste Nennung ${esc(n.first_seen)} · letzte ${esc(n.last_seen)}</div>
    `;
    detail.querySelectorAll("[data-goto]").forEach(el => el.addEventListener("click", () => {
      const target = nodeIndex.get(el.getAttribute("data-goto"));
      if (target) { focusNode(target); selectNode(target.id); }
    }));
    draw();
  }

  function showEdge(e){
    state.selected = null;
    const a = nodeIndex.get(e.source), b = nodeIndex.get(e.target);
    if (!a || !b) return;
    const ex = (e.examples||[]).map(x => `<blockquote>${esc(x.sentence)}
      <div class="hint" style="margin-top:5px">${esc(x.article)} · ${esc(x.date)}${x.context ? " · " + esc(x.context) : ""}${x.cues && x.cues.length ? " · " + esc(x.cues.join(", ")) : ""}${x.signals && x.signals.length ? " · " + esc(x.signals.join(", ")) : ""}</div></blockquote>`).join("");
    const signals = Object.entries(e.signals||{}).map(([k,v]) => `<span class="badge">${esc(k)} ${v}×</span>`).join("");
    const senti = e.sentiment || {label:"neutral", score:0, positive:0, negative:0, hostile:0, sentences:0, direction:{}};
    const sentiColor = `rgb(${SENTI_RGB[senti.label] || SENTI_RGB.neutral})`;
    const barPos = Math.round(((senti.score + 1) / 2) * 100);
    const dirs = Object.entries(senti.direction || {}).map(([k, v]) => {
      const [from, to] = k.split(">");
      return `<div class="row" style="cursor:default"><span class="n">${esc((nodeIndex.get(from)||{}).name || from)} → ${esc((nodeIndex.get(to)||{}).name || to)}</span><span class="c">${v}×</span></div>`;
    }).join("");
    detail.innerHTML = `
      <h2>${esc(a.name)} ↔ ${esc(b.name)}</h2>
      <div class="sub">Stärke ${e.strength ?? "–"} · ${e.weight} gemeinsame Artikel · ${e.sentences} gemeinsame Sätze (${e.body_sentences ?? "–"} im Fließtext, ${e.list_sentences ?? "–"} in Aufzählungen)</div>
      ${e.years && Object.keys(e.years).length ? `<div class="hint">Jahre: ${Object.entries(e.years).map(([y, c]) => y + " (" + c + ")").join(" · ")}</div>` : ""}
      <h3>Beziehungston</h3>
      <div><span class="badge" style="border-color:${sentiColor};color:${sentiColor}">${esc(SENTI_LABEL[senti.label] || senti.label)}</span>
        <span class="badge">${senti.positive.toFixed(1)} positiv</span>
        <span class="badge">${senti.negative.toFixed(1)} negativ</span>
        ${senti.hostile ? `<span class="badge">${senti.hostile}× feindselig</span>` : ""}
        <span class="badge">${senti.sentences} Belegstellen</span></div>
      <div style="margin:8px 0 2px;height:6px;border-radius:3px;background:linear-gradient(90deg,rgb(255,86,86),#3a4756,rgb(86,214,140))">
        <div style="width:2px;height:10px;background:#fff;margin-left:${barPos}%;transform:translateY(-2px)"></div></div>
      <div class="hint">Skala: feindselig ← sachlich → freundlich</div>
      ${dirs ? `<h3>Tendenz (wer → wen)</h3>${dirs}` : ""}
      ${signals ? `<h3>Themen</h3><div>${signals}</div>` : ""}
      <h3>Belegstellen</h3>
      ${ex || `<div class="hint">Keine Beispielsätze gespeichert.</div>`}
      <h3>Artikel</h3>
      <div class="hint">${e.articles.map(id => `<a class="article" href="${esc((DATA.articles[id]||{}).url||"#")}" target="_blank" rel="noopener">${esc((DATA.articles[id]||{}).title||id)}<small>${esc((DATA.articles[id]||{}).date||"")}</small></a>`).join("")}</div>
    `;
    draw();
  }

  function clearSelection(){
    state.selected = null;
    detail.innerHTML = `<div class="empty"><h2 style="font-size:15px;color:#e6edf3">Person auswählen</h2>
      Klicken Sie auf einen Knoten oder eine Kante, um Funktion, Parteizugehörigkeit,
      Artikel und die gemeinsamen Nennungen zu sehen.</div>`;
    draw();
  }

  document.addEventListener("keydown", e => { if (e.key === "Escape") clearSelection(); });

  function focusNode(n){
    const targetK = Math.max(view.k, 1.25);
    view.k = targetK;
    view.x = W()/2 - n.x*targetK;
    view.y = H()/2 - n.y*targetK;
    draw();
  }

  // ---------- Filter & Listen ----------
  function yearsInRange(map, from, to){
    if (!map) return 0;
    let total = 0;
    for (const [year, count] of Object.entries(map)){
      const y = Number(year);
      if (y >= from && y <= to) total += count;
    }
    return total;
  }

  function sentiLabelOf(e){
    return (e.sentiment && e.sentiment.label) || "neutral";
  }

  function sentiOk(e){
    const label = sentiLabelOf(e);
    if (state.sentiFilter === "all") return true;
    if (state.sentiFilter === "labelled") return label !== "neutral";
    if (state.sentiFilter === "conflict") return label === "negativ" || label === "feindselig";
    if (state.sentiFilter === "positive") return label === "positiv" || label === "gemischt";
    return true;
  }

  function applyFilters(){
    const partyOk = n => n.party ? state.parties.has(n.party) : state.parties.has("__none__");
    const linked = new Set();
    edges.forEach(e => {
      const inYears = yearsInRange(e.years, state.yearFrom, state.yearTo);
      const evidenced = !state.evidenceOnly || (e.sentences || 0) > 0;
      if (inYears >= state.minWeight && sentiOk(e) && evidenced){ linked.add(e.source); linked.add(e.target); }
    });
    nodes.forEach(n => {
      const active = yearsInRange(n.years, state.yearFrom, state.yearTo) > 0;
      const solid = state.minArticles === "solid"
        ? (n.articles >= 2 || !!n.role || !!n.party || (n.tone && n.tone.critical >= 2))
        : n.articles >= Number(state.minArticles);
      let vis = solid && partyOk(n) && active;
      const toneLabel = (n.tone && n.tone.label) || "";
      if (state.toneFilter === "critical") vis = vis && toneLabel.indexOf("kritisch") >= 0;
      if (state.toneFilter === "positive") vis = vis && toneLabel.indexOf("zustimmend") >= 0;
      if (!state.showIsolated) vis = vis && linked.has(n.id);
      n.visible = n.forced ? true : vis;     // Suchtreffer bleiben sichtbar
    });
    edges.forEach(e => {
      const evidenced = !state.evidenceOnly || (e.sentences || 0) > 0;
      e.visible = yearsInRange(e.years, state.yearFrom, state.yearTo) >= state.minWeight
                  && sentiOk(e) && evidenced;
    });
    renderList();
    draw();
  }

  // Suchtext inklusive früherer Namen („Elisabeth Pauer“ findet Pauer-Gerbavsits).
  function searchText(n){
    const aliases = (n.aliases || []).map(a => a.name).join(" ");
    return (n.name + " " + aliases + " " + (n.variants || []).join(" ")).toLowerCase();
  }

  function renderList(){
    const list = document.getElementById("personList");
    let items = nodes.filter(n => n.visible);
    if (state.query) items = items.filter(n => searchText(n).includes(state.query));
    items.sort((a,b) => b.articles - a.articles || b.degree - a.degree);
    document.getElementById("listCount").textContent = "(" + items.length + ")";
    list.innerHTML = items.map(n => `
      <div class="row" data-id="${esc(n.id)}">
        <span class="n"><i style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${colorOf(n)};margin-right:7px"></i>${esc(n.name)}${n.aliases && n.aliases.length ? `<span style="color:#5f6b78;font-size:11px"> · früher ${esc(n.aliases[0].name.split(" ").slice(-1)[0])}</span>` : ""}</span>
        <span class="c">${n.articles}A · ${n.degree}G</span>
      </div>`).join("");
    list.querySelectorAll("[data-id]").forEach(el => el.addEventListener("click", () => {
      const n = nodeIndex.get(el.getAttribute("data-id"));
      if (n){ focusNode(n); selectNode(n.id); }
    }));
  }

  function buildStamp(){
    const raw = (DATA.meta && DATA.meta.generated) || "";
    const d = new Date(raw);
    if (isNaN(d.getTime())) return raw.slice(0, 16).replace("T", " ");
    const p2 = n => String(n).padStart(2, "0");
    return `${p2(d.getDate())}.${p2(d.getMonth()+1)}.${d.getFullYear()}, ${p2(d.getHours())}:${p2(d.getMinutes())}`;
  }

  function labelledEdges(){
    const sentiment = DATA.meta.sentiment;
    if (!sentiment) return 0;
    if (Array.isArray(sentiment)) return sentiment.filter(x => x !== "neutral").length;
    return Object.entries(sentiment)
      .filter(([label]) => label !== "neutral")
      .reduce((sum, [, count]) => sum + count, 0);
  }

  function renderStats(){
    const m = DATA.meta;
    document.getElementById("stats").innerHTML = `
      <span><b>${m.articles_crawled}</b> Artikel</span>
      <span><b>${m.persons}</b> Personen</span>
      <span><b>${m.edges}</b> Beziehungen</span>
      <span><b>${m.mentions}</b> Nennungen</span>
      <span>${esc(m.date_from)} – ${esc(m.date_to)}</span>
      <span title="Zeitpunkt dieser Auswertung">Stand ${esc(buildStamp())}</span>
      <span title="Kanten mit erkennbarem Beziehungston">${labelledEdges()} bewertete Kanten</span>`;
  }

  function renderPartyChips(){
    const box = document.getElementById("partyChips");
    const parties = DATA.parties;
    box.innerHTML = parties.map(p => `<span class="chip on" data-party="${esc(p)}">
        <i style="background:${PARTY_COLORS[p]||"#7f8fa1"}"></i>${esc(p)}</span>`).join("")
      + `<span class="chip on" data-party="__none__"><i style="background:#7f8fa1"></i>ohne Partei</span>`;
    box.querySelectorAll(".chip").forEach(chip => {
      chip.addEventListener("click", () => {
        const p = chip.getAttribute("data-party");
        const on = !chip.classList.contains("on");
        chip.classList.toggle("on", on);
        if (on) state.parties.add(p); else state.parties.delete(p);
        applyFilters();
      });
    });
    state.parties.add("__none__");
  }

  function renderLegend(){
    if (state.colorMode === "community"){
      const sizes = DATA.meta.community_sizes || {};
      const labels = DATA.meta.community_labels || {};
      const ids = Object.keys(sizes).slice(0, 9);
      document.getElementById("legend").innerHTML =
        `<div style="margin-bottom:6px;color:#8b98a5">Netzwerk-Cluster (Personen)</div>`
        + ids.map(id => {
            const color = COMMUNITY_COLORS[Number(id) % COMMUNITY_COLORS.length];
            const who = labels[id] ? ` · ${esc(labels[id])}` : "";
            return `<div><i style="background:${color}"></i>Cluster ${Number(id) + 1}`
                 + ` <span style="color:#6b7885">(${sizes[id]}${who})</span></div>`;
          }).join("")
        + `<div><i style="background:#3a4552"></i>nicht zugeordnet</div>`
        + `<div style="margin-top:7px;padding-top:7px;border-top:1px solid #26303d;color:#6b7885">`
        + `Cluster = dicht verbundene Gruppe (Louvain)<br>Knotengröße = Artikelanzahl</div>`;
      return;
    }
    const used = DATA.parties.slice(0, 6);
    const senti = [["feindselig", "feindselig"], ["negativ", "negativ"],
                   ["gemischt", "gemischt"], ["positiv", "freundlich"]];
    document.getElementById("legend").innerHTML =
      used.map(p => `<div><i style="background:${PARTY_COLORS[p]||"#7f8fa1"}"></i>${esc(p)}</div>`).join("")
      + `<div><i style="background:#7f8fa1"></i>ohne Partei / unklar</div>
         <div style="margin-top:7px;padding-top:7px;border-top:1px solid #26303d">Kante = Beziehungston</div>`
      + senti.map(([key, label]) =>
          `<div><i style="background:rgb(${SENTI_RGB[key]})"></i>${esc(label)}</div>`).join("")
      + `<div><i style="background:rgb(${SENTI_RGB.neutral})"></i>sachlich / ohne Wertung</div>
         <div style="margin-top:6px;color:#6b7885">Knotengröße = Artikelanzahl<br>Kantenstärke = gemeinsame Artikel</div>`;
  }

  // ---------- Steuerung ----------
  const searchInput = document.getElementById("search");
  const searchResults = document.getElementById("searchResults");
  const searchHint = document.getElementById("searchHint");
  const MAX_RESULTS = 14;
  let searchHits = [];
  let searchActive = -1;

  function rankName(node, query){
    const name = node.name.toLowerCase();
    const idx = name.indexOf(query);
    if (idx === 0) return 0;                                  // Namensanfang
    if (idx > 0 && /[\s\-]/.test(name[idx-1])) return 1;       // Wortanfang
    return 2;                                                  // irgendwo
  }

  function computeHits(query){
    return nodes
      .filter(n => searchText(n).includes(query))
      .sort((a, b) => rankName(a, query) - rankName(b, query)
        || b.articles - a.articles || a.name.localeCompare(b.name));
  }

  // Einfache Editierdistanz für Tippfehler und Namensvarianten ("Ronald" -> "Roland").
  function editDistance(a, b){
    if (a === b) return 0;
    const rows = a.length + 1, cols = b.length + 1;
    let prev = Array.from({length: cols}, (_, j) => j);
    for (let i = 1; i < rows; i++){
      const cur = [i];
      for (let j = 1; j < cols; j++){
        const cost = a[i-1] === b[j-1] ? 0 : 1;
        cur[j] = Math.min(prev[j] + 1, cur[j-1] + 1, prev[j-1] + cost);
        if (i > 1 && j > 1 && a[i-1] === b[j-2] && a[i-2] === b[j-1]){
          cur[j] = Math.min(cur[j], prev[j-1] + 1);   // Vertauschung
        }
      }
      prev = cur;
    }
    return prev[cols-1];
  }

  function fuzzyCandidates(query){
    const words = query.split(/\s+/).filter(w => w.length >= 3);
    if (!words.length) return [];
    const scored = [];
    for (const node of nodes){
      const parts = node.name.toLowerCase().split(/\s+/);
      let best = 99;
      for (const word of words){
        for (const part of parts){
          const distance = editDistance(word, part);
          if (distance < best) best = distance;
        }
      }
      const tolerance = words.some(w => best <= 2 && best < w.length - 1) ? best : 99;
      if (tolerance <= 2) scored.push({node, distance: best});
    }
    scored.sort((a, b) => a.distance - b.distance
      || b.node.articles - a.node.articles || a.node.name.localeCompare(b.node.name));
    return scored.slice(0, MAX_RESULTS).map(entry => entry.node);
  }

  function paintActive(){
    searchResults.querySelectorAll(".hit").forEach((el, i) => {
      el.classList.toggle("active", i === searchActive);
      if (i === searchActive) el.scrollIntoView({block: "nearest"});
    });
  }

  function renderSearch(hits, noteAt = -1){
    searchHits = hits;
    searchActive = hits.length ? 0 : -1;
    searchInput.setAttribute("aria-expanded", hits.length ? "true" : "false");
    if (!hits.length){
      searchResults.innerHTML = `<div class="none">Keine Person gefunden.</div>`;
      searchResults.classList.add("open");
      return;
    }
    searchResults.innerHTML = hits.slice(0, MAX_RESULTS).map((n, i) => {
      const noteHtml = i === noteAt
        ? `<div class="none" style="border-top:1px solid #26303d;border-bottom:1px solid #26303d">Ähnliche Namen:</div>`
        : "";
      return noteHtml + `
      <div class="hit${i === searchActive ? " active" : ""}" data-id="${esc(n.id)}" role="option">
        <i style="background:${colorOf(n)}"></i>
        <span class="nm">${esc(n.name)}</span>
        <span class="mt">${n.articles} A · ${n.degree} G${n.party ? " · " + esc(n.party) : ""}</span>
      </div>`;
    }).join("");
    searchResults.classList.add("open");
    searchResults.querySelectorAll(".hit").forEach(el => {
      el.addEventListener("click", () => pickSearchHit(el.getAttribute("data-id")));
      el.addEventListener("mouseenter", () => {
        searchActive = [...searchResults.querySelectorAll(".hit")].indexOf(el);
        paintActive();
      });
    });
  }

  function closeSearchResults(){
    searchResults.classList.remove("open");
    searchInput.setAttribute("aria-expanded", "false");
  }

  function pickSearchHit(id){
    const node = nodeIndex.get(id);
    if (!node) return;
    node.forced = true;          // bleibt sichtbar, auch wenn Filter ihn ausblenden
    applyFilters();
    focusNode(node);
    selectNode(node.id);
    closeSearchResults();
    searchHint.textContent = `${searchHits.length} Treffer`;
  }

  function resetSearch(){
    state.query = "";
    state.matches = null;
    searchHits = [];
    searchActive = -1;
    searchHint.textContent = "";
    searchInput.setAttribute("aria-expanded", "false");
    searchResults.innerHTML = "";
    closeSearchResults();
    nodes.forEach(n => { n.forced = false; });
    applyFilters();
  }

  searchInput.addEventListener("input", e => {
    const query = e.target.value.trim().toLowerCase();
    state.query = query;
    if (!query){ resetSearch(); return; }
    let hits = computeHits(query);
    // Ähnliche Namen anhängen – auch wenn es wenige exakte Treffer gibt
    // ("Ronald" findet nur "Ronald Gollatz", nicht "Roland Fürst").
    const similar = fuzzyCandidates(query).filter(n => !hits.includes(n));
    let noteAt = -1;
    if (similar.length && hits.length < 3){
      noteAt = hits.length;
      hits = hits.concat(similar.slice(0, Math.max(0, MAX_RESULTS - hits.length)));
    }
    state.matches = new Set(hits.map(n => n.id));
    searchHint.textContent = hits.length
      ? (noteAt >= 0 ? `${hits.length} Treffer (inkl. ähnlicher Namen)` : `${hits.length} Treffer – bitte in der Liste auswählen`)
      : "keine Treffer";
    renderSearch(hits, noteAt);
    applyFilters();
    if (hits.length === 1){ focusNode(hits[0]); selectNode(hits[0].id); }
  });

  searchInput.addEventListener("keydown", e => {
    if (e.key === "Escape"){ searchInput.value = ""; resetSearch(); searchInput.blur(); return; }
    if (!searchHits.length) return;
    if (e.key === "ArrowDown"){
      e.preventDefault();
      searchActive = Math.min(Math.min(searchHits.length, MAX_RESULTS) - 1, searchActive + 1);
      paintActive();
    } else if (e.key === "ArrowUp"){
      e.preventDefault();
      searchActive = Math.max(0, searchActive - 1);
      paintActive();
    } else if (e.key === "Enter"){
      e.preventDefault();
      const hit = searchHits[Math.max(0, searchActive)];
      if (hit) pickSearchHit(hit.id);
    }
  });

  searchInput.addEventListener("focus", () => {
    if (state.query && searchHits.length) renderSearch(searchHits);
  });
  document.addEventListener("click", e => {
    if (!e.target.closest("#search") && !e.target.closest("#searchResults")) closeSearchResults();
  });
  document.getElementById("weight").addEventListener("input", e => {
    state.minWeight = +e.target.value;
    document.getElementById("weightVal").textContent = state.minWeight;
    applyFilters();
  });
  function updateYearLabel(){
    document.getElementById("yearLabel").textContent = `${state.yearFrom}–${state.yearTo}`;
  }

  function initYearRange(){
    const years = new Set();
    nodes.forEach(n => Object.keys(n.years || {}).forEach(y => years.add(Number(y))));
    edges.forEach(e => Object.keys(e.years || {}).forEach(y => years.add(Number(y))));
    if (!years.size) return;
    const min = Math.min(...years), max = Math.max(...years);
    const from = document.getElementById("yearFrom");
    const to = document.getElementById("yearTo");
    from.min = to.min = String(min);
    from.max = to.max = String(max);
    from.value = String(min);
    to.value = String(max);
    state.yearFrom = min;
    state.yearTo = max;
    updateYearLabel();
  }

  document.getElementById("yearFrom").addEventListener("input", e => {
    state.yearFrom = Math.min(Number(e.target.value), state.yearTo);
    e.target.value = String(state.yearFrom);
    updateYearLabel();
    applyFilters();
  });
  document.getElementById("yearTo").addEventListener("input", e => {
    state.yearTo = Math.max(Number(e.target.value), state.yearFrom);
    e.target.value = String(state.yearTo);
    updateYearLabel();
    applyFilters();
  });

  document.getElementById("sentiFilter").addEventListener("change", e => {
    state.sentiFilter = e.target.value;
    applyFilters();
  });
  document.getElementById("toneFilter").addEventListener("change", e => {
    state.toneFilter = e.target.value;
    applyFilters();
  });
  document.getElementById("minArticles").addEventListener("change", e => {
    state.minArticles = e.target.value; applyFilters();
  });
  document.getElementById("labels").addEventListener("change", e => {
    state.showLabels = e.target.checked; draw();
  });
  document.getElementById("colorMode").addEventListener("change", e => {
    state.colorMode = e.target.value;
    renderLegend();
    draw();
  });

  document.getElementById("evidenceOnly").addEventListener("change", e => {
    state.evidenceOnly = e.target.checked;
    applyFilters();
  });
  document.getElementById("isolated").addEventListener("change", e => {
    state.showIsolated = e.target.checked; applyFilters();
  });
  document.getElementById("btnCenter").addEventListener("click", () => {
    fitView(); draw();
  });
  document.getElementById("btnPng").addEventListener("click", () => {
    const a = document.createElement("a");
    a.download = "personennetzwerk-burgenland.png";
    a.href = canvas.toDataURL("image/png");
    a.click();
  });
  document.getElementById("btnJson").addEventListener("click", () => {
    const blob = new Blob([JSON.stringify(DATA, null, 1)], {type:"application/json"});
    const a = document.createElement("a");
    a.download = "graph.json";
    a.href = URL.createObjectURL(blob);
    a.click();
  });

  function fitView(){
    const vis = visibleNodes();
    if (!vis.length) return;
    // Perzentil-Grenzen statt Min/Max: Einzelne Ausreißer weit draußen würden
    // sonst den Maßstab so klein machen, dass der Kern verschwindet.
    // Für den Bildausschnitt zählt der Zusammenhang, nicht die Randnotizen:
    // Knoten mit mindestens zwei Beziehungen bilden den Kern.
    const core = vis.filter(n => Number.isFinite(n.x) && Number.isFinite(n.y) && (n.degree || 0) >= 2);
    const finite = core.length > vis.length * 0.25
      ? core
      : vis.filter(n => Number.isFinite(n.x) && Number.isFinite(n.y));
    if (!finite.length) { view.k = 0.5; view.x = W()/2; view.y = H()/2; return; }
    const xs = finite.map(n => n.x).sort((a,b) => a-b);
    const ys = finite.map(n => n.y).sort((a,b) => a-b);
    const pick = (arr, q) => arr[Math.min(arr.length-1, Math.max(0, Math.floor(q*(arr.length-1))))];
    const lo = 0.08, hi = 0.92;
    let minX = pick(xs, lo), maxX = pick(xs, hi), minY = pick(ys, lo), maxY = pick(ys, hi);
    if (!Number.isFinite(minX) || !Number.isFinite(maxX) || maxX - minX > 40000 || maxY - minY > 40000){
      view.k = 0.5; view.x = W()/2; view.y = H()/2; return;
    }
    const pad = 90;
    const k = Math.min(3.5, 1.1 * Math.min((W()-pad*2)/Math.max(1,maxX-minX), (H()-pad*2)/Math.max(1,maxY-minY)));
    view.k = Math.max(0.2, k);
    view.x = W()/2 - (minX+maxX)/2 * view.k;
    view.y = H()/2 - (minY+maxY)/2 * view.k;
  }

  // ---------- Start ----------
  document.getElementById("loading").classList.add("on");
  resize();
  initLayout();
  const iterations = nodes.length > 1500 ? 90 : nodes.length > 1200 ? 110 : nodes.length > 700 ? 160 : 260;
  simulate(iterations);
  const maxWeight = Math.max(...DATA.edges.map(e => e.weight), 3);
  const slider = document.getElementById("weight");
  slider.max = Math.min(8, maxWeight);
  renderStats();
  initYearRange();
  renderPartyChips();
  renderLegend();
  fitView();
  applyFilters();
  if (DATA.edges.length){
    const top = DATA.edges[0];
    const a = nodeIndex.get(top.source);
    if (a){ selectNode(a.id); }
  }
  document.getElementById("loading").classList.remove("on");
  // Für Fehlersuche im Browser: window.__DBG__ in der Konsole inspizierbar.
  window.__DBG__ = {nodes, edges, state, view, separate, simulate, get visibleNodes(){return nodes.filter(n=>n.visible).length;},
                    get visibleEdges(){return edges.filter(e=>e.visible).length;},
                    get positions(){return nodes.slice(0,5).map(n=>({name:n.name,x:n.x,y:n.y}));}};
})();