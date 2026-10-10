#!/usr/bin/env python3
"""Minimalist, premium web dashboard viewer for Agent Learning Pilot experiments."""

import http.server
import json
import os
import socketserver
from pathlib import Path

PORT = 8000
BASE_DIR = Path(__file__).resolve().parent.parent

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Agent Learning Pilot — Research Deck</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0b0f19;
      --card-bg: rgba(18, 24, 39, 0.75);
      --card-hover: rgba(28, 38, 62, 0.9);
      --border: rgba(255, 255, 255, 0.08);
      --border-glow: rgba(59, 130, 246, 0.4);
      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --text-dim: #6b7280;
      --accent-blue: #3b82f6;
      --accent-emerald: #10b981;
      --accent-purple: #a855f7;
      --accent-amber: #f59e0b;
      --glass: blur(16px);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: 'Inter', -apple-system, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      background-image: 
        radial-gradient(circle at 10% 20%, rgba(59, 130, 246, 0.08) 0%, transparent 40%),
        radial-gradient(circle at 90% 80%, rgba(168, 85, 247, 0.08) 0%, transparent 40%);
    }
    header {
      padding: 16px 36px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: rgba(11, 15, 25, 0.85);
      backdrop-filter: var(--glass);
      position: sticky;
      top: 0;
      z-index: 50;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .badge {
      width: 36px;
      height: 36px;
      border-radius: 10px;
      background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue));
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 15px;
      color: #fff;
      box-shadow: 0 0 15px rgba(59, 130, 246, 0.4);
    }
    .brand h1 {
      font-size: 18px;
      font-weight: 700;
      letter-spacing: -0.01em;
    }
    .brand span {
      font-size: 12px;
      color: var(--text-dim);
      margin-left: 6px;
    }
    .status-badge {
      padding: 6px 14px;
      border-radius: 999px;
      background: rgba(16, 185, 129, 0.1);
      border: 1px solid rgba(16, 185, 129, 0.25);
      font-size: 12px;
      color: var(--accent-emerald);
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 500;
    }
    .dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--accent-emerald);
      box-shadow: 0 0 8px var(--accent-emerald);
    }
    main {
      max-width: 1400px;
      width: 100%;
      margin: 0 auto;
      padding: 32px 36px;
      display: flex;
      flex-direction: column;
      gap: 28px;
    }
    .grid-overview {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 18px;
    }
    .metric-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      backdrop-filter: var(--glass);
      border-radius: 14px;
      padding: 20px 22px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .metric-card .title {
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-dim);
    }
    .metric-card .val {
      font-size: 26px;
      font-weight: 700;
      font-family: 'JetBrains Mono', monospace;
      color: #fff;
    }
    .card-full {
      background: var(--card-bg);
      border: 1px solid var(--border);
      backdrop-filter: var(--glass);
      border-radius: 16px;
      padding: 24px 28px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .card-title {
      font-size: 16px;
      font-weight: 600;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .conditions-row {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 14px;
    }
    .condition-box {
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .condition-box h4 {
      font-size: 14px;
      font-weight: 600;
      color: #fff;
    }
    .condition-box p {
      font-size: 12px;
      color: var(--text-muted);
      line-height: 1.5;
    }
    
    /* Metrics table */
    .table-container {
      overflow-x: auto;
      border: 1px solid var(--border);
      border-radius: 10px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 13px;
    }
    th {
      background: rgba(255, 255, 255, 0.04);
      padding: 12px 16px;
      font-weight: 600;
      color: var(--text-dim);
      text-transform: uppercase;
      font-size: 11px;
      letter-spacing: 0.05em;
      border-bottom: 1px solid var(--border);
    }
    td {
      padding: 12px 16px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
      font-family: 'JetBrains Mono', monospace;
    }
    tr:last-child td { border-bottom: none; }
    .condition-label { font-family: 'Inter', sans-serif; font-weight: 600; color: #fff; }
    .score-high { color: var(--accent-emerald); font-weight: 600; }
    .score-mid { color: var(--accent-amber); }
    .score-low { color: #f87171; }

    /* Figure tabs */
    .fig-tabs {
      display: flex;
      gap: 8px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 12px;
    }
    .fig-tab {
      padding: 8px 16px;
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid var(--border);
      color: var(--text-muted);
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s;
    }
    .fig-tab.active, .fig-tab:hover {
      background: rgba(59, 130, 246, 0.15);
      border-color: var(--accent-blue);
      color: #fff;
    }
    .fig-viewer {
      display: flex;
      justify-content: center;
      align-items: center;
      padding: 16px;
      background: rgba(0, 0, 0, 0.3);
      border-radius: 12px;
      border: 1px solid var(--border);
      min-height: 380px;
    }
    .fig-viewer img {
      max-width: 100%;
      max-height: 480px;
      border-radius: 8px;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
    }

    /* Tasks grid */
    .tasks-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
      gap: 10px;
      max-height: 320px;
      overflow-y: auto;
      padding-right: 6px;
    }
    .task-chip {
      background: rgba(255, 255, 255, 0.02);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px;
      text-align: center;
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      cursor: pointer;
      transition: all 0.2s ease;
    }
    .task-chip:hover {
      background: rgba(59, 130, 246, 0.15);
      border-color: var(--accent-blue);
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
    }
    .family-badge {
      display: inline-block;
      font-size: 10px;
      padding: 2px 6px;
      border-radius: 4px;
      margin-top: 4px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .family-al { background: rgba(59, 130, 246, 0.15); color: var(--accent-blue); }
    .family-db { background: rgba(16, 185, 129, 0.15); color: var(--accent-emerald); }
    .family-dm { background: rgba(168, 85, 247, 0.15); color: var(--accent-purple); }
    .family-se { background: rgba(245, 158, 11, 0.15); color: var(--accent-amber); }

    /* Modal */
    .modal-overlay {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0, 0, 0, 0.7);
      backdrop-filter: blur(8px);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 100;
    }
    .modal-overlay.active { display: flex; }
    .modal-card {
      background: #111827;
      border: 1px solid var(--border);
      border-radius: 16px;
      width: 90%;
      max-width: 640px;
      max-height: 85vh;
      overflow-y: auto;
      padding: 28px;
      box-shadow: 0 20px 40px rgba(0,0,0,0.8);
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .modal-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      border-bottom: 1px solid var(--border);
      padding-bottom: 12px;
    }
    .modal-close {
      background: none;
      border: none;
      color: var(--text-dim);
      font-size: 20px;
      cursor: pointer;
    }
    .modal-close:hover { color: #fff; }
    .code-block {
      background: rgba(0, 0, 0, 0.4);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      color: #93c5fd;
      white-space: pre-wrap;
      overflow-x: auto;
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="badge">AL</div>
      <div>
        <h1>Agent Learning Pilot</h1>
      </div>
      <span>Controlled Feedback Transfer Experiment</span>
    </div>
    <div class="status-badge">
      <div class="dot"></div>
      <span>Ollama Qwen Active (qwen2.5:7b)</span>
    </div>
  </header>

  <main>
    <div class="grid-overview">
      <div class="metric-card">
        <div class="title">Evaluated Model</div>
        <div class="val" style="font-size: 20px;">qwen2.5:7b</div>
      </div>
      <div class="metric-card">
        <div class="title">Total Benchmark Tasks</div>
        <div class="val">48</div>
      </div>
      <div class="metric-card">
        <div class="title">Task Families</div>
        <div class="val">4 (AL, DB, DM, SE)</div>
      </div>
      <div class="metric-card">
        <div class="title">Experimental Conditions</div>
        <div class="val">4 Tested</div>
      </div>
    </div>

    <!-- Experimental Conditions -->
    <div class="card-full">
      <div class="card-title">
        <span>Experimental Conditions</span>
        <span style="font-size: 12px; color: var(--text-dim); font-weight: normal;">3 independent trials per condition</span>
      </div>
      <div class="conditions-row">
        <div class="condition-box">
          <h4>1. Baseline</h4>
          <p>Zero feedback persistence. Each coding task evaluated with an independent context window.</p>
        </div>
        <div class="condition-box">
          <h4>2. Reflection</h4>
          <p>Self-reflection generated after test feedback and appended to future prompt contexts.</p>
        </div>
        <div class="condition-box">
          <h4>3. Memory</h4>
          <p>Key-value memory store retrieving previous bug fixes and error signatures for matching tasks.</p>
        </div>
        <div class="condition-box">
          <h4>4. Workflow</h4>
          <p>Dynamic workflow adaptation based on cumulative test execution results and feedback history.</p>
        </div>
      </div>
    </div>

    <!-- Comparative Results Table -->
    <div class="card-full">
      <div class="card-title">
        <span>Comparative Results Across Task Splits</span>
        <span style="font-size: 12px; color: var(--text-dim); font-weight: normal;">Mean Success Rates</span>
      </div>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Condition</th>
              <th>Cross-Family Transfer</th>
              <th>Held-Out Tasks</th>
              <th>Regression Avoidance</th>
              <th>Feedback Recovery</th>
            </tr>
          </thead>
          <tbody id="metricsTbody">
            <tr>
              <td class="condition-label">Baseline</td>
              <td class="score-mid">33.3%</td>
              <td class="score-low">0.0%</td>
              <td class="score-low">25.0%</td>
              <td class="score-high">75.0%</td>
            </tr>
            <tr>
              <td class="condition-label">Reflection</td>
              <td class="score-mid">33.3%</td>
              <td class="score-low">0.0%</td>
              <td class="score-low">25.0%</td>
              <td class="score-high">75.0%</td>
            </tr>
            <tr>
              <td class="condition-label">Memory</td>
              <td class="score-high">58.3%</td>
              <td class="score-high">100.0%</td>
              <td class="score-high">75.0%</td>
              <td class="score-high">75.0%</td>
            </tr>
            <tr>
              <td class="condition-label">Workflow Mutation</td>
              <td class="score-high">50.0%</td>
              <td class="score-high">100.0%</td>
              <td class="score-high">75.0%</td>
              <td class="score-high">100.0%</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Research Figures Viewer -->
    <div class="card-full">
      <div class="card-title">
        <span>Research Plots & Experiment Figures</span>
        <span style="font-size: 12px; color: var(--text-dim); font-weight: normal;">Generated from empirical pilot execution</span>
      </div>
      <div class="fig-tabs">
        <button class="fig-tab active" onclick="switchFig('success_by_condition.png', this)">Success by Condition</button>
        <button class="fig-tab" onclick="switchFig('retention.png', this)">Retention Across Tasks</button>
        <button class="fig-tab" onclick="switchFig('transfer_matrix.png', this)">Transfer Matrix</button>
        <button class="fig-tab" onclick="switchFig('cost_vs_capability.png', this)">Cost vs Capability</button>
      </div>
      <div class="fig-viewer">
        <img id="figImage" src="/figures/success_by_condition.png" alt="Experiment Figure">
      </div>
    </div>

    <!-- Task Benchmark Suite -->
    <div class="card-full">
      <div class="card-title">
        <span>Task Benchmark Suite (48 Total)</span>
        <span style="font-size: 12px; color: var(--text-dim); font-weight: normal;">Click any task to inspect specification & starter code</span>
      </div>
      <div class="tasks-grid" id="tasksDeck">
        <!-- Rendered via script -->
      </div>
    </div>
  </main>

  <!-- Interactive Task Modal -->
  <div class="modal-overlay" id="taskModal">
    <div class="modal-card">
      <div class="modal-header">
        <div>
          <h3 id="mTitle" style="font-size: 18px; font-weight: 700; color: #fff;">Task Details</h3>
          <span id="mMeta" style="font-size: 12px; color: var(--accent-blue); font-family: 'JetBrains Mono', monospace;"></span>
        </div>
        <button class="modal-close" onclick="closeModal()">&times;</button>
      </div>
      <div>
        <h4 style="font-size: 12px; text-transform: uppercase; color: var(--text-dim); margin-bottom: 6px;">Specification</h4>
        <p id="mSpec" style="font-size: 13px; color: var(--text); line-height: 1.5;"></p>
      </div>
      <div>
        <h4 style="font-size: 12px; text-transform: uppercase; color: var(--text-dim); margin-bottom: 6px;">Starter Implementation</h4>
        <pre class="code-block" id="mCode"></pre>
      </div>
    </div>
  </div>

  <script>
    const families = {
      'al': { name: 'Algorithms', cls: 'family-al' },
      'db': { name: 'Database', cls: 'family-db' },
      'dm': { name: 'Data Manip', cls: 'family-dm' },
      'se': { name: 'Software Eng', cls: 'family-se' }
    };

    function switchFig(filename, btn) {
      document.querySelectorAll('.fig-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById('figImage').src = '/figures/' + filename;
    }

    const deck = document.getElementById('tasksDeck');
    ['al', 'db', 'dm', 'se'].forEach(f => {
      for (let i = 1; i <= 12; i++) {
        const num = i < 10 ? '0' + i : '' + i;
        const taskId = `${f}_${num}`;
        const chip = document.createElement('div');
        chip.className = 'task-chip';
        chip.innerHTML = `
          <div>${taskId}</div>
          <span class="family-badge ${families[f].cls}">${families[f].name}</span>
        `;
        chip.onclick = () => openTask(taskId);
        deck.appendChild(chip);
      }
    });

    async function openTask(taskId) {
      try {
        const r = await fetch(`/api/tasks/${taskId}`);
        if (r.ok) {
          const t = await r.json();
          document.getElementById('mTitle').textContent = t.title || taskId;
          document.getElementById('mMeta').textContent = `ID: ${t.id} | Family: ${t.family} | Difficulty: ${t.difficulty || 'medium'}`;
          document.getElementById('mSpec').textContent = t.specification || 'No specification details provided.';
          document.getElementById('mCode').textContent = t.starter_code || '# Starter code not available';
          document.getElementById('taskModal').classList.add('active');
        }
      } catch (err) {
        console.error('Failed to load task', err);
      }
    }

    function closeModal() {
      document.getElementById('taskModal').classList.remove('active');
    }

    window.onclick = function(e) {
      if (e.target === document.getElementById('taskModal')) {
        closeModal();
      }
    };
  </script>
</body>
</html>
"""

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path.startswith("/dashboard"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "model": "qwen2.5:7b"}).encode("utf-8"))
        elif self.path.startswith("/figures/"):
            filename = self.path.split("/figures/")[-1]
            fig_path = BASE_DIR / "results" / "figures" / filename
            if fig_path.exists():
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.end_headers()
                self.wfile.write(fig_path.read_bytes())
            else:
                self.send_response(404)
                self.end_headers()
        elif self.path.startswith("/api/tasks/"):
            task_id = self.path.split("/api/tasks/")[-1]
            task_dir = BASE_DIR / "data" / "tasks" / task_id
            task_json = task_dir / "task.json"
            if task_json.exists():
                data = json.loads(task_json.read_text(encoding="utf-8"))
                starter_file = task_dir / "starter.py"
                if starter_file.exists():
                    data["starter_code"] = starter_file.read_text(encoding="utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()
        elif self.path == "/api/metrics":
            metrics_path = BASE_DIR / "results" / "aggregated" / "metrics.json"
            if metrics_path.exists():
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(metrics_path.read_bytes())
            else:
                self.send_response(404)
                self.end_headers()
        else:
            super().do_GET()

def run_server(port=PORT):
    with socketserver.TCPServer(("", port), DashboardHandler) as httpd:
        print(f"Agent Learning Pilot dashboard running at: http://localhost:{port}/")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")

if __name__ == "__main__":
    run_server()
