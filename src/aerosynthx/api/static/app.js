// AeroSynthX minimal UI -- vanilla JS, no framework.
(() => {
  const $ = (sel) => document.querySelector(sel);

  const runsState = { offset: 0, limit: 50, total: 0 };

  async function jget(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    return r.json();
  }

  async function loadVersion() {
    try {
      const v = await jget("/api/v1/version");
      $("#version").textContent = `v${v.version}`;
    } catch {
      $("#version").textContent = "offline";
    }
  }

  function renderResult(result) {
    const panel = $("#result-panel");
    panel.hidden = false;
    $("#result-summary").innerHTML = `
      <p><strong>Run ID:</strong> <code>${result.run_id}</code></p>
      <p><strong>Status:</strong>
        <span class="status-${result.status}">${result.status}</span></p>
      ${result.case_dir ? `<p><strong>Case:</strong> <code>${result.case_dir}</code></p>` : ""}
      <p><a href="/api/v1/runs/${result.run_id}/report" target="_blank" rel="noopener">Download report</a></p>
    `;
    const tbody = $("#stages tbody");
    tbody.innerHTML = "";
    for (const s of result.stages) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${s.name}</td>
        <td class="status-${s.status}">${s.status}</td>
        <td>${s.duration_ms}</td>
        <td>${(s.output_digest || "").slice(0, 12)}</td>
      `;
      tbody.appendChild(tr);
    }

    // Handle OpenFOAM files
    const filesUl = $("#files");
    filesUl.innerHTML = "";
    if (result.case_dir) {
      filesUl.parentElement.hidden = false;
      jget(`/api/v1/runs/${result.run_id}/files`).then(({ files }) => {
        for (const f of files) {
          const li = document.createElement("li");
          li.innerHTML = `<a href="/api/v1/runs/${result.run_id}/files/${f}" target="_blank">${f}</a>`;
          filesUl.appendChild(li);
        }
      });
    } else {
      filesUl.parentElement.hidden = true;
    }

    // Handle XFOIL results
    const xfoilTable = $("#xfoil-results");
    const xfoilTbody = xfoilTable.querySelector("tbody");
    xfoilTbody.innerHTML = "";
    if (result.xfoil_results && result.xfoil_results.length > 0) {
      xfoilTable.hidden = false;
      xfoilTable.previousElementSibling.hidden = false; // Show "XFOIL Results" heading
      for (const row of result.xfoil_results) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${row.alpha_deg.toFixed(3)}</td>
          <td>${row.cl.toFixed(4)}</td>
          <td>${row.cd.toFixed(5)}</td>
          <td>${row.cm.toFixed(4)}</td>
        `;
        xfoilTbody.appendChild(tr);
      }
    } else {
      xfoilTable.hidden = true;
      xfoilTable.previousElementSibling.hidden = true;
    }
  }

  async function loadRuns() {
    const tbody = $("#runs tbody");
    tbody.innerHTML = "";
    const params = new URLSearchParams();
    params.set("limit", String(runsState.limit));
    params.set("offset", String(runsState.offset));
    const q = $("#runs-search").value.trim();
    if (q) params.set("q", q);
    const status = $("#runs-status").value;
    if (status) params.set("status", status);
    const r = await fetch(`/api/v1/runs?${params.toString()}`);
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    runsState.total = Number(r.headers.get("X-Total-Count") || "0");
    const runs = await r.json();
    for (const row of runs) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><a href="#" data-id="${row.run_id}">${row.run_id}</a></td>
        <td class="status-${row.status}">${row.status}</td>
        <td>${row.created_at_iso}</td>
        <td>${row.intent_text}</td>
        <td><a href="/api/v1/runs/${row.run_id}/report" target="_blank" rel="noopener">Report</a></td>
      `;
      tr.querySelector("a").addEventListener("click", async (e) => {
        e.preventDefault();
        renderResult(await jget(`/api/v1/runs/${row.run_id}`));
      });
      tbody.appendChild(tr);
    }
    updatePager();
  }

  function updatePager() {
    const { offset, limit, total } = runsState;
    const start = total === 0 ? 0 : offset + 1;
    const end = Math.min(offset + limit, total);
    $("#runs-page-info").textContent = `${start}-${end} of ${total}`;
    $("#runs-prev").disabled = offset <= 0;
    $("#runs-next").disabled = offset + limit >= total;
  }

  $("#intent-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = {
      intent_text: $("#intent-text").value,
      resume: $("#resume").checked,
      analysis_mode: $("#analysis-mode").value,
    };
    const r = await fetch("/api/v1/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      alert(`Run failed: ${r.status} ${await r.text()}`);
      return;
    }
    renderResult(await r.json());
    runsState.offset = 0;
    loadRuns();
  });

  $("#refresh-runs").addEventListener("click", () => {
    runsState.offset = 0;
    loadRuns();
  });
  $("#runs-search").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      runsState.offset = 0;
      loadRuns();
    }
  });
  $("#runs-status").addEventListener("change", () => {
    runsState.offset = 0;
    loadRuns();
  });
  $("#runs-prev").addEventListener("click", () => {
    runsState.offset = Math.max(0, runsState.offset - runsState.limit);
    loadRuns();
  });
  $("#runs-next").addEventListener("click", () => {
    runsState.offset += runsState.limit;
    loadRuns();
  });

  loadVersion();
  loadRuns();
})();
