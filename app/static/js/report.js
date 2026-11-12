/* The report form's live calculation.
 *
 * Asks the server for the priority on every change rather than reimplementing
 * the formula here. There is one priority algorithm in this system and it
 * lives in app/domain/priority.py; duplicating it in JavaScript would mean two
 * answers that drift apart.
 */
(function () {
  "use strict";

  var form = document.getElementById("report-form");
  if (!form) return;

  var badge = document.getElementById("priority-badge");
  var explanation = document.getElementById("priority-explanation");
  var slaLine = document.getElementById("priority-sla");
  var categoryHint = document.getElementById("category-hint");

  var fields = {
    title: document.getElementById("f-title"),
    description: document.getElementById("f-description"),
    service: document.getElementById("f-service"),
    category: document.getElementById("f-category"),
    impact: document.getElementById("f-impact"),
    urgency: document.getElementById("f-urgency"),
    affected: document.getElementById("f-affected")
  };

  function debounce(fn, wait) {
    var timer = null;
    return function () {
      clearTimeout(timer);
      timer = setTimeout(fn, wait);
    };
  }

  function refreshPriority() {
    var params = new URLSearchParams({
      impact: fields.impact.value,
      urgency: fields.urgency.value,
      service_id: fields.service.value,
      affected_users_count: fields.affected.value || "1"
    });

    fetch("/api/incidents/priority-preview?" + params.toString(), { headers: { Accept: "application/json" } })
      .then(function (response) { return response.ok ? response.json() : null; })
      .then(function (data) {
        if (!data) return;
        badge.textContent = data.priority + " " + data.label;
        badge.className = "badge badge--" + data.priority.toLowerCase();
        explanation.textContent = data.explanation;
        slaLine.textContent = "Target: " + data.sla + ".";
      })
      .catch(function () { /* the panel is an aid, never a blocker */ });
  }

  function refreshCategory() {
    if (fields.category.value) return;
    var title = fields.title.value.trim();
    if (title.length < 8) return;

    var params = new URLSearchParams({ title: title, description: fields.description.value });
    fetch("/api/incidents/category-suggestion?" + params.toString(), { headers: { Accept: "application/json" } })
      .then(function (response) { return response.ok ? response.json() : null; })
      .then(function (data) {
        if (!data || !data.suggestion) return;
        categoryHint.textContent =
          "Suggested: " + data.suggestion.name +
          " (" + Math.round(data.suggestion.confidence * 100) + "% confident, from " +
          data.suggestion.matched.join(", ") + ").";
      })
      .catch(function () {});
  }

  ["impact", "urgency", "service", "affected"].forEach(function (key) {
    fields[key].addEventListener("change", refreshPriority);
  });
  fields.affected.addEventListener("input", debounce(refreshPriority, 300));

  var categoryWatch = debounce(refreshCategory, 500);
  fields.title.addEventListener("input", categoryWatch);
  fields.description.addEventListener("input", categoryWatch);

  refreshPriority();
})();
