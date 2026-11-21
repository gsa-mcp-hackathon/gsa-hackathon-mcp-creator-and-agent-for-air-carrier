/* Air Carrier front center. No dependencies. */
(function () {
  "use strict";

  // ---- theme ------------------------------------------------------------
  // Light is the default. Dark is applied only when the person chose it with
  // the toggle; the OS preference is not consulted. Until 2026-11-20 this
  // file fell back to the OS preference and saved it as if chosen, so a dark
  // laptop opened the app dark for good. The new key drops those saved values.
  var KEY = "ac-theme-choice";
  function apply(t, remember) {
    document.documentElement.setAttribute("data-theme", t);
    if (remember) { try { localStorage.setItem(KEY, t); } catch (e) {} }
  }
  var saved = null;
  try { saved = localStorage.getItem(KEY); localStorage.removeItem("ac-theme"); } catch (e) {}
  apply(saved === "dark" ? "dark" : "light", false);

  document.addEventListener("click", function (e) {
    var t = e.target.closest("[data-theme-toggle]");
    if (t) {
      apply(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark", true);
      return;
    }
    // ---- lightbox -------------------------------------------------------
    var img = e.target.closest("[data-lightbox]");
    if (img) {
      var lb = document.getElementById("lightbox");
      lb.querySelector("img").src = img.getAttribute("data-full") || img.src;
      lb.classList.add("on");
      return;
    }
    if (e.target.closest("#lightbox")) {
      document.getElementById("lightbox").classList.remove("on");
    }
    // ---- filter chips ---------------------------------------------------
    var chip = e.target.closest("[data-filter]");
    if (chip) {
      var scope = chip.closest("[data-filter-scope]") || document;
      scope.querySelectorAll("[data-filter]").forEach(function (c) { c.classList.remove("on"); });
      chip.classList.add("on");
      var want = chip.getAttribute("data-filter");
      var target = document.querySelector(chip.getAttribute("data-target"));
      if (!target) return;
      target.querySelectorAll("[data-tags]").forEach(function (row) {
        var tags = row.getAttribute("data-tags") || "";
        row.classList.toggle("hide", want !== "*" && tags.indexOf(want) === -1);
      });
    }
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      var lb = document.getElementById("lightbox");
      if (lb) lb.classList.remove("on");
    }
  });

  // ---- live search ------------------------------------------------------
  document.addEventListener("input", function (e) {
    var box = e.target.closest("[data-search]");
    if (!box) return;
    var target = document.querySelector(box.getAttribute("data-search"));
    if (!target) return;
    var q = box.value.trim().toLowerCase();
    var n = 0;
    target.querySelectorAll("[data-row]").forEach(function (row) {
      var hit = !q || row.textContent.toLowerCase().indexOf(q) !== -1;
      row.classList.toggle("hide", !hit);
      if (hit) n++;
    });
    var out = document.querySelector(box.getAttribute("data-count"));
    if (out) out.textContent = n;
  });

  // ---- sortable tables --------------------------------------------------
  document.addEventListener("click", function (e) {
    var th = e.target.closest("th[data-sort]");
    if (!th) return;
    var table = th.closest("table");
    var idx = Array.prototype.indexOf.call(th.parentNode.children, th);
    var desc = th.getAttribute("data-dir") !== "desc";
    th.parentNode.querySelectorAll("th").forEach(function (o) { o.removeAttribute("data-dir"); });
    th.setAttribute("data-dir", desc ? "desc" : "asc");
    var body = table.tBodies[0];
    var rows = Array.prototype.slice.call(body.rows);
    rows.sort(function (a, b) {
      var x = a.cells[idx].getAttribute("data-v") || a.cells[idx].textContent;
      var y = b.cells[idx].getAttribute("data-v") || b.cells[idx].textContent;
      var nx = parseFloat(String(x).replace(/[^0-9.\-]/g, ""));
      var ny = parseFloat(String(y).replace(/[^0-9.\-]/g, ""));
      var c = (!isNaN(nx) && !isNaN(ny)) ? nx - ny : String(x).localeCompare(String(y));
      return desc ? -c : c;
    });
    rows.forEach(function (r) { body.appendChild(r); });
  });
})();

/* ---- grouped navigation -------------------------------------------------
   Click to open, not hover. A hover menu opens when someone is on their way
   somewhere else, and on a touch screen it either does nothing or needs two
   taps. Click is unambiguous on both. Escape closes, arrow keys walk the
   items, and focus leaving the group closes it, so the menu is usable
   without a mouse. */
(function () {
  var groups = [].slice.call(document.querySelectorAll('.navgroup'));
  if (!groups.length) return;

  function close(g) {
    g.removeAttribute('data-open');
    var b = g.querySelector('.navtop');
    if (b) b.setAttribute('aria-expanded', 'false');
  }
  function closeAll(except) {
    groups.forEach(function (g) { if (g !== except) close(g); });
  }
  function open(g) {
    closeAll(g);
    g.setAttribute('data-open', '1');
    var b = g.querySelector('.navtop');
    if (b) b.setAttribute('aria-expanded', 'true');
  }

  groups.forEach(function (g) {
    var btn = g.querySelector('.navtop');
    var items = [].slice.call(g.querySelectorAll('.navmenu a'));

    btn.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      if (g.getAttribute('data-open') === '1') { close(g); } else { open(g); }
    });

    btn.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        open(g);
        if (items[0]) items[0].focus();
      }
    });

    g.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { close(g); btn.focus(); return; }
      var i = items.indexOf(document.activeElement);
      if (i === -1) return;
      if (e.key === 'ArrowDown') { e.preventDefault(); (items[i + 1] || items[0]).focus(); }
      if (e.key === 'ArrowUp') { e.preventDefault(); (items[i - 1] || btn).focus(); }
    });

    // Focus leaving the group entirely closes it. Checked on the next tick
    // because at focusout time the new target is not yet focused.
    g.addEventListener('focusout', function () {
      setTimeout(function () {
        if (!g.contains(document.activeElement)) close(g);
      }, 0);
    });
  });

  document.addEventListener('click', function (e) {
    if (!e.target.closest('.navgroup')) closeAll(null);
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeAll(null);
  });
})();

/* ---- contribute: pick a question, then answer it -------------------------
   Clicking a question fills the form and scrolls to it rather than opening a
   modal. A modal hides the question you are answering at the moment you are
   answering it, which is when you most want to reread it. */
(function () {
  var form = document.getElementById('capture');
  if (!form) return;
  var gapField = document.getElementById('f-gap');
  var ctx = document.getElementById('f-context');
  var title = document.getElementById('form-title');
  var status = document.getElementById('f-status');

  // 2026-11-11: opening a question loads its brief on demand (nothing is
  // pre-generated), marks the question active, and puts the cursor in the
  // answer box, which sits at the top of the page and stays in view.
  var briefBox = document.getElementById('cx-brief');
  var briefBody = document.getElementById('cb-body');
  var intro = document.getElementById('cx-intro');
  var fileIn = document.getElementById('f-files');
  var fileList = document.getElementById('f-filelist');
  var drop = document.getElementById('f-drop');
  var MAXMB = 10, MAXF = 3, picked = [], seq = 0;

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function li(xs) {
    return (xs || []).map(function (x) { return '<li>' + esc(x) + '</li>'; }).join('');
  }
  function renderBrief(j) {
    var s = j.summary || {}, ev = j.evidence || {}, g = ev.gap || {};
    document.getElementById('cb-exp').textContent = 'Exposure ' + (ev.exposure_display || 'not sized')
      + (g.executor ? ' · sits with ' + g.executor : '');
    var h = '<p class="cb-what">' + esc(s.what_it_is) + '</p>'
      + '<div class="grid g2 cb-cols"><div><h4>What we have</h4><ul>' + li(s.what_we_have) + '</ul></div>'
      + '<div><h4>What is needed</h4><ul>' + li(s.what_is_needed) + '</ul></div></div>';
    if (s.how_you_can_help) h += '<div class="note ok"><b>How you can help.</b> ' + esc(s.how_you_can_help) + '</div>';
    (ev.transactions || []).forEach(function (t) {
      h += '<details class="fig-drill"><summary>Underlying transactions: ' + esc(t.piid) + ' · '
        + esc(t.actions) + ' actions · ' + esc(t.obligation_display) + '</summary>'
        + '<table class="ledger"><thead><tr><th>Mod</th><th>Date</th><th class="num">Obligation</th><th>Description</th></tr></thead>'
        + (t.largest || []).map(function (x) {
          return '<tr><td>' + esc(x.modification_number) + '</td><td>' + esc(x.action_date) + '</td><td class="num">'
            + esc(x.federal_action_obligation) + '</td><td style="font-size:.76rem">'
            + esc(String(x.transaction_description || '').slice(0, 90)) + '</td></tr>';
        }).join('') + '</table><a href="' + esc(t.href) + '">All of them in the detail table</a></details>';
    });
    if ((ev.variances || []).length) {
      h += '<p style="font-size:.8rem;margin:.4rem 0">Cited by '
        + ev.variances.map(function (v) { return '<a href="/variances#' + esc(v.id) + '">' + esc(v.id) + '</a> ' + esc(v.title); }).join('; ') + '</p>';
    }
    var by = s.generated_by === 'model' ? 'Summary by ' + esc(j.model) + ' from the register; a lead, not a reported figure.'
      : esc(s.reason || 'Summary assembled from the register by code.');
    h += '<p class="muted cb-foot">' + by + (j.cached ? ' (cached)' : '') + ' <a href="' + esc((ev.links || {}).register) + '">Register entry</a></p>';
    briefBody.innerHTML = h;
  }
  function openQuestion(b) {
    var id = b.getAttribute('data-answer'), my = ++seq;
    document.querySelectorAll('.cx-qbtn.on').forEach(function (x) { x.classList.remove('on'); });
    b.classList.add('on');
    gapField.value = id;
    ctx.style.display = 'none';
    if (intro) intro.hidden = true;
    if (briefBox) {
      briefBox.hidden = false;
      document.getElementById('cb-id').textContent = id;
      document.getElementById('cb-type').textContent = (b.getAttribute('data-type') || '').toLowerCase();
      document.getElementById('cb-title').textContent = b.getAttribute('data-q') || '';
      document.getElementById('cb-exp').textContent = '';
      briefBody.innerHTML = '<p class="muted"><span class="spin"></span> Writing the brief for ' + esc(id) + '…</p>';
      fetch('/api/gaps/' + encodeURIComponent(id) + '/brief').then(function (r) { return r.json(); })
        .then(function (j) { if (my !== seq) return; if (j.error) { briefBody.innerHTML = '<p class="muted">' + esc(j.error) + '</p>'; return; } renderBrief(j); })
        .catch(function () { if (my === seq) briefBody.innerHTML = '<p class="muted">The brief could not be loaded. You can still answer.</p>'; });
    }
    title.textContent = 'Answering ' + id;
    var card = document.getElementById('form-card');
    if (card.getBoundingClientRect().top < 0) card.scrollIntoView({ behavior: 'smooth', block: 'start' });
    setTimeout(function () { document.getElementById('f-body').focus({ preventScroll: true }); }, 200);
  }
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-answer]');
    if (b) openQuestion(b);
  });

  // Filter: free text plus a type chip, in place.
  var search = document.getElementById('q-search'), typeSel = '';
  function applyFilter() {
    var q = (search && search.value || '').trim().toLowerCase(), n = 0;
    document.querySelectorAll('#q-list .cx-qbtn').forEach(function (b) {
      var ok = (!q || b.getAttribute('data-text').indexOf(q) >= 0)
        && (!typeSel || (typeSel === 'easy' ? b.getAttribute('data-easy') === '1' : b.getAttribute('data-type') === typeSel));
      b.parentNode.hidden = !ok; if (ok) n++;
    });
    var c = document.getElementById('q-count'); if (c) c.textContent = n;
  }
  if (search) search.addEventListener('input', applyFilter);
  var chips = document.getElementById('q-types');
  if (chips) chips.addEventListener('click', function (e) {
    var c = e.target.closest('[data-type]'); if (!c) return;
    chips.querySelectorAll('.chip').forEach(function (x) { x.classList.remove('on'); });
    c.classList.add('on'); typeSel = c.getAttribute('data-type'); applyFilter();
  });

  // Attachments: read in the browser, sent as base64 in the JSON body.
  function showFiles() {
    fileList.innerHTML = picked.map(function (f, i) {
      return '<li>' + esc(f.name) + ' <span class="muted">' + (f.size / 1048576).toFixed(1) + ' MB</span> '
        + '<button type="button" class="linkbtn" data-rm="' + i + '">remove</button></li>';
    }).join('');
  }
  function addFiles(list) {
    Array.prototype.forEach.call(list, function (f) {
      if (picked.length >= MAXF) { status.textContent = 'At most ' + MAXF + ' files.'; return; }
      if (f.size > MAXMB * 1048576) { status.textContent = f.name + ' is larger than ' + MAXMB + ' MB.'; return; }
      picked.push(f);
    });
    showFiles();
  }
  if (fileIn) fileIn.addEventListener('change', function () { addFiles(fileIn.files); fileIn.value = ''; });
  if (fileList) fileList.addEventListener('click', function (e) {
    var r = e.target.closest('[data-rm]'); if (!r) return;
    picked.splice(+r.getAttribute('data-rm'), 1); showFiles();
  });
  if (drop) {
    ['dragover', 'dragenter'].forEach(function (ev) { drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add('over'); }); });
    ['dragleave', 'drop'].forEach(function (ev) { drop.addEventListener(ev, function () { drop.classList.remove('over'); }); });
    drop.addEventListener('drop', function (e) { e.preventDefault(); addFiles(e.dataTransfer.files); });
  }
  function b64(f) {
    return new Promise(function (ok, bad) {
      var r = new FileReader();
      r.onload = function () { ok({ name: f.name, type: f.type, size: f.size, b64: String(r.result).split(',')[1] || '' }); };
      r.onerror = bad; r.readAsDataURL(f);
    });
  }

  form.addEventListener('reset', function () {
    gapField.value = '';
    ctx.style.display = 'none';
    title.textContent = 'Tell us what you know';
    status.textContent = '';
    picked = []; showFiles();
    if (briefBox) briefBox.hidden = true;
    if (intro) intro.hidden = false;
    document.querySelectorAll('.cx-qbtn.on').forEach(function (x) { x.classList.remove('on'); });
  });

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var fd = new FormData(form);
    var payload = { kind: 'sme_assertion' };
    fd.forEach(function (v, k) { if (typeof v === 'string') payload[k] = v; });
    if (!(payload.body || '').trim() && !picked.length) {
      status.textContent = 'Write an answer or attach a document.'; status.style.color = 'var(--warn)'; return;
    }
    status.textContent = 'sending...'; status.style.color = '';
    Promise.all(picked.map(b64)).then(function (atts) {
      payload.attachments = atts;
      return fetch('/api/capture', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
      });
    }).then(function (r) { return r.json(); }).then(function (j) {
      // Say exactly what happened. "Thanks!" when nothing was stored is the
      // kind of small lie that stops people contributing a second time.
      if (j.error) { status.textContent = j.error; status.style.color = 'var(--warn)'; return; }
      var refused = (j.refused || []).length ? ' Not accepted: ' + j.refused.join('; ') + '.' : '';
      if (j.stored) {
        status.textContent = 'Recorded, thank you. ' + (j.note || '') + refused;
      } else {
        status.textContent = 'Received, but not stored: ' + (j.note || '') + ' Keep a copy of what you wrote.' + refused;
      }
      status.style.color = j.stored ? 'var(--ok)' : 'var(--warn)';
    }).catch(function () {
      status.textContent = 'Could not reach the server. Nothing was sent.';
      status.style.color = 'var(--bad)';
    });
  });
})();

/* ---- knowledge base search ---------------------------------------------- */
(function () {
  var go = document.getElementById('kbgo');
  if (!go) return;
  var q = document.getElementById('kbq');
  var auth = document.getElementById('kbauth');
  var res = document.getElementById('kbres');

  function run() {
    if (!q.value.trim()) return;
    res.innerHTML = '<p class="muted">searching...</p>';
    fetch('/api/search?q=' + encodeURIComponent(q.value) +
          '&authoritative=' + (auth.checked ? 'true' : 'false'))
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (j.error) { res.innerHTML = '<p class="muted">' + j.error + '</p>'; return; }
        if (!j.count) { res.innerHTML = '<p class="muted">Nothing matched.</p>'; return; }
        res.innerHTML = j.hits.map(function (h) {
          return '<div class="kbhit"><span class="cit">' + h.citation +
            ' · ' + h.grade + '</span><p>' +
            h.text.replace(/</g, '&lt;').slice(0, 520) + '…</p></div>';
        }).join('');
      });
  }
  go.addEventListener('click', run);
  q.addEventListener('keydown', function (e) { if (e.key === 'Enter') run(); });
})();

function esc(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function usd(s) {
  var n = Number(s);
  if (s === '' || isNaN(n)) return esc(s);
  return (n < 0 ? '-$' : '$') + Math.abs(n).toLocaleString('en-US',
    { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/* ---- detail table ---------------------------------------------------------
   Server does the filtering, sorting and the exact sum, so the total under the
   table is the total over every matching row, not the page on screen. */
(function () {
  var root = document.getElementById('xp');
  if (!root) return;
  var ds = root.getAttribute('data-ds');
  var st = { q: '', sort: '', desc: false, page: 1, f: {} };
  var q = document.getElementById('xp-q');
  var tbl = document.getElementById('xp-table');
  var timer;

  function params(withPage) {
    var p = new URLSearchParams();
    if (st.q) p.set('q', st.q);
    if (st.sort) { p.set('sort', st.sort); if (st.desc) p.set('desc', '1'); }
    Object.keys(st.f).forEach(function (k) { if (st.f[k]) p.set('f.' + k, st.f[k]); });
    if (withPage) p.set('page', st.page);
    return p.toString();
  }

  function load() {
    fetch('/api/explore/' + ds + '?' + params(true)).then(function (r) { return r.json(); })
      .then(render).catch(function () {
        tbl.innerHTML = '<tbody><tr><td class="muted">Could not load the table.</td></tr></tbody>';
      });
    document.getElementById('xp-csv').href = '/api/explore/' + ds + '/csv?' + params(false);
  }

  function render(j) {
    var cols = j.columns;
    var h = '<thead><tr>' + cols.map(function (c) {
      var on = j.sort === c.field;
      return '<th class="' + (c.kind === 'usd' || c.kind === 'int' ? 'num ' : '') + 'sortable" ' +
        'data-f="' + c.field + '" aria-sort="' + (on ? (j.desc ? 'descending' : 'ascending') : 'none') +
        '" tabindex="0">' + esc(c.label) + (on ? (j.desc ? ' ▾' : ' ▴') : '') + '</th>';
    }).join('') + '</tr></thead><tbody>';
    h += j.rows.map(function (r) {
      return '<tr>' + cols.map(function (c) {
        var v = r[c.field];
        if (c.kind === 'usd') return '<td class="num mono">' + usd(v) + '</td>';
        if (c.kind === 'int') return '<td class="num">' + esc(v) + '</td>';
        if (c.field === 'table_id') return '<td><button type="button" class="linkbtn" data-cells="' +
          esc(v) + '">open</button></td>';
        if (c.field === '_row_sha') return '<td class="mono muted" title="' + esc(v) + '">' +
          esc(String(v).slice(0, 10)) + '</td>';
        var s = String(v == null ? '' : v);
        return '<td' + (s.length > 90 ? ' title="' + esc(s) + '"' : '') + '>' +
          esc(s.length > 90 ? s.slice(0, 90) + '…' : s) + '</td>';
      }).join('') + '</tr>';
    }).join('') || '<tr><td colspan="' + cols.length + '" class="muted">Nothing matches.</td></tr>';
    tbl.innerHTML = h + '</tbody>';

    var s = '<b>' + j.total.toLocaleString() + '</b> of ' + j.of.toLocaleString() + ' rows';
    if (j.sum !== null && j.sum !== undefined) s += ' · ' + esc(j.sum_field) + ' total <b class="mono">' + usd(j.sum) + '</b>';
    document.getElementById('xp-sum').innerHTML = s;

    var fx = document.getElementById('xp-facets');
    if (!fx.dataset.built) {
      fx.innerHTML = Object.keys(j.facets).map(function (k) {
        var label = (cols.filter(function (c) { return c.field === k; })[0] || {}).label || k;
        return '<select data-facet="' + k + '" aria-label="' + esc(label) + '"><option value="">All ' +
          esc(label.toLowerCase()) + '</option>' + j.facets[k].map(function (kv) {
            return '<option value="' + esc(kv[0]) + '">' + esc(kv[0] || '(blank)') + ' (' + kv[1] + ')</option>';
          }).join('') + '</select>';
      }).join(' ');
      fx.dataset.built = '1';
    }

    var pg = document.getElementById('xp-pager');
    pg.innerHTML = j.pages > 1 ? '<button type="button" class="btn" data-pg="-1"' + (j.page <= 1 ? ' disabled' : '') +
      '>Previous</button> <span class="muted">page ' + j.page + ' of ' + j.pages + '</span> ' +
      '<button type="button" class="btn" data-pg="1"' + (j.page >= j.pages ? ' disabled' : '') + '>Next</button>' : '';
  }

  root.addEventListener('click', function (e) {
    var th = e.target.closest('th[data-f]');
    if (th) {
      var f = th.getAttribute('data-f');
      st.desc = st.sort === f ? !st.desc : false;
      st.sort = f; st.page = 1; load(); return;
    }
    var pb = e.target.closest('[data-pg]');
    if (pb) { st.page += Number(pb.getAttribute('data-pg')); load(); return; }
    var cb = e.target.closest('[data-cells]');
    if (cb) cells(cb.getAttribute('data-cells'));
  });
  root.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && e.target.matches('th[data-f]')) e.target.click();
  });
  root.addEventListener('change', function (e) {
    if (!e.target.matches('[data-facet]')) return;
    st.f[e.target.getAttribute('data-facet')] = e.target.value; st.page = 1; load();
  });
  q.addEventListener('input', function () {
    clearTimeout(timer);
    timer = setTimeout(function () { st.q = q.value.trim(); st.page = 1; load(); }, 250);
  });

  function cells(id) {
    var box = document.getElementById('xp-cells');
    var body = document.getElementById('xp-cells-body');
    box.classList.remove('hide');
    body.innerHTML = '<p class="muted">Reading cells…</p>';
    box.scrollIntoView({ behavior: 'smooth', block: 'start' });
    fetch('/api/exhibit/' + encodeURIComponent(id)).then(function (r) { return r.json(); }).then(function (j) {
      document.getElementById('xp-cells-title').textContent =
        (j.title || 'Exhibit table') + ' · ' + (j.filename || '') + ' p.' + (j.page || '');
      if (j.error) { body.innerHTML = '<p class="muted">' + esc(j.error) + '</p>'; return; }
      if (!j.grid) {
        body.innerHTML = '<div class="note">Cells are not shipped with the app (' + j.n_rows + ' rows x ' +
          j.n_cols + ' columns). ' + esc(j.reason) + ' The table is on page ' + esc(j.page) +
          ' of ' + esc(j.filename) + '.</div>';
        return;
      }
      body.innerHTML = '<div class="tscroll"><table class="ledger"><tbody>' + j.grid.map(function (row, i) {
        var t = j.header_rows && j.header_rows[i] ? 'th' : 'td';
        return '<tr>' + row.map(function (v) { return '<' + t + '>' + esc(v) + '</' + t + '>'; }).join('') + '</tr>';
      }).join('') + '</tbody></table></div><p class="muted" style="font-size:.76rem">Live from the cell store.</p>';
    });
  }
  load();
})();

/* ---- ask the evidence -----------------------------------------------------
   The answer is shown with the tools that produced it and its citations, and
   marked as a lead every time, so it cannot be mistaken for a reported figure. */
(function () {
  var form = document.getElementById('ask-form');
  if (!form) return;
  var log = document.getElementById('ask-log');
  var q = document.getElementById('ask-q');
  var go = document.getElementById('ask-go');
  var history = [];

  function md(s) {
    var lines = esc(s).split('\n'), out = [], tbl = [];
    function flush() {
      if (!tbl.length) return;
      var rows = tbl.filter(function (l) { return !/^\|\s*:?-{2,}/.test(l); });
      out.push('<table class="ledger">' + rows.map(function (l, i) {
        var cells = l.replace(/^\||\|$/g, '').split('|');
        var t = i === 0 ? 'th' : 'td';
        return '<tr>' + cells.map(function (c) { return '<' + t + '>' + c.trim() + '</' + t + '>'; }).join('') + '</tr>';
      }).join('') + '</table>');
      tbl = [];
    }
    lines.forEach(function (l) {
      if (/^\s*\|/.test(l)) { tbl.push(l.trim()); return; }
      flush();
      if (/^\s*[-*] /.test(l)) out.push('<li>' + l.replace(/^\s*[-*] /, '') + '</li>');
      else if (l.trim()) out.push('<p>' + l + '</p>');
    });
    flush();
    return out.join('').replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\[([^\]]{1,80})\]/g, '<span class="cit">[$1]</span>');
  }

  function add(cls, html) {
    var d = document.createElement('div');
    d.className = 'msg ' + cls; d.innerHTML = html; log.appendChild(d);
    d.scrollIntoView({ behavior: 'smooth', block: 'end' });
    return d;
  }

  function ask(text) {
    add('me', '<p>' + esc(text) + '</p>');
    var wait = add('bot', '<p class="muted">Working through the evidence… this can take 20 seconds.</p>');
    go.disabled = true;
    fetch('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: text, history: history }) })
      .then(function (r) { return r.json(); }).then(function (j) {
        var h = '<span class="b b-warn">lead</span> ';
        if (j.error) { wait.innerHTML = '<p class="muted">' + esc(j.error) + '</p>'; return; }
        if (j.mode === 'search-only') {
          h += '<span class="muted">' + esc(j.reason) + ' Closest passages:</span>' +
            (j.hits || []).map(function (x) { return '<div class="kbhit"><span class="cit">' + esc(x.cite) +
              '</span><p>' + esc(x.text) + '</p></div>'; }).join('');
        } else {
          h += md(j.answer || '(no answer)');
          history.push({ role: 'user', content: text }, { role: 'assistant', content: j.answer || '' });
        }
        if (j.trace && j.trace.length) h += '<details class="trace"><summary>' + j.trace.length +
          ' tool call' + (j.trace.length > 1 ? 's' : '') + ' · ' + esc(j.model || '') + ' · ' + j.seconds + 's</summary>' +
          j.trace.map(function (t) { return '<div class="mono">' + (t.ok ? '✓ ' : '✗ ') + esc(t.tool) + ' ' +
            esc(JSON.stringify(t.args)) + (t.note ? ' <span class="muted">' + esc(t.note) + '</span>' : '') + '</div>'; }).join('') +
          '</details>';
        if (j.citations && j.citations.length) h += '<div class="cites">' + j.citations.slice(0, 12).map(function (c) {
          return '<span class="chip">' + esc(c.label) + '</span>'; }).join('') + '</div>';
        wait.innerHTML = h;
      }).catch(function () {
        wait.innerHTML = '<p class="muted">Could not reach the server.</p>';
      }).finally(function () { go.disabled = false; });
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var t = q.value.trim(); if (!t) return;
    q.value = ''; ask(t);
  });
  q.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
  });
  document.getElementById('ask-starters').addEventListener('click', function (e) {
    var b = e.target.closest('[data-ask]'); if (b) ask(b.textContent.trim());
  });
})();
