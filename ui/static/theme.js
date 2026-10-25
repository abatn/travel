// Theme-Umschaltung: System (Default) -> gespeicherte Wahl in localStorage["theme"].
// Das Inline-Script im <head> setzt data-theme bereits vor dem ersten Paint (kein FOUC).
(function () {
  var KEY = 'theme';
  var root = document.documentElement;
  var mq = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  var btn = document.getElementById('theme-toggle');
  var meta = document.querySelector('meta[name="theme-color"]');

  function stored() {
    try {
      var v = localStorage.getItem(KEY);
      return (v === 'light' || v === 'dark') ? v : null;
    } catch (e) { return null; }
  }

  function systemTheme() {
    return (mq && mq.matches) ? 'dark' : 'light';
  }

  function resolved() {
    return stored() || systemTheme();
  }

  function label(theme) {
    if (!btn) return '';
    var key = theme === 'dark' ? 'labelToLight' : 'labelToDark';
    return btn.dataset[key] || btn.dataset.labelDefault || 'Theme';
  }

  function apply(theme) {
    root.setAttribute('data-theme', theme);
    root.style.colorScheme = theme;
    if (meta) {
      var color = theme === 'dark' ? meta.dataset.themeDark : meta.dataset.themeLight;
      if (color) meta.setAttribute('content', color);
    }
    if (btn) {
      var text = label(theme);
      btn.setAttribute('aria-label', text);
      btn.setAttribute('title', text);
      // aria-pressed = "Dark aktiv?" – der Button schaltet zwischen den Modi um.
      btn.setAttribute('aria-pressed', theme === 'dark' ? 'true' : 'false');
    }
    document.dispatchEvent(new CustomEvent('themechange', { detail: { theme: theme, preference: stored() || 'system' } }));
  }

  function render() { apply(resolved()); }

  // Sofort anwenden (idempotent zum Inline-Script), dann Button verdrahten.
  render();
  if (btn) {
    btn.addEventListener('click', function () {
      var next = resolved() === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem(KEY, next); } catch (e) { /* privater Modus */ }
      apply(next);
    });
  }

  // Systemwechsel nur beachten, solange keine eigene Wahl gespeichert ist.
  if (mq) {
    var onSystemChange = function () { if (!stored()) render(); };
    if (mq.addEventListener) mq.addEventListener('change', onSystemChange);
    else if (mq.addListener) mq.addListener(onSystemChange);
  }

  // Wahl in einem anderen Tab geändert.
  window.addEventListener('storage', function (e) {
    if (e.key === KEY) render();
  });

  // Für Tests/Debug: gespeicherte Wahl zurücksetzen.
  window.resetTheme = function () {
    try { localStorage.removeItem(KEY); } catch (e) { /* ignore */ }
    render();
  };
})();
