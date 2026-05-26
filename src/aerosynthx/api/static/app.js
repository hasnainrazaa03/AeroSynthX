// AeroSynthX minimal UI -- vanilla JS, no framework.
(() => {
  const $ = (sel) => document.querySelector(sel);

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
    const ul = $("#files");
    ul.innerHTML = "";
    if (result.status === "completed") {
      jget(`/api/v1/runs/${result.run_id}/files`).then(({ files }) => {
        for (const f of files) {
          const li = document.createElement("li");
          li.innerHTML = `<a href="/api/v1/runs/${result.run_id}/files/${f}" target="_blank">${f}</a>`;
          ul.appendChild(li);
        }
      });
    }
  }

  async function loadRuns() {
    const tbody = $("#runs tbody");
    tbody.innerHTML = "";
    const runs = await jget("/api/v1/runs");
    for (const r of runs) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><a href="#" data-id="${r.run_id}">${r.run_id}</a></td>
        <td class="status-${r.status}">${r.status}</td>
        <td>${r.created_at_iso}</td>
        <td>${r.intent_text}</td>
      `;
      tr.querySelector("a").addEventListener("click", async (e) => {
        e.preventDefault();
        renderResult(await jget(`/api/v1/runs/${r.run_id}`));
      });
      tbody.appendChild(tr);
    }
  }

  $("#intent-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = {
      intent_text: $("#intent-text").value,
      resume: $("#resume").checked,
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
    loadRuns();
  });

  $("#refresh-runs").addEventListener("click", loadRuns);

  loadVersion();
  loadRuns();
})();
