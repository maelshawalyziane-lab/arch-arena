/* ARCH Arena — rendu des mathématiques et helpers partagés.
 *
 * Objectif unique : **que les formules soient composées proprement**, toujours.
 *
 *   1. les polices mathématiques sont attendues avant le premier rendu (sinon KaTeX
 *      compose avec la police de secours et les symboles sont décalés) ;
 *   2. KaTeX est appelé par element déjà balisé (.math-inline / .math-block), donc une
 *      seule passe, sans parcours de texte devinable, et avec les macros des concours ;
 *   3. si une formule résiste (commande inconnue, corruption), on retente après
 *      nettoyage, puis on affiche la formule **en clair** plutôt qu'en rouge — une
 *      erreur visible serait pire que le texte d'origine ;
 *   4. les blocs trop larges (matrices, systèmes) deviennent scrollables, jamais coupés.
 */
(function () {
  "use strict";

  var KATEX_OPTIONS = {
    delimiters: [
      { left: "$$", right: "$$", display: true },
      { left: "\\[", right: "\\]", display: true },
      { left: "\\(", right: "\\)", display: false },
      { left: "$", right: "$", display: false }
    ],
    throwOnError: false,
    errorColor: "inherit",
    strict: false,
    trust: false,
    ignoredClasses: ["tex-source", "submission-text"],
    /* Mêmes renommages que le serveur (problems/services/tex.py) : les énoncés des
     * concours utilisent \plus{}, \equal{}, \ZZ…, que KaTeX ne connaît pas. Les
     * macros couvrent aussi ce qu'un élève tape dans sa soumission. */
    macros: {
      "\\plus": "+",
      "\\minus": "-",
      "\\equal": "=",
      "\\ZZ": "\\mathbb{Z}",
      "\\RR": "\\mathbb{R}",
      "\\QQ": "\\mathbb{Q}",
      "\\NN": "\\mathbb{N}",
      "\\CC": "\\mathbb{C}",
      "\\ee": "\\mathrm{e}",
      "\\sgn": "\\operatorname{sgn}",
      "\\hdots": "\\ldots",
      "\\o": "\\text{ø}"
    }
  };

  /** Commandes de mise en page à retirer avant un second essai de rendu. */
  var STRIP = /\\(?:vspace|hspace)\s*\{[^{}]*\}|\\(?:sub)*section\*?\s*\{[^{}]*\}|\\(?:eq)?ref\s*\{[^{}]*\}|\\label\s*\{[^{}]*\}|\\(?:indent|noindent|hfill|break|newpage|eqno|atop|displaystyle|limits)\b|\\(?:smallskip|medskip|bigskip)\b/g;

  function katexReady() {
    return typeof window.katex === "object" && typeof window.katex.render === "function";
  }

  /** Vrai quand les polices mathématiques sont composables (ou après expirations). */
  function fontsReady() {
    if (!document.fonts || !document.fonts.load) { return Promise.resolve(); }
    var wanted = ["KaTeX_Main", "KaTeX_Math", "KaTeX_Size1", "KaTeX_AMS", "KaTeX_Caligraphic"];
    var attempts = wanted.map(function (family) {
      return document.fonts.load("italic 1em " + family + ", serif").catch(function () { return []; });
    });
    // Course contre le temps : mieux vaut composer tout de suite que d'attendre
    // indéfiniment une police qui ne viendra jamais (aperçu hors ligne).
    var deadline = new Promise(function (resolve) { setTimeout(resolve, 1500); });
    return Promise.race([Promise.all(attempts), deadline]);
  }

  /** Une formule : rendu direct, puis après nettoyage, puis en clair. */
  function renderOne(element) {
    var tex = element.getAttribute("data-tex");
    if (tex === null) {
      tex = element.textContent;
      element.setAttribute("data-tex", tex);
    }
    var display = element.classList.contains("math-block") ||
      element.classList.contains("katex-display") ||
      element.tagName === "DIV";
    var body = tex.replace(/^\$\$|\$\$$/g, "").replace(/^\$|\$$/g, "").trim();
    if (!body) { return; }

    var options = Object.assign({}, KATEX_OPTIONS, { displayMode: display });
    var node;
    try {
      node = window.katex.renderToString(body, options);
    } catch (firstError) {
      var cleaned = body.replace(STRIP, " ").replace(/\s{2,}/g, " ").trim();
      try {
        node = window.katex.renderToString(cleaned, options);
      } catch (secondError) {
        // Dernier recours : la formule reste lisible, en clair, sans rouge.
        element.classList.add("math-raw");
        element.textContent = body;
        element.setAttribute("title", "Formule affichée telle quelle (rendu KaTeX impossible)");
        return;
      }
    }
    element.innerHTML = node;
    element.classList.add("math-typeset");
    if (display) {
      var displayNode = element.querySelector(".katex-display");
      if (displayNode) { makeScrollable(displayNode); }
    }
  }

  /** Les formules larges défilent horizontalement au lieu de déborder. */
  function makeScrollable(node) {
    var parent = node.parentElement;
    if (!parent || parent.dataset.mathScroll === "1") { return; }
    parent.dataset.mathScroll = "1";
    var measure = function () {
      if (node.scrollWidth > parent.clientWidth + 1) {
        parent.classList.add("math-overflow");
      } else {
        parent.classList.remove("math-overflow");
      }
    };
    measure();
    if (typeof ResizeObserver === "function") {
      new ResizeObserver(measure).observe(parent);
    } else {
      window.addEventListener("resize", measure);
    }
  }

  /**
   * Compose les mathématiques d'un sous-arbre (ou du document).
   *
   * Seuls les éléments balisés `math-inline` / `math-block` sont traités : le serveur a
   * déjà découpé le texte, il n'y a donc rien à deviner ni à re-parcourir.
   */
  function typeset(root) {
    root = root || document.body;
    if (!katexReady()) { return false; }
    var nodes = root.querySelectorAll(".math-inline, .math-block");
    for (var i = 0; i < nodes.length; i++) {
      if (nodes[i].dataset.mathTypeset === "1") { continue; }
      nodes[i].dataset.mathTypeset = "1";
      renderOne(nodes[i]);
    }
    return true;
  }

  window.ARCH = { typeset: typeset, katexReady: katexReady, initTheme: initTheme };

  var booted = false;

  /* ------------------------------------------------------------- theme ---- */
  function initTheme() {
    var button = document.getElementById("theme-toggle");
    if (!button) { return; }
    button.addEventListener("click", function () {
      var html = document.documentElement;
      var next = html.dataset.theme === "dark" ? "light" : "dark";
      html.dataset.theme = next;
      try { localStorage.setItem("arch-theme", next); } catch (err) { /* stockage indisponible */ }
      var meta = document.querySelector('meta[name="theme-color"]');
      if (meta) { meta.setAttribute("content", next === "dark" ? "#090d16" : "#f6f7fb"); }
    });
  }

  function boot() {
    if (booted) { return; }
    booted = true;
    initTheme();

    if (!katexReady()) {
      // le script KaTeX a échoué (hors ligne ?) : on réessaie une fois, puis on
      // affiche les formules en clair, jamais en rouge ni en « backslash » brut
      window.setTimeout(function () {
        if (!katexReady()) {
          document.documentElement.classList.add("math-unavailable");
        }
      }, 2500);
      return;
    }

    document.documentElement.classList.add("math-loading");
    fontsReady().then(function () {
      document.documentElement.classList.remove("math-loading");
      typeset(document.body);
    });
  }

  document.addEventListener("DOMContentLoaded", boot);
  if (document.readyState === "interactive" || document.readyState === "complete") { boot(); }
})();
