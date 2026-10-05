const input = document.getElementById("trace-input");
const statusPill = document.getElementById("status-pill");
const errorBox = document.getElementById("error");
const summary = document.getElementById("summary");
const gatesBox = document.getElementById("gates");
const policyTable = document.getElementById("policy-table");
const mode = document.getElementById("mode");
const hint = document.getElementById("mode-hint");
const badge = document.getElementById("experiment-badge");
const interpretation = document.getElementById("interpretation");
const fileInput = document.getElementById("trace-file");

const syntheticExample = [
  {
    id: "trace-1",
    initial_quality: 0.40,
    steps: [
      { quality: 0.66, cost: 0.05, predicted_gain: 0.24 },
      { quality: 0.67, cost: 0.16, predicted_gain: 0.02 },
      { quality: 0.68, cost: 0.16, predicted_gain: 0.01 }
    ]
  },
  {
    id: "trace-2",
    initial_quality: 0.52,
    steps: [
      { quality: 0.78, cost: 0.05, predicted_gain: 0.22 },
      { quality: 0.79, cost: 0.15, predicted_gain: 0.01 },
      { quality: 0.80, cost: 0.15, predicted_gain: 0.01 }
    ]
  }
];

const realTemplate = [
  {
    task_id: "task-001",
    model: "provider/model-name",
    prompt_hash: "sha256-of-original-prompt",
    initial_quality: 0.20,
    steps: [
      {
        step_index: 1,
        quality: 0.55,
        cost: 0.05,
        predicted_gain: 0.20,
        latency_ms: 900,
        input_tokens: 120,
        output_tokens: 80
      },
      {
        step_index: 2,
        quality: 0.72,
        cost: 0.08,
        predicted_gain: 0.12,
        latency_ms: 1100,
        input_tokens: 180,
        output_tokens: 110
      }
    ]
  }
];

function pct(x) {
  return (x * 100).toFixed(2) + "%";
}

function num(x) {
  return Number(x).toFixed(4);
}

function loadExample() {
  const real = mode.value === "real";
  input.value = JSON.stringify(real ? realTemplate : syntheticExample, null, 2);
}

function syncMode() {
  const real = mode.value === "real";
  badge.textContent = real ? "Real trace" : "Synthetic";
  badge.className = "pill neutral";
  hint.textContent = real
    ? "Real trace mode: task_id, model, prompt_hash, initial_quality and contiguous step_index values are required."
    : "Synthetic demo: paste evaluator traces directly.";
  interpretation.textContent = real
    ? "Real mode validates trace provenance fields before running the frozen ThinkGate gates. A pass is only meaningful on genuinely collected, untouched evaluation traces."
    : "Synthetic SUCCESS is a wiring check. Switch to Real trace mode for preregistered evaluation of externally collected LLM traces.";
  loadExample();
}

function render(report) {
  const success = report.status === "SUCCESS";
  statusPill.textContent = report.status;
  statusPill.className = "pill " + (success ? "success" : "failed");

  summary.className = "summary";
  const extra = report.experiment_type === "REAL_TRACE"
    ? "<br>Mode: <code>REAL_TRACE</code> · Traces: " + report.trace_count + " · " + report.validation
    : "";
  summary.innerHTML =
    "<strong>" + report.status + "</strong><br>" +
    "Stronger baseline: <code>" + report.stronger_baseline + "</code><br>" +
    "Utility improvement: " + pct(report.observed.utility_improvement) + " · " +
    "Quality drop: " + num(report.observed.quality_drop) + " · " +
    "Cost reduction: " + pct(report.observed.cost_reduction) +
    extra;

  const labels = {
    utility_gain: "Utility gain ≥ 5%",
    quality_retention: "Quality drop ≤ 0.01",
    cost_reduction: "Compute cost reduction ≥ 10%"
  };

  gatesBox.innerHTML = Object.entries(report.gates)
    .map(function(entry) {
      const key = entry[0];
      const ok = entry[1];
      return (
        '<div class="gate">' +
        "<span>" + (labels[key] || key) + "</span>" +
        '<strong class="' + (ok ? "pass" : "fail") + '">' +
        (ok ? "PASS" : "FAIL") +
        "</strong></div>"
      );
    })
    .join("");

  policyTable.innerHTML = Object.values(report.policies)
    .map(function(p) {
      return (
        "<tr>" +
        "<td>" + p.name + "</td>" +
        "<td>" + num(p.mean_quality) + "</td>" +
        "<td>" + num(p.mean_cost) + "</td>" +
        "<td>" + num(p.mean_utility) + "</td>" +
        "</tr>"
      );
    })
    .join("");
}

document.getElementById("load-example").addEventListener("click", loadExample);
mode.addEventListener("change", syncMode);

fileInput.addEventListener("change", async function() {
  errorBox.textContent = "";
  const file = fileInput.files && fileInput.files[0];
  if (!file) return;
  try {
    input.value = await file.text();
  } catch (err) {
    errorBox.textContent = "Could not read JSON file.";
  }
});

document.getElementById("evaluate").addEventListener("click", async function() {
  errorBox.textContent = "";
  let traces;

  try {
    traces = JSON.parse(input.value);
    if (!Array.isArray(traces)) {
      throw new Error("Input must be a JSON array of traces.");
    }
  } catch (err) {
    errorBox.textContent = err.message;
    return;
  }

  try {
    const real = mode.value === "real";
    const endpoint = real ? "/api/evaluate-real" : "/api/evaluate";
    const body = real
      ? { traces: traces, margin: Number(document.getElementById("margin").value || 0) }
      : { traces: traces, margin: Number(document.getElementById("margin").value || 0) };

    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Evaluation failed.");
    }
    render(data);
  } catch (err) {
    errorBox.textContent = err.message;
  }
});

syncMode();
