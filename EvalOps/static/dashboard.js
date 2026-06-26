// Global State
let taskIdToName = {};
let activeChart = null;

// On Page Load
document.addEventListener("DOMContentLoaded", async () => {
  await loadTasks();
  await loadRunSelector();
  
  // Set up event listeners
  document.getElementById("btnLoadRun").addEventListener("click", loadActiveRun);
  document.getElementById("btnRunEval").addEventListener("click", triggerNewEvaluation);
});

// Fetch tasks to build a task_id -> task_name map
async function loadTasks() {
  try {
    const resp = await fetch("/tasks");
    const tasks = await resp.json();
    tasks.forEach(t => {
      taskIdToName[t.id] = t.name;
    });
  } catch (err) {
    console.error("Error loading tasks mapping:", err);
  }
}

// Fetch list of unique run IDs and populate the selector
async function loadRunSelector() {
  try {
    const resp = await fetch("/runs");
    const runIds = await resp.json();
    
    const select = document.getElementById("runSelect");
    // Clear previous options
    select.innerHTML = "";
    
    if (runIds.length === 0) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "-- No Runs Found --";
      select.appendChild(opt);
      return;
    }
    
    runIds.forEach(id => {
      const opt = document.createElement("option");
      opt.value = id;
      opt.textContent = `Run: ${id.substring(0, 8)}...`;
      select.appendChild(opt);
    });
  } catch (err) {
    console.error("Error loading run selector list:", err);
  }
}

// Trigger a mock/new run evaluation run for local testing
async function triggerNewEvaluation() {
  const model = prompt("Enter model name to evaluate:", "llama3");
  if (!model) return;
  
  try {
    const resp = await fetch("/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dataset_path: "golden_datasets/example_dataset.json",
        model: model
      })
    });
    const result = await resp.json();
    alert(`Evaluation run started successfully!\nRun ID: ${result.run_id}`);
    
    // Reload selector list after a short delay
    setTimeout(loadRunSelector, 2000);
  } catch (err) {
    alert("Failed to start evaluation run: " + err);
  }
}

// Load and render all sections of the active selected run
async function loadActiveRun() {
  const runSelect = document.getElementById("runSelect");
  const runId = runSelect.value;
  if (!runId) {
    alert("Please select a valid run ID first.");
    return;
  }
  
  try {
    // 1. Fetch main run report
    const reportResp = await fetch(`/runs/${runId}`);
    const report = await reportResp.json();
    
    // 2. Fetch regressions
    const regResp = await fetch(`/runs/${runId}/regressions`);
    const regressions = await regResp.json();
    
    renderSummaryCards(report);
    renderResultsTable(report.runs, regressions);
    renderRegressionsPanel(regressions);
    renderHumanFeedbackPanel(report.runs, runId);
    
    // Get a baseline run to render comparison chart
    // We will use the next run in the selector list as the baseline if available
    let baselineRunId = null;
    const selectOptions = Array.from(runSelect.options);
    const activeIndex = selectOptions.findIndex(opt => opt.value === runId);
    if (activeIndex !== -1 && activeIndex + 1 < selectOptions.length) {
      baselineRunId = selectOptions[activeIndex + 1].value;
    }
    
    await renderChart(report.runs, runId, baselineRunId);
    
  } catch (err) {
    console.error("Error loading run data details:", err);
    alert("Error loading run details: " + err);
  }
}

// Render Summary Cards Row
function renderSummaryCards(report) {
  document.getElementById("valTotalTasks").textContent = report.total_tasks;
  document.getElementById("valPassRate").textContent = `${Math.round(report.pass_rate * 100)}%`;
  document.getElementById("valAvgScore").textContent = report.avg_score.toFixed(2);
  document.getElementById("valAvgLatency").textContent = `${Math.round(report.avg_latency_ms)}ms`;
  document.getElementById("valRegressions").textContent = report.regressions;
}

// Render Task Results Table
function renderResultsTable(runs, regressions) {
  const tbody = document.getElementById("resultsTableBody");
  tbody.innerHTML = "";
  
  const regTaskIds = new Set(regressions.map(r => r.task_id));
  
  runs.forEach(run => {
    const tr = document.createElement("tr");
    
    const taskName = taskIdToName[run.task_id] || run.task_id;
    
    // Determine status class
    let statusClass = "status-pass";
    let statusText = "PASS";
    
    if (regTaskIds.has(run.task_id)) {
      statusClass = "status-fail";
      statusText = "REGRESSION";
    } else if (run.score < 0.7) {
      statusClass = "status-warn";
      statusText = "BORDERLINE";
    }
    
    tr.innerHTML = `
      <td><strong>${taskName}</strong></td>
      <td>${run.model}</td>
      <td style="font-weight: 500;">${run.score.toFixed(2)}</td>
      <td>${Math.round(run.latency_ms)} ms</td>
      <td>${run.tokens_used}</td>
      <td>${run.score < 0.3 ? "Yes" : "No"}</td>
      <td><span class="status-badge ${statusClass}">${statusText}</span></td>
    `;
    
    tbody.appendChild(tr);
  });
}

// Render score trend chart comparing current vs baseline runs
async function renderChart(currentRuns, currentRunId, baselineRunId) {
  const ctx = document.getElementById("scoreChart").getContext("2d");
  
  if (activeChart) {
    activeChart.destroy();
  }
  
  const labels = currentRuns.map(r => taskIdToName[r.task_id] || r.task_id);
  const currentScores = currentRuns.map(r => r.score);
  
  let baselineScores = [];
  if (baselineRunId) {
    try {
      const resp = await fetch(`/runs/${currentRunId}/compare?baseline_run_id=${baselineRunId}`);
      const comparisons = await resp.json();
      const compMap = {};
      comparisons.forEach(c => {
        compMap[c.task_id] = c;
      });
      // Match back to current runs order
      currentRuns.forEach(r => {
        const comp = compMap[r.task_id];
        // baseline score = current_score - score_delta
        const baseScore = comp ? (r.score - comp.score_delta) : 0.0;
        baselineScores.push(baseScore);
      });
    } catch (err) {
      console.error("Failed to load baseline comparison for chart:", err);
      baselineScores = currentRuns.map(() => 0.7); // fallback threshold line
    }
  } else {
    // Fallback threshold reference line
    baselineScores = currentRuns.map(() => 0.7);
  }
  
  activeChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Current Run',
          data: currentScores,
          borderColor: '#6c63ff',
          backgroundColor: 'rgba(108, 99, 255, 0.1)',
          borderWidth: 3,
          tension: 0.3,
          fill: true
        },
        {
          label: baselineRunId ? 'Baseline Run' : 'Pass Threshold (0.7)',
          data: baselineScores,
          borderColor: baselineRunId ? '#9ca3af' : '#ef4444',
          borderDash: baselineRunId ? [] : [5, 5],
          borderWidth: 2,
          tension: 0.1,
          fill: false
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          min: 0,
          max: 1,
          ticks: {
            stepSize: 0.2
          }
        }
      }
    }
  });
}

// Render collapsible regressions panel
function renderRegressionsPanel(regressions) {
  const panel = document.getElementById("regressionsPanelBody");
  panel.innerHTML = "";
  
  if (regressions.length === 0) {
    panel.innerHTML = `<p style="color: var(--text-muted); font-size: 0.9em;">No regressions detected in the active run.</p>`;
    return;
  }
  
  regressions.forEach(reg => {
    const div = document.createElement("div");
    div.className = "collapsible";
    
    div.innerHTML = `
      <div class="collapsible-header" onclick="toggleCollapsible(this)">
        <span>⚠️ <strong>${reg.task_name}</strong></span>
        <span style="color: var(--fail)">Delta: ${reg.delta.toFixed(2)}</span>
      </div>
      <div class="collapsible-content">
        <p><strong>Baseline Score:</strong> ${reg.baseline_score.toFixed(2)}</p>
        <p><strong>Current Score:</strong> ${reg.current_score.toFixed(2)}</p>
        <p><strong>Evaluated Model:</strong> ${reg.model}</p>
        <p><strong>Detected At:</strong> ${new Date().toLocaleTimeString()}</p>
      </div>
    `;
    
    panel.appendChild(div);
  });
}

// Helper to toggle collapsible elements
window.toggleCollapsible = (element) => {
  const content = element.nextElementSibling;
  if (content.style.display === "block") {
    content.style.display = "none";
  } else {
    content.style.display = "block";
  }
};

// Render Human Feedback panel
function renderHumanFeedbackPanel(runs, runId) {
  const panel = document.getElementById("feedbackPanelBody");
  panel.innerHTML = "";
  
  runs.forEach(run => {
    const taskName = taskIdToName[run.task_id] || run.task_id;
    const div = document.createElement("div");
    div.className = "feedback-item";
    
    div.innerHTML = `
      <div style="font-weight: 600; font-size: 0.95em; margin-bottom: 4px;">${taskName}</div>
      <div style="font-size: 0.85em; color: var(--text-muted); margin-bottom: 8px;">Model Output: "${run.output.substring(0, 80)}..."</div>
      
      <div class="stars-container" data-task-id="${run.task_id}">
        <span class="star" data-value="1" onclick="rateStar(this, 1)">★</span>
        <span class="star" data-value="2" onclick="rateStar(this, 2)">★</span>
        <span class="star" data-value="3" onclick="rateStar(this, 3)">★</span>
        <span class="star" data-value="4" onclick="rateStar(this, 4)">★</span>
        <span class="star" data-value="5" onclick="rateStar(this, 5)">★</span>
      </div>
      
      <textarea placeholder="Add audit notes/comments..." id="notes-${run.task_id}"></textarea>
      <button onclick="submitFeedback('${runId}', '${run.task_id}')" style="font-size: 0.8em; padding: 4px 12px;">Submit Rating</button>
    `;
    
    panel.appendChild(div);
  });
}

// Interactive Star Rating widgets
window.rateStar = (starElement, rating) => {
  const container = starElement.parentElement;
  container.setAttribute("data-rating", rating);
  
  const stars = Array.from(container.children);
  stars.forEach((star, index) => {
    if (index < rating) {
      star.style.color = "var(--star-active)";
    } else {
      star.style.color = "var(--star-inactive)";
    }
  });
};

// Submit Human feedback POST API call
window.submitFeedback = async (runId, taskId) => {
  const container = document.querySelector(`.stars-container[data-task-id="${taskId}"]`);
  const rating = parseInt(container.getAttribute("data-rating") || "5");
  const notes = document.getElementById(`notes-${taskId}`).value;
  
  try {
    const resp = await fetch("/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        run_id: runId,
        task_id: taskId,
        rating: rating,
        notes: notes
      })
    });
    
    if (resp.ok) {
      alert("Human audit feedback saved successfully!");
    } else {
      alert("Failed to submit feedback rating.");
    }
  } catch (err) {
    alert("Feedback submission error: " + err);
  }
};
