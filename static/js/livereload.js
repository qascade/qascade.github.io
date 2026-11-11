/* Dev-only: polls the build stamp and reloads when the site is rebuilt.
   Injected only when build.py runs with --livereload (i.e. via serve.py). */
(function () {
  var current = null;
  function check() {
    fetch("/__build", { cache: "no-store" })
      .then(function (r) { return r.ok ? r.text() : null; })
      .then(function (stamp) {
        if (!stamp) return;
        stamp = stamp.trim();
        if (current === null) { current = stamp; return; }
        if (stamp !== current) location.reload();
      })
      .catch(function () {});
  }
  setInterval(check, 900);
  check();
})();
