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

function calibratedExample() {
  return Array.from({ length: 6 }, (_, i) => {
    const base = 0.18 + i * 0.02;
    return {
      task_id: "task-00" + (i + 1),
      model: "provider/model-name",
      prompt_hash: "example-hash-" + (i + 1),
      initial_quality: base,
      steps: [
        { step_index: 1, quality: base + 0.28, cost: 0.05, latency_ms: 900, input_tokens: 120, output_tokens: 80 },
        { step_index: 2, quality: base + 0.34, cost: 0.08, latency_ms: 1100, input_tokens: 180, output_tokens: 110 },
        { step_index: 3, quality: base + 0.35, cost: 0.12, latency_ms: 1300, input_tokens: 220, output_tokens: 130 }
      ]
    };
  });
}

function pct(x) {
  return (x * 100).toFixed(2) + "%";
}

function num(x) {
  return Number(x).toFixed(4);
}

function loadExample() {
  const selected = mode.value;
  const template = selected === "calibrated"
    ? calibratedExample()
    : (selected === "real" ? realTemplate : syntheticExample);
  input.value = JSON.stringify(template, null, 2);
}

function syncMode() {
  const selected = mode.value;
  badge.textContent = selected === "calibrated"
    ? "Calibrated"
    : (selected === "real" ? "Real trace" : "Synthetic");
  badge.className = "pill neutral";

  if (selected === "calibrated") {
    hint.textContent = "Upload at least 5 observed task traces. predicted_gain is learned from train traces and must not be supplied.";
    interpretation.textContent = "Calibrated mode learns predicted gain on train traces, selects the decision margin on tune traces, and applies the frozen success gates only to held-out eval traces.";
    document.getElementById("margin").disabled = true;
  } else if (selected === "real") {
    hint.textContent = "Real trace mode requires task_id, model, prompt_hash, initial_quality, contiguous step_index values, and externally supplied predicted_gain.";
    interpretation.textContent = "Real mode validates trace provenance fields before running the frozen ThinkGate gates. A pass is meaningful only on genuinely collected, untouched evaluation traces.";
    document.getElementById("margin").disabled = false;
  } else {
    hint.textContent = "Synthetic demo: paste evaluator traces directly.";
    interpretation.textContent = "Synthetic SUCCESS is a wiring check. Use calibrated mode to test a learned predicted-gain policy on held-out traces.";
    document.getElementById("margin").disabled = false;
  }
  loadExample();
}

function render(report) {
  const success = report.status === "SUCCESS";
  statusPill.textContent = report.status;
  statusPill.className = "pill " + (success ? "success" : "failed");

  summary.className = "summary";
  let extra = "";
  if (report.experiment_type === "REAL_TRACE") {
    extra = "<br>Mode: <code>REAL_TRACE</code> · Traces: " + report.trace_count + " · " + report.validation;
  } else if (report.experiment_type === "CALIBRATED_REAL_TRACE") {
    extra = "<br>Mode: <code>CALIBRATED_REAL_TRACE</code> · Split: " +
      report.split.train + "/" + report.split.tune + "/" + report.split.eval +
      " · Margin: " + report.selected_margin + "<br>" + report.validation;
  }

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
    const selected = mode.value;
    const endpoint = selected === "calibrated"
      ? "/api/calibrate-evaluate"
      : (selected === "real" ? "/api/evaluate-real" : "/api/evaluate");
    const body = selected === "calibrated"
      ? { traces: traces }
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
