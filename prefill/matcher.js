/*
 * Field matcher for the prefill helper.
 *
 * Deliberately does NOT target per-provider selectors. Lever server-renders stable
 * names, Greenhouse is often embedded on the company's own domain, and Ashby renders
 * its form entirely in React with no name attributes at all. The only thing all three
 * share is a visible label next to each field, so that is what this matches on.
 *
 * Pure and side-effect-free apart from filling: no network, no storage, no submitting.
 * Exposed as window.JobPrefill so it can be unit-tested in a plain page.
 */
(function (global) {
  "use strict";

  // Order matters: the first rule that matches a label wins, so "first name" must be
  // tested before the generic "name".
  var RULES = [
    { key: "firstName",   re: /\b(first|given)\s*name\b/i },
    { key: "lastName",    re: /\b(last|family|sur)\s*name\b/i },
    { key: "fullName",    re: /\b(full\s*name|your\s*name|candidate\s*name)\b|^name$/i },
    { key: "email",       re: /\be-?mail\b/i },
    { key: "phone",       re: /\b(phone|mobile|contact\s*number|cell)\b/i },
    { key: "linkedin",    re: /\blinked\s*in\b/i },
    { key: "github",      re: /\bgit\s*hub\b/i },
    { key: "portfolio",   re: /\b(portfolio|personal\s*(web)?site|website|other\s*url)\b/i },
    { key: "location",    re: /\b(location|city|current\s*city|where.*based)\b/i },
    { key: "college",     re: /\b(college|university|school|institute)\b/i },
    { key: "degree",      re: /\b(degree|qualification|course)\b/i },
    { key: "gradYear",    re: /\b(graduation|passing)\s*(year|date)\b|\byear\s*of\s*(graduation|passing)\b/i },
    { key: "noticePeriod",re: /\bnotice\s*period\b|\bhow soon.*(join|start)\b|\bavailability\b/i },
    { key: "experience",  re: /\b(years?\s*of\s*experience|total\s*experience|work\s*experience)\b/i },
    { key: "currentCtc",  re: /\bcurrent\s*(ctc|salary|compensation)\b/i },
    { key: "expectedCtc", re: /\bexpected\s*(ctc|salary|compensation)\b|\bsalary\s*expectation/i },
    { key: "company",     re: /\b(current\s*(company|employer)|organi[sz]ation)\b/i }
  ];

  // Never touch these, whatever their label says.
  var SKIP_TYPES = ["hidden", "password", "submit", "button", "reset", "image", "file"];
  var SKIP_NAME_RE = /captcha|csrf|authenticity|token|honeypot|_gotcha/i;

  function visible(el) {
    if (!el || el.disabled || el.readOnly) return false;
    if (el.type && SKIP_TYPES.indexOf(el.type.toLowerCase()) !== -1) return false;
    var nm = (el.name || "") + " " + (el.id || "");
    if (SKIP_NAME_RE.test(nm)) return false;
    var r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) return false;
    var s = global.getComputedStyle ? global.getComputedStyle(el) : null;
    if (s && (s.display === "none" || s.visibility === "hidden")) return false;
    return true;
  }

  // Collect every label signal available for a field, best first. The name-derived part
  // is kept last and marked, because it helps matching but reads badly on screen.
  function labelParts(el) {
    var parts = [];
    if (el.id) {
      var l = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
      if (l) parts.push(l.textContent);
    }
    if (el.getAttribute("aria-label")) parts.push(el.getAttribute("aria-label"));
    var ldby = el.getAttribute("aria-labelledby");
    if (ldby) {
      ldby.split(/\s+/).forEach(function (id) {
        var n = document.getElementById(id);
        if (n) parts.push(n.textContent);
      });
    }
    var wrap = el.closest ? el.closest("label") : null;
    if (wrap) parts.push(wrap.textContent);
    if (el.placeholder) parts.push(el.placeholder);

    // Ashby and similar render the label as a sibling div rather than a <label>.
    if (parts.join(" ").trim().length < 3 && el.parentElement) {
      var p = el.parentElement;
      for (var i = 0; i < 3 && p; i++) {
        var txt = "";
        for (var c = 0; c < p.childNodes.length; c++) {
          var node = p.childNodes[c];
          if (node.nodeType === 3) txt += node.textContent;
          else if (node !== el && node.children && node.children.length === 0) txt += " " + node.textContent;
        }
        if (txt.trim().length >= 3) { parts.push(txt); break; }
        p = p.parentElement;
      }
    }

    // Normalise and drop exact repeats: a label[for] and a wrapping <label> usually
    // carry the very same text, which would otherwise appear twice.
    var seen = {}, clean = [];
    parts.forEach(function (t) {
      t = String(t || "").replace(/\s+/g, " ").trim();
      if (!t) return;
      var k = t.toLowerCase();
      if (seen[k]) return;
      seen[k] = 1;
      clean.push(t);
    });
    if (el.name) clean.push(el.name.replace(/[\[\]_\-]+/g, " ").replace(/\s+/g, " ").trim());
    return clean;
  }

  // Everything joined: used for matching, where more signal is better.
  function labelOf(el) {
    return labelParts(el).join(" ").replace(/\s+/g, " ").trim();
  }

  // Just the human-readable label: used for anything shown on screen.
  function displayOf(el) {
    var parts = labelParts(el);
    if (el.name && parts.length > 1) parts = parts.slice(0, -1);
    return (parts[0] || "").replace(/\s+/g, " ").trim();
  }

  function classify(label) {
    for (var i = 0; i < RULES.length; i++) {
      if (RULES[i].re.test(label)) return RULES[i].key;
    }
    return null;
  }

  // React and other frameworks track value on the DOM node, so a plain assignment is
  // ignored. Go through the native setter and fire the events they listen for.
  function setValue(el, value) {
    var proto = el instanceof global.HTMLTextAreaElement
      ? global.HTMLTextAreaElement.prototype
      : global.HTMLInputElement.prototype;
    var desc = Object.getOwnPropertyDescriptor(proto, "value");
    if (desc && desc.set) desc.set.call(el, value);
    else el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function setSelect(el, value) {
    var want = String(value).toLowerCase();
    for (var i = 0; i < el.options.length; i++) {
      var o = el.options[i];
      if (o.value.toLowerCase() === want || o.text.toLowerCase().indexOf(want) !== -1) {
        el.selectedIndex = i;
        el.dispatchEvent(new Event("change", { bubbles: true }));
        return true;
      }
    }
    return false;
  }

  /**
   * Fill what can be matched. Returns a report; never submits anything.
   * @param {Object} profile  key -> value, keys matching RULES above
   * @param {Object} opts     { overwrite: false, highlight: true }
   */
  function fill(profile, opts) {
    opts = opts || {};
    var overwrite = !!opts.overwrite;
    var highlight = opts.highlight !== false;

    var filled = [], skipped = [], unmatched = [];
    var nodes = document.querySelectorAll("input, textarea, select");

    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      if (!visible(el)) continue;

      var label = labelOf(el);
      var shown = displayOf(el) || label;
      var key = classify(label);

      if (!key) {
        unmatched.push({ label: shown.slice(0, 80) || "(no label)", tag: el.tagName.toLowerCase() });
        continue;
      }
      var value = profile[key];
      if (value === undefined || value === null || value === "") {
        skipped.push({ key: key, label: shown.slice(0, 60), reason: "no value in profile" });
        continue;
      }
      if (el.value && !overwrite) {
        skipped.push({ key: key, label: shown.slice(0, 60), reason: "already filled" });
        continue;
      }

      var ok = el.tagName.toLowerCase() === "select" ? setSelect(el, value) : (setValue(el, value), true);
      if (!ok) {
        skipped.push({ key: key, label: shown.slice(0, 60), reason: "no matching option" });
        continue;
      }
      if (highlight) {
        el.style.outline = "2px solid #1a7f4b";
        el.style.outlineOffset = "1px";
      }
      filled.push({ key: key, label: shown.slice(0, 60), value: String(value).slice(0, 40) });
    }

    return { filled: filled, skipped: skipped, unmatched: unmatched };
  }

  global.JobPrefill = { fill: fill, classify: classify, labelOf: labelOf, displayOf: displayOf, RULES: RULES };
})(typeof window !== "undefined" ? window : this);
