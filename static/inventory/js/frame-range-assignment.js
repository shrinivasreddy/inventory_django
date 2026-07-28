(function () {
  "use strict";

  function replaceOptions(select, placeholder, options) {
    var previous = select.value;
    select.innerHTML = "";
    var empty = document.createElement("option");
    empty.value = "";
    empty.textContent = placeholder;
    select.appendChild(empty);
    options.forEach(function (option) {
      var element = document.createElement("option");
      element.value = String(option.value);
      element.textContent = option.label;
      select.appendChild(element);
    });
    if (Array.prototype.some.call(select.options, function (option) {
      return option.value === previous;
    })) {
      select.value = previous;
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var project = document.getElementById("id_project");
    var user = document.getElementById("id_user");
    var start = document.getElementById("id_start_frame");
    var end = document.getElementById("id_end_frame");
    if (!project || !user || !start || !end) return;

    var endpoint = new URL("../available-options/", window.location.href);
    project.addEventListener("change", function () {
      replaceOptions(user, "Select a project member", []);
      replaceOptions(start, "Select an unassigned frame", []);
      replaceOptions(end, "Select an unassigned frame", []);
      if (!project.value) return;

      endpoint.searchParams.set("project_id", project.value);
      fetch(endpoint.toString(), { credentials: "same-origin" })
        .then(function (response) {
          if (!response.ok) throw new Error("Unable to load project frame options.");
          return response.json();
        })
        .then(function (data) {
          replaceOptions(user, "Select a project member", (data.users || []).map(function (item) {
            return { value: item.id, label: item.label };
          }));
          var frames = (data.frames || []).map(function (frame) {
            return { value: frame, label: String(frame) };
          });
          replaceOptions(start, "Select an unassigned frame", frames);
          replaceOptions(end, "Select an unassigned frame", frames);
        })
        .catch(function () {
          replaceOptions(start, "Unable to load frames", []);
          replaceOptions(end, "Unable to load frames", []);
        });
    });
  });
}());
