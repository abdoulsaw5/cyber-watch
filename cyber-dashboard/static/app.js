(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const SVGNS = "http://www.w3.org/2000/svg";
  const reducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const state = {
    items: [], category: "map", country: null,
    labels: {}, desc: {}, countries: [], health: {}, world: null,
    refreshing: false, total: 0,
    priorityOnly: false, saved: [],
  };
  let pollTimer = null;

  // ---------- helpers ----------
  const ago = (ts) => {
    if (!ts) return "";
    const s = Math.max(0, Date.now() / 1000 - ts);
    if (s < 3600) return Math.max(1, Math.round(s / 60)) + "m ago";
    if (s < 86400) return Math.round(s / 3600) + "h ago";
    return Math.round(s / 86400) + "d ago";
  };
  const el = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  };
  const meta = (name) => state.countries.find((c) => c.name === name);
  const flagUrl = (name) => { const m = meta(name); return m ? `/static/flags/${m.flag}.svg` : ""; };
  const flagImg = (name, extraClass) => {
    const img = el("img", "flag" + (extraClass ? " " + extraClass : ""));
    img.src = flagUrl(name);
    img.alt = name;
    img.title = name;
    img.width = 16; img.height = 12;
    img.loading = "lazy";
    return img;
  };

  // ---------- saved stories (browser storage, per visitor) ----------
  const SAVED_KEY = "cyberwatch-saved";
  const SAVED_MAX = 200;
  const asList = (v) => (Array.isArray(v) ? v.filter((x) => typeof x === "string") : []);
  function loadSaved() {
    try {
      const raw = JSON.parse(localStorage.getItem(SAVED_KEY) || "[]");
      if (!Array.isArray(raw)) return [];
      return raw
        .filter((x) => x && typeof x.id === "string" && typeof x.title === "string" && typeof x.link === "string" && /^https?:\/\//i.test(x.link))
        .map((x) => ({
          id: x.id, title: x.title, link: x.link, source: String(x.source || ""), summary: String(x.summary || ""),
          official: !!x.official, category: String(x.category || ""), ts: Number(x.ts) || 0, savedAt: Number(x.savedAt) || 0,
          severity: x.severity === "urgent" || x.severity === "high" ? x.severity : null,
          categories: asList(x.categories), countries: asList(x.countries), cves: asList(x.cves),
          badges: Array.isArray(x.badges) ? x.badges.filter((b) => b && typeof b.label === "string").map((b) => ({ label: b.label, level: b.level === "urgent" ? "urgent" : "high" })) : [],
        }));
    } catch (e) { return []; }
  }
  function persistSaved() {
    try { localStorage.setItem(SAVED_KEY, JSON.stringify(state.saved)); } catch (e) { /* storage full or blocked */ }
  }
  const isSaved = (id) => state.saved.some((x) => x.id === id);
  const savedItems = () => [...state.saved].sort((a, b) => b.savedAt - a.savedAt);
  function toggleSaved(it) {
    if (isSaved(it.id)) {
      state.saved = state.saved.filter((x) => x.id !== it.id);
    } else {
      state.saved = [{ ...it, savedAt: Date.now() }, ...state.saved].slice(0, SAVED_MAX);
    }
    persistSaved();
    render(true);
  }
  state.saved = loadSaved();

  const inCat = (it, cat) => cat === "map" || cat === "all" || it.categories.includes(cat);
  const catItems = (cat = state.category) => (cat === "saved" ? savedItems() : state.items.filter((it) => inCat(it, cat)));
  const visibleItems = () => catItems().filter((it) =>
    (!state.country || it.countries.includes(state.country)) && (!state.priorityOnly || it.severity));

  function countryCounts() {
    const m = new Map(state.countries.map((c) => [c.name, 0]));
    for (const it of catItems()) for (const n of it.countries) if (m.has(n)) m.set(n, m.get(n) + 1);
    return m;
  }

  // Pairs of countries mentioned together in the same story (for the animated arcs).
  function arcPairs() {
    const pairs = new Map();
    for (const it of catItems()) {
      const cs = it.countries;
      for (let i = 0; i < cs.length; i++) {
        for (let j = i + 1; j < cs.length; j++) {
          const key = [cs[i], cs[j]].sort().join("|");
          pairs.set(key, (pairs.get(key) || 0) + 1);
        }
      }
    }
    let arr = [...pairs.entries()].map(([k, n]) => { const [a, b] = k.split("|"); return { a, b, n }; });
    if (state.country) arr = arr.filter((p) => p.a === state.country || p.b === state.country);
    return arr.sort((x, y) => y.n - x.n).slice(0, 16);
  }

  // ---------- clock ----------
  setInterval(() => { $("clock").textContent = new Date().toLocaleTimeString([], { hour12: false }); }, 1000);

  // ---------- map ----------
  const svg = d3.select("#map");
  let projection, landSel, byIso = new Map();

  // Leave room on the left so the headline panel never covers the Americas.
  const leftInset = () => {
    if (window.innerWidth <= 900) return 10;
    const feed = document.querySelector(".feed");
    return feed ? Math.round(feed.getBoundingClientRect().right) + 18 : 500;
  };

  function drawMap() {
    if (!state.world || !state.countries.length) return;
    const w = window.innerWidth, h = window.innerHeight;
    svg.attr("viewBox", `0 0 ${w} ${h}`).selectAll("*").remove();
    projection = d3.geoNaturalEarth1().fitExtent([[leftInset(), 70], [w - 10, h - 45]], { type: "Sphere" });
    const path = d3.geoPath(projection);
    byIso = new Map(state.countries.map((c) => [c.iso, c]));

    svg.append("path").attr("class", "graticule").attr("d", path(d3.geoGraticule10()));
    const land = topojson.feature(state.world, state.world.objects.countries);
    // Draw non-focus countries first so highlighted ones sit on top.
    const feats = [...land.features].sort((a, b) => byIso.has(String(a.id)) - byIso.has(String(b.id)));
    landSel = svg.append("g").selectAll("path").data(feats).join("path")
      .attr("class", (d) => (byIso.has(String(d.id)) ? "land focus" : "land"))
      .attr("d", path);

    const focus = landSel.filter((d) => byIso.has(String(d.id)));
    focus.attr("tabindex", 0).attr("role", "button")
      .attr("aria-label", (d) => byIso.get(String(d.id)).name)
      .on("click", (_, d) => toggleCountry(byIso.get(String(d.id)).name))
      .on("keydown", (ev, d) => {
        if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); toggleCountry(byIso.get(String(d.id)).name); }
      })
      .append("title");

    svg.append("g").attr("id", "arcs");
    svg.append("g").attr("id", "pins");
    updateMap();
  }

  function drawArcs() {
    const g = svg.select("#arcs");
    g.selectAll("*").remove();
    for (const p of arcPairs()) {
      const A = meta(p.a), B = meta(p.b);
      if (!A || !B) continue;
      const [x1, y1] = projection([A.lon, A.lat]);
      const [x2, y2] = projection([B.lon, B.lat]);
      const dx = x2 - x1, dy = y2 - y1, dist = Math.hypot(dx, dy) || 1;
      // Curve the line upward, like the arcs on a flight or attack map.
      let nx = -dy / dist, ny = dx / dist;
      if (ny > 0) { nx = -nx; ny = -ny; }
      const cx = (x1 + x2) / 2 + nx * dist * 0.28, cy = (y1 + y2) / 2 + ny * dist * 0.28;
      const d = `M${x1},${y1} Q${cx},${cy} ${x2},${y2}`;
      const hot = state.country && (p.a === state.country || p.b === state.country);
      const arc = g.append("path").attr("class", "arc" + (hot ? " hot" : "")).attr("d", d)
        .style("stroke-width", Math.min(3, 1 + p.n * 0.2));
      arc.append("title").text(`${p.a} and ${p.b}: ${p.n} stories mention both`);
      if (!reducedMotion) {
        const spark = g.append("circle").attr("class", "spark").attr("r", 2.2);
        spark.append("animateMotion")
          .attr("dur", `${(3 + (p.n % 4) + dist / 400).toFixed(1)}s`)
          .attr("repeatCount", "indefinite")
          .attr("path", d);
      }
    }
  }

  function updateMap() {
    if (!landSel) return;
    const counts = countryCounts();
    const nameOf = (d) => (byIso.has(String(d.id)) ? byIso.get(String(d.id)).name : null);
    landSel
      .classed("selected", (d) => nameOf(d) !== null && nameOf(d) === state.country)
      .classed("quiet", (d) => nameOf(d) !== null && counts.get(nameOf(d)) === 0);
    landSel.filter((d) => nameOf(d) !== null).select("title")
      .text((d) => `${nameOf(d)}: ${counts.get(nameOf(d))} stories (click to filter)`);

    drawArcs();

    const g = svg.select("#pins");
    g.selectAll("*").remove();
    const data = state.countries.filter((c) => counts.get(c.name) > 0).map((c) => ({ ...c, n: counts.get(c.name) }));
    const pins = g.selectAll("g").data(data).join("g")
      .attr("class", (d) => "pin" + (state.country === d.name ? " active" : ""))
      .attr("transform", (d) => `translate(${projection([d.lon, d.lat])})`)
      .on("click", (_, d) => toggleCountry(d.name));
    pins.append("title").text((d) => `${d.name}: ${d.n} stories`);
    pins.append("circle").attr("class", "ring").attr("r", 4);
    pins.append("circle").attr("class", "core").attr("r", (d) => 3 + Math.min(5, Math.sqrt(d.n)));
    // Flag and count labels only belong on the Global Threat Map tab. On category tabs the pins
    // stay as plain pulsing dots (the flags already appear on each headline).
    if (state.category === "map") {
      pins.append("image").attr("href", (d) => `/static/flags/${d.flag}.svg`)
        .attr("x", 11).attr("y", -7).attr("width", 18).attr("height", 14);
      pins.append("text").attr("x", 33).attr("y", 4)
        .text((d) => (state.country === d.name ? `${d.name}  ${d.n}` : String(d.n)));
    }
  }

  function toggleCountry(name) {
    state.country = state.country === name ? null : name;
    render();
  }

  // ---------- tabs ----------
  function renderTabs() {
    const nav = $("tabs");
    nav.textContent = "";
    for (const [key, label] of Object.entries(state.labels)) {
      const b = el("button", "tab" + (state.category === key ? " on" : ""), label);
      if (key !== "map") {
        const n = catItems(key).filter((it) => !state.country || it.countries.includes(state.country)).length;
        b.appendChild(el("span", "n", String(n)));
      }
      b.addEventListener("click", () => { state.category = key; render(); });
      nav.appendChild(b);
    }
  }

  // ---------- list / leaderboard ----------
  function renderLeaderboard(list) {
    // Most active countries first, but no numbers or bars shown.
    const counts = countryCounts();
    const rows = [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
    list.appendChild(el("li", "lb-hint", "Pick a country here or click it on the map. Switch tabs to narrow by category."));
    for (const [name] of rows) {
      const li = el("li");
      const b = el("button", "lb-row");
      b.appendChild(flagImg(name));
      b.appendChild(document.createTextNode(name));
      b.addEventListener("click", () => toggleCountry(name));
      li.appendChild(b);
      list.appendChild(li);
    }
  }

  function renderRow(it) {
    const li = el("li", "row" + (it.severity ? " sev-" + it.severity : ""));
    const m = el("div", "meta");
    m.appendChild(el("span", "tag" + (it.official ? " official" : ""), it.official ? "Official" : (state.labels[it.category] || it.category)));
    for (const b of it.badges || []) m.appendChild(el("span", "sev " + b.level, b.label));
    m.appendChild(el("span", "", it.source));
    m.appendChild(el("span", "", ago(it.ts)));
    for (const id of it.cves || []) {
      if (!/^CVE-\d{4}-\d{4,7}$/.test(id)) continue;
      const a = el("a", "cve", id);
      a.href = `https://nvd.nist.gov/vuln/detail/${id}`;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.title = "Look up this vulnerability in the National Vulnerability Database";
      m.appendChild(a);
    }
    const known = it.countries.filter((c) => meta(c));
    if (known.length) {
      const fl = el("span", "flags");
      for (const c of known) fl.appendChild(flagImg(c));
      m.appendChild(fl);
    }
    const title = el("button", "row-title", it.title);
    title.addEventListener("click", () => openReader(it));

    const actions = el("div", "actions");
    const saved = isSaved(it.id);
    const star = el("button", "star" + (saved ? " on" : ""), saved ? "\u2605" : "\u2606");
    star.title = saved ? "Remove from saved" : "Save for later";
    star.setAttribute("aria-label", star.title);
    star.setAttribute("aria-pressed", String(saved));
    star.addEventListener("click", () => toggleSaved(it));
    const ext = el("a", "ext", "\u2197");
    ext.href = it.link;
    ext.target = "_blank";
    ext.rel = "noopener noreferrer";
    ext.title = "Open on the original site";
    ext.setAttribute("aria-label", "Open on the original site");
    actions.append(star, ext);

    li.append(m, title, actions);
    return li;
  }

  function renderList() {
    const list = $("list");
    list.textContent = "";
    $("desc").textContent = state.desc[state.category] || "";
    $("clearfilter").classList.toggle("hidden", !state.country);

    const onBoard = state.category === "map" && !state.country;
    $("priority").classList.toggle("hidden", onBoard);
    $("priority").classList.toggle("on", state.priorityOnly);
    $("priority").setAttribute("aria-pressed", String(state.priorityOnly));

    if (onBoard) {
      $("count").textContent = "Threat hotspots";
      renderLeaderboard(list);
      return;
    }

    const items = visibleItems();
    const label = state.labels[state.category] || "";
    const parts = [`${items.length} ${items.length === 1 ? "story" : "stories"}`];
    if (state.country) parts.push(state.country);
    if (state.category !== "map") parts.push(label);
    if (state.priorityOnly) parts.push("Priority only");
    $("count").textContent = parts.join(" \u00b7 ");

    if (!items.length) {
      const where = state.country ? ` mentioning ${state.country}` : "";
      let msg;
      if (state.category === "saved" && !state.saved.length) {
        msg = "Nothing saved yet. Press the star on any story to keep it here. Saved stories stay on this device.";
      } else if (state.priorityOnly) {
        msg = `No priority stories${where} in this view. Turn off Priority only to see everything.`;
      } else if (state.refreshing && state.category !== "saved") {
        msg = "Loading sources. Stories appear here as they arrive.";
      } else {
        msg = `No ${label} stories${where} right now. Try another category, or press Refresh.`;
      }
      list.appendChild(el("li", "empty", msg));
      return;
    }
    for (const it of items) list.appendChild(renderRow(it));
  }

  function renderTicker() {
    const t = $("ticker");
    t.textContent = "";
    for (const it of state.items.slice(0, 30)) {
      const s = el("span");
      s.appendChild(el("b", "", it.source));
      s.appendChild(document.createTextNode(it.title));
      t.appendChild(s);
    }
  }

  function render(keepScroll = false) {
    const sc = keepScroll ? $("list").scrollTop : 0;
    renderTabs();
    renderList();
    updateMap();
    $("list").scrollTop = sc;
  }

  // ---------- source health ----------
  function renderHealth() {
    const entries = Object.entries(state.health);
    const okN = entries.filter(([, h]) => h.ok).length;
    $("healthsum").textContent = `${okN} of ${entries.length} sources working`;
    const ul = $("healthlist");
    ul.textContent = "";
    entries.sort((a, b) => (a[1].ok - b[1].ok) || a[0].localeCompare(b[0]));
    for (const [name, h] of entries) {
      const li = el("li", "hrow");
      li.appendChild(el("span", h.ok ? "ok" : "bad", h.ok ? "✓" : "✗"));
      const mid = el("span", "", name);
      mid.appendChild(el("span", "cat", (state.labels[h.category] || h.category)));
      li.appendChild(mid);
      li.appendChild(el("span", "why", h.ok ? `${h.count} items` : h.error));
      ul.appendChild(li);
    }
  }
  $("updated").addEventListener("click", () => {
    renderHealth();
    $("health").classList.toggle("hidden");
  });
  $("closehealth").addEventListener("click", () => $("health").classList.add("hidden"));

  // ---------- reader ----------
  async function openReader(it) {
    $("reader").classList.remove("hidden");
    $("rsource").textContent = `${it.source}  \u00b7  ${ago(it.ts)}`;
    $("rtitle").textContent = it.title;
    $("openorig").href = it.link;
    const body = $("rtext");
    body.textContent = "Loading article...";
    try {
      const r = await fetch(`/api/article/${encodeURIComponent(it.id)}`);
      if (r.status === 404) {
        body.textContent = "This story has rotated out of the live feed, so no preview is available here. Use Open on site.";
        return;
      }
      if (!r.ok) throw new Error(r.status);
      const data = await r.json();
      body.textContent = "";
      if (data.fallback) {
        body.appendChild(el("div", "note", "This site did not allow full text extraction. Showing the feed summary. Use Open on site to read the full article."));
      }
      if (!data.paragraphs.length) body.appendChild(el("p", "", "No preview available. Use Open on site."));
      for (const p of data.paragraphs) body.appendChild(el("p", "", p));
    } catch (e) {
      body.textContent = "Could not load the article here. Use Open on site.";
    }
    document.querySelector(".reader-body").scrollTop = 0;
  }
  const closeReader = () => $("reader").classList.add("hidden");
  $("closereader").addEventListener("click", closeReader);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { closeReader(); $("health").classList.add("hidden"); }
  });
  $("clearfilter").addEventListener("click", () => { state.country = null; render(); });
  $("priority").addEventListener("click", () => { state.priorityOnly = !state.priorityOnly; render(); });

  // ---------- data ----------
  async function load() {
    clearTimeout(pollTimer);
    try {
      const r = await fetch("/api/news");
      const data = await r.json();
      state.items = data.items;
      state.labels = { ...data.labels, saved: "Saved" };
      state.desc = { ...data.desc, saved: "Stories you starred for later. They are kept in this browser only." };
      state.health = data.health || {};
      state.refreshing = !!data.refreshing;
      state.total = data.total_sources || Object.keys(state.health).length;
      const mapNeedsDraw = !state.countries.length;
      state.countries = data.countries;

      const done = Object.keys(state.health).length;
      const ok = Object.values(state.health).filter((h) => h.ok).length;
      if (state.refreshing && !data.updated) $("updated").textContent = `Loading ${done}/${state.total} sources`;
      else if (state.refreshing) $("updated").textContent = "Refreshing";
      else $("updated").textContent = data.updated
        ? `Updated ${new Date(data.updated).toLocaleTimeString([], { hour12: false })} \u00b7 ${ok}/${state.total} sources OK`
        : "No data yet";

      if (state.world && (mapNeedsDraw || !landSel)) drawMap();
      render(true);
      renderTicker();
      if (!$("health").classList.contains("hidden")) renderHealth();
      // While feeds are still loading, check back every few seconds.
      if (state.refreshing) pollTimer = setTimeout(load, 3000);
    } catch (e) {
      $("updated").textContent = "Backend offline";
      pollTimer = setTimeout(load, 8000);
    }
  }

  $("refresh").addEventListener("click", async () => {
    $("updated").textContent = "Refreshing";
    try { await fetch("/api/refresh", { method: "POST" }); } catch (e) { /* ignore */ }
    load();
  });

  // ---------- boot ----------
  fetch("/static/vendor/countries-110m.json").then((r) => r.json()).then((w) => {
    state.world = w;
    drawMap();
  });
  window.addEventListener("themechange", () => setTimeout(drawMap, 80));
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => setTimeout(drawMap, 30));
  let resizeTimer;
  window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(drawMap, 150); });
  load();
  setInterval(() => { if (!state.refreshing) load(); }, 5 * 60 * 1000);
})();
