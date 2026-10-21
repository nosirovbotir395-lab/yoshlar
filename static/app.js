// Nusxa olish tugmalari: data-copy="element-id"
document.addEventListener("click", function (e) {
  var btn = e.target.closest("[data-copy]");
  if (!btn) return;
  var el = document.getElementById(btn.getAttribute("data-copy"));
  if (!el) return;
  var text = el.value || el.textContent;
  var done = function () { var t = btn.textContent; btn.textContent = "✓ Nusxa olindi"; setTimeout(function () { btn.textContent = t; }, 1600); };
  if (navigator.clipboard) { navigator.clipboard.writeText(text).then(done, function () { el.select(); document.execCommand("copy"); done(); }); }
  else { el.select(); document.execCommand("copy"); done(); }
});
