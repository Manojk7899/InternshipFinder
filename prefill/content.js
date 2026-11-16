/*
 * Injected on toolbar click, after matcher.js. Loads the saved profile, fills what it
 * can, and reports back in a panel.
 *
 * It does not submit, does not click anything, and does not touch captcha, CSRF, file
 * or hidden fields - the matcher refuses those outright. Submitting stays manual, both
 * because these forms are captcha-protected and because the questions worth answering
 * are the ones a machine answers badly.
 */
(async function () {
  "use strict";

  var PANEL_ID = "job-prefill-panel";
  var old = document.getElementById(PANEL_ID);
  if (old) old.remove();

  var store = await chrome.storage.local.get("profile");
  var profile = store.profile;

  if (!profile || !Object.keys(profile).length) {
    panel(
      "No profile saved yet",
      "<p>Open the extension's <strong>Options</strong> page and fill in your details first.</p>",
      []
    );
    return;
  }

  var report = window.JobPrefill.fill(profile, { overwrite: false, highlight: true });

  var body = "";
  body += "<p class='jp-count'><strong>" + report.filled.length + "</strong> field" +
          (report.filled.length === 1 ? "" : "s") + " filled" +
          (report.unmatched.length ? ", <strong>" + report.unmatched.length + "</strong> left for you" : "") +
          ".</p>";

  if (report.unmatched.length) {
    body += "<p class='jp-h'>You need to answer these yourself</p><ul>";
    report.unmatched.forEach(function (u) {
      body += "<li>" + esc(u.label) + "</li>";
    });
    body += "</ul>";
  }

  if (report.skipped.length) {
    body += "<p class='jp-h'>Skipped</p><ul>";
    report.skipped.forEach(function (s) {
      body += "<li>" + esc(s.label) + " <span class='jp-dim'>(" + esc(s.reason) + ")</span></li>";
    });
    body += "</ul>";
  }

  body += "<p class='jp-warn'>Check every filled field, attach your resume, " +
          "answer the questions above, then submit it yourself.</p>";

  panel("Prefilled", body, report.filled);

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function panel(title, html) {
    var d = document.createElement("div");
    d.id = PANEL_ID;
    d.innerHTML =
      "<div class='jp-bar'><span>" + esc(title) + "</span><button type='button' id='jp-x'>&times;</button></div>" +
      "<div class='jp-body'>" + html + "</div>";

    var css = document.createElement("style");
    css.textContent =
      "#" + PANEL_ID + "{position:fixed;top:14px;right:14px;z-index:2147483647;width:310px;" +
      "max-height:72vh;overflow:auto;background:#fff;color:#15181d;border:1px solid #d3d9e0;" +
      "border-radius:10px;box-shadow:0 8px 28px rgba(0,0,0,.18);font:13px/1.5 system-ui,sans-serif}" +
      "#" + PANEL_ID + " .jp-bar{display:flex;justify-content:space-between;align-items:center;" +
      "padding:9px 12px;border-bottom:1px solid #e6eaef;font-weight:600}" +
      "#" + PANEL_ID + " .jp-bar button{border:0;background:none;font-size:19px;line-height:1;" +
      "cursor:pointer;color:#6b7684}" +
      "#" + PANEL_ID + " .jp-body{padding:10px 13px 14px}" +
      "#" + PANEL_ID + " p{margin:0 0 9px}" +
      "#" + PANEL_ID + " ul{margin:0 0 10px;padding-left:17px}" +
      "#" + PANEL_ID + " li{margin-bottom:4px}" +
      "#" + PANEL_ID + " .jp-h{font-size:11px;text-transform:uppercase;letter-spacing:.06em;" +
      "color:#6b7684;font-weight:600;margin-bottom:4px}" +
      "#" + PANEL_ID + " .jp-dim{color:#8a93a0}" +
      "#" + PANEL_ID + " .jp-warn{background:#fdf4e6;border-left:3px solid #b45309;padding:8px 10px;" +
      "border-radius:0 6px 6px 0;color:#7c3d06}" +
      "@media (prefers-color-scheme:dark){#" + PANEL_ID + "{background:#1a1f27;color:#e7ecf3;" +
      "border-color:#333c48}#" + PANEL_ID + " .jp-bar{border-color:#2b333d}" +
      "#" + PANEL_ID + " .jp-warn{background:#2a2113;color:#f0b457;border-color:#f0b457}}";

    d.appendChild(css);
    document.documentElement.appendChild(d);
    var x = d.querySelector("#jp-x");
    if (x) x.onclick = function () { d.remove(); };
  }
})();
