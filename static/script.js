const UNIT_LABELS = {
  SFD: "Single family dwelling",
  SS: "Secondary suite",
  LWH: "Laneway / backyard suite",
};

const LOAD_FIELDS = [
  ["space_heating", "Space heat", "Electric heat, furnace, boiler, or baseboard load"],
  ["air_conditioning", "Air conditioning", "Compressor/nameplate cooling load"],
  ["range_watts", "Range", "Total range nameplate watts"],
  ["tankless_watts", "Tankless water heater", "Electric tankless domestic water heater load"],
  ["steamer_watts", "Steamer", "Steam shower or steamer load"],
  ["pool_hot_tub_watts", "Pool / hot tub / spa", "Whole equipment nameplate watts"],
  ["ev_charging_watts", "EV charging", "EVSE load in watts"],
];

const BELOW_GROUND_AREA_FACTOR = 0.75;

let lastCalculationInput = null;
let lastCalculationResult = null;

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

function formatWatts(value) {
  const number = Number(value) || 0;
  return `${number.toLocaleString(undefined, { maximumFractionDigits: 2 })} W`;
}

function formatM2(value) {
  const number = Number(value) || 0;
  return `${number.toLocaleString(undefined, { maximumFractionDigits: 2 })} m2`;
}

function formatAmps(value) {
  return `${(Number(value) || 0).toFixed(1)} A`;
}

function formatPercent(value) {
  return value === null || value === undefined ? "Rule" : `${Number(value).toFixed(0)}%`;
}

function parseNumber(input) {
  const value = Number.parseFloat(input?.value || "0");
  return Number.isFinite(value) && value > 0 ? value : 0;
}

function unitCard(unit) {
  const loadRows = LOAD_FIELDS.map(([key, label, hint]) => `
    <div class="load-row" data-load-key="${key}">
      <label>
        <span>${label}</span>
        <small>${hint}</small>
      </label>
      <input type="number" min="0" step="1" inputmode="decimal" name="${key}_${unit}" placeholder="0">
    </div>
  `).join("");

  return `
    <article class="unit-card" data-unit="${unit}">
      <div class="unit-card-header">
        <div>
          <p class="eyebrow">${unit}</p>
          <h2>${UNIT_LABELS[unit]}</h2>
        </div>
        <label class="toggle-line">
          <input type="checkbox" class="interlock-input" name="interlocked_${unit}">
          <span>Heat / AC interlocked</span>
        </label>
      </div>

      <div class="primary-fields">
        <label class="input-field">
          <span>Above ground m2</span>
          <input type="number" min="0" step="0.1" inputmode="decimal" name="above_ground_m2_${unit}" placeholder="m2">
        </label>
        <label class="input-field">
          <span>Below ground m2 (75% counted)</span>
          <input type="number" min="0" step="0.1" inputmode="decimal" name="below_ground_m2_${unit}" placeholder="m2">
        </label>
      </div>

      <div class="load-list">${loadRows}</div>

      <div class="additional-loads" data-unit="${unit}">
        <div class="section-heading">
          <div>
            <h3>Additional loads over 1500 W</h3>
            <p>Dryers, tank-style water heaters, and other fixed loads. Leave out heating, cooling, EV, tankless, and pool/hot tub/spa loads already entered above.</p>
          </div>
          <button type="button" class="small-button add-load">Add</button>
        </div>
        <div class="additional-list"></div>
      </div>
    </article>
  `;
}

function additionalLoadRow() {
  const row = document.createElement("div");
  row.className = "additional-row";
  row.innerHTML = `
    <input type="text" class="additional-description" placeholder="Description">
    <input type="number" class="additional-watts" min="0" step="1" inputmode="decimal" placeholder="Watts">
    <button type="button" class="icon-button remove-load" aria-label="Remove additional load" title="Remove">Remove</button>
  `;
  row.querySelector(".remove-load").addEventListener("click", () => row.remove());
  return row;
}

function selectedUnits() {
  return $$(".unit-toggle:checked").map((input) => input.value);
}

function renderUnits() {
  const container = $("#unitsContainer");
  const units = selectedUnits();
  const existingValues = collectFormData({ includeEmpty: true });

  container.innerHTML = units.map(unitCard).join("");
  units.forEach((unit) => {
    const card = $(`.unit-card[data-unit="${unit}"]`);
    const previous = existingValues.units.find((item) => item.unit_type === unit);
    if (previous) restoreUnitValues(card, previous);
    $(".add-load", card).addEventListener("click", () => {
      $(".additional-list", card).appendChild(additionalLoadRow());
    });
  });
}

function restoreUnitValues(card, data) {
  const aboveGround = data.above_ground_m2 ?? data.area_m2 ?? "";
  $(`[name="above_ground_m2_${data.unit_type}"]`, card).value = aboveGround || "";
  $(`[name="below_ground_m2_${data.unit_type}"]`, card).value = data.below_ground_m2 || "";
  $(`[name="interlocked_${data.unit_type}"]`, card).checked = Boolean(data.heating_cooling_interlocked);
  LOAD_FIELDS.forEach(([key]) => {
    const input = $(`[name="${key}_${data.unit_type}"]`, card);
    if (input) input.value = data[key] || "";
  });

  (data.additional_items || []).forEach((item) => {
    const row = additionalLoadRow();
    $(".additional-description", row).value = item.description || "";
    $(".additional-watts", row).value = item.watts || "";
    $(".additional-list", card).appendChild(row);
  });
}

function collectFormData(options = {}) {
  const units = selectedUnits().map((unit) => {
    const card = $(`.unit-card[data-unit="${unit}"]`);
    if (!card) {
      return { unit_type: unit, additional_items: [] };
    }

    const additionalItems = $$(".additional-row", card)
      .map((row) => ({
        description: $(".additional-description", row).value.trim(),
        watts: parseNumber($(".additional-watts", row)),
      }))
      .filter((item) => options.includeEmpty || item.description || item.watts > 0);

    const unitData = {
      unit_type: unit,
      above_ground_m2: parseNumber($(`[name="above_ground_m2_${unit}"]`, card)),
      below_ground_m2: parseNumber($(`[name="below_ground_m2_${unit}"]`, card)),
      heating_cooling_interlocked: $(`[name="interlocked_${unit}"]`, card).checked,
      additional_items: additionalItems,
      additional_load: additionalItems.reduce((sum, item) => sum + item.watts, 0),
    };
    unitData.area_m2 = unitData.above_ground_m2 + (unitData.below_ground_m2 * BELOW_GROUND_AREA_FACTOR);

    LOAD_FIELDS.forEach(([key]) => {
      unitData[key] = parseNumber($(`[name="${key}_${unit}"]`, card));
    });

    return unitData;
  });

  return {
    num_units: units.length,
    conductor_type: $("[name='conductorType']:checked").value,
    units,
  };
}

function renderResults(data) {
  $("#emptyState").classList.add("hidden");
  $("#resultContent").classList.remove("hidden");
  $("#resultError").classList.add("hidden");
  $("#totalAmps").textContent = formatAmps(data["Total Amps"]);
  $("#totalWatts").textContent = `${formatWatts(data["Total Calculated Load (Watts)"])} total load`;
  $("#serviceOcp").textContent = data["Service OCP size (Amps)"] || "N/A";
  $("#serviceConductor").textContent = data["Service Conductor Type and Size"] || "N/A";
  $("#basicDemandLoad").textContent = formatWatts(data["Basic Demand Load (Watts)"] ?? data["Combined No-HVAC Load (Watts)"]);
  $("#towardsDemandLoad").textContent = formatWatts(data["100% Towards Demand Load (Watts)"] ?? data["Total HVAC Load (Watts)"]);

  $("#unitResults").innerHTML = (data.units || []).map((unit) => `
    <article class="unit-result">
      <div>
        <span>${unit.unit_type || "Unit"}</span>
        <strong>${formatAmps(unit.unit_amps)}</strong>
      </div>
      <dl>
        <div><dt>Load</dt><dd>${formatWatts(unit.calculated_load)}</dd></div>
        <div><dt>OCP</dt><dd>${unit.unit_ocp || "N/A"}</dd></div>
        <div><dt>Conductor</dt><dd>${unit.unit_conductor || "N/A"}</dd></div>
      </dl>
      ${renderAreaSummary(unit.area_summary)}
      ${renderBreakdownTable(unit.breakdown || [])}
    </article>
  `).join("");

  const serviceBreakdown = $("#serviceBreakdown");
  if (serviceBreakdown) {
    serviceBreakdown.innerHTML = renderBreakdownTable(data["Service Demand Breakdown"] || []);
  }

  $("#reviewButton").disabled = false;
}

function renderAreaSummary(summary) {
  if (!summary) return "";
  return `
    <div class="area-summary">
      <div class="area-summary-heading">
        <strong>Area used for BASIC demand</strong>
        <span>${formatM2(summary.effective_area_m2)}</span>
      </div>
      <div class="area-summary-row">
        <span>Above ground</span>
        <span>${formatM2(summary.above_ground_m2)}</span>
        <strong>${formatWatts(summary.above_ground_watts)}</strong>
      </div>
      <div class="area-summary-row">
        <span>Below ground, 75% counted</span>
        <span>${formatM2(summary.below_ground_counted_m2)} of ${formatM2(summary.below_ground_m2)}</span>
        <strong>${formatWatts(summary.below_ground_watts)}</strong>
      </div>
      <div class="area-summary-total">
        <span>Basic area watts</span>
        <strong>${formatWatts(summary.basic_area_watts)}</strong>
      </div>
    </div>
  `;
}

function renderBreakdownTable(rows) {
  if (!rows.length) return "";
  return `
    <div class="breakdown-table">
      <div class="breakdown-head">
        <span>Calculation</span>
        <span>Nameplate</span>
        <span>Demand</span>
        <span>Included</span>
      </div>
      ${rows.map((row) => `
        <div class="breakdown-row">
          <div>
            <strong>${row.label}</strong>
            <small>${row.rule}${row.note ? ` · ${row.note}` : ""}</small>
          </div>
          <span>${row.nameplate_watts === null || row.nameplate_watts === undefined ? "-" : formatWatts(row.nameplate_watts)}</span>
          <span>${formatPercent(row.demand_percent)}</span>
          <strong>${formatWatts(row.demand_watts)}</strong>
        </div>
      `).join("")}
    </div>
  `;
}

async function calculateLoad(event) {
  event.preventDefault();
  const button = $(".primary-action");
  button.disabled = true;
  button.textContent = "Calculating...";

  try {
    const inputData = collectFormData();
    lastCalculationInput = inputData;
    localStorage.setItem("lastCalculationInput", JSON.stringify(inputData));

    const response = await fetch("/api/calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(inputData),
    });

    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || payload.message || "Calculation failed.");

    lastCalculationResult = payload;
    localStorage.setItem("lastCalculationResult", JSON.stringify(payload));
    renderResults(payload);
  } catch (error) {
    $("#emptyState").classList.add("hidden");
    $("#resultContent").classList.remove("hidden");
    $("#resultError").classList.remove("hidden");
    $("#resultError").innerHTML = `<h2>Calculation failed</h2><p>${error.message}</p>`;
  } finally {
    button.disabled = false;
    button.textContent = "Calculate";
  }
}

async function sendCalculationEmail() {
  const userEmail = window.prompt("Email address for the calculation PDF:");
  if (!userEmail) return;
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(userEmail)) {
    window.alert("Enter a valid email address.");
    return;
  }
  if (!lastCalculationInput || !lastCalculationResult) {
    window.alert("Calculate first, then send the PDF.");
    return;
  }

  const button = $("#emailButton");
  button.disabled = true;
  button.textContent = "Sending...";
  try {
    const response = await fetch("/api/send_calculation_email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        userEmail,
        inputData: lastCalculationInput,
        resultData: lastCalculationResult,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.message || "Email failed to send.");
    window.alert(payload.message || "Email sent successfully.");
  } catch (error) {
    window.alert(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "Email PDF";
  }
}

function resetCalculator() {
  localStorage.removeItem("lastCalculationInput");
  localStorage.removeItem("lastCalculationResult");
  window.location.reload();
}

document.addEventListener("DOMContentLoaded", () => {
  $$(".unit-toggle").forEach((input) => input.addEventListener("change", renderUnits));
  $("#loadCalcForm").addEventListener("submit", calculateLoad);
  $("#emailButton").addEventListener("click", sendCalculationEmail);
  $("#reviewButton").addEventListener("click", () => { window.location.href = "/api/review_form"; });
  $("#resetButton").addEventListener("click", resetCalculator);
  renderUnits();
});
