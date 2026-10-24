// Live-Anzeige des Suchlaufs: pollt den Job-Status und fuellt die Ergebnislisten.
(function () {
  const form = document.getElementById('searchform');
  if (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      const data = new FormData(form);
      const body = new URLSearchParams(data);
      const delay = (typeof window.homeAgentRun === 'function') ? window.homeAgentRun(body) : 0;
      fetch('/api/search', { method: 'POST', body: body })
        .then(r => r.json())
        .then(d => {
          const go = () => { window.location.href = '/jobs/' + d.job_id; };
          if (delay) { setTimeout(go, delay); } else { go(); }
        })
        .catch(err => alert('Suche konnte nicht gestartet werden: ' + err));
    });
  }

  // ---------------------------------------------------------- Orts-Autocomplete
  const placeCategory = (function () {
    const cats = Array.from(document.querySelectorAll('input[name="categories"]:checked'))
      .map(el => el.value);
    if (cats.length === 1) return cats[0];
    if (document.querySelector('input[name="categories"][value="flights"]:checked')) return 'flights';
    return cats[0] || 'flights';
  })();
  const list = document.getElementById('places');
  if (list) {
    const inputs = document.querySelectorAll(
      'input[name="origin"], input[name="destination"], input[name="city"], ' +
      'input[name="ferry_origin"], input[name="ferry_destination"], ' +
      'input[name="cruise_origin"], input[name="cruise_destination"]');
    const timer = {};
    inputs.forEach(function (input) {
      input.setAttribute('list', 'places');
      input.setAttribute('autocomplete', 'off');
      input.addEventListener('input', function () {
        const q = input.value.trim();
        clearTimeout(timer[input.name]);
        if (q.length < 2) return;
        timer[input.name] = setTimeout(function () {
          fetch('/api/resolve/suggest?category=' + placeCategory +
                '&q=' + encodeURIComponent(q))
            .then(r => r.json())
            .then(d => {
              const items = (d.suggestions || []);
              list.innerHTML = items.map(s =>
                '<option value="' + s.code + '">' + s.label + '</option>').join('');
            })
            .catch(() => {});
        }, 220);
      });
      // Nach dem Verlassen: Code/Name anzeigen, wenn es ein Treffer ist
      input.addEventListener('blur', function () {
        const q = input.value.trim();
        if (q.length < 3) return;
        fetch('/api/resolve?category=' + placeCategory + '&text=' + encodeURIComponent(q))
          .then(r => r.json())
          .then(d => {
            if (!d.ok) return;
            input.dataset.resolvedCode = d.code || '';
            input.title = (d.name || '') + (d.code ? ' (' + d.code + ')' : '');
          })
          .catch(() => {});
      });
    });
  }

  const live = document.getElementById('live-status');
  if (!live) return;
  const jobId = window.location.pathname.split('/').pop();
  try { localStorage.setItem('lastJob', jobId); } catch (e) {}

  function statusDot(status) {
    if (status === 'ok') return 'ok';
    if (status === 'skipped') return 'warn';
    if (status === 'waiting') return 'wait';
    if (status === 'error' || status === 'corrupt') return 'err';
    return '';
  }

  // Zeilen in-place aktualisieren; fehlende Zeilen werden angelegt
  // (die Seite kann geladen werden, bevor der Server die Quellenliste geschrieben hat)
  function ensureRow(table, cat, source) {
    let row = table.querySelector('tr[data-source="' + source + '"]');
    if (row) return row;
    const tbody = table.querySelector('tbody');
    if (!tbody) return null;
    const placeholder = tbody.querySelector('tr td[colspan]');
    if (placeholder) placeholder.parentElement.remove();
    row = document.createElement('tr');
    row.dataset.source = source;
    row.innerHTML = '<td class="muted small">' + cat + '</td><td>' + source + '</td>' +
      '<td><span class="dot wait"></span></td><td class="st">wartet</td>' +
      '<td class="it">0</td><td class="du">–</td><td class="er muted small"></td>';
    // alphabetisch einsortieren
    const rows = Array.from(tbody.querySelectorAll('tr[data-source]'));
    const next = rows.find(r => r.dataset.source > source);
    if (next) tbody.insertBefore(row, next); else tbody.appendChild(row);
    return row;
  }

  function renderProviders(cats) {
    const table = document.querySelector('#live-status table');
    if (!table) return {answered: 0, total: 0};
    let answered = 0, total = 0;
    Object.keys(cats || {}).forEach(cat => {
      (cats[cat].providers || []).forEach(p => {
        const row = ensureRow(table, cat, p.source);
        if (!row) return;
        total++;
        if (p.status && p.status !== 'waiting') answered++;
        const cls = statusDot(p.status);
        const dot = row.querySelector('.dot');
        if (dot) dot.className = 'dot ' + cls;
        const st = row.querySelector('td.st');
        if (st) {
          st.textContent = p.status === 'waiting' ? 'wartet' : (p.status || '');
          st.className = 'st ' + cls;
        }
        const it = row.querySelector('td.it');
        if (it) it.textContent = (p.items === null || p.items === undefined) ? '–' : p.items;
        const du = row.querySelector('td.du');
        if (du) du.textContent = (p.elapsed_s === null || p.elapsed_s === undefined)
          ? '–' : p.elapsed_s + ' s';
        const er = row.querySelector('td.er');
        if (er) er.textContent = p.error ? String(p.error).slice(0, 90) : '';
      });
    });
    return {answered: answered, total: total};
  }

  function updateBadges(cats) {
    Object.keys(cats || {}).forEach(cat => {
      const badge = document.getElementById('badge-' + cat);
      if (!badge) return;
      const c = cats[cat];
      if (c.state === 'done') {
        badge.textContent = (c.items || 0) + ' Angebote';
        badge.className = 'tag ok';
      } else if (c.state === 'error') {
        badge.textContent = 'Fehler';
        badge.className = 'tag warn';
      }
    });
  }

  function renderBundling(comp) {
    const box = document.getElementById('bundling');
    if (!box || !comp || box.dataset.filled === 'done') return;
    if (!comp.variants) return;
    const rec = comp.recommendation || {};
    const money = v => (v === null || v === undefined) ? 'n/v'
      : v.toFixed(2).replace('.', ',') + ' ' + (comp.currency || 'EUR');
    let html = '<h2>Bündelungsvorschlag</h2>';
    if (rec.id) {
      html += '<div class="best"><div><span class="label">Empfehlung</span>' +
        '<span class="price">' + money(rec.total) + '</span>' +
        '<span class="muted">' + (rec.label || '') + '</span></div></div>';
    }
    html += '<table class="table"><thead><tr><th>Variante</th><th>Summe</th>' +
      '<th>je Person/Nacht</th></tr></thead><tbody>' +
      (comp.variants || []).map(v => '<tr' + (rec.id === v.id ? ' class="win"' : '') + '>' +
        '<td>' + (v.label || v.id) + '</td><td>' + money(v.total) + '</td>' +
        '<td>' + money(v.price_per_person_night) + '</td></tr>').join('') +
      '</tbody></table>';
    if (comp.decision_notes && comp.decision_notes.length) {
      html += '<ul class="notes">' + comp.decision_notes.map(n => '<li>' + n + '</li>').join('') + '</ul>';
    }
    box.innerHTML = html;
    box.dataset.filled = 'done';
  }

  // ---------------------------------------------------------------- Agenten-Graph
  const SVG_NS = 'http://www.w3.org/2000/svg';
  const graph = { built: false, nodes: {}, edges: {}, centerText: null,
                  centerSub: null, halo: null, sources: [] };

  function svgEl(name, attrs) {
    const el = document.createElementNS(SVG_NS, name);
    Object.keys(attrs || {}).forEach(k => el.setAttribute(k, attrs[k]));
    return el;
  }

  function buildGraph(sources) {
    const svg = document.getElementById('agent-svg');
    if (!svg) return;
    const W = 1000, H = 300, cx = W / 2, cy = H / 2;
    const rx = 392, ry = 100;
    svg.innerHTML = '';

    // weicher Schein fuer den Agenten-Knoten
    const defs = svgEl('defs');
    const grad = svgEl('radialGradient', { id: 'agentGrad', cx: '50%', cy: '50%', r: '50%' });
    grad.appendChild(svgEl('stop', { offset: '0%', 'stop-color': '#4c8dff', 'stop-opacity': '0.55' }));
    grad.appendChild(svgEl('stop', { offset: '100%', 'stop-color': '#4c8dff', 'stop-opacity': '0.05' }));
    defs.appendChild(grad);
    svg.appendChild(defs);

    const edgesG = svgEl('g', { class: 'edges' });
    const nodesG = svgEl('g', { class: 'nodes' });
    svg.appendChild(edgesG);
    svg.appendChild(nodesG);

    const n = sources.length || 1;
    // Gleichmäßig nach Bogenlänge verteilen: bei vielen Quellen überlappen sonst
    // die Knoten am oberen/unteren Ellipsenrand (dort ist der Winkelabstand zu klein).
    const perimeter = [];
    let total = 0, prev = null;
    const STEPS = 720;
    for (let k = 0; k <= STEPS; k++) {
      const a = (k / STEPS) * Math.PI * 2 - Math.PI / 2;
      const px = cx + rx * Math.cos(a), py = cy + ry * Math.sin(a);
      if (prev) total += Math.hypot(px - prev[0], py - prev[1]);
      perimeter.push({ d: total, x: px, y: py });
      prev = [px, py];
    }
    function pointAt(fraction) {
      const target = fraction * total;
      let lo = 0, hi = perimeter.length - 1;
      while (lo < hi) {
        const mid = (lo + hi) >> 1;
        if (perimeter[mid].d < target) lo = mid + 1; else hi = mid;
      }
      const p = perimeter[lo];
      return { x: p.x, y: p.y };
    }

    sources.forEach((src, i) => {
      const pos = pointAt(i / n);
      const x = pos.x, y = pos.y;
      // Kontrollpunkt: leichte Kruemmung
      const mx = (cx + x) / 2, my = (cy + y) / 2;
      const curve = { x: mx + (y - cy) * 0.18, y: my - (x - cx) * 0.18 };

      const d = `M ${cx} ${cy} Q ${curve.x} ${curve.y} ${x} ${y}`;
      const edge = svgEl('path', { d, class: 'edge waiting', 'data-source': src.id,
                                   'fill': 'none', 'stroke-linecap': 'round' });
      const packet = svgEl('circle', { r: 3.2, class: 'packet', 'data-source': src.id });
      packet.style.offsetPath = `path("${d}")`;
      edgesG.appendChild(edge);
      edgesG.appendChild(packet);

      const g = svgEl('g', { class: 'node waiting', 'data-source': src.id,
                             transform: `translate(${x},${y})` });
      const wide = n <= 10 ? 78 : 66;      // bei vielen Quellen schmaler
      g.appendChild(svgEl('rect', { x: -wide, y: -14, width: wide * 2, height: 28, rx: 8 }));
      const label = svgEl('text', { x: 0, y: 5, 'text-anchor': 'middle', class: 'node-label' });
      const maxLen = n <= 10 ? 22 : 17;
      label.textContent = src.id.length > maxLen ? src.id.slice(0, maxLen - 1) + '…' : src.id;
      g.appendChild(label);
      const dot = svgEl('circle', { cx: wide - 8, cy: -9, r: 3.5, class: 'node-dot' });
      g.appendChild(dot);
      nodesG.appendChild(g);

      graph.nodes[src.id] = g;
      graph.edges[src.id] = edge;
      graph.packets = graph.packets || {};
      graph.packets[src.id] = packet;
    });

    // Zentrum
    const center = svgEl('g', { class: 'agent-node' });
    const halo = svgEl('circle', { cx, cy, r: 70, class: 'halo' });
    const ring = svgEl('circle', { cx, cy, r: 54, class: 'agent-ring', fill: 'url(#agentGrad)' });
    const t1 = svgEl('text', { x: cx, y: cy - 8, 'text-anchor': 'middle', class: 'agent-title' });
    t1.textContent = 'Agent';
    const t2 = svgEl('text', { x: cx, y: cy + 16, 'text-anchor': 'middle', class: 'agent-count' });
    t2.textContent = '0/' + sources.length;
    center.appendChild(halo);
    center.appendChild(ring);
    center.appendChild(t1);
    center.appendChild(t2);
    nodesG.appendChild(center);

    graph.centerText = t1;
    graph.centerSub = t2;
    graph.halo = halo;
    graph.sources = sources.map(s => s.id);
    graph.built = true;
  }

  function renderGraph(cats) {
    const sources = [];
    Object.keys(cats || {}).forEach(cat => {
      (cats[cat].providers || []).forEach(p => sources.push({ id: p.source, cat, status: p.status }));
    });
    if (!sources.length) return {answered: 0, total: 0};
    const ids = sources.map(s => s.id).join('|');
    if (!graph.built || (graph.ids && graph.ids !== ids)) {
      buildGraph(sources);
      graph.ids = ids;
      graph.lastStatus = {};
    }
    let answered = 0;
    sources.forEach(src => {
      const status = src.status || 'waiting';
      if (status !== 'waiting') answered++;
      const cls = status === 'ok' ? 'ok'
        : (status === 'skipped' || status === 'corrupt') ? 'skipped'
        : status === 'error' ? 'error' : 'waiting';
      const node = graph.nodes[src.id];
      const edge = graph.edges[src.id];
      if (node) node.setAttribute('class', 'node ' + cls);
      if (edge) edge.setAttribute('class', 'edge ' + cls);
      const prev = graph.lastStatus[src.id];
      if (prev && prev === 'waiting' && cls !== 'waiting') {
        // kurzes Aufleuchten, wenn eine Quelle gerade geantwortet hat
        if (edge) {
          edge.setAttribute('class', 'edge ' + cls + ' pulse');
          setTimeout(() => edge.setAttribute('class', 'edge ' + cls), 1200);
        }
      }
      graph.lastStatus[src.id] = cls;
    });
    return {answered: answered, total: sources.length};
  }

  function updateProgress(answered, total, done) {
    const label = document.getElementById('progress-label');
    if (graph.centerSub) graph.centerSub.textContent = answered + '/' + total;
    if (graph.halo) graph.halo.classList.toggle('done', done);
    if (label) {
      label.textContent = done
        ? 'Fertig – ' + answered + '/' + total + ' Quellen haben geantwortet'
        : answered + ' von ' + total + ' Quellen geantwortet …';
    }
    const box = document.querySelector('.agent-graph');
    if (box) box.classList.toggle('done', done);
  }

  function renderTables(cats) {
    Object.keys(cats || {}).forEach(cat => {
      const tbody = document.querySelector('#tbl-' + cat + ' tbody');
      if (!tbody) return;
      const c = cats[cat];
      if (c.state !== 'done') {
        if (!tbody.dataset.filled) {
          tbody.innerHTML = '<tr><td colspan="5" class="muted">Suche läuft …</td></tr>';
        }
        return;
      }
      if (tbody.dataset.filled === 'done') return;
      const rows = (c.top || []);
      tbody.dataset.filled = 'done';
      if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="muted">Keine Angebote in dieser Kategorie.</td></tr>';
        return;
      }
      tbody.innerHTML = rows.map((r, i) =>
        '<tr><td>' + (r.price === null || r.price === undefined ? 'n/v' : r.price.toFixed(2).replace('.', ',') + ' ' + (r.currency || '')) +
        '</td><td>' + (r.all_in === null || r.all_in === undefined ? '<span class="muted">n/v</span>' : r.all_in.toFixed(2).replace('.', ',')) +
        '</td><td>' + (r.provider || r.name || '') + '</td><td class="muted small">' + (r.source || '') + '</td>' +
        '<td><a href="/jobs/' + jobId + '/detail/' + cat + '/' + i + '">Details</a></td></tr>').join('');
    });
  }

  let finished = false;
  function tick() {
    if (finished) return;
    fetch('/api/jobs/' + jobId).then(r => r.json()).then(d => {
      const stat = renderProviders(d.categories);
      renderGraph(d.categories);
      renderTables(d.categories);
      updateBadges(d.categories);
      const done = (d.state === 'done' || d.state === 'error');
      updateProgress(stat.answered, stat.total, done);
      if (d.state === 'done') renderBundling(d.comparison);
      if (done) {
        finished = true;
        const hint = document.getElementById('live-hint');
        if (hint) hint.textContent = d.state === 'done'
          ? 'Suche abgeschlossen – die Preise gelten für den Moment der Abfrage.'
          : 'Suche fehlgeschlagen: ' + (d.error || 'unbekannter Fehler');
        return;
      }
      setTimeout(tick, 1500);
    }).catch(() => { setTimeout(tick, 4000); });
  }
  tick();
})();

// --- Startseite: interaktives Agenten-Schaubild ---------------------------
(function () {
  const svg = document.getElementById('home-agent-svg');
  if (!svg) return;
  const NS = 'http://www.w3.org/2000/svg';
  const CX = 450, CY = 260;
  const CATS = [
    { id: 'flights', label: 'Flüge',        x: CX,  y: 64 },
    { id: 'hotels',  label: 'Hotels',       x: 790, y: CY },
    { id: 'ferries', label: 'Fähren',       x: CX,  y: 456 },
    { id: 'cruises', label: 'Kreuzfahrten', x: 110, y: CY }
  ];
  const counts = {};
  const el = function (name, attrs) {
    const node = document.createElementNS(NS, name);
    for (const key in (attrs || {})) node.setAttribute(key, attrs[key]);
    return node;
  };

  // Verlauf für das Zentrum
  const defs = el('defs');
  const grad = el('radialGradient', { id: 'homeGrad', cx: '50%', cy: '50%', r: '50%' });
  grad.appendChild(el('stop', { offset: '0%', 'stop-color': '#4c8dff', 'stop-opacity': '0.55' }));
  grad.appendChild(el('stop', { offset: '100%', 'stop-color': '#4c8dff', 'stop-opacity': '0.06' }));
  defs.appendChild(grad);
  svg.appendChild(defs);

  const edgesG = el('g', { class: 'home-edges' });
  const nodesG = el('g', { class: 'home-nodes' });
  const centerG = el('g', { class: 'home-center' });
  svg.appendChild(edgesG);
  svg.appendChild(nodesG);
  svg.appendChild(centerG);

  // Schleife: Wahrnehmen -> Planen -> Handeln -> Beobachten
  centerG.appendChild(el('circle', { cx: CX, cy: CY, r: 118, class: 'home-loop' }));
  [['Wahrnehmen', CX - 100, CY - 92, 'p1'],
   ['Planen',     CX + 100, CY - 92, 'p2'],
   ['Handeln',    CX + 100, CY + 106, 'p3'],
   ['Beobachten', CX - 100, CY + 106, 'p4']].forEach(function (p) {
    const t = el('text', { x: p[1], y: p[2], 'text-anchor': 'middle', class: 'home-phase ' + p[3] });
    t.textContent = p[0];
    centerG.appendChild(t);
  });

  // Zentrum
  centerG.appendChild(el('circle', { cx: CX, cy: CY, r: 62, class: 'core' }));
  const title = el('text', { x: CX, y: CY - 6, 'text-anchor': 'middle', class: 'title' });
  title.textContent = 'Agent';
  const mind = el('text', { x: CX, y: CY + 16, 'text-anchor': 'middle', class: 'mind' });
  mind.textContent = 'bereit';
  centerG.appendChild(title);
  centerG.appendChild(mind);

  const nodes = {};
  const edges = {};
  CATS.forEach(function (c) {
    const dx = c.x - CX, dy = c.y - CY, len = Math.hypot(dx, dy) || 1;
    const ux = dx / len, uy = dy / len;
    const x1 = CX + ux * 70, y1 = CY + uy * 70;
    const x2 = c.x - ux * 84, y2 = c.y - uy * 36;
    const mx = (x1 + x2) / 2 - uy * 16, my = (y1 + y2) / 2 + ux * 16;
    const edge = el('path', {
      d: 'M' + x1 + ',' + y1 + ' Q' + mx + ',' + my + ' ' + x2 + ',' + y2,
      class: 'home-edge waiting', 'data-cat': c.id
    });
    edgesG.appendChild(edge);
    edges[c.id] = edge;

    const g = el('g', { class: 'home-node waiting', 'data-cat': c.id, tabindex: '0',
                        role: 'button', 'aria-label': c.label + ' auswählen' });
    g.appendChild(el('rect', { x: c.x - 86, y: c.y - 30, width: 172, height: 60, rx: 12 }));
    const label = el('text', { x: c.x - 70, y: c.y - 4, class: 'label' });
    label.textContent = c.label;
    const sub = el('text', { x: c.x - 70, y: c.y + 14, class: 'sub' });
    sub.textContent = 'wird geprüft';
    g.appendChild(label);
    g.appendChild(sub);
    g.appendChild(el('circle', { cx: c.x + 66, cy: c.y - 14, r: 5, class: 'dot' }));
    nodesG.appendChild(g);
    nodes[c.id] = { g: g, sub: sub };

    const activate = function () {
      const box = document.querySelector('input[name="categories"][value="' + c.id + '"]');
      if (box) {
        box.checked = true;
        mind.textContent = c.label + ' ausgewählt';
      }
    };
    g.addEventListener('click', activate);
    g.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); activate(); }
    });
  });

  function setCategory(cat, status, sub) {
    if (!nodes[cat] || !edges[cat]) return;
    nodes[cat].g.setAttribute('class', 'home-node ' + status);
    edges[cat].setAttribute('class', 'home-edge ' + status);
    if (sub) nodes[cat].sub.textContent = sub;
  }

  function total() {
    return CATS.reduce(function (sum, c) { return sum + (counts[c.id] || 0); }, 0);
  }

  function fromStatus(d) {
    CATS.forEach(function (c) {
      const items = (d.categories || {})[c.id] || [];
      const active = items.filter(function (p) { return p.enabled !== false; });
      const blocked = active.filter(function (p) { return p.blocked_until; });
      if (!active.length) { setCategory(c.id, 'error', 'keine Quelle'); return; }
      if (blocked.length === active.length) {
        setCategory(c.id, 'error', active.length + ' blockiert'); return;
      }
      counts[c.id] = active.length;
      setCategory(c.id, 'waiting', active.length + ' Quellen');
    });
    mind.textContent = 'bereit · ' + total() + ' Quellen';
  }

  function fromJob(d) {
    let ok = 0, all = 0;
    Object.keys(d.categories || {}).forEach(function (cat) {
      const providers = (d.categories[cat] || {}).providers || [];
      if (!providers.length) return;
      const good = providers.filter(function (p) { return p.status === 'ok'; }).length;
      ok += good;
      all += providers.length;
      counts[cat] = providers.length;
      setCategory(cat, good === 0 ? 'error' : 'ok', good + '/' + providers.length + ' ok');
    });
    if (all) {
      mind.textContent = 'letzte Suche · ' + ok + '/' + all + ' ok';
    } else {
      // Lauf ohne Ergebnisse (z. B. noch nicht gestartet) -> normaler Status
      lastJob = null;
      try { localStorage.removeItem('lastJob'); } catch (e) {}
      refreshStatus();
    }
  }

  let lastJob = null;
  function refreshStatus() {
    fetch('/api/status').then(function (r) { return r.json(); })
      .then(function (d) { if (!lastJob) fromStatus(d); })
      .catch(function () { mind.textContent = 'Status nicht verfügbar'; });
  }
  try { lastJob = localStorage.getItem('lastJob'); } catch (e) {}
  if (lastJob) {
    fetch('/api/jobs/' + encodeURIComponent(lastJob))
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (d) { fromJob(d); return; }
        // gemerkter Lauf existiert nicht mehr (z. B. Serverneustart)
        lastJob = null;
        try { localStorage.removeItem('lastJob'); } catch (e) {}
        refreshStatus();
      })
      .catch(function () { lastJob = null; refreshStatus(); });
  }
  refreshStatus();
  setInterval(refreshStatus, 30000);

  // Beim Start einer Suche die Phasen sichtbar machen, dann normal weiterleiten.
  window.homeAgentRun = function (params) {
    const chosen = params.getAll('categories');
    CATS.forEach(function (c) {
      if (chosen.indexOf(c.id) >= 0) setCategory(c.id, 'running', 'läuft');
    });
    mind.textContent = 'Analysiere Anfrage …';
    setTimeout(function () { mind.textContent = 'Frage ' + Math.max(chosen.length, 1) + ' Kategorien ab …'; }, 350);
    setTimeout(function () { mind.textContent = 'Ergebnisse werden zusammengeführt …'; }, 800);
    return 1150;
  };
})();
