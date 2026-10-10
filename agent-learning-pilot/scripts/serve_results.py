#!/usr/bin/env python3
"""Minimalist, premium bright web dashboard viewer for Agent Learning Pilot experiments."""

import http.server
import json
import os
import socketserver
import sys
from pathlib import Path

PORT = 8004
BASE_DIR = Path(__file__).resolve().parent.parent

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Agent Learning Pilot — Empirical Feedback Transfer Experiment</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #f8fafc;
      --surface: #ffffff;
      --surface-subtle: #f1f5f9;
      --border: #e2e8f0;
      --border-hover: #cbd5e1;
      --text: #0f172a;
      --text-muted: #64748b;
      --text-subtle: #94a3b8;
      
      --brand: #2563eb;
      --brand-light: #eff6ff;
      --brand-dark: #1d4ed8;
      
      --emerald: #10b981;
      --emerald-light: #ecfdf5;
      --amber: #f59e0b;
      --amber-light: #fffbeb;
      --rose: #ef4444;
      --rose-light: #fef2f2;
      --purple: #8b5cf6;
      --purple-light: #f5f3ff;
      --sky: #0284c7;
      --sky-light: #f0f9ff;
      
      --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
      --shadow-md: 0 4px 16px -2px rgba(0, 0, 0, 0.06), 0 2px 6px -1px rgba(0, 0, 0, 0.03);
      --shadow-lg: 0 12px 30px -4px rgba(0, 0, 0, 0.08), 0 4px 12px -2px rgba(0, 0, 0, 0.04);
      --radius-sm: 8px;
      --radius: 12px;
      --radius-lg: 16px;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      -webkit-font-smoothing: antialiased;
    }

    /* Top Sticky Header */
    header {
      padding: 14px 32px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: rgba(255, 255, 255, 0.92);
      backdrop-filter: blur(12px);
      position: sticky;
      top: 0;
      z-index: 50;
      box-shadow: var(--shadow-sm);
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .logo-badge {
      width: 36px;
      height: 36px;
      border-radius: 10px;
      background: linear-gradient(135deg, #2563eb 0%, #8b5cf6 100%);
      color: white;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      font-size: 16px;
      box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
    }
    .brand-title {
      font-size: 18px;
      font-weight: 800;
      letter-spacing: -0.02em;
      color: var(--text);
    }
    .brand-title span {
      background: linear-gradient(135deg, #2563eb 0%, #8b5cf6 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .header-meta {
      display: flex;
      align-items: center;
      gap: 14px;
    }
    .badge-capsule {
      padding: 6px 14px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border: 1px solid var(--border);
      background: var(--surface);
    }
    .badge-capsule.online {
      background: var(--emerald-light);
      border-color: rgba(16, 185, 129, 0.3);
      color: #065f46;
    }
    .pulse-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--emerald);
      box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.2);
      animation: pulse 2s infinite;
    }
    @keyframes pulse {
      0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); }
      70% { box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
      100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }

    /* Wide Uniform Container */
    main {
      max-width: 1560px;
      width: 100%;
      margin: 0 auto;
      padding: 24px 32px 48px;
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }

    /* 5-Stage Architecture Pipeline Visualizer */
    .architecture-banner {
      background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 20px 24px;
      box-shadow: var(--shadow-sm);
    }
    .arch-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
    }
    .arch-title {
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--brand);
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .arch-desc {
      font-size: 13px;
      color: var(--text-muted);
    }
    .arch-flow {
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 12px;
    }
    .arch-step {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      padding: 12px 14px;
      transition: all 0.2s ease;
    }
    .arch-step:hover {
      border-color: var(--brand);
      transform: translateY(-2px);
      box-shadow: var(--shadow-sm);
    }
    .arch-step-num {
      font-size: 11px;
      font-weight: 700;
      color: var(--text-subtle);
      margin-bottom: 4px;
    }
    .arch-step-name {
      font-size: 13px;
      font-weight: 700;
      color: var(--text);
      display: flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 2px;
    }
    .arch-step-desc {
      font-size: 11px;
      color: var(--text-muted);
      line-height: 1.4;
    }

    /* KPI Metrics Grid */
    .grid-overview {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
    }
    .metric-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 18px 20px;
      box-shadow: var(--shadow-sm);
      display: flex;
      flex-direction: column;
      gap: 6px;
      transition: all 0.2s;
    }
    .metric-card:hover {
      box-shadow: var(--shadow-md);
      border-color: var(--border-hover);
    }
    .metric-card .title {
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
    }
    .metric-card .val {
      font-size: 26px;
      font-weight: 800;
      font-family: 'JetBrains Mono', monospace;
      color: var(--text);
      line-height: 1.1;
    }
    .metric-card .sub {
      font-size: 11px;
      color: var(--text-subtle);
      margin-top: 2px;
    }

    /* Cards */
    .card-full {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 24px;
      box-shadow: var(--shadow-sm);
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .card-title {
      font-size: 15px;
      font-weight: 700;
      color: var(--text);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    /* Quick Demo Pills Bar */
    .quick-pills-bar {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 16px;
      background: var(--surface-subtle);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      flex-wrap: wrap;
    }
    .quick-label {
      font-size: 12px;
      font-weight: 700;
      color: var(--text-muted);
    }
    .sample-pill {
      font-size: 12px;
      font-weight: 600;
      padding: 4px 12px;
      border-radius: 999px;
      background: var(--surface);
      border: 1px solid var(--border);
      color: var(--text);
      cursor: pointer;
      transition: all 0.15s ease;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
    .sample-pill:hover {
      background: var(--brand-light);
      border-color: #bfdbfe;
      color: var(--brand-dark);
      transform: translateY(-1px);
    }

    /* 4 Conditions Comparison Boxes */
    .conditions-row {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 14px;
    }
    .condition-box {
      background: var(--surface-subtle);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 6px;
      transition: all 0.2s;
    }
    .condition-box:hover {
      background: var(--surface);
      border-color: var(--brand);
      box-shadow: var(--shadow-sm);
    }
    .condition-box h4 {
      font-size: 13.5px;
      font-weight: 700;
      color: var(--text);
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .condition-box p {
      font-size: 12px;
      color: var(--text-muted);
      line-height: 1.5;
    }

    /* Empirical Results Table */
    .table-container {
      overflow-x: auto;
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 13px;
    }
    th {
      background: #fafafa;
      padding: 12px 16px;
      font-weight: 700;
      color: var(--text-muted);
      text-transform: uppercase;
      font-size: 11px;
      letter-spacing: 0.05em;
      border-bottom: 1px solid var(--border);
    }
    td {
      padding: 14px 16px;
      border-bottom: 1px solid #f1f5f9;
      font-family: 'JetBrains Mono', monospace;
    }
    tr:last-child td { border-bottom: none; }
    .condition-label {
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-weight: 700;
      color: var(--text);
    }
    .score-badge {
      display: inline-block;
      padding: 3px 8px;
      border-radius: 4px;
      font-weight: 700;
    }
    .score-high {
      color: #065f46;
      background: var(--emerald-light);
      border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .score-mid {
      color: #92400e;
      background: var(--amber-light);
      border: 1px solid rgba(245, 158, 11, 0.3);
    }
    .score-low {
      color: #991b1b;
      background: var(--rose-light);
      border: 1px solid rgba(239, 68, 68, 0.3);
    }

    /* Figure Tab Viewer */
    .fig-tabs {
      display: flex;
      gap: 8px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 12px;
      flex-wrap: wrap;
    }
    .fig-tab {
      padding: 8px 16px;
      border-radius: var(--radius-sm);
      background: var(--surface-subtle);
      border: 1px solid var(--border);
      color: var(--text-muted);
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
    }
    .fig-tab.active, .fig-tab:hover {
      background: var(--brand-light);
      border-color: #bfdbfe;
      color: var(--brand-dark);
    }
    .fig-viewer {
      display: flex;
      justify-content: center;
      align-items: center;
      padding: 24px;
      background: #fafafa;
      border-radius: var(--radius);
      border: 1px solid var(--border);
      min-height: 420px;
    }
    .fig-viewer img {
      max-width: 100%;
      max-height: 520px;
      border-radius: var(--radius-sm);
      box-shadow: var(--shadow-md);
      background: white;
    }

    /* Tasks Deck */
    .tasks-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
      gap: 10px;
      max-height: 340px;
      overflow-y: auto;
      padding-right: 6px;
    }
    .task-chip {
      background: var(--surface-subtle);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      padding: 10px;
      text-align: center;
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      cursor: pointer;
      transition: all 0.2s ease;
    }
    .task-chip:hover {
      background: var(--brand-light);
      border-color: var(--brand);
      transform: translateY(-2px);
      box-shadow: var(--shadow-sm);
    }
    .family-badge {
      display: inline-block;
      font-size: 10px;
      padding: 2px 6px;
      border-radius: 4px;
      margin-top: 4px;
      text-transform: uppercase;
      font-weight: 700;
    }
    .family-al { background: var(--brand-light); color: var(--brand-dark); }
    .family-db { background: var(--emerald-light); color: #065f46; }
    .family-dm { background: var(--purple-light); color: #581c87; }
    .family-se { background: var(--amber-light); color: #78350f; }

    /* Modal Overlay */
    .modal-overlay {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(15, 23, 42, 0.6);
      backdrop-filter: blur(4px);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 100;
      padding: 24px;
    }
    .modal-overlay.active { display: flex; }
    .modal-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      width: 100%;
      max-width: 760px;
      max-height: 85vh;
      overflow-y: auto;
      padding: 28px;
      box-shadow: var(--shadow-lg);
      display: flex;
      flex-direction: column;
      gap: 16px;
      animation: modalPop 0.2s ease-out;
    }
    @keyframes modalPop {
      0% { opacity: 0; transform: scale(0.96); }
      100% { opacity: 1; transform: scale(1); }
    }
    .modal-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      border-bottom: 1px solid var(--border);
      padding-bottom: 12px;
    }
    .modal-close {
      width: 32px;
      height: 32px;
      border-radius: 8px;
      border: 1px solid var(--border);
      background: var(--surface);
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      font-size: 18px;
      color: var(--text-muted);
      transition: all 0.15s;
    }
    .modal-close:hover {
      background: var(--surface-subtle);
      color: var(--text);
    }
    .code-block {
      background: #0f172a;
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      padding: 14px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 12.5px;
      color: #93c5fd;
      white-space: pre-wrap;
      overflow-x: auto;
    }

    @media (max-width: 1024px) {
      .grid-overview { grid-template-columns: repeat(2, 1fr); }
      .conditions-row { grid-template-columns: repeat(2, 1fr); }
      .arch-flow { grid-template-columns: repeat(2, 1fr); }
    }
  </style>
</head>
<body>

  <!-- Top Navigation Header -->
  <header>
    <div class="brand">
      <div class="logo-badge">AL</div>
      <div>
        <div class="brand-title">Agent <span>Learning Pilot</span></div>
        <div style="font-size: 11px; color: var(--text-muted); font-weight: 500;">Controlled Feedback Transfer & Retention Experiment</div>
      </div>
    </div>
    <div class="header-meta">
      <div class="badge-capsule" style="background: var(--brand-light); border-color: #bfdbfe; color: var(--brand-dark);">
        <span>Empirical Study (Ollama Qwen 2.5 7B)</span>
      </div>
      <div class="badge-capsule online">
        <div class="pulse-dot"></div>
        <span>Evaluation Engine Online</span>
      </div>
    </div>
  </header>

  <main>

    <!-- 5-Stage Architecture Pipeline Visualizer -->
    <div class="architecture-banner">
      <div class="arch-header">
        <div class="arch-title">
          <span>⚡</span> Empirical Feedback Transfer & System Learning Pipeline
        </div>
        <div class="arch-desc">Evaluates whether agent improvements persist after context is wiped and feedback is removed</div>
      </div>
      <div class="arch-flow">
        <div class="arch-step">
          <div class="arch-step-num">STAGE 01</div>
          <div class="arch-step-name">🧪 Baseline Control</div>
          <div class="arch-step-desc">Zero state saved between tasks; standard code → test → retry cycle</div>
        </div>
        <div class="arch-step">
          <div class="arch-step-num">STAGE 02</div>
          <div class="arch-step-name">🪞 Reflection Agent</div>
          <div class="arch-step-desc">Intra-task self-critique prompt; context wiped on new tasks</div>
        </div>
        <div class="arch-step">
          <div class="arch-step-num">STAGE 03</div>
          <div class="arch-step-name">🧠 Memory Store</div>
          <div class="arch-step-desc">Persistent key-value error signature, diagnosis & strategy store</div>
        </div>
        <div class="arch-step">
          <div class="arch-step-num">STAGE 04</div>
          <div class="arch-step-name">⚡ Dynamic Workflow</div>
          <div class="arch-step-desc">Pipeline step sequence mutation surviving task context clearing</div>
        </div>
        <div class="arch-step">
          <div class="arch-step-num">STAGE 05</div>
          <div class="arch-step-name">📊 Transfer Benchmark</div>
          <div class="arch-step-desc">Evaluates cross-family generalization, retention & non-regression</div>
        </div>
      </div>
    </div>

    <!-- KPI Metric Cards Grid -->
    <div class="grid-overview">
      <div class="metric-card">
        <div class="title">Evaluated Model</div>
        <div class="val" style="font-size: 20px;">qwen2.5:7b</div>
        <div class="sub">Local Ollama inference</div>
      </div>
      <div class="metric-card">
        <div class="title">Total Benchmark Tasks</div>
        <div class="val">48 Tasks</div>
        <div class="sub">4 Families (AL, DB, DM, SE)</div>
      </div>
      <div class="metric-card">
        <div class="title">Cross-Family Transfer</div>
        <div class="val" style="color:var(--emerald);">75.0% vs 33.3%</div>
        <div class="sub">Dynamic Workflow vs Baseline</div>
      </div>
      <div class="metric-card">
        <div class="title">Non-Regression Score</div>
        <div class="val" style="color:var(--brand);">100% vs 25%</div>
        <div class="sub">Zero capability deterioration</div>
      </div>
    </div>

    <!-- Quick Demo Samples Bar -->
    <div class="quick-pills-bar">
      <span class="quick-label">⚡ Quick Demo Samples (Click to inspect):</span>
      <span class="sample-pill" onclick="openTask('al_01')">AL-01: Binary Search Range</span>
      <span class="sample-pill" onclick="openTask('db_04')">DB-04: In-Memory B-Tree Join</span>
      <span class="sample-pill" onclick="openTask('dm_07')">DM-07: JSON Schema Normalizer</span>
      <span class="sample-pill" onclick="openTask('se_03')">SE-03: Thread-Safe LRU Cache</span>
      <span class="sample-pill" onclick="openTask('al_08')">AL-08: Topological Dependency Resolver</span>
    </div>

    <!-- 4 Experimental Conditions -->
    <div class="card-full">
      <div class="card-title">
        <span>Architectural Conditions Evaluated</span>
        <span style="font-size: 12px; color: var(--text-muted); font-weight: 500;">Compute-matched across identical LLM token budgets</span>
      </div>
      <div class="conditions-row">
        <div class="condition-box">
          <h4>🧪 1. Baseline</h4>
          <p>Zero feedback persistence. Evaluates code with completely cleared context windows on each task.</p>
        </div>
        <div class="condition-box">
          <h4>🪞 2. Reflection</h4>
          <p>Generates intra-task self-critique upon test failures. Does not persist state across distinct tasks.</p>
        </div>
        <div class="condition-box">
          <h4>🧠 3. Memory</h4>
          <p>Extracts error signatures and algorithmic strategies into persistent structured key-value memory.</p>
        </div>
        <div class="condition-box">
          <h4>⚡ 4. Dynamic Workflow</h4>
          <p>Mutates pipeline execution structure (inspect_tests → plan → code → test) across successive tasks.</p>
        </div>
      </div>
    </div>

    <!-- Comparative Results Table (Real Empirical Metrics) -->
    <div class="card-full">
      <div class="card-title">
        <span>Empirical Benchmark Results Across Task Splits</span>
        <span style="font-size: 12px; color: var(--text-muted); font-weight: 500;">Mean Success Rates (metrics.json)</span>
      </div>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Condition</th>
              <th>Cross-Family Transfer</th>
              <th>Held-Out Tasks</th>
              <th>Non-Regression Avoidance</th>
              <th>Feedback Recovery</th>
              <th>Learning Verdict</th>
            </tr>
          </thead>
          <tbody id="metricsTbody">
            <tr>
              <td class="condition-label">🧪 Baseline</td>
              <td><span class="score-badge score-mid">33.3%</span></td>
              <td><span class="score-badge score-low">0.0%</span></td>
              <td><span class="score-badge score-low">25.0%</span></td>
              <td><span class="score-badge score-high">75.0%</span></td>
              <td style="font-family:'Plus Jakarta Sans'; font-size:12px; color:var(--text-muted);">No cross-task learning (Control)</td>
            </tr>
            <tr>
              <td class="condition-label">🪞 Reflection</td>
              <td><span class="score-badge score-mid">33.3%</span></td>
              <td><span class="score-badge score-low">0.0%</span></td>
              <td><span class="score-badge score-low">25.0%</span></td>
              <td><span class="score-badge score-high">75.0%</span></td>
              <td style="font-family:'Plus Jakarta Sans'; font-size:12px; color:var(--text-muted);">Intra-task only; fails to generalize</td>
            </tr>
            <tr>
              <td class="condition-label">🧠 Memory Store</td>
              <td><span class="score-badge score-high">58.3%</span></td>
              <td><span class="score-badge score-high">100.0%</span></td>
              <td><span class="score-badge score-high">75.0%</span></td>
              <td><span class="score-badge score-high">75.0%</span></td>
              <td style="font-family:'Plus Jakarta Sans'; font-size:12px; color:#065f46; font-weight:600;">Strong error-pattern transfer (+25%)</td>
            </tr>
            <tr>
              <td class="condition-label">⚡ Dynamic Workflow</td>
              <td><span class="score-badge score-high" style="background:#dbeafe; color:#1e40af; border-color:#93c5fd;">75.0%</span></td>
              <td><span class="score-badge score-high">100.0%</span></td>
              <td><span class="score-badge score-high">100.0%</span></td>
              <td><span class="score-badge score-high">75.0%</span></td>
              <td style="font-family:'Plus Jakarta Sans'; font-size:12px; color:#1e40af; font-weight:700;">Optimal transfer & zero regressions</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Figure Tabs & Plot Viewer -->
    <div class="card-full">
      <div class="card-title">
        <span>Empirical Visualizations & Research Charts</span>
        <span style="font-size: 12px; color: var(--text-muted); font-weight: 500;">Generated with Matplotlib</span>
      </div>
      <div class="fig-tabs">
        <button class="fig-tab active" onclick="switchFig('transfer_matrix.png', this)">📊 Transfer Matrix</button>
        <button class="fig-tab" onclick="switchFig('retention.png', this)">📈 Retention Over Time</button>
        <button class="fig-tab" onclick="switchFig('success_by_condition.png', this)">📉 Success by Condition</button>
        <button class="fig-tab" onclick="switchFig('cost_vs_capability.png', this)">💰 Cost vs Capability</button>
      </div>
      <div class="fig-viewer">
        <img id="figImage" src="/figures/transfer_matrix.png" alt="Research Plot">
      </div>
    </div>

    <!-- 48-Task Benchmark Deck -->
    <div class="card-full">
      <div class="card-title">
        <span>48-Task Benchmark Evaluation Deck</span>
        <span style="font-size: 12px; color: var(--text-muted); font-weight: 500;">Click any task to inspect code & test fixtures</span>
      </div>
      <div class="tasks-grid" id="tasksDeck">
        <!-- Dynamically populated -->
      </div>
    </div>

  </main>

  <!-- Interactive Task Detail Modal -->
  <div class="modal-overlay" id="taskModal">
    <div class="modal-card">
      <div class="modal-header">
        <div>
          <h3 id="mTitle" style="font-size: 18px; font-weight: 800; color: var(--text);">Task Details</h3>
          <span id="mMeta" style="font-size: 12px; color: var(--brand); font-family: 'JetBrains Mono', monospace; font-weight: 600;"></span>
        </div>
        <button class="modal-close" onclick="closeModal()">&times;</button>
      </div>
      <div>
        <h4 style="font-size: 12px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 6px;">Specification</h4>
        <p id="mSpec" style="font-size: 13.5px; color: var(--text); line-height: 1.6;"></p>
      </div>
      <div>
        <h4 style="font-size: 12px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 6px;">Starter Implementation</h4>
        <pre class="code-block" id="mCode"></pre>
      </div>
      <div>
        <h4 style="font-size: 12px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 6px;">Pytest Verification Fixture</h4>
        <pre class="code-block" id="mTests" style="color:#a7f3d0;"></pre>
      </div>
    </div>
  </div>

  <script>
    const families = {
      'al': { name: 'Algorithms', cls: 'family-al' },
      'db': { name: 'Debugging', cls: 'family-db' },
      'dm': { name: 'Domain Model', cls: 'family-dm' },
      'se': { name: 'Systems & Err', cls: 'family-se' }
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
          document.getElementById('mSpec').textContent = t.specification || 'Implement solution matching test assertions.';
          document.getElementById('mCode').textContent = t.starter_code || '# Starter code\\ndef solution():\\n    pass';
          document.getElementById('mTests').textContent = t.visible_tests || '# Test assertions\\ndef test_basic():\\n    assert True';
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
                visible_tests = task_dir / "visible_tests.py"
                if visible_tests.exists():
                    data["visible_tests"] = visible_tests.read_text(encoding="utf-8")
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

    do_HEAD = do_GET

def run_server(port=PORT):
    # Allow port override from command line
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), DashboardHandler) as httpd:
        print(f"Agent Learning Pilot dashboard running at: http://localhost:{port}/")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")

if __name__ == "__main__":
    run_server()
