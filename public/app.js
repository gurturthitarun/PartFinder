(function () {
  "use strict";

  const vehicleSelect = document.getElementById("vehicle-select");
  const versionSelect = document.getElementById("version-select");
  const partInput = document.getElementById("part-input");
  const suggestionsEl = document.getElementById("suggestions");
  const resultsSection = document.getElementById("results");
  const resultsList = document.getElementById("results-list");
  const resultsCount = document.getElementById("results-count");
  const emptyState = document.getElementById("empty-state");
  const statusLine = document.getElementById("status-line");
  const statsLine = document.getElementById("stats-line");
  const modeButtons = document.querySelectorAll(".mode-btn");
  const panelByVehicle = document.getElementById("panel-by-vehicle");
  const panelByNumber = document.getElementById("panel-by-number");
  const numberInput = document.getElementById("number-input");

  let numberDebounceTimer = null;

  // ---------- Mode toggle ----------
  modeButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      modeButtons.forEach((b) => {
        b.classList.toggle("active", b === btn);
        b.setAttribute("aria-selected", b === btn ? "true" : "false");
      });
      const mode = btn.dataset.mode;
      panelByVehicle.hidden = mode !== "by-vehicle";
      panelByNumber.hidden = mode !== "by-number";
      closeSuggestions();
      setStatus("");
      resetEmptyStateCopy();
      showEmptyState(true);
    });
  });

  function resetEmptyStateCopy() {
    const isNumberMode = !panelByNumber.hidden;
    emptyState.querySelector("p").textContent = isNumberMode
      ? "No part number entered yet."
      : "No part selected yet.";
    emptyState.querySelector(".empty-plate-sub").textContent = isNumberMode
      ? "Type a part number (or a fragment of one) above — it's matched against every vehicle's catalogue."
      : "Choose a vehicle above, then search for a part name to pull its number from the catalogue.";
  }

  // ---------- Search by part number ----------
  numberInput.addEventListener("input", () => {
    const query = numberInput.value.trim();
    setStatus("");
    clearTimeout(numberDebounceTimer);

    if (!query) {
      showEmptyState(true);
      return;
    }
    if (query.length < 2) {
      setStatus("Keep typing — need at least 2 characters.");
      return;
    }

    numberDebounceTimer = setTimeout(async () => {
      try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
        const parts = await res.json();
        setStatus("");
        renderResults(parts, null);
      } catch (e) {
        setStatus("Couldn't search — try again.");
      }
    }, 180);
  });

  let activeSuggestionIndex = -1;
  let currentSuggestions = [];
  let debounceTimer = null;

  function escapeHtml(str) {
    return str.replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function highlight(name, query) {
    if (!query) return escapeHtml(name);
    const idx = name.toLowerCase().indexOf(query.toLowerCase());
    if (idx === -1) return escapeHtml(name);
    const before = escapeHtml(name.slice(0, idx));
    const match = escapeHtml(name.slice(idx, idx + query.length));
    const after = escapeHtml(name.slice(idx + query.length));
    return `${before}<mark>${match}</mark>${after}`;
  }

  function setStatus(msg) {
    if (!msg) {
      statusLine.hidden = true;
      statusLine.textContent = "";
      return;
    }
    statusLine.hidden = false;
    statusLine.textContent = msg;
  }

  function showEmptyState(show) {
    emptyState.hidden = !show;
    resultsSection.hidden = show;
  }

  // ---------- Init ----------
  async function init() {
    try {
      const res = await fetch("/api/vehicles");
      const vehicles = await res.json();
      vehicleSelect.innerHTML =
        '<option value="">Select a vehicle…</option>' +
        vehicles.map((v) => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join("");
      vehicleSelect.disabled = false;
      statsLine.textContent = `${vehicles.length} vehicle catalogues indexed`;
    } catch (e) {
      statsLine.textContent = "Could not load the parts index.";
    }
  }

  vehicleSelect.addEventListener("change", async () => {
    const vehicle = vehicleSelect.value;
    partInput.value = "";
    closeSuggestions();
    showEmptyState(true);

    if (!vehicle) {
      versionSelect.innerHTML = '<option value="Any">Any</option>';
      versionSelect.disabled = true;
      partInput.disabled = true;
      partInput.placeholder = "Select a vehicle first…";
      return;
    }

    partInput.disabled = false;
    partInput.placeholder = "Start typing a part name…";

    versionSelect.disabled = true;
    versionSelect.innerHTML = '<option value="Any">Any</option>';
    try {
      const res = await fetch(`/api/versions?vehicle=${encodeURIComponent(vehicle)}`);
      const versions = await res.json();
      versionSelect.innerHTML =
        '<option value="Any">Any</option>' +
        versions.map((v) => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join("");
    } catch (e) {
      // Any-only fallback already set
    }
    versionSelect.disabled = false;
  });

  function closeSuggestions() {
    suggestionsEl.hidden = true;
    suggestionsEl.innerHTML = "";
    currentSuggestions = [];
    activeSuggestionIndex = -1;
  }

  function renderSuggestions(items, query) {
    currentSuggestions = items;
    activeSuggestionIndex = -1;
    if (!items.length) {
      suggestionsEl.innerHTML = '<li class="no-match">No matching part names</li>';
      suggestionsEl.hidden = false;
      return;
    }
    suggestionsEl.innerHTML = items
      .map((item, i) => `<li data-index="${i}">${highlight(item.name, query)}</li>`)
      .join("");
    suggestionsEl.hidden = false;
  }

  partInput.addEventListener("input", () => {
    const vehicle = vehicleSelect.value;
    const query = partInput.value.trim();
    setStatus("");

    if (!vehicle) return;
    clearTimeout(debounceTimer);

    if (!query) {
      closeSuggestions();
      showEmptyState(true);
      return;
    }

    debounceTimer = setTimeout(async () => {
      const version = versionSelect.value || "Any";
      try {
        const res = await fetch(
          `/api/suggest?vehicle=${encodeURIComponent(vehicle)}&version=${encodeURIComponent(version)}&q=${encodeURIComponent(query)}`
        );
        const items = await res.json();
        renderSuggestions(items, query);
      } catch (e) {
        setStatus("Couldn't fetch suggestions — try again.");
      }
    }, 160);
  });

  suggestionsEl.addEventListener("click", (e) => {
    const li = e.target.closest("li[data-index]");
    if (!li) return;
    const item = currentSuggestions[Number(li.dataset.index)];
    if (item) selectPart(item.name);
  });

  partInput.addEventListener("keydown", (e) => {
    if (suggestionsEl.hidden || !currentSuggestions.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      activeSuggestionIndex = Math.min(activeSuggestionIndex + 1, currentSuggestions.length - 1);
      updateActiveSuggestion();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      activeSuggestionIndex = Math.max(activeSuggestionIndex - 1, 0);
      updateActiveSuggestion();
    } else if (e.key === "Enter") {
      e.preventDefault();
      const pick = currentSuggestions[activeSuggestionIndex] || currentSuggestions[0];
      if (pick) selectPart(pick.name);
    } else if (e.key === "Escape") {
      closeSuggestions();
    }
  });

  function updateActiveSuggestion() {
    [...suggestionsEl.children].forEach((li, i) => {
      li.classList.toggle("active", i === activeSuggestionIndex);
    });
    const activeEl = suggestionsEl.children[activeSuggestionIndex];
    if (activeEl) activeEl.scrollIntoView({ block: "nearest" });
  }

  document.addEventListener("click", (e) => {
    if (!e.target.closest(".field-autocomplete")) closeSuggestions();
  });

  async function selectPart(name) {
    partInput.value = name;
    closeSuggestions();
    const vehicle = vehicleSelect.value;
    const version = versionSelect.value || "Any";
    setStatus("Looking up part number…");
    try {
      const res = await fetch(
        `/api/part?vehicle=${encodeURIComponent(vehicle)}&version=${encodeURIComponent(version)}&name=${encodeURIComponent(name)}`
      );
      const parts = await res.json();
      setStatus("");
      renderResults(parts, vehicle);
    } catch (e) {
      setStatus("Couldn't fetch that part — try again.");
    }
  }

  function renderResults(parts, vehicle) {
    if (!parts.length) {
      showEmptyState(true);
      if (vehicle) {
        emptyState.querySelector("p").textContent = "No part number found.";
        emptyState.querySelector(".empty-plate-sub").textContent =
          "Try clearing the variant filter, or check the spelling of the part name.";
      } else {
        emptyState.querySelector("p").textContent = "No matches across any vehicle.";
        emptyState.querySelector(".empty-plate-sub").textContent =
          "Double-check the part number, or try just a fragment of it.";
      }
      return;
    }

    showEmptyState(false);
    resultsCount.textContent = vehicle
      ? `${parts.length} match${parts.length > 1 ? "es" : ""} · ${vehicle}`
      : `${parts.length} match${parts.length > 1 ? "es" : ""} across all vehicles`;
    resultsList.innerHTML = parts
      .map((p) => {
        const tags = [];
        if (!vehicle) tags.push(p.vehicle);
        if (p.section) tags.push(p.section);
        if (p.remarks) tags.push(p.remarks);
        if (p.version) tags.push(p.version);
        return `
          <div class="result-plate">
            <div class="result-top">
              <div>
                <p class="result-name">${escapeHtml(p.part_name)}</p>
                <p class="result-meta">${escapeHtml(p.vehicle)} · page ${escapeHtml(String(p.page))} of ${escapeHtml(p.source_file)}</p>
              </div>
              <div class="part-number-tag">${escapeHtml(p.part_number || "—")}</div>
            </div>
            ${tags.length ? `<div class="result-tags">${tags.map((t) => `<span class="result-tag">${escapeHtml(t)}</span>`).join("")}</div>` : ""}
          </div>
        `;
      })
      .join("");
  }

  init();
})();
