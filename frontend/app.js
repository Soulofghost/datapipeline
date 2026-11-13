// DataPipeline — Automated ETL Framework Frontend Engine
const API_BASE = '/api/v1';

let activePipelines = [];
let selectedPipelineId = null;

// DOM Elements
const statPipelines = document.getElementById('statPipelines');
const statRuns = document.getElementById('statRuns');
const statRows = document.getElementById('statRows');
const statQuality = document.getElementById('statQuality');
const statDuration = document.getElementById('statDuration');
const pipelineContainer = document.getElementById('pipelineContainer');
const runDetailsContainer = document.getElementById('runDetailsContainer');
const warehouseContainer = document.getElementById('warehouseContainer');
const latestRunStatus = document.getElementById('latestRunStatus');
const sandboxInput = document.getElementById('sandboxInput');
const sandboxOutput = document.getElementById('sandboxOutput');
const sandboxExecuteBtn = document.getElementById('sandboxExecuteBtn');
const refreshSummaryBtn = document.getElementById('refreshSummaryBtn');
const newPipelineForm = document.getElementById('newPipelineForm');
const addPipelinePanel = document.getElementById('addPipelinePanel');

// Tab Switching
document.querySelectorAll('.tab-btn').forEach(button => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

    button.classList.add('active');
    const tabId = button.getAttribute('data-tab');
    document.getElementById(tabId).classList.add('active');

    if (tabId === 'warehouseTab') {
      fetchWarehouseRecords();
    }
  });
});

function toggleAddPipelineModal() {
  if (addPipelinePanel) {
    addPipelinePanel.classList.toggle('hidden');
  }
}

// Format numbers
function formatNum(n) {
  return new Intl.NumberFormat().format(n || 0);
}

// Fetch System Telemetry Summary
async function fetchSystemSummary() {
  try {
    const res = await fetch(`${API_BASE}/warehouse/summary`);
    if (!res.ok) throw new Error('Failed to fetch summary');
    const data = await res.json();

    if (statPipelines) statPipelines.textContent = data.total_pipelines;
    if (statRuns) statRuns.textContent = formatNum(data.lifetime_runs);
    if (statRows) statRows.textContent = formatNum(data.total_rows_processed);
    if (statQuality) statQuality.textContent = `${data.average_quality_score.toFixed(1)}%`;
    if (statDuration) statDuration.textContent = `${data.average_execution_time_ms.toFixed(2)} ms`;
  } catch (err) {
    console.error('Error fetching summary:', err);
  }
}

// Fetch Pipelines
async function fetchPipelines() {
  try {
    const res = await fetch(`${API_BASE}/pipelines`);
    if (!res.ok) throw new Error('Failed to fetch pipelines');
    activePipelines = await res.json();
    renderPipelines();
    if (!selectedPipelineId && activePipelines.length > 0) {
      selectPipeline(activePipelines[0].id);
    }
  } catch (err) {
    console.error('Error loading pipelines:', err);
    pipelineContainer.innerHTML = `<div class="empty-state">Unable to load pipelines. Ensure backend is running.</div>`;
  }
}

function renderPipelines() {
  if (!activePipelines || activePipelines.length === 0) {
    pipelineContainer.innerHTML = `<div class="empty-state">No pipelines registered. Click '+ Create Pipeline' to configure one.</div>`;
    return;
  }

  pipelineContainer.innerHTML = activePipelines.map(pipe => {
    const isSelected = pipe.id === selectedPipelineId;
    return `
      <div class="pipeline-card ${isSelected ? 'active' : ''}" onclick="selectPipeline('${pipe.id}')">
        <div class="pipe-header">
          <span class="pipe-name">${escapeHtml(pipe.name)}</span>
          <span class="pipe-source-badge">${pipe.source_type}</span>
        </div>
        <p class="pipe-desc">${escapeHtml(pipe.description)}</p>
        <div class="pipe-meta">
          <span>Target: <code>${escapeHtml(pipe.target_table)}</code></span>
          <span>Dedup Key: <code>${escapeHtml(pipe.config?.dedup_key || 'None')}</code></span>
        </div>
        <div class="pipe-actions">
          <button class="btn btn-sm btn-primary" onclick="event.stopPropagation(); triggerPipelineRun('${pipe.id}')">
            Execute Pipeline
          </button>
        </div>
      </div>
    `;
  }).join('');
}

function selectPipeline(id) {
  selectedPipelineId = id;
  renderPipelines();
  fetchPipelineRuns(id);
}

// Fetch historical runs for selected pipeline
async function fetchPipelineRuns(pipeId) {
  try {
    const res = await fetch(`${API_BASE}/pipelines/${pipeId}/runs`);
    if (!res.ok) throw new Error('Failed to fetch runs');
    const runs = await res.json();
    renderRunsView(runs);
  } catch (err) {
    console.error('Error fetching runs:', err);
  }
}

function renderRunsView(runs) {
  if (!runs || runs.length === 0) {
    runDetailsContainer.innerHTML = `
      <div class="empty-state">
        <p>No executions logged yet for pipeline <code>${escapeHtml(selectedPipelineId)}</code>.</p>
        <p>Click "Execute Pipeline" to trigger the ETL transform.</p>
      </div>
    `;
    latestRunStatus.textContent = "Awaiting Trigger";
    latestRunStatus.className = "status-pill";
    return;
  }

  const latest = runs[0];
  latestRunStatus.textContent = latest.status;
  latestRunStatus.className = `status-pill status-${latest.status.toLowerCase()}`;

  const runCardsHtml = runs.slice(0, 5).map(r => `
    <div class="run-item">
      <div class="run-row-head">
        <span class="run-id font-mono">${r.id}</span>
        <span class="run-date">${new Date(r.created_at).toLocaleTimeString()}</span>
      </div>
      <div class="run-metrics">
        <span>In: <strong>${r.input_count}</strong></span>
        <span>Out: <strong>${r.output_count}</strong></span>
        <span>Filtered: <strong>${r.filtered_count}</strong></span>
        <span>Duration: <strong>${r.execution_time_ms.toFixed(2)} ms</strong></span>
        <span>Quality: <strong class="text-gold">${r.quality_score.toFixed(1)}%</strong></span>
      </div>
    </div>
  `).join('');

  runDetailsContainer.innerHTML = `
    <div class="run-summary-box">
      <div class="summary-stat-row">
        <div>
          <span class="lbl">Last Execution</span>
          <span class="val font-mono">${latest.id}</span>
        </div>
        <div>
          <span class="lbl">Throughput Status</span>
          <span class="val text-emerald">${latest.output_count} Records Processed</span>
        </div>
        <div>
          <span class="lbl">Quality Score</span>
          <span class="val text-gold">${latest.quality_score.toFixed(1)}%</span>
        </div>
      </div>
    </div>

    <h4 style="margin-top:1.5rem; margin-bottom:0.75rem; color:var(--text-muted); font-size:0.75rem; text-transform:uppercase;">
      Recent Execution History
    </h4>
    <div class="runs-history-list">
      ${runCardsHtml}
    </div>
  `;
}

// Trigger Pipeline Run
async function triggerPipelineRun(pipelineId) {
  latestRunStatus.textContent = "EXECUTING...";
  latestRunStatus.className = "status-pill status-running";

  try {
    const res = await fetch(`${API_BASE}/pipelines/${pipelineId}/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ records: [] })
    });

    if (!res.ok) throw new Error('Pipeline execution failed');
    const result = await res.json();

    latestRunStatus.textContent = result.status;
    latestRunStatus.className = `status-pill status-completed`;

    // Render diagnostic breakdown with samples
    renderExecutionDiagnostic(result);

    // Refresh telemetry counters
    fetchSystemSummary();
  } catch (err) {
    console.error('Pipeline run error:', err);
    latestRunStatus.textContent = "FAILED";
    latestRunStatus.className = "status-pill status-failed";
    alert(`Execution failed: ${err.message}`);
  }
}

function renderExecutionDiagnostic(result) {
  const sampleRecordsJson = JSON.stringify(result.sample_records, null, 2);

  runDetailsContainer.innerHTML = `
    <div class="run-execution-banner">
      <div class="metric-ribbon">
        <div class="ribbon-col">
          <span class="r-lbl">Input Rows</span>
          <span class="r-val">${result.input_count}</span>
        </div>
        <div class="ribbon-col">
          <span class="r-lbl">Output Rows</span>
          <span class="r-val text-emerald">${result.output_count}</span>
        </div>
        <div class="ribbon-col">
          <span class="r-lbl">Dedup / Filtered</span>
          <span class="r-val text-coral">${result.filtered_count}</span>
        </div>
        <div class="ribbon-col">
          <span class="r-lbl">Latency</span>
          <span class="r-val text-purple">${result.execution_time_ms.toFixed(2)} ms</span>
        </div>
        <div class="ribbon-col">
          <span class="r-lbl">Throughput</span>
          <span class="r-val text-cyan">${result.throughput_rows_per_sec.toFixed(0)} rps</span>
        </div>
        <div class="ribbon-col">
          <span class="r-lbl">Quality Score</span>
          <span class="r-val text-gold">${result.quality_score.toFixed(1)}%</span>
        </div>
      </div>
    </div>

    <div class="quality-profile-panel">
      <h3>Data Quality Profiler</h3>
      <div class="quality-grid">
        <div class="q-cell">
          <span class="q-title">Null Values Detected</span>
          <span class="q-num">${result.quality_profile.null_counts}</span>
        </div>
        <div class="q-cell">
          <span class="q-title">Duplicates Dropped</span>
          <span class="q-num">${result.quality_profile.duplicates_dropped}</span>
        </div>
        <div class="q-cell">
          <span class="q-title">Fields Profiled</span>
          <span class="q-num">${result.quality_profile.fields_profiled.length}</span>
        </div>
      </div>
    </div>

    <div class="sample-records-panel">
      <h3>Transformed &amp; Loaded Warehouse Records (Sample)</h3>
      <pre class="code-box">${escapeHtml(sampleRecordsJson)}</pre>
    </div>
  `;
}

// Fetch Warehouse Records
async function fetchWarehouseRecords() {
  if (!warehouseContainer) return;
  warehouseContainer.innerHTML = '<div class="empty-state">Querying warehouse lake...</div>';

  try {
    const res = await fetch(`${API_BASE}/warehouse/records?limit=25`);
    if (!res.ok) throw new Error('Failed to load warehouse data');
    const records = await res.json();

    if (!records || records.length === 0) {
      warehouseContainer.innerHTML = '<div class="empty-state">No records found in warehouse. Execute an ETL pipeline to load records.</div>';
      return;
    }

    warehouseContainer.innerHTML = `
      <table class="wh-table">
        <thead>
          <tr>
            <th>Warehouse ID</th>
            <th>Pipeline</th>
            <th>Ingested At</th>
            <th>Normalized Payload</th>
          </tr>
        </thead>
        <tbody>
          ${records.map(r => `
            <tr>
              <td class="font-mono text-cyan">${r.id}</td>
              <td class="font-mono">${r.pipeline_id}</td>
              <td>${new Date(r.created_at).toLocaleTimeString()}</td>
              <td><pre class="inline-json">${escapeHtml(JSON.stringify(r.data))}</pre></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } catch (err) {
    console.error('Error fetching warehouse records:', err);
    warehouseContainer.innerHTML = `<div class="empty-state text-coral">Error querying warehouse: ${err.message}</div>`;
  }
}

// Sandbox Execution
if (sandboxExecuteBtn) {
  sandboxExecuteBtn.addEventListener('click', async () => {
    const rawText = sandboxInput.value.trim();
    if (!rawText) {
      alert('Please provide JSON records in the sandbox input.');
      return;
    }

    let records;
    try {
      records = JSON.parse(rawText);
      if (!Array.isArray(records)) {
        throw new Error('Input must be a JSON array of objects.');
      }
    } catch (e) {
      alert(`Invalid JSON format: ${e.message}`);
      return;
    }

    sandboxExecuteBtn.disabled = true;
    sandboxExecuteBtn.textContent = 'Executing Transform...';

    try {
      const targetPipeId = selectedPipelineId || (activePipelines[0] ? activePipelines[0].id : null);
      if (!targetPipeId) {
        alert('No pipeline selected for execution.');
        return;
      }

      const res = await fetch(`${API_BASE}/pipelines/${targetPipeId}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ records })
      });

      if (!res.ok) throw new Error('Sandbox run failed');
      const data = await res.json();

      sandboxOutput.textContent = JSON.stringify({
        status: data.status,
        input_count: data.input_count,
        output_count: data.output_count,
        filtered_count: data.filtered_count,
        execution_time_ms: data.execution_time_ms,
        quality_score: data.quality_score,
        sample_transformed: data.sample_records
      }, null, 2);

      fetchSystemSummary();
    } catch (err) {
      sandboxOutput.textContent = `Error: ${err.message}`;
    } finally {
      sandboxExecuteBtn.disabled = false;
      sandboxExecuteBtn.textContent = 'Run Ingestion Transform';
    }
  });
}

// Create Pipeline Form Handler
if (newPipelineForm) {
  newPipelineForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const name = document.getElementById('pipeName').value.trim();
    const description = document.getElementById('pipeDesc').value.trim();
    const source_type = document.getElementById('pipeSource').value;
    const target_table = document.getElementById('pipeTarget').value.trim();
    const dedup_key = document.getElementById('pipeDedup').value.trim();
    const maskRaw = document.getElementById('pipeMask').value.trim();

    const pii_mask_fields = maskRaw ? maskRaw.split(',').map(s => s.trim()).filter(Boolean) : [];

    const payload = {
      name,
      description,
      source_type,
      target_table,
      config: {
        dedup_key: dedup_key || null,
        drop_null_fields: dedup_key ? [dedup_key] : [],
        pii_mask_fields: pii_mask_fields,
        derive_fields: {}
      }
    };

    try {
      const res = await fetch(`${API_BASE}/pipelines`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) throw new Error('Failed to create pipeline');
      const created = await res.json();

      newPipelineForm.reset();
      toggleAddPipelineModal();
      await fetchPipelines();
      selectPipeline(created.id);
      fetchSystemSummary();
    } catch (err) {
      alert(`Error creating pipeline: ${err.message}`);
    }
  });
}

if (refreshSummaryBtn) {
  refreshSummaryBtn.addEventListener('click', () => {
    fetchSystemSummary();
    if (selectedPipelineId) fetchPipelineRuns(selectedPipelineId);
  });
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Initialize on load
fetchSystemSummary();
fetchPipelines();
