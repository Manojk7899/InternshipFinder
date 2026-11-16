/* Loads and saves the prefill profile. Local storage only - nothing leaves the browser. */
(function () {
  "use strict";

  var KEYS = [
    "firstName", "lastName", "fullName", "email", "phone", "location",
    "linkedin", "github", "portfolio",
    "college", "degree", "gradYear", "noticePeriod",
    "experience", "company", "currentCtc", "expectedCtc"
  ];

  var form = document.getElementById("f");
  var status = document.getElementById("status");

  chrome.storage.local.get("profile", function (store) {
    var p = store.profile || {};
    KEYS.forEach(function (k) {
      var el = document.getElementById(k);
      if (el && p[k]) el.value = p[k];
    });
  });

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var p = {};
    KEYS.forEach(function (k) {
      var el = document.getElementById(k);
      var v = el ? el.value.trim() : "";
      if (v) p[k] = v;
    });

    // Fill in the single-field full name from the split parts, so forms asking for
    // either shape get something sensible.
    if (!p.fullName && (p.firstName || p.lastName)) {
      p.fullName = [p.firstName, p.lastName].filter(Boolean).join(" ");
    }

    chrome.storage.local.set({ profile: p }, function () {
      status.textContent = "Saved " + Object.keys(p).length + " fields";
      setTimeout(function () { status.textContent = ""; }, 2500);
    });
  });
})();
