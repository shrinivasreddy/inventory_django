(function () {
  "use strict";

  function setupIndividualMemberRemoval() {
    var chosen = document.getElementById("id_members_to");
    if (!chosen) return false;
    if (document.getElementById("individual-member-access")) return true;

    var panel = document.createElement("section");
    panel.id = "individual-member-access";
    panel.className = "individual-member-access";
    panel.setAttribute("aria-labelledby", "individual-member-access-title");
    panel.innerHTML =
      '<div class="individual-member-access__heading">' +
      '<span><strong id="individual-member-access-title">Individual access</strong>' +
      '<small>Remove one user without affecting anyone else.</small></span>' +
      '<span class="individual-member-access__count" aria-live="polite"></span>' +
      '</div><div class="individual-member-access__list"></div>';

    chosen.parentNode.insertBefore(panel, chosen);
    var list = panel.querySelector(".individual-member-access__list");
    var count = panel.querySelector(".individual-member-access__count");

    function render() {
      var options = Array.prototype.slice.call(chosen.options);
      count.textContent = options.length + (options.length === 1 ? " member" : " members");
      list.replaceChildren();

      if (!options.length) {
        var empty = document.createElement("p");
        empty.className = "individual-member-access__empty";
        empty.textContent = "No users currently have access to this project.";
        list.appendChild(empty);
        return;
      }

      options.forEach(function (option) {
        var row = document.createElement("div");
        row.className = "individual-member-access__row";

        var identity = document.createElement("span");
        identity.className = "individual-member-access__identity";
        var avatar = document.createElement("span");
        avatar.className = "individual-member-access__avatar";
        avatar.setAttribute("aria-hidden", "true");
        avatar.textContent = option.text.trim().slice(0, 1).toUpperCase() || "U";
        var name = document.createElement("strong");
        name.textContent = option.text;
        identity.appendChild(avatar);
        identity.appendChild(name);

        var remove = document.createElement("button");
        remove.type = "button";
        remove.className = "individual-member-access__remove";
        remove.setAttribute("aria-label", "Remove " + option.text + " from this project");
        remove.innerHTML = '<span aria-hidden="true">&times;</span> Remove';
        remove.addEventListener("click", function () {
          Array.prototype.forEach.call(chosen.options, function (item) {
            item.selected = false;
          });
          option.selected = true;
          var removeSelected = document.querySelector(".selector-chooser .selector-remove");
          if (removeSelected) removeSelected.click();
          window.setTimeout(render, 0);
        });

        row.appendChild(identity);
        row.appendChild(remove);
        list.appendChild(row);
      });
    }

    new MutationObserver(render).observe(chosen, { childList: true });
    render();
    return true;
  }

  function initializeWhenDjangoWidgetIsReady() {
    if (setupIndividualMemberRemoval()) return;
    var observer = new MutationObserver(function () {
      if (setupIndividualMemberRemoval()) observer.disconnect();
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeWhenDjangoWidgetIsReady);
  } else initializeWhenDjangoWidgetIsReady();
})();
