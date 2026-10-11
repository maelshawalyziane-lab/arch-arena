/* ARCH Arena - problem detail page: hint reveals, AI submission, unlock swap.
 *
 * The gate itself is enforced server-side; this file only drives the UI and
 * re-fetches the rendered solution once the server reports `unlocked: true`.
 */
(function () {
  "use strict";

  var root = document.getElementById("problem-root");
  if (!root) { return; }

  var verifyUrl = root.dataset.verifyUrl;
  var statusUrl = root.dataset.statusUrl;
  var resetUrl = root.dataset.resetUrl;

  function csrfToken() {
    var input = document.querySelector("#submission-form input[name=csrfmiddlewaretoken]");
    if (input) { return input.value; }
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function typeset(el) {
    if (window.ARCH && window.ARCH.typeset) { window.ARCH.typeset(el || document.body); }
  }

  function flash(message, kind) {
    var verdict = document.getElementById("verdict");
    if (!verdict) { return; }
    verdict.hidden = false;
    verdict.className = "verdict notice " + (kind || "info");
    verdict.innerHTML = '<div class="verdict-body"></div>';
    verdict.querySelector(".verdict-body").textContent = message;
  }

  /* ---------------------------------------------------- hint reveals ---- */
  document.addEventListener("click", function (event) {
    var button = event.target.closest(".js-reveal-hint");
    if (!button) { return; }
    event.preventDefault();
    button.disabled = true;
    var original = button.textContent;
    button.textContent = "ouverture…";

    fetch(button.dataset.url, {
      method: "POST",
      headers: { "X-CSRFToken": csrfToken(), "Accept": "application/json" },
      credentials: "same-origin"
    })
      .then(function (response) { return response.json().then(function (data) { return { ok: response.ok, data: data }; }); })
      .then(function (result) {
        if (!result.ok) {
          button.disabled = false;
          button.textContent = original;
          flash(result.data.feedback || "Impossible de révéler cet indice.", "warn");
          return;
        }
        var item = button.closest(".hint");
        item.classList.add("revealed");
        var body = item.querySelector(".hint-body");
        body.innerHTML = '<div class="rendered">' + result.data.content_html + "</div>";
        typeset(body);
        var head = item.querySelector(".hint-head");
        var pill = document.createElement("span");
        pill.className = "pill ok";
        pill.textContent = "révélé";
        head.replaceChild(pill, button);
        /* the next hint's lock badge becomes a live button */
        var next = item.nextElementSibling;
        if (next) {
          var locked = next.querySelector(".pill.locked");
          if (locked) {
            var revealUrl = next.querySelector(".hint") ? null : null;
            var nb = document.createElement("button");
            nb.type = "button";
            nb.className = "btn ghost small js-reveal-hint";
            nb.dataset.url = button.dataset.url.replace(/\d+\/reveal\/?$/, (parseInt(item.dataset.order, 10) + 1) + "/reveal");
            nb.textContent = "Révéler l'indice " + (parseInt(item.dataset.order, 10) + 1);
            locked.parentNode.replaceChild(nb, locked);
          }
        }
        var progress = document.getElementById("hint-progress");
        if (progress) { progress.textContent = String((parseInt(progress.textContent, 10) || 0) + 1) + "/" + root.dataset.hintCount; }
      })
      .catch(function () {
        button.disabled = false;
        button.textContent = original;
        flash("Erreur réseau pendant la révélation de l'indice.", "error");
      });
  });

  /* ------------------------------------------------------- submission --- */
  var form = document.getElementById("submission-form");
  var textarea = document.getElementById("submission-text");
  var submitButton = document.getElementById("submit-btn");
  var spinner = document.getElementById("submit-spinner");
  var submitLabel = document.getElementById("submit-label");
  var charCount = document.getElementById("char-count");

  if (textarea && charCount) {
    var updateCount = function () { charCount.textContent = String(textarea.value.length); };
    textarea.addEventListener("input", updateCount);
    updateCount();
    textarea.addEventListener("keydown", function (event) {
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
        event.preventDefault();
        form.requestSubmit ? form.requestSubmit() : form.submit();
      }
    });
  }

  function setBusy(busy) {
    if (!submitButton) { return; }
    submitButton.disabled = busy;
    if (spinner) { spinner.hidden = !busy; }
    if (submitLabel) { submitLabel.textContent = busy ? "Évaluation…" : "Soumettre à l'évaluation IA"; }
    if (textarea) { textarea.readOnly = busy; }
  }

  if (form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var text = textarea ? textarea.value.trim() : "";
      if (!text) { flash("Écrivez un plan de solution avant de soumettre.", "warn"); return; }

      setBusy(true);
      flash("Envoi de votre rédaction au correcteur — cela peut prendre quelques secondes…", "info");
      var started = Date.now();

      fetch(verifyUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken(),
          "Accept": "application/json"
        },
        credentials: "same-origin",
        body: JSON.stringify({ text: text })
      })
        .then(function (response) {
          return response.json().catch(function () { return {}; }).then(function (data) {
            return { status: response.status, data: data };
          });
        })
        .then(function (result) {
          setBusy(false);
          var data = result.data || {};
          var elapsed = ((Date.now() - started) / 1000).toFixed(1);
          var engine = data.engine ? " [" + data.engine + "]" : "";
          if (data.unlocked) {
            flash("✓ Accepté" + engine + " — " + (data.feedback || "") + " Déblocage de la solution officielle…", "success");
            refreshSolution();
          } else if (result.status === 429) {
            flash(data.feedback || "Quota de soumissions atteint — réessayez plus tard.", "warn");
          } else if (data.error === "grader_unavailable") {
            flash((data.feedback || "Le correcteur est indisponible.") + " Rien n'a été considéré comme faux ; réessayez bientôt.", "warn");
          } else if (data.error) {
            flash(data.feedback || data.error, "error");
          } else {
            flash("Pas encore accepté" + engine + " (" + elapsed + " s) : " + (data.feedback || ""), "fail");
            appendHistoryFromVerdict(data, text);
          }
          if (typeof data.rate_remaining === "number") {
            var note = document.getElementById("rate-note");
            if (note) { note.textContent = String(data.rate_remaining); }
          }
        })
        .catch(function () {
          setBusy(false);
          flash("Erreur réseau : la soumission n'a pas été envoyée. Votre texte est toujours dans la zone de saisie.", "error");
        });
    });
  }

  function appendHistoryFromVerdict(data, text) {
    var verdict = document.getElementById("verdict");
    if (!verdict) { return; }
    var detail = document.createElement("details");
    detail.className = "submission-text";
    detail.innerHTML = "<summary>Votre copie soumise</summary>";
    var pre = document.createElement("pre");
    pre.textContent = text;
    detail.appendChild(pre);
    verdict.appendChild(detail);
  }

  /* ------------------------------------------ unlock => re-render server-side */
  function refreshSolution() {
    fetch(window.location.pathname, { headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" })
      .then(function (response) { return response.text(); })
      .then(function (html) {
        var doc = new DOMParser().parseFromString(html, "text/html");
        var fresh = doc.getElementById("solution-panel");
        var current = document.getElementById("solution-panel");
        if (fresh && current) {
          current.replaceWith(fresh);
          typeset(fresh);
        }
        var badge = doc.getElementById("solve-badge");
        var myBadge = document.getElementById("solve-badge");
        if (badge && myBadge) { myBadge.replaceWith(badge); }
        root.dataset.solved = "1";
        /* also refresh the (now permanent) submission panel and history */
        var freshSubmission = doc.getElementById("submission");
        var mySubmission = document.getElementById("submission");
        if (freshSubmission && mySubmission) { mySubmission.replaceWith(freshSubmission); }
        var freshHistory = doc.getElementById("history");
        var myHistory = document.getElementById("history");
        if (freshHistory && !myHistory) {
          var panel = document.getElementById("submission");
          if (panel) { panel.parentNode.insertBefore(freshHistory, panel.nextSibling); }
        }
        document.getElementById("solution-panel").scrollIntoView({ behavior: "smooth", block: "start" });
      })
      .catch(function () { window.location.reload(); });
  }

  /* --------------------------------------------------- progress reset --- */
  var resetButton = document.getElementById("reset-progress");
  if (resetButton) {
    resetButton.addEventListener("click", function () {
      if (!window.confirm("Reverrouiller cette fiche, supprimer vos soumissions et refermer les indices ouverts ?")) { return; }
      resetButton.disabled = true;
      fetch(resetUrl, {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken(), "Accept": "application/json" },
        credentials: "same-origin"
      })
        .then(function () { window.location.reload(); })
        .catch(function () { resetButton.disabled = false; flash("Impossible de réinitialiser la progression.", "error"); });
    });
  }

  /* Optional: poll status (used after a PENDING verdict) */
  window.ARCHProblem = {
    pollStatus: function () {
      return fetch(statusUrl, { headers: { "Accept": "application/json" }, credentials: "same-origin" })
        .then(function (response) { return response.json(); });
    }
  };
})();
