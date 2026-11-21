/* SI: the run panel, the review dialog, and the picture's interactive charts.
   Vanilla, no framework, no CDN. Every figure drawn here is a display string
   the server computed; this file never adds, rounds or converts a number.

   Flow: a button that names its scope (data-si-task + data-si-subject) starts
   a run; the panel polls /api/v1/si/runs/{id}?after=N and draws each step as
   it happens, with its agent, rule and whether code or a model wrote it; when
   the run is done the two verdicts and the proposals arrive; "Review N
   proposals" opens the dialog, which asks the server, per proposal, whether
   this person may apply it, and shows the refusal in place when not. */
(function () {
  "use strict";
  var API = "/api/v1/si";
  var dock = document.getElementById("si-dock");
  if (!dock) return;
  var modal = document.getElementById("si-modal");
  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function req(method, url, body) {
    var o = { method: method, credentials: "same-origin", headers: {} };
    if (body !== undefined) { o.headers["Content-Type"] = "application/json"; o.body = JSON.stringify(body); }
    return fetch(url, o).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) {
        if (!r.ok) {
          var d = j && j.detail;
          throw new Error(typeof d === "string" ? d : (d ? JSON.stringify(d) : "HTTP " + r.status));
        }
        return j;
      });
    });
  }

  var KIND = { route: "Route", pack: "Pack", step: "Step", note: "Note", verdict: "Check",
               done: "Done", error: "Stopped", refused: "Refused", gate: "Gate" };
  var STATUS = { queued: "Queued", routing: "Routing to a specialist", packing: "Packing the records",
                 working: "The specialist is working", checking: "Checking the answer twice",
                 ready: "Ready for a person", blocked: "Stopped by a check", failed: "Stopped",
                 decided: "Decided" };
  var VERDICT = { pass: "PASS", pass_with_notes: "PASS WITH NOTES", fail: "FAIL", error: "ERROR",
                  not_run: "NOT RUN" };

  var cur = null, seen = 0, timer = null, lastRun = null, team = [];

  function rule(r) { return r ? '<span class="si-rule" title="Rule ' + esc(r) + '">' + esc(r) + "</span>" : ""; }
  function by(e) {
    if (e.by && e.by !== "code" && e.by !== "none")
      return '<span class="si-by si-by-model" title="Written by a model; grounded by the canvas">' +
        esc(e.by.replace("databricks-", "")) + "</span>";
    return '<span class="si-by" title="Computed by code">code</span>';
  }

  function drawTeam(active) {
    $("si-team").innerHTML = team.map(function (a, i) {
      return '<li class="si-agent si-' + esc(a.kind.toLowerCase()) + (active === a.name ? " on" : "") +
        '" title="' + esc(a.job) + '"><b>' + esc(a.name) + "</b><span>" + esc(a.kind.toLowerCase()) + "</span></li>" +
        (i < team.length - 1 ? '<li class="si-arrow" aria-hidden="true">&rarr;</li>' : "");
    }).join("");
  }

  function stepHTML(e) {
    var res = e.kind === "verdict" && e.data ? (e.data.result || "") : "";
    return '<li class="si-step si-k-' + esc(e.kind) + (res ? " si-v-" + esc(res) : "") + '">' +
      '<div class="si-step-h"><span class="si-who">' + esc(e.agent) + '</span><span class="si-kind">' +
      esc(KIND[e.kind] || e.kind) + "</span>" + rule(e.rule) + by(e) +
      '<time datetime="' + esc(e.at) + '">' + esc((e.at || "").slice(11, 19)) + "</time></div>" +
      "<p>" + esc(e.text) + "</p></li>";
  }

  function openDock() { dock.hidden = false; document.body.classList.add("si-open"); }
  function closeDock() { dock.hidden = true; document.body.classList.remove("si-open"); if (timer) clearTimeout(timer); }

  function reset(label) {
    seen = 0; lastRun = null; team = [];
    $("si-run-no").textContent = "Run";
    $("si-run-label").textContent = label || "Starting";
    $("si-run-q").textContent = "";
    $("si-team").innerHTML = "";
    $("si-steps").innerHTML = "";
    $("si-result").innerHTML = "";
    $("si-status").textContent = "Starting";
    $("si-review").hidden = true;
  }

  function start(task, subject, page, params, label) {
    if (timer) clearTimeout(timer);
    reset(label);
    openDock();
    req("POST", API + "/runs", { task_id: task, subject: subject, page: page, params: params || {} })
      .then(function (j) { cur = j.run_id; absorb(j.run); poll(); })
      .catch(function (err) {
        cur = null; lastRun = null;            // nothing to review or poll
        $("si-review").hidden = true;
        $("si-status").textContent = "Refused";
        $("si-status").className = "si-status si-s-failed";
        $("si-steps").innerHTML = '<li class="si-step si-k-refused"><div class="si-step-h"><span class="si-who">Orchestrator</span>' +
          '<span class="si-kind">Refused</span></div><p>' + esc(err.message) + "</p></li>";
      });
  }

  function absorb(run) {
    if (!run) return;
    if (run.team && run.team.length) team = run.team;
    $("si-run-no").textContent = "Run " + run.run_id.slice(0, 8) + " \u00b7 " + (run.page || "");
    $("si-run-label").textContent = run.label;
    $("si-run-q").textContent = run.question || "";
    $("si-open-log").href = "/runs/" + run.run_id;
    var html = "";
    (run.events || []).forEach(function (e) { if (e.seq > seen) { html += stepHTML(e); seen = e.seq; } });
    if (html) {
      $("si-steps").insertAdjacentHTML("beforeend", html);
      var last = run.events[run.events.length - 1];
      drawTeam(last && last.agent);
      $("si-steps").lastElementChild.scrollIntoView({ block: "nearest" });
    } else if (!$("si-team").innerHTML) { drawTeam(null); }
    $("si-status").textContent = STATUS[run.status] || run.status;
    $("si-status").className = "si-status si-s-" + run.status;
  }

  function poll() {
    if (!cur) return;
    req("GET", API + "/runs/" + cur + "?after=" + seen).then(function (run) {
      absorb(run);
      if (run.done) { lastRun = run; drawTeam(null); result(run); }
      else timer = setTimeout(poll, 700);
    }).catch(function (err) {
      $("si-status").textContent = "Lost the run: " + err.message;
    });
  }

  function verdictHTML(v, name) {
    if (!v) return "";
    var rows = (v.checks || []).map(function (c) {
      return '<tr class="' + (c.result === "pass" ? "" : "si-fail") + '"><td>' + esc(c.name) + '</td><td class="mono">' +
        esc(c.expected) + '</td><td class="mono">' + esc(c.actual) + "</td><td>" + esc(c.result) + "</td></tr>";
    }).join("");
    return '<details class="si-verdict si-v-' + esc(v.result) + '"><summary><b>' + esc(name) + "</b> " +
      '<span class="si-vbadge">' + esc(VERDICT[v.result] || v.result) + "</span>" +
      (v.total ? " <span>" + v.passed + " of " + v.total + " conditions pass</span>" : "") +
      (v.model ? ' <span class="si-by si-by-model">' + esc(v.model.replace("databricks-", "")) + "</span>" : "") +
      "</summary>" + (v.notes ? '<p class="small">' + esc(v.notes) + "</p>" : "") +
      (rows ? '<div class="tscroll"><table class="si-checks"><thead><tr><th>Condition</th><th>Expected</th><th>Actual</th><th>Result</th></tr></thead><tbody>' +
        rows + "</tbody></table></div>" : "") + "</details>";
  }

  function packHTML(p) {
    if (!p) return "";
    var facts = (p.facts || []).map(function (f) {
      return "<tr><td>" + esc(f.label) + '</td><td class="mono">' + esc(f.display) + '</td><td class="small">' +
        esc(f.computation) + "</td><td>" + rule(f.rule) + "</td></tr>";
    }).join("");
    return '<details class="si-pack"><summary>Packed <b>' + esc(p.record_count) + "</b> " + esc(p.noun) +
      " from " + esc(p.source) + ' <span class="mono small">' + esc(p.provenance_id) + "</span>" +
      (p.live ? ' <span class="b b-ok">live</span>' : ' <span class="b b-warn">extract</span>') + "</summary>" +
      (p.notes && p.notes.length ? '<p class="small">' + p.notes.map(esc).join("<br>") + "</p>" : "") +
      '<div class="tscroll"><table class="si-facts"><thead><tr><th>Fact</th><th>Value</th><th>How</th><th>Rule</th></tr></thead><tbody>' +
      facts + "</tbody></table></div></details>";
  }

  function result(run) {
    var h = "";
    if (run.error) h += '<div class="si-error"><b>Stopped.</b> ' + esc(run.error) + "</div>";
    if (run.finding) h += '<div class="si-finding"><h4>Finding</h4><p>' + esc(run.finding) + "</p></div>";
    if (run.flags && run.flags.length) {
      h += '<ul class="si-flags">' + run.flags.map(function (f) {
        return '<li class="si-flag-' + esc(f.severity) + '"><b>Flag for a person</b> ' + esc(f.text) + "</li>";
      }).join("") + "</ul>";
    }
    var v = run.verdicts || {};
    h += '<div class="si-verdicts">' + verdictHTML(v.canvas, "Canvas re-check") +
      verdictHTML(v.records_checker, "Records Checker") + "</div>";
    h += packHTML(run.pack);
    var c = run.counts || {};
    h += '<p class="small si-counts">' + esc(c.proposals || 0) + " proposals: " + esc(c.reviewable || 0) +
      " to review, " + esc(c.applied || 0) + " applied, " + esc(c.rejected || 0) + " rejected, " +
      esc(c.blocked || 0) + " blocked. " + esc((run.persisted && (run.persisted.note || run.persisted.error)) || "") + "</p>";
    $("si-result").innerHTML = h;
    var n = (run.proposals || []).length;
    $("si-review").hidden = n === 0;
    $("si-review").textContent = c.reviewable ? "Review " + c.reviewable + (c.reviewable === 1 ? " proposal" : " proposals") : "See the proposals";
  }

  // ---------------------------------------------------------------- review
  function blanks(p) {
    return (p.marked_blanks || []).map(function (b) {
      return '<div class="si-blank" title="' + esc(b.why) + '"><span>Marked blank</span> ' + esc(b.field) +
        " &middot; <i>" + esc(b.who_fills) + " fills it</i></div>";
    }).join("");
  }
  function flags(p) {
    return (p.flags || []).map(function (f) {
      return '<div class="si-pflag si-flag-' + esc(f.severity) + '">Flags for a person: ' + esc(f.text) + "</div>";
    }).join("");
  }

  function openReview() {
    var run = lastRun; if (!run) return;
    $("si-modal-eyebrow").textContent = "Run " + run.run_id.slice(0, 8) + " \u00b7 Review and decide";
    $("si-modal-h").textContent = run.label;
    $("si-receipt").innerHTML = "";
    $("si-notes-wrap").hidden = true; $("si-notes").value = "";
    var rows = (run.proposals || []).map(function (p) {
      var pending = p.status === "pending";
      return '<tr data-pid="' + esc(p.proposal_id) + '" class="si-p-' + esc(p.status) + '">' +
        '<td><input type="checkbox" aria-label="Apply ' + esc(p.title) + '" ' + (pending ? "checked" : "disabled") + "></td>" +
        "<td><b>" + esc(p.goes_to.office) + '</b><div class="mono small">' + esc(p.goes_to.role) + "</div>" +
          (p.addressed_to ? '<div class="si-addr small">Addressed to <b>' + esc(p.addressed_to) + "</b></div>" : "") + "</td>" +
        '<td><div class="si-ptitle">' + esc(p.title) + "</div><p>" + esc(p.proposed) + "</p>" + blanks(p) + flags(p) +
        (p.status !== "pending" ? '<div class="si-pstate">' + esc(p.status) + (p.block_reason ? ": " + esc(p.block_reason) : "") + "</div>" : "") +
        "</td><td>" + esc(p.why) + '<div class="small">' + (p.drafted_by === "code" ? "Drafted by code" : "Drafted by code, worded by " + esc(p.drafted_by.replace("databricks-", ""))) + "</div></td>" +
        "<td>" + rule(p.rule) + "</td></tr>" +
        '<tr class="si-auth-row" data-auth-for="' + esc(p.proposal_id) + '" hidden><td colspan="5"></td></tr>';
    }).join("");
    $("si-review-rows").innerHTML = rows;
    if (typeof modal.showModal === "function") modal.showModal(); else modal.setAttribute("open", "");
    req("GET", API + "/runs/" + run.run_id + "/authority?action=apply").then(function (j) {
      Object.keys(j.authority || {}).forEach(function (pid) {
        var a = j.authority[pid];
        var tr = $("si-review-rows").querySelector('tr[data-pid="' + pid + '"]');
        if (!tr || a.allowed) return;
        var box = tr.querySelector("input"); if (box) { box.checked = false; box.disabled = true; }
        var ar = $("si-review-rows").querySelector('tr[data-auth-for="' + pid + '"]');
        var h = a.handoff || {};
        ar.hidden = false;
        ar.firstElementChild.innerHTML = '<div class="si-refusal"><b>' + esc(h.office || "Another office") +
          " owns this.</b> " + esc(a.reason) + (h.note ? " " + esc(h.note) : "") +
          (h.text ? ' <button type="button" class="btn sm ghost" data-si-copy="' + esc(location.origin + "/runs/" + run.run_id) +
            '">Copy the run link for ' + esc(h.office) + "</button>" : "") + "</div>";
      });
    }).catch(function (err) {
      $("si-receipt").innerHTML = '<div class="si-error">The authority check could not run: ' + esc(err.message) + ". Nothing can be applied until it does.</div>";
      $("si-review-rows").querySelectorAll("input").forEach(function (b) { b.checked = false; b.disabled = true; });
    });
  }

  function ticked() {
    return Array.prototype.map.call($("si-review-rows").querySelectorAll("tr[data-pid] input:checked"),
      function (b) { return b.closest("tr").getAttribute("data-pid"); });
  }

  function decide(action) {
    var ids = ticked();
    if (!ids.length) { $("si-receipt").innerHTML = '<div class="si-note">Tick at least one proposal you may decide.</div>'; return; }
    var notes = $("si-notes").value.trim();
    if (action === "reject" && !notes) {
      $("si-notes-wrap").hidden = false; $("si-notes").focus();
      $("si-receipt").innerHTML = '<div class="si-note">A reason is required to reject. Write it, then press Reject again.</div>';
      return;
    }
    $("si-apply").disabled = $("si-reject").disabled = true;
    req("POST", API + "/runs/" + lastRun.run_id + "/decide", { proposal_ids: ids, action: action, notes: notes || null })
      .then(function (r) {
        var h = '<div class="si-receipt ' + (r.done.length ? "ok" : "bad") + '"><b>' + esc(r.text) + "</b> Run " +
          esc(r.run_id.slice(0, 8)) + ". " + esc(r.where) + "</div>";
        (r.refused || []).forEach(function (x) {
          h += '<div class="si-refusal"><b>' + esc(x.title) + ":</b> " + esc(x.reason) + "</div>";
        });
        $("si-receipt").innerHTML = h;
        return req("GET", API + "/runs/" + lastRun.run_id + "?full=1").then(function (run) {
          lastRun = run; result(run);
          (run.proposals || []).forEach(function (p) {
            var tr = $("si-review-rows").querySelector('tr[data-pid="' + p.proposal_id + '"]');
            if (tr && p.status !== "pending") {
              tr.className = "si-p-" + p.status;
              var b = tr.querySelector("input"); b.checked = false; b.disabled = true;
            }
          });
          if (r.done.length) {
            try { sessionStorage.setItem("si-recomputed", r.text + " Run " + r.run_id.slice(0, 8) + "."); } catch (e) {}
            document.dispatchEvent(new CustomEvent("si:decided", { detail: r }));
          }
        });
      })
      .catch(function (err) { $("si-receipt").innerHTML = '<div class="si-error">' + esc(err.message) + "</div>"; })
      .then(function () { $("si-apply").disabled = $("si-reject").disabled = false; });
  }

  function closeModal() { if (modal.open) modal.close(); }

  // ---------------------------------------------------------------- wiring
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-si-task]");
    if (b) {
      var params = {};
      try { params = JSON.parse(b.getAttribute("data-si-params") || "{}"); } catch (x) { params = {}; }
      start(b.getAttribute("data-si-task"), b.getAttribute("data-si-subject"),
            b.getAttribute("data-si-page") || location.pathname, params, b.textContent.trim());
      return;
    }
    if (e.target.closest("[data-si-close]")) { closeDock(); return; }
    if (e.target.closest("[data-si-modal-close]")) { closeModal(); return; }
    var cp = e.target.closest("[data-si-copy]");
    if (cp) {
      var url = cp.getAttribute("data-si-copy");
      (navigator.clipboard ? navigator.clipboard.writeText(url) : Promise.reject()).then(
        function () { cp.textContent = "Link copied"; }, function () { cp.textContent = url; });
      return;
    }
    var open = e.target.closest("[data-si-open-run]");
    if (open) {
      e.preventDefault();
      if (timer) clearTimeout(timer);
      reset("Loading run"); openDock(); cur = open.getAttribute("data-si-open-run"); poll();
    }
  });
  $("si-review").addEventListener("click", openReview);
  $("si-apply").addEventListener("click", function () { decide("apply"); });
  $("si-reject").addEventListener("click", function () { decide("reject"); });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !modal.open && !dock.hidden) closeDock();
  });

  // A reported figure is tested by a form, not typed into a chat.
  document.addEventListener("submit", function (e) {
    var f = e.target.closest("form[data-si-test]");
    if (!f) return;
    e.preventDefault();
    var fd = new FormData(f), params = {};
    if (fd.get("reported_total")) params.reported_total = String(fd.get("reported_total")).trim();
    if (fd.get("reported_label")) params.reported_label = fd.get("reported_label");
    start("reconcile_obligations", f.getAttribute("data-si-subject"), f.getAttribute("data-si-page") || location.pathname,
          params, "Test a reported figure against " + f.getAttribute("data-si-subject"));
  });

  // After a decision on the picture, the page recomputes from the records.
  document.addEventListener("si:decided", function () {
    if (document.body.hasAttribute("data-si-recompute")) {
      $("si-receipt").insertAdjacentHTML("beforeend", '<div class="si-note">Recomputing the picture from the records\u2026</div>');
      setTimeout(function () { location.href = location.pathname + "?fresh=1"; }, 1400);
    }
  });
  try {
    var msg = sessionStorage.getItem("si-recomputed");
    var toast = $("si-toast");
    if (msg && toast) { toast.textContent = "Recomputed after a decision: " + msg; toast.hidden = false; sessionStorage.removeItem("si-recomputed"); }
  } catch (e) {}

  // ------------------------------------------------- interactive obligations
  // Click a fiscal year to read it; shift-click a second to read the range.
  // The server sums the actions; the browser only says which years.
  var sel = {};
  document.addEventListener("click", function (e) {
    var bar = e.target.closest("[data-si-bar]");
    if (!bar) return;
    var piid = bar.getAttribute("data-contract"), fy = bar.getAttribute("data-fy");
    var s = sel[piid] || {};
    if (e.shiftKey && s.from) { s.to = fy; if (s.to < s.from) { var t = s.from; s.from = s.to; s.to = t; } }
    else { s = { from: fy, to: fy }; }
    sel[piid] = s;
    var svg = bar.closest("svg");
    svg.querySelectorAll("[data-si-bar]").forEach(function (r) {
      var y = r.getAttribute("data-fy");
      r.classList.toggle("on", y >= s.from && y <= s.to);
    });
    var out = document.querySelector('[data-si-range="' + piid + '"]');
    if (!out) return;
    out.innerHTML = '<p class="small">Reading FY' + esc(s.from) + (s.to !== s.from ? " to FY" + esc(s.to) : "") + "\u2026</p>";
    req("GET", API + "/obligations?contract=" + encodeURIComponent(piid) + "&fy_from=" + s.from + "&fy_to=" + s.to)
      .then(function (j) {
        var f = j.total;
        out.innerHTML = '<div class="si-range-v"><span class="mono">' + esc(f.display) + "</span> " +
          "<span>" + esc(j.count) + " actions, FY" + esc(s.from) + (s.to !== s.from ? " to FY" + esc(s.to) : "") + "</span></div>" +
          '<p class="small">' + esc(f.provenance.computation) + " \u00b7 " + esc(f.provenance.source) +
          (j.live ? "" : " \u00b7 extract") + "</p>" +
          '<div class="tscroll"><table class="si-top"><thead><tr><th>Mod</th><th>Date</th><th>Amount</th><th>Description</th></tr></thead><tbody>' +
          (j.top || []).map(function (r) {
            return '<tr><td class="mono">' + esc(r.mod) + '</td><td class="mono">' + esc(String(r.action_date || "").slice(0, 10)) +
              '</td><td class="mono">' + esc(r.display) + "</td><td>" + esc(r.description) + "</td></tr>";
          }).join("") + "</tbody></table></div>";
      })
      .catch(function (err) { out.innerHTML = '<p class="si-error">' + esc(err.message) + "</p>"; });
  });
})();
