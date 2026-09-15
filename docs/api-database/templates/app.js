(function () {
  var root = document.documentElement;
  var nav = document.querySelector(".docnav");
  function syncNavHeight() {
    if (!nav) return;
    root.style.setProperty("--docnav-height", Math.ceil(nav.getBoundingClientRect().height) + "px");
  }
  syncNavHeight();
  window.addEventListener("resize", syncNavHeight);
  if (window.ResizeObserver && nav) {
    new ResizeObserver(syncNavHeight).observe(nav);
  }
  var box = document.getElementById("tocFilter");
  var list = document.querySelector("#toc ul");
  if (!box || !list) return;
  var groups = [];
  Array.prototype.forEach.call(list.children, function (row) {
    if (row.className.indexOf("tgroup") !== -1) {
      groups.push({ head: row, children: [] });
    } else if (groups.length) {
      groups[groups.length - 1].children.push(row);
    }
  });
  function hit(row, query) {
    return !query || row.textContent.toLowerCase().indexOf(query) !== -1;
  }
  box.addEventListener("input", function () {
    var query = box.value.trim().toLowerCase();
    groups.forEach(function (group) {
      var childHit = group.children.some(function (row) { return hit(row, query); });
      var headHit = hit(group.head, query);
      group.head.hidden = !headHit && !childHit;
      group.children.forEach(function (row) { row.hidden = !childHit && !headHit; });
    });
  });
})();
