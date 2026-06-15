// AeroSynthX minimal UI -- vanilla JS, no framework.
(() => {
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  const runsState = { offset: 0, limit: 15, total: 0 };
  let searchTimeout = null;

  // Initialize API Key from local storage
  const apiKeyInput = $("#api-key");
  const storedKey = localStorage.getItem("aerosynthx_api_key");
  if (storedKey) apiKeyInput.value = storedKey;

  apiKeyInput.addEventListener("input", (e) => {
    localStorage.setItem("aerosynthx_api_key", e.target.value.trim());
  });

  function getHeaders() {
    const headers = { "Content-Type": "application/json" };
    const key = apiKeyInput.value.trim();
    if (key) {
      headers["X-API-Key"] = key;
    }
    return headers;
  }

  async function jget(url) {
    const r = await fetch(url, { headers: getHeaders() });
    if (!r.ok) {
        if (r.status === 401) throw new Error("Unauthorized (Check API Key)");
        throw new Error(`${r.status} ${r.statusText}`);
    }
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

  function sortTable(tableId, columnSelector, isNumeric) {
      const tbody = $(`#${tableId} tbody`);
      const rows = Array.from(tbody.querySelectorAll("tr"));
      const th = $(`#${tableId} th[data-sort="${columnSelector}"]`);

      let asc = th.dataset.asc === "true";
      asc = !asc;
      th.dataset.asc = asc;

      // Reset other headers
      $$(`#${tableId} th[data-sort]`).forEach(h => {
          if (h !== th) h.dataset.asc = "";
      });

      const idx = Array.from(th.parentNode.children).indexOf(th);

      rows.sort((a, b) => {
          let valA = a.children[idx].innerText.trim();
          let valB = b.children[idx].innerText.trim();

          if (isNumeric) {
              valA = parseFloat(valA) || 0;
              valB = parseFloat(valB) || 0;
              return asc ? valA - valB : valB - valA;
          } else {
              return asc ? valA.localeCompare(valB) : valB.localeCompare(valA);
          }
      });

      tbody.innerHTML = "";
      rows.forEach(r => tbody.appendChild(r));
  }

  function renderResult(result) {
    const panel = $("#result-panel");
    panel.hidden = false;

    let reportLink = "";
    if (result.status === "completed") {
        const keyQuery = apiKeyInput.value.trim() ? `?api_key=${encodeURIComponent(apiKeyInput.value.trim())}` : '';
        // Note: passing api_key in URL is not secure for real deployments, but works for this simple UI demo if backend supports it or if we just rely on the browser opening it without auth.
        // For strict header auth, the report should be downloaded via fetch and rendered.
        reportLink = `<p><a href="/api/v1/runs/${result.run_id}/report" target="_blank" rel="noopener">Download report</a></p>`;
    }

    $("#result-summary").innerHTML = `
      <p><strong>Run ID:</strong> <code>${result.run_id}</code></p>
      <p><strong>Status:</strong>
        <span class="status-${result.status}">${result.status}</span></p>
      ${result.case_dir ? `<p><strong>Case:</strong> <code>${result.case_dir}</code></p>` : ""}
      ${reportLink}
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
    if (result.case_dir && result.status === "completed") {
      filesUl.parentElement.hidden = false;
      filesUl.previousElementSibling.hidden = false;
      jget(`/api/v1/runs/${result.run_id}/files`).then(({ files }) => {
        for (const f of files) {
          const li = document.createElement("li");
          li.innerHTML = `<a href="/api/v1/runs/${result.run_id}/files/${f}" target="_blank">${f}</a>`;
          filesUl.appendChild(li);
        }
      });
    } else {
      filesUl.hidden = true;
      filesUl.previousElementSibling.hidden = true;
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
    const spinner = $("#history-spinner");
    spinner.hidden = false;

    try {
        const params = new URLSearchParams();
        params.set("limit", String(runsState.limit));
        params.set("offset", String(runsState.offset));
        const q = $("#runs-search").value.trim();
        if (q) params.set("q", q);
        const status = $("#runs-status").value;
        if (status) params.set("status", status);

        const r = await fetch(`/api/v1/runs?${params.toString()}`, { headers: getHeaders() });
        if (!r.ok) {
            if (r.status === 401) throw new Error("Unauthorized (Check API Key)");
            throw new Error(`${r.status} ${r.statusText}`);
        }

        runsState.total = Number(r.headers.get("X-Total-Count") || "0");
        const runs = await r.json();

        tbody.innerHTML = "";
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
            try {
                renderResult(await jget(`/api/v1/runs/${row.run_id}`));
            } catch (err) {
                alert(`Error loading run: ${err.message}`);
            }
          });
          tbody.appendChild(tr);
        }
        updatePager();
    } catch (error) {
        tbody.innerHTML = `<tr><td colspan="5" class="status-failed">Failed to load history: ${error.message}</td></tr>`;
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
        const r = await fetch("/api/v1/runs", {
          method: "POST",
          headers: getHeaders(),
          body: JSON.stringify(body),
        });
        if (!r.ok) {
          if (r.status === 401) throw new Error("Unauthorized (Check API Key)");
          throw new Error(`Run failed: ${r.status} ${await r.text()}`);
        }
        renderResult(await r.json());
        runsState.offset = 0;
        loadRuns();
    } catch (error) {
        alert(error.message);
    } finally {
        btn.disabled = false;
        spinner.hidden = true;
    }
  });

  // Live search
  $("#runs-search").addEventListener("input", (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        runsState.offset = 0;
        loadRuns();
    }, 300); // 300ms debounce
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

  // Table sorting setup
  $$("#stages th[data-sort]").forEach(th => {
      th.addEventListener("click", () => sortTable("stages", th.dataset.sort, th.dataset.sort === "ms"));
  });

  $$("#xfoil-results th[data-sort]").forEach(th => {
      th.addEventListener("click", () => sortTable("xfoil-results", th.dataset.sort, true));
  });

  loadVersion();
  loadRuns();
})();
