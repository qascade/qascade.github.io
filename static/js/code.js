/* Adds a "copy" button to every highlighted code block. */
window.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".highlight").forEach(function (block) {
    var pre = block.querySelector("pre");
    if (!pre) return;

    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "copy-code";
    btn.textContent = "Copy";
    btn.setAttribute("aria-label", "Copy code to clipboard");

    btn.addEventListener("click", function () {
      var source = pre.querySelector("code") || pre;
      // copy without the line-number gutter, if the fence used linenums
      var clone = source.cloneNode(true);
      clone.querySelectorAll(".linenos, .lineno, .gutter").forEach(function (n) {
        n.remove();
      });
      var text = clone.innerText.replace(/\s+$/, "");

      if (!navigator.clipboard) {
        btn.textContent = "Unavailable";
        return;
      }
      navigator.clipboard.writeText(text).then(
        function () {
          btn.textContent = "Copied";
          setTimeout(function () { btn.textContent = "Copy"; }, 1400);
        },
        function () { btn.textContent = "Failed"; }
      );
    });

    block.appendChild(btn);
  });
});
