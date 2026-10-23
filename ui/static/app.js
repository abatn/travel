// Live-Anzeige des Suchlaufs: pollt den Job-Status und fuellt die Ergebnislisten.
(function () {
  const form = document.getElementById('searchform');
  if (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      const data = new FormData(form);
      const body = new URLSearchParams(data);
      fetch('/api/search', { method: 'POST', body: body })
        .then(r => r.json())
        .then(d => { window.location.href = '/jobs/' + d.job_id; })
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
