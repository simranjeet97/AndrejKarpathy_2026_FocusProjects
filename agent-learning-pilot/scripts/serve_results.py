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
      width: 34px;
      height: 34px;
      border-radius: 8px;
      background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue));
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 14px;
      color: #fff;
    }
    .brand h1 {
      font-size: 17px;
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
      font-size: 15px;
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
    .tasks-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
      gap: 10px;
      max-height: 380px;
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
      transition: all 0.2s ease;
    }
    .task-chip:hover {
      background: rgba(59, 130, 246, 0.12);
      border-color: rgba(59, 130, 246, 0.4);
      color: #fff;
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
        <div class="val">4</div>
      </div>
      <div class="metric-card">
        <div class="title">Intervening Tasks</div>
        <div class="val">5</div>
      </div>
    </div>

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

    <div class="card-full">
      <div class="card-title">
        <span>Task Benchmark Suite (48 Total)</span>
        <span style="font-size: 12px; color: var(--text-dim); font-weight: normal;">AL: Algorithm | DB: Database | DM: Data Manipulation | SE: Software Engineering</span>
      </div>
      <div class="tasks-grid" id="tasksDeck">
        <!-- Rendered via script -->
      </div>
    </div>
  </main>

  <script>
    const families = {
      'al': { name: 'Algorithms', cls: 'family-al' },
      'db': { name: 'Database', cls: 'family-db' },
      'dm': { name: 'Data Manip', cls: 'family-dm' },
      'se': { name: 'Software Eng', cls: 'family-se' }
    };

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
        deck.appendChild(chip);
      }
    });
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
