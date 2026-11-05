// Applies the saved theme before the page paints (no flash), then wires the Theme menu.
(function () {
  var KEY = "cyberwatch-theme";
  var valid = ["midnight", "newsroom", "daylight", "command"];
  var theme = "midnight";
  try {
    var saved = localStorage.getItem(KEY);
    if (valid.indexOf(saved) > -1) theme = saved;
  } catch (e) { /* storage blocked: fall back to default */ }
  // A link like /?theme=daylight picks a theme directly.
  try {
    var q = new URLSearchParams(window.location.search).get("theme");
    if (valid.indexOf(q) > -1) theme = q;
  } catch (e) { /* ignore */ }
  document.documentElement.setAttribute("data-theme", theme);

  document.addEventListener("DOMContentLoaded", function () {
    var sel = document.getElementById("theme");
    if (!sel) return;
    sel.value = theme;
    sel.addEventListener("change", function () {
      theme = sel.value;
      document.documentElement.setAttribute("data-theme", theme);
      try { localStorage.setItem(KEY, theme); } catch (e) { /* ignore */ }
      window.dispatchEvent(new Event("themechange"));
    });
  });
})();
