// AeroSynthX modern UI
(() => {
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  const runsState = { offset: 0, limit: 10, total: 0 };
  let searchTimeout = null;
  let xfoilChart = null;

  // --- API & State Management ---
  const apiKeyInput = $("#api-key");
  apiKeyInput.value = localStorage.getItem("aerosynthx_api_key") || "";
  apiKeyInput.addEventListener("input", (e) => localStorage.setItem("aerosynthx_api_key", e.target.value.trim()));

  function getHeaders() {
    const headers = { "Content-Type": "application/json" };
    const key = apiKeyInput.value.trim();
    if (key) headers["X-API-Key"] = key;
    return headers;
  }

  async function apiCall(url, options = {}) {
    const r = await fetch(url, { headers: getHeaders(), ...options });
    if (!r.ok) {
      if (r.status === 401) throw new Error("Unauthorized (Check API Key)");
      try {
        const err = await r.json();
        throw new Error(err.detail.message || JSON.stringify(err.detail));
      } catch {
        throw new Error(`${r.status} ${r.statusText}`);
      }
    }
    return r.json();
  }

  // --- UI Rendering ---
  function renderResult(result) {
    $("#result-panel").hidden = false;
    $("#result-summary").innerHTML = `
      <p><strong>Run ID:</strong> <code>${result.run_id}</code></p>
      <p><strong>Status:</strong> <span class="status-${result.status}">${result.status}</span></p>
      ${result.case_dir ? `<p><strong>Case:</strong> <code>${result.case_dir}</code></p>` : ""}
      ${result.status === "completed" ? `<p><a href="/api/v1/runs/${result.run_id}/report" target="_blank">Download Report</a></p>` : ""}
    `;
    renderStages(result.stages);
    renderFiles(result);
    renderXfoilResults(result);
  }

  function renderStages(stages) {
    const tbody = $("#stages tbody");
    tbody.innerHTML = "";
    for (const s of stages) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${s.name}</td>
        <td class="status-${s.status}">${s.status}</td>
        <td>${s.duration_ms}</td>
        <td>${(s.output_digest || "").slice(0, 12)}</td>
        <td class="status-failed">${s.error || ""}</td>
      `;
      tbody.appendChild(tr);
    }
  }

  function renderFiles(result) {
    const filesUl = $("#files");
    filesUl.innerHTML = "";
    const container = filesUl.parentElement;
    if (result.case_dir && result.status === "completed") {
      container.hidden = false;
      apiCall(`/api/v1/runs/${result.run_id}/files`).then(({ files }) => {
        files.forEach(f => {
          const li = document.createElement("li");
          li.innerHTML = `<a href="/api/v1/runs/${result.run_id}/files/${f}" target="_blank">${f}</a>`;
          filesUl.appendChild(li);
        });
      });
    } else {
      container.hidden = true;
    }
  }

  function renderXfoilResults(result) {
    const table = $("#xfoil-results");
    const chartCanvas = $("#xfoil-chart");
    const tbody = table.querySelector("tbody");
    tbody.innerHTML = "";

    if (result.xfoil_results && result.xfoil_results.length > 0) {
      table.hidden = false;
      chartCanvas.hidden = false;
      result.xfoil_results.forEach(row => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${row.alpha_deg.toFixed(3)}</td>
          <td>${row.cl.toFixed(4)}</td>
          <td>${row.cd.toFixed(5)}</td>
          <td>${row.cm.toFixed(4)}</td>
        `;
        tbody.appendChild(tr);
      });
      renderChart(result.xfoil_results);
    } else {
      table.hidden = true;
      chartCanvas.hidden = true;
    }
  }

  function renderChart(data) {
    const ctx = $("#xfoil-chart").getContext("2d");
    if (xfoilChart) xfoilChart.destroy();
    xfoilChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: data.map(r => r.alpha_deg.toFixed(2)),
        datasets: [{
          label: 'Cl',
          data: data.map(r => r.cl),
          borderColor: '#7aa2f7',
          yAxisID: 'y'
        }, {
          label: 'Cd',
          data: data.map(r => r.cd),
          borderColor: '#f7768e',
          yAxisID: 'y1'
        }]
      },
      options: {
        scales: {
          y: { position: 'left', ticks: { color: '#c0caf5' } },
          y1: { position: 'right', grid: { drawOnChartArea: false }, ticks: { color: '#c0caf5' } }
        },
        plugins: { legend: { labels: { color: '#c0caf5' } } }
      }
    });
  }

  async function loadRuns() {
    const spinner = $("#history-spinner");
    spinner.hidden = false;
    try {
      const params = new URLSearchParams({ limit: runsState.limit, offset: runsState.offset });
      const q = $("#runs-search").value.trim();
      if (q) params.set("q", q);
      const status = $("#runs-status").value;
      if (status) params.set("status", status);

      const r = await fetch(`/api/v1/runs?${params.toString()}`, { headers: getHeaders() });
      if (!r.ok) throw new Error(`Failed to load history: ${r.status}`);

      runsState.total = Number(r.headers.get("X-Total-Count") || "0");
      const runs = await r.json();

      const tbody = $("#runs tbody");
      tbody.innerHTML = "";
      runs.forEach(row => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><a href="#" data-id="${row.run_id}">${row.run_id}</a></td>
          <td class="status-${row.status}">${row.status}</td>
          <td>${row.created_at_iso}</td>
          <td>${row.intent_text}</td>
          <td><a href="/api/v1/runs/${row.run_id}/report" target="_blank">Report</a></td>
        `;
        tr.querySelector("a").addEventListener("click", async (e) => {
          e.preventDefault();
          try {
            renderResult(await apiCall(`/api/v1/runs/${row.run_id}`));
          } catch (err) {
            alert(err.message);
          }
        });
        tbody.appendChild(tr);
      });
      updatePager();
    } catch (error) {
      $("#runs tbody").innerHTML = `<tr><td colspan="5" class="status-failed">${error.message}</td></tr>`;
    } finally {
      spinner.hidden = true;
    }
  }

  function updatePager() {
    const { offset, limit, total } = runsState;
    const start = total === 0 ? 0 : offset + 1;
    const end = Math.min(offset + limit, total);
    $("#runs-page-info").textContent = `${start}-${end} of ${total}`;
    $("#runs-prev").disabled = offset <= 0;
    $("#runs-next").disabled = offset + limit >= total;
  }

  // --- Event Listeners ---
  $("#intent-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = $("#run-btn");
    const spinner = $("#run-spinner");
    btn.disabled = true;
    spinner.hidden = false;
    try {
      const body = {
        intent_text: $("#intent-text").value,
        resume: $("#resume").checked,
        analysis_mode: $("#analysis-mode").value,
      };
      const result = await apiCall("/api/v1/runs", { method: "POST", body: JSON.stringify(body) });
      renderResult(result);
      runsState.offset = 0;
      loadRuns();
    } catch (error) {
      alert(error.message);
    } finally {
      btn.disabled = false;
      spinner.hidden = true;
    }
  });

  // Tabs
  $$(".tab-link").forEach(button => {
    button.addEventListener("click", () => {
      const tab = button.dataset.tab;
      $$(".tab-link").forEach(b => b.classList.remove("active"));
      $$(".tab-content").forEach(c => c.hidden = c.id !== tab);
      button.classList.add("active");
    });
  });

  // Dynamic forms
  function addVariableRow(containerId) {
    const container = $(`#${containerId}`);
    const row = document.createElement("div");
    row.className = "variable-row";
    row.innerHTML = `
      <input type="text" class="variable-key" placeholder="e.g., flow.reynolds_target">
      <input type="text" class="variable-values" placeholder="e.g., 1e6, 2e6, 3e6">
      <button type="button" class="remove-btn">-</button>
    `;
    row.querySelector(".remove-btn").addEventListener("click", () => row.remove());
    container.appendChild(row);
  }
  $("#add-study-variable").addEventListener("click", () => addVariableRow("study-variables"));
  $("#add-opt-variable").addEventListener("click", () => addVariableRow("opt-variables"));

  // History search and filter
  $("#runs-search").addEventListener("input", () => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      runsState.offset = 0;
      loadRuns();
    }, 300);
  });
  $("#runs-status").addEventListener("change", () => {
    runsState.offset = 0;
    loadRuns();
  });

  // Pager
  $("#runs-prev").addEventListener("click", () => { runsState.offset -= runsState.limit; loadRuns(); });
  $("#runs-next").addEventListener("click", () => { runsState.offset += runsState.limit; loadRuns(); });

  // Table sorting
  $$("#stages th[data-sort]").forEach(th => th.addEventListener("click", () => sortTable("stages", th.dataset.sort, th.dataset.sort === "ms")));
  $$("#xfoil-results th[data-sort]").forEach(th => th.addEventListener("click", () => sortTable("xfoil-results", th.dataset.sort, true)));

  // Initial Load
  loadVersion();
  loadRuns();
})();
