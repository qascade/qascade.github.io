/* Theme switcher: persists the choice in localStorage and applies it before
   paint via the inline bootstrap in base.html (so there is no flash). */
(function () {
  var KEY = "sp-theme";
  var picker = document.querySelector(".theme-picker");
  if (!picker) return;

  var toggle = picker.querySelector(".theme-toggle");
  var menu = picker.querySelector(".theme-menu");
  var buttons = Array.prototype.slice.call(menu.querySelectorAll("button[data-theme]"));

  function read() {
    try { return localStorage.getItem(KEY) || "auto"; } catch (e) { return "auto"; }
  }

  function apply(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem(KEY, theme); } catch (e) {}
    buttons.forEach(function (b) {
      var on = b.getAttribute("data-theme") === theme;
      b.setAttribute("aria-checked", on ? "true" : "false");
      if (on) {
        var label = toggle.querySelector(".label");
        if (label) label.textContent = b.textContent.trim();
      }
    });
  }

  function close() {
    menu.hidden = true;
    toggle.setAttribute("aria-expanded", "false");
  }

  toggle.addEventListener("click", function (e) {
    e.stopPropagation();
    var opening = menu.hidden;
    menu.hidden = !opening;
    toggle.setAttribute("aria-expanded", opening ? "true" : "false");
  });

  buttons.forEach(function (b) {
    b.addEventListener("click", function () {
      apply(b.getAttribute("data-theme"));
      close();
    });
  });

  document.addEventListener("click", function (e) {
    if (!picker.contains(e.target)) close();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") close();
  });

  apply(read());
})();
