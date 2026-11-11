/* Renders the \(...\) and \[...\] spans emitted by pymdownx.arithmatex.
   Loaded only on pages whose Markdown actually contained math. */
window.addEventListener("DOMContentLoaded", function () {
  if (typeof renderMathInElement !== "function") return;
  renderMathInElement(document.body, {
    delimiters: [
      { left: "\\[", right: "\\]", display: true },
      { left: "\\(", right: "\\)", display: false }
    ],
    throwOnError: false,
    errorColor: "#c0392b",
    // let \begin{align} etc. work without explicit $$ fences
    trust: false
  });
});
