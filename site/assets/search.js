(function () {
  var input = document.getElementById("q");
  var list = document.getElementById("results");
  var note = document.getElementById("search-note");
  if (!input || !list) return;

  var indexUrl = document.currentScript.dataset.index;
  var corpus = null;
  var loading = null;
  var MAX = 25;

  function load() {
    if (loading) return loading;
    loading = fetch(indexUrl)
      .then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      })
      .then(function (data) {
        corpus = data;
      });
    return loading;
  }

  function escapeHtml(s) {
    return s.replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function excerpt(text, at, term) {
    var start = Math.max(0, at - 45);
    var end = Math.min(text.length, at + term.length + 65);
    var head = start > 0 ? "\u2026" : "";
    var tail = end < text.length ? "\u2026" : "";
    return (
      head +
      escapeHtml(text.slice(start, at)) +
      "<mark>" +
      escapeHtml(text.slice(at, at + term.length)) +
      "</mark>" +
      escapeHtml(text.slice(at + term.length, end)) +
      tail
    );
  }

  function render(term) {
    list.innerHTML = "";
    if (!corpus) return;

    var needle = term.toLowerCase();
    var hits = 0;

    for (var i = 0; i < corpus.length && hits < MAX; i++) {
      var record = corpus[i];
      var at = record.haystack.indexOf(needle);
      if (at === -1) continue;
      hits++;

      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = record.url;
      a.textContent = "Sheet " + record.number;
      var p = document.createElement("p");
      p.innerHTML = excerpt(record.text, at, term);
      li.appendChild(a);
      li.appendChild(p);
      list.appendChild(li);
    }

    if (hits === 0) {
      note.textContent = "No page contains that. Try a shorter piece of the word.";
    } else if (hits === MAX) {
      note.textContent = "First " + MAX + " matches. Narrow the term to see fewer.";
    } else {
      note.textContent = hits === 1 ? "1 page matches." : hits + " pages match.";
    }
  }

  var timer;
  input.addEventListener("input", function () {
    var term = input.value.trim();
    clearTimeout(timer);

    if (term.length < 2) {
      list.innerHTML = "";
      note.textContent = "Matches text as it appears on the page, marks and all.";
      return;
    }

    timer = setTimeout(function () {
      note.textContent = "Searching\u2026";
      load()
        .then(function () {
          render(term);
        })
        .catch(function () {
          note.textContent = "Search is unavailable. Browse the pages below instead.";
        });
    }, 120);
  });
})();
