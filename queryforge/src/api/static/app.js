// QueryForge Dashboard App Logic

document.addEventListener('DOMContentLoaded', () => {
  // Constants
  const API_BASE = window.location.origin;

  // DOM Elements
  const statusApi = document.getElementById('status-api');
  const statusDb = document.getElementById('status-db');
  const statusCache = document.getElementById('status-cache');
  const toolsCount = document.getElementById('tools-count');
  const toolsList = document.getElementById('tools-list');
  const btnClearCache = document.getElementById('btnClearCache');
  
  // PDF
  const pdfDropZone = document.getElementById('pdf-drop-zone');
  const pdfFileInput = document.getElementById('pdf-file-input');
  const pdfResultCard = document.getElementById('pdf-result-card');
  const pdfFilename = document.getElementById('pdf-filename');
  const pdfPages = document.getElementById('pdf-pages');
  const pdfSummaryText = document.getElementById('pdf-summary-text');
  const pdfBulletsList = document.getElementById('pdf-bullets-list');
  const pdfTokens = document.getElementById('pdf-tokens');

  // Query
  const queryInput = document.getElementById('query-input');
  const btnRunQuery = document.getElementById('btn-run-query');
  const btnExamples = document.querySelectorAll('.btn-example');
  
  // Pipeline/Stepper
  const pipelineCard = document.getElementById('pipeline-card');
  const pipelineStatusText = document.getElementById('pipeline-status-text');
  const pipelineSteps = document.getElementById('pipeline-steps');

  // Response
  const responseCard = document.getElementById('response-card');
  const responseAnswer = document.getElementById('response-answer');
  const responseSources = document.getElementById('response-sources');
  const latencyBadge = document.getElementById('latency-badge');

  // Charts
  const chartsCard = document.getElementById('charts-card');
  const chartsGallery = document.getElementById('charts-gallery');

  // Dialog
  const dialogNotification = document.getElementById('dialog-notification');
  const dialogTitle = document.getElementById('dialog-title');
  const dialogMessage = document.getElementById('dialog-message');

  // Initial State Load
  updateSystemHealth();
  updateToolRegistry();

  // Health Polling - 10s intervals
  setInterval(updateSystemHealth, 10000);

  // Example Queries Click
  btnExamples.forEach(btn => {
    btn.addEventListener('click', () => {
      queryInput.value = btn.textContent;
      queryInput.focus();
    });
  });

  // Dialog Helper
  function showNotification(title, message) {
    dialogTitle.textContent = title;
    dialogMessage.textContent = message;
    dialogNotification.showModal();
  }

  // API Call - Health
  async function updateSystemHealth() {
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (!res.ok) throw new Error('API degraded');
      const data = await res.json();
      
      // Update API
      statusApi.className = 'status-indicator ok';
      
      // Update DB
      statusDb.className = data.db ? 'status-indicator ok' : 'status-indicator offline';
      
      // Update Cache (Redis/Dragonfly)
      statusCache.className = data.dragonfly ? 'status-indicator ok' : 'status-indicator degraded';
    } catch (e) {
      statusApi.className = 'status-indicator offline';
      statusDb.className = 'status-indicator offline';
      statusCache.className = 'status-indicator offline';
    }
  }

  // API Call - Tool Registry & Stats
  async function updateToolRegistry() {
    try {
      const [toolsRes, statsRes] = await Promise.all([
        fetch(`${API_BASE}/tools`),
        fetch(`${API_BASE}/tool-stats`)
      ]);
      
      if (!toolsRes.ok) throw new Error('Failed to load tools');
      const tools = await toolsRes.json();
      const stats = statsRes.ok ? await statsRes.json() : {};

      toolsCount.textContent = tools.length;
      toolsList.innerHTML = '';

      if (tools.length === 0) {
        toolsList.innerHTML = '<div class="tool-desc">No tools registered.</div>';
        return;
      }

      tools.forEach(tool => {
        const calls = stats[tool.name] || 0;
        const div = document.createElement('div');
        div.className = 'tool-item';
        div.innerHTML = `
          <div class="tool-item-info">
            <span class="tool-name" title="${tool.name}">${tool.name}</span>
            <span class="tool-desc" title="${tool.description}">${tool.description}</span>
          </div>
          <span class="tool-calls-count">${calls} calls</span>
        `;
        toolsList.appendChild(div);
      });
    } catch (e) {
      toolsList.innerHTML = `<div class="tool-desc" style="color:var(--color-primary)">Error loading registry: ${e.message}</div>`;
    }
  }

  // Clear Cache Action
  const btnClearCacheElement = document.getElementById('btn-clear-cache');
  if (btnClearCacheElement) {
    btnClearCacheElement.addEventListener('click', async () => {
      try {
        const res = await fetch(`${API_BASE}/cache/clear`);
        if (!res.ok) throw new Error('Failed to clear cache');
        const data = await res.json();
        showNotification('Cache Cleared', `Successfully cleared cache. ${data.cleared_count || 0} response keys deleted.`);
      } catch (e) {
        showNotification('Error', e.message);
      }
    });
  }

  // PDF Ingestion - File Select Dialog
  pdfDropZone.addEventListener('click', () => {
    pdfFileInput.click();
  });

  pdfFileInput.addEventListener('change', () => {
    if (pdfFileInput.files.length > 0) {
      handlePdfUpload(pdfFileInput.files[0]);
    }
  });

  // PDF Ingestion - Drag and Drop
  pdfDropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    pdfDropZone.classList.add('dragover');
  });

  pdfDropZone.addEventListener('dragleave', () => {
    pdfDropZone.classList.remove('dragover');
  });

  pdfDropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    pdfDropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      if (file.type === 'application/pdf') {
        handlePdfUpload(file);
      } else {
        showNotification('Invalid File', 'Only PDF files are supported for ingestion.');
      }
    }
  });

  // Handle PDF Ingest API
  async function handlePdfUpload(file) {
    pdfResultCard.classList.remove('hidden');
    pdfFilename.textContent = file.name;
    pdfPages.className = 'badge badge-yellow';
    pdfPages.textContent = 'Uploading...';
    pdfSummaryText.textContent = 'Sending document to analysis engine...';
    pdfBulletsList.innerHTML = '';
    pdfTokens.textContent = '0';

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${API_BASE}/ingest-pdf`, {
        method: 'POST',
        body: formData
      });

      if (!res.ok) throw new Error('PDF analysis failure');
      const summary = await res.json();

      pdfPages.textContent = `${summary.page_count} pages`;
      pdfSummaryText.textContent = summary.summary;
      pdfTokens.textContent = summary.tokens_used;

      pdfBulletsList.innerHTML = '';
      summary.key_points.forEach(point => {
        const li = document.createElement('li');
        li.textContent = point;
        pdfBulletsList.appendChild(li);
      });
    } catch (e) {
      pdfPages.className = 'badge badge-red';
      pdfPages.textContent = 'Failed';
      pdfSummaryText.textContent = `Error: ${e.message}. Check that the PDF file is valid and the server is running.`;
    }
  }

  // Run Query Action
  btnRunQuery.addEventListener('click', async () => {
    const query = queryInput.value.trim();
    if (!query) return;

    // Reset Workspace Elements
    pipelineCard.classList.remove('hidden');
    responseCard.classList.add('hidden');
    chartsCard.classList.add('hidden');

    btnRunQuery.disabled = true;
    btnRunQuery.innerHTML = `FORGING... <span class="btn-icon-right">⎋</span>`;

    // 1. Simulate initial thinking steps
    pipelineStatusText.textContent = 'Planning execution sequence...';
    pipelineSteps.innerHTML = `
      <div class="timeline-item active" id="step-plan">
        <div class="timeline-dot"></div>
        <div class="timeline-title">
          <span>Agent Planning Sequence</span>
          <span class="timeline-meta">Active</span>
        </div>
        <div class="timeline-desc">Analyzing request semantic intentions and mapping tool dependencies...</div>
      </div>
      <div class="timeline-item" id="step-exec">
        <div class="timeline-dot"></div>
        <div class="timeline-title">
          <span>Tool Execution Pipeline</span>
          <span class="timeline-meta">Pending</span>
        </div>
        <div class="timeline-desc">Awaiting plan orchestration...</div>
      </div>
      <div class="timeline-item" id="step-synth">
        <div class="timeline-dot"></div>
        <div class="timeline-title">
          <span>Ollama Response Synthesis</span>
          <span class="timeline-meta">Pending</span>
        </div>
        <div class="timeline-desc">Awaiting findings synthesis...</div>
      </div>
    `;

    // Timeline simulated transitions
    const planTimer = setTimeout(() => {
      const stepPlan = document.getElementById('step-plan');
      if (stepPlan) {
        stepPlan.className = 'timeline-item success';
        stepPlan.querySelector('.timeline-meta').textContent = 'Completed';
      }
      
      const stepExec = document.getElementById('step-exec');
      if (stepExec) {
        stepExec.className = 'timeline-item active';
        stepExec.querySelector('.timeline-meta').textContent = 'Active';
        stepExec.querySelector('.timeline-desc').textContent = 'Executing planned tools in dependency order...';
      }
      pipelineStatusText.textContent = 'Running database & SaaS metrics tools...';
    }, 1500);

    const execTimer = setTimeout(() => {
      const stepExec = document.getElementById('step-exec');
      if (stepExec) {
        stepExec.className = 'timeline-item success';
        stepExec.querySelector('.timeline-meta').textContent = 'Completed';
      }
      
      const stepSynth = document.getElementById('step-synth');
      if (stepSynth) {
        stepSynth.className = 'timeline-item active';
        stepSynth.querySelector('.timeline-meta').textContent = 'Active';
        stepSynth.querySelector('.timeline-desc').textContent = 'Compiling key findings and formatting final answers...';
      }
      pipelineStatusText.textContent = 'Synthesizing final findings...';
    }, 4500);

    try {
      const res = await fetch(`${API_BASE}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query })
      });

      // Clear simulated timers
      clearTimeout(planTimer);
      clearTimeout(execTimer);

      if (!res.ok) throw new Error('Agent execution returned error');
      const response = await res.json();

      // Render actual tool timeline
      pipelineStatusText.textContent = 'Execution sequence complete';
      pipelineSteps.innerHTML = '';

      if (response.tool_calls.length === 0) {
        pipelineSteps.innerHTML = `
          <div class="timeline-item success">
            <div class="timeline-dot"></div>
            <div class="timeline-title">
              <span>Direct Answer Synthesis</span>
              <span class="timeline-meta">No tools required</span>
            </div>
            <div class="timeline-desc">The query was resolved directly by Ollama without executing database/API tools.</div>
          </div>
        `;
      } else {
        response.tool_calls.forEach((call, index) => {
          const item = document.createElement('div');
          const isSuccess = call.output.success;
          item.className = `timeline-item ${isSuccess ? 'success' : 'failed'}`;
          
          let detailsHtml = '';
          if (call.input.arguments && Object.keys(call.input.arguments).length > 0) {
            detailsHtml += `<div><strong>Args:</strong> <code>${JSON.stringify(call.input.arguments)}</code></div>`;
          }
          if (isSuccess && call.output.result) {
            let resPreview = '';
            if (typeof call.output.result === 'object') {
              resPreview = JSON.stringify(call.output.result);
            } else {
              resPreview = String(call.output.result);
            }
            if (resPreview.length > 200) resPreview = resPreview.substring(0, 200) + '...';
            detailsHtml += `<div><strong>Output:</strong> <code>${resPreview}</code></div>`;
          } else if (call.output.error) {
            detailsHtml += `<div style="color:var(--color-primary)"><strong>Error:</strong> ${call.output.error}</div>`;
          }

          item.innerHTML = `
            <div class="timeline-dot"></div>
            <div class="timeline-title">
              <span>Step ${index + 1}: ${call.input.tool_name}</span>
              <span class="timeline-meta" style="color:${isSuccess ? 'var(--color-primary)' : 'var(--color-yellow)'}">
                ${isSuccess ? 'SUCCESS' : 'FAILED'} (${call.output.latency_ms}ms)
              </span>
            </div>
            <div class="timeline-desc">Context: ${call.input.caller_context}</div>
            <div class="timeline-details">${detailsHtml}</div>
          `;
          pipelineSteps.appendChild(item);
        });
      }

      // Render Synthesized Response
      responseCard.classList.remove('hidden');
      latencyBadge.textContent = `${(response.total_latency_ms / 1000).toFixed(2)}s`;
      responseAnswer.innerHTML = renderSimpleMarkdown(response.answer);

      // Render Sources List
      responseSources.innerHTML = '';
      if (response.sources.length > 0) {
        response.sources.forEach(src => {
          const li = document.createElement('li');
          li.textContent = src;
          responseSources.appendChild(li);
        });
      } else {
        responseSources.innerHTML = '<li>No specific external database or web sources cited.</li>';
      }

      // Render Charts Gallery
      if (response.chart_paths && response.chart_paths.length > 0) {
        chartsCard.classList.remove('hidden');
        chartsGallery.innerHTML = '';
        
        response.chart_paths.forEach(path => {
          // Extract filename (split on / or \)
          const filename = path.replace(/\\/g, '/').split('/').pop();
          
          const container = document.createElement('div');
          container.className = 'chart-container';
          container.innerHTML = `
            <span class="chart-title">📊 ${filename}</span>
            <img src="${API_BASE}/charts/${filename}" alt="QueryForge Chart: ${filename}" class="chart-image">
          `;
          chartsGallery.appendChild(container);
        });
      }

      // Reload Tool stats list count
      updateToolRegistry();

    } catch (e) {
      clearTimeout(planTimer);
      clearTimeout(execTimer);
      pipelineStatusText.textContent = 'Execution failed';
      pipelineSteps.innerHTML = `
        <div class="timeline-item failed">
          <div class="timeline-dot"></div>
          <div class="timeline-title">
            <span>Query Engine Crash</span>
            <span class="timeline-meta" style="color:var(--color-primary)">ERROR</span>
          </div>
          <div class="timeline-desc">${e.message}</div>
        </div>
      `;
    } finally {
      btnRunQuery.disabled = false;
      btnRunQuery.innerHTML = `FORGE QUERY <span class="btn-icon-right">➔</span>`;
    }
  });

  // Simple Regex-based Markdown Parser
  function renderSimpleMarkdown(text) {
    if (!text) return '';
    let html = text;

    // Convert Windows line breaks
    html = html.replace(/\r\n/g, '\n');

    // 1. Headers (### Header)
    html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');

    // 2. Bold (**text**)
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // 3. Inline code (`code`)
    html = html.replace(/`(.*?)`/g, '<code>$1</code>');

    // 4. Blockquotes
    html = html.replace(/^\> (.*$)/gim, '<blockquote>$1</blockquote>');

    // 5. Code blocks (```code```)
    html = html.replace(/```([\s\S]*?)```/g, '<pre>$1</pre>');

    // 6. Tables (| col | col |)
    // Detect markdown tables and convert to html tables
    const lines = html.split('\n');
    let inTable = false;
    let tableHtml = '';
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      if (line.startsWith('|') && line.endsWith('|')) {
        // Skip separator row (e.g. |---|---|)
        if (line.includes('---') || line.includes('-:-')) {
          continue;
        }
        
        if (!inTable) {
          inTable = true;
          tableHtml += '<table>';
        }
        
        const cells = line.split('|').slice(1, -1).map(c => c.trim());
        const rowType = tableHtml.includes('<thead>') ? 'td' : 'th';
        
        if (rowType === 'th') {
          tableHtml += '<thead><tr>';
          cells.forEach(cell => {
            tableHtml += `<th>${cell}</th>`;
          });
          tableHtml += '</tr></thead><tbody>';
        } else {
          tableHtml += '<tr>';
          cells.forEach(cell => {
            tableHtml += `<td>${cell}</td>`;
          });
          tableHtml += '</tr>';
        }
      } else {
        if (inTable) {
          inTable = false;
          tableHtml += '</tbody></table>';
          // Replace original markdown lines with reconstructed table html
          // We find where the table started and replace lines
          lines[i - 1] = tableHtml + '\n' + lines[i - 1];
          tableHtml = '';
        }
      }
    }
    
    // In case table ends at the very last line
    if (inTable) {
      tableHtml += '</tbody></table>';
      lines[lines.length - 1] += '\n' + tableHtml;
    }
    
    html = lines.join('\n');

    // Remove empty paragraphs
    html = html.replace(/\n\n/g, '<br>');

    return html;
  }
});
