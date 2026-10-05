const input = document.getElementById("trace-input");
const statusPill = document.getElementById("status-pill");
const errorBox = document.getElementById("error");
const summary = document.getElementById("summary");
const gatesBox = document.getElementById("gates");
const policyTable = document.getElementById("policy-table");

const example = [
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

function loadExample() {
  input.value = JSON.stringify(example, null, 2);
}

function pct(x) {
  return (x * 100).toFixed(2) + "%";
}

function num(x) {
  return Number(x).toFixed(4);
}

function render(report) {
  const success = report.status === "SUCCESS";
  statusPill.textContent = report.status;
  statusPill.className = "pill " + (success ? "success" : "failed");

  summary.className = "summary";
  summary.innerHTML =
    "<strong>" + report.status + "</strong><br>" +
    "Stronger baseline: <code>" + report.stronger_baseline + "</code><br>" +
    "Utility improvement: " + pct(report.observed.utility_improvement) + " · " +
    "Quality drop: " + num(report.observed.quality_drop) + " · " +
    "Cost reduction: " + pct(report.observed.cost_reduction);

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
    const response = await fetch("/api/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        traces: traces,
        margin: Number(document.getElementById("margin").value || 0)
      })
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

loadExample();
