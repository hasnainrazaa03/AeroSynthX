// AeroSynthX Modern UI Engine
(() => {
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  const runsState = { offset: 0, limit: 10, total: 0 };
  let searchTimeout = null;
  let xfoilChart = null;
  let threeScene = null;
  let threeRenderer = null;
  let threeCamera = null;
  let threeControls = null;

  // --- API & State Management ---
  const apiKeyInput = $("#api-key");
  if (apiKeyInput) {
    apiKeyInput.value = localStorage.getItem("aerosynthx_api_key") || "";
    apiKeyInput.addEventListener("input", (e) => localStorage.setItem("aerosynthx_api_key", e.target.value.trim()));
  }

  function getHeaders() {
    const headers = { "Content-Type": "application/json" };
    if (apiKeyInput) {
      const key = apiKeyInput.value.trim();
      if (key) headers["X-API-Key"] = key;
    }
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

  async function pollStatus(endpoint, initialResult, statusField = "status") {
      let result = initialResult;
      let id = result.run_id || result.study_id || result.optimization_id;

      while (result[statusField] === "queued" || result[statusField] === "running" || result[statusField] === "pending") {
          await new Promise(resolve => setTimeout(resolve, 2000)); // Poll every 2 seconds
          result = await apiCall(`${endpoint}/${id}`);
      }
      return result;
  }

  async function loadVersion() {
    try {
      const info = await apiCall("/api/v1/version");
      $("#version").textContent = info.version;
    } catch {
      $("#version").textContent = "unknown";
    }
  }

  function sortTable(tableId, field, isNumeric) {
    const table = $(`#${tableId}`);
    const tbody = table.querySelector("tbody");
    const rows = Array.from(tbody.querySelectorAll("tr"));
    const th = table.querySelector(`th[data-sort="${field}"]`);
    const isAsc = !th.classList.contains("sort-asc");
    
    table.querySelectorAll("th").forEach(header => {
        header.classList.remove("sort-asc", "sort-desc");
    });
    th.classList.add(isAsc ? "sort-asc" : "sort-desc");

    rows.sort((a, b) => {
        const headers = Array.from(table.querySelectorAll("th"));
        const colIndex = headers.indexOf(th);
        const cellA = a.children[colIndex].textContent.trim();
        const cellB = b.children[colIndex].textContent.trim();

        if (isNumeric) {
            const valA = parseFloat(cellA) || 0;
            const valB = parseFloat(cellB) || 0;
            return isAsc ? valA - valB : valB - valA;
        } else {
            return isAsc ? cellA.localeCompare(cellB) : cellB.localeCompare(cellA);
        }
    });

    tbody.innerHTML = "";
    rows.forEach(r => tbody.appendChild(r));
  }

  // --- Three.js 3D Wing Renderer ---
  function initThreeJS(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = "";

    const width = container.clientWidth || 400;
    const height = container.clientHeight || 380;

    threeScene = new THREE.Scene();
    threeScene.background = null;

    threeCamera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);

    threeRenderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    threeRenderer.setSize(width, height);
    threeRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(threeRenderer.domElement);

    threeControls = new THREE.OrbitControls(threeCamera, threeRenderer.domElement);
    threeControls.enableDamping = true;
    threeControls.dampingFactor = 0.05;
    threeControls.maxPolarAngle = Math.PI;
    threeControls.minDistance = 2;
    threeControls.maxDistance = 100;

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.45);
    threeScene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.85);
    dirLight1.position.set(10, 20, 15);
    threeScene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0x0ea5e9, 0.55);
    dirLight2.position.set(-10, -20, -15);
    threeScene.add(dirLight2);

    const pointLight = new THREE.PointLight(0x6366f1, 1.2, 30);
    pointLight.position.set(0, 5, 0);
    threeScene.add(pointLight);

    let animationFrameId;
    function animate() {
      animationFrameId = requestAnimationFrame(animate);
      if (threeControls) threeControls.update();
      if (threeRenderer && threeScene && threeCamera) {
        threeRenderer.render(threeScene, threeCamera);
      }
    }
    animate();

    const resizeObserver = new ResizeObserver(() => {
      if (!container || !threeCamera || !threeRenderer) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      if (w === 0 || h === 0) return;
      threeCamera.aspect = w / h;
      threeCamera.updateProjectionMatrix();
      threeRenderer.setSize(w, h);
    });
    resizeObserver.observe(container);

    container.cleanup = () => {
      cancelAnimationFrame(animationFrameId);
      resizeObserver.disconnect();
      if (threeControls) threeControls.dispose();
      if (threeRenderer) threeRenderer.dispose();
      threeScene = null;
      threeCamera = null;
      threeRenderer = null;
      threeControls = null;
    };
  }

  function render3DWing(coordinates) {
    const containerEl = $("#wing-3d-container");
    if (!containerEl) return;
    containerEl.hidden = false;

    const canvasContainer = document.getElementById("wing-3d-canvas-container");
    if (canvasContainer.cleanup) {
      canvasContainer.cleanup();
    }
    initThreeJS("wing-3d-canvas-container");

    if (!threeScene) return;

    const geometry = new THREE.BufferGeometry();
    
    const numStations = coordinates.length;
    if (numStations < 2) return;
    const numPoints = coordinates[0].length;

    const vertices = [];
    const indices = [];

    for (let s = 0; s < numStations; s++) {
      for (let p = 0; p < numPoints; p++) {
        const pt = coordinates[s][p];
        vertices.push(pt[1], pt[2], pt[0]);
      }
    }

    for (let s = 0; s < numStations - 1; s++) {
      for (let p = 0; p < numPoints; p++) {
        const nextP = (p + 1) % numPoints;

        const v00 = s * numPoints + p;
        const v10 = (s + 1) * numPoints + p;
        const v01 = s * numPoints + nextP;
        const v11 = (s + 1) * numPoints + nextP;

        indices.push(v00, v10, v01);
        indices.push(v10, v11, v01);
      }
    }

    geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();

    const material = new THREE.MeshStandardMaterial({
      color: 0x0ea5e9,
      roughness: 0.2,
      metalness: 0.8,
      side: THREE.DoubleSide,
      flatShading: false
    });

    const mesh = new THREE.Mesh(geometry, material);
    threeScene.add(mesh);

    const mirroredMesh = new THREE.Mesh(geometry, material);
    mirroredMesh.scale.set(-1, 1, 1);
    threeScene.add(mirroredMesh);

    const wireframeMaterial = new THREE.MeshBasicMaterial({
      color: 0x0ea5e9,
      wireframe: true,
      transparent: true,
      opacity: 0.15
    });

    const wireframe = new THREE.Mesh(geometry, wireframeMaterial);
    threeScene.add(wireframe);

    const mirroredWireframe = new THREE.Mesh(geometry, wireframeMaterial);
    mirroredWireframe.scale.set(-1, 1, 1);
    threeScene.add(mirroredWireframe);

    geometry.computeBoundingBox();
    const bbox = geometry.boundingBox;
    const center = new THREE.Vector3();
    bbox.getCenter(center);
    center.x = 0;

    threeControls.target.copy(center);
    
    const size = new THREE.Vector3();
    bbox.getSize(size);
    const maxDim = Math.max(size.x * 2, size.y, size.z);
    
    threeCamera.position.set(0, center.y + maxDim * 0.7, center.z + maxDim * 1.1);
    threeCamera.lookAt(center);
    threeControls.update();
  }

  // --- UI Rendering ---
  function renderRunResult(result) {
    $("#result-panel").hidden = false;

    let reportLink = "";
    if (result.status === "completed") {
        reportLink = `<p><a href="/api/v1/runs/${result.run_id}/report" target="_blank" rel="noopener" class="badge-status ready-badge">Download Full HTML Report</a></p>`;
    }

    let geomHtml = "";
    if (result.wing) {
      geomHtml = `
        <p><strong>Geometry Type:</strong> 3D Wing</p>
        <p><strong>Span:</strong> ${result.wing.span} m</p>
        <p><strong>Sweep / Dihedral / Twist:</strong> ${result.wing.sweep_deg}° / ${result.wing.dihedral_deg}° / ${result.wing.twist_deg}°</p>
        <p><strong>Root Airfoil:</strong> NACA ${result.wing.root_airfoil.designation} (${result.wing.root_airfoil.chord_m}m chord)</p>
        <p><strong>Tip Airfoil:</strong> NACA ${result.wing.tip_airfoil ? result.wing.tip_airfoil.designation : "N/A"} (${result.wing.tip_airfoil ? result.wing.tip_airfoil.chord_m : "N/A"}m chord)</p>
      `;
    } else if (result.airfoil) {
      geomHtml = `
        <p><strong>Geometry Type:</strong> 2D Airfoil (NACA ${result.airfoil.designation})</p>
        <p><strong>Chord length:</strong> ${result.airfoil.chord_m} m</p>
        <p><strong>Family:</strong> ${result.airfoil.family}</p>
      `;
    }

    $("#result-summary").innerHTML = `
      <div class="summary-info">
        <p><strong>ID:</strong> <code>${result.run_id}</code></p>
        <p><strong>Status:</strong> <span class="status-${result.status}">${result.status}</span></p>
        ${geomHtml}
        ${result.case_dir ? `<p><strong>Output Directory:</strong> <code>${result.case_dir}</code></p>` : ""}
        ${reportLink}
      </div>
    `;

    renderStages(result.stages || []);
    renderFiles(result);
    renderXfoilResults(result);
    
    if (result.wing && result.wing.coordinates) {
      render3DWing(result.wing.coordinates);
    } else {
      const containerEl = $("#wing-3d-container");
      if (containerEl) containerEl.hidden = true;
      const canvasContainer = document.getElementById("wing-3d-canvas-container");
      if (canvasContainer && canvasContainer.cleanup) {
        canvasContainer.cleanup();
      }
    }
    
    // Smooth scroll to the result panel
    $("#result-panel").scrollIntoView({ behavior: 'smooth' });
    lucide.createIcons();
  }

  function renderStudyResult(result) {
    $("#result-panel").hidden = false;

    let reportLink = "";
    if (result.status === "completed") {
        reportLink = `<p><a href="/api/v1/studies/${result.study_id}/report" target="_blank" rel="noopener" class="badge-status ready-badge">Download Study Report</a></p>`;
    }

    $("#result-summary").innerHTML = `
      <div class="summary-info">
        <p><strong>Type:</strong> Parametric Study</p>
        <p><strong>ID:</strong> <code>${result.study_id}</code></p>
        <p><strong>Name:</strong> ${result.study_name}</p>
        <p><strong>Status:</strong> <span class="status-${result.status}">${result.status}</span></p>
        <p><strong>Total Iterations:</strong> ${result.runs ? result.runs.length : 0}</p>
        ${reportLink}
      </div>
    `;

    // Hide single-run specific elements
    $("#stages").parentElement.hidden = true;
    $("#xfoil-results").parentElement.hidden = true;
    
    const containerEl = $("#wing-3d-container");
    if (containerEl) containerEl.hidden = true;
    const canvasContainer = document.getElementById("wing-3d-canvas-container");
    if (canvasContainer && canvasContainer.cleanup) {
      canvasContainer.cleanup();
    }
    
    $("#result-panel").scrollIntoView({ behavior: 'smooth' });
    lucide.createIcons();
  }

  function renderOptResult(result) {
    $("#result-panel").hidden = false;

    $("#result-summary").innerHTML = `
      <div class="summary-info">
        <p><strong>Type:</strong> Optimization Search</p>
        <p><strong>ID:</strong> <code>${result.optimization_id}</code></p>
        <p><strong>Status:</strong> <span class="status-${result.status || 'completed'}">completed</span></p>
        <p><strong>Best Selected Run ID:</strong> <code>${result.best_run_id}</code></p>
      </div>
    `;

    // Hide single-run specific elements
    $("#stages").parentElement.hidden = true;
    $("#xfoil-results").parentElement.hidden = true;
    
    const containerEl = $("#wing-3d-container");
    if (containerEl) containerEl.hidden = true;
    const canvasContainer = document.getElementById("wing-3d-canvas-container");
    if (canvasContainer && canvasContainer.cleanup) {
      canvasContainer.cleanup();
    }
    
    $("#result-panel").scrollIntoView({ behavior: 'smooth' });
    lucide.createIcons();
  }

  function renderStages(stages) {
    const tableContainer = $("#stages").parentElement;
    tableContainer.hidden = false;
    const tbody = $("#stages tbody");
    tbody.innerHTML = "";
    for (const s of stages) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${s.name}</strong></td>
        <td><span class="status-${s.status}">${s.status}</span></td>
        <td>${s.duration_ms}</td>
        <td><code>${(s.output_digest || "").slice(0, 12)}</code></td>
        <td class="status-failed">${s.error || ""}</td>
      `;
      tbody.appendChild(tr);
    }
  }

  function renderFiles(result) {
    const filesUl = $("#files");
    filesUl.innerHTML = "";
    const container = filesUl.parentElement;

    // Handle 3D wing json indicator
    if (result.wing) {
       container.hidden = false;
       filesUl.previousElementSibling.hidden = false;
       const li = document.createElement("li");
       li.innerHTML = `<i data-lucide="file-check" style="margin-right:0.5rem; width:1.1rem; color:var(--success-color);"></i><span>3D Wing representation generated. Check run workspace directory.</span>`;
       filesUl.appendChild(li);
    }

    if (result.case_dir && result.status === "completed") {
      container.hidden = false;
      filesUl.previousElementSibling.hidden = false;
      apiCall(`/api/v1/runs/${result.run_id}/files`).then(({ files }) => {
        for (const f of files) {
          const li = document.createElement("li");
          li.innerHTML = `<i data-lucide="file" style="margin-right:0.5rem; width:1.1rem; color:var(--accent-color);"></i><a href="/api/v1/runs/${result.run_id}/files/${f}" target="_blank">${f}</a>`;
          filesUl.appendChild(li);
        }
        lucide.createIcons();
      });
    } else if (!result.wing) {
      container.hidden = true;
      filesUl.previousElementSibling.hidden = true;
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
      table.previousElementSibling.hidden = false; 
      for (const row of result.xfoil_results) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${row.alpha_deg.toFixed(3)}</td>
          <td>${row.cl.toFixed(4)}</td>
          <td>${row.cd.toFixed(5)}</td>
          <td>${row.cm.toFixed(4)}</td>
        `;
        tbody.appendChild(tr);
      }
      renderChart(result.xfoil_results);
    } else {
      table.hidden = true;
      chartCanvas.hidden = true;
      table.previousElementSibling.hidden = true;
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
          label: 'Cl (Lift Coefficient)',
          data: data.map(r => r.cl),
          borderColor: '#22d3ee',
          backgroundColor: 'rgba(34, 211, 238, 0.05)',
          tension: 0.2,
          yAxisID: 'y'
        }, {
          label: 'Cd (Drag Coefficient)',
          data: data.map(r => r.cd),
          borderColor: '#f43f5e',
          backgroundColor: 'rgba(244, 63, 94, 0.05)',
          tension: 0.2,
          yAxisID: 'y1'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: { position: 'left', ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } },
          y1: { position: 'right', grid: { drawOnChartArea: false }, ticks: { color: '#94a3b8' } }
        },
        plugins: { legend: { labels: { color: '#f8fafc', font: { family: 'Outfit' } } } }
      }
    });
  }

  async function loadRuns() {
    const spinner = $("#history-spinner");
    if (spinner) spinner.hidden = false;
    try {
      const params = new URLSearchParams({ limit: runsState.limit, offset: runsState.offset });
      const q = $("#runs-search").value.trim();
      if (q) params.set("q", q);
      const status = $("#runs-status").value;
      if (status) params.set("status", status);

      const r = await fetch(`/api/v1/runs?${params.toString()}`, { headers: getHeaders() });
      if (!r.ok) {
          if (r.status === 401) throw new Error("Unauthorized (Check API Key)");
          throw new Error(`Failed to load history: ${r.status}`);
      }

      runsState.total = Number(r.headers.get("X-Total-Count") || "0");
      const runs = await r.json();

      const tbody = $("#runs tbody");
      tbody.innerHTML = "";
      runs.forEach(row => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><code><a href="#" data-id="${row.run_id}">${row.run_id.slice(0, 8)}...</a></code></td>
          <td><span class="status-${row.status}">${row.status}</span></td>
          <td style="white-space: nowrap; font-size: 0.8rem; color: var(--text-secondary);">${new Date(row.created_at_iso).toLocaleString()}</td>
          <td style="max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${row.intent_text}</td>
          <td>
            <a href="/api/v1/runs/${row.run_id}/report" target="_blank" class="btn-secondary" style="font-size: 0.75rem; padding: 0.3rem 0.6rem; text-decoration: none; display: inline-flex; align-items: center; gap: 0.25rem;">
              <i data-lucide="external-link" style="width: 0.8rem; height: 0.8rem;"></i> Report
            </a>
          </td>
        `;
        tr.querySelector("a").addEventListener("click", async (e) => {
          e.preventDefault();
          try {
            renderRunResult(await apiCall(`/api/v1/runs/${row.run_id}`));
          } catch (err) {
            alert(err.message);
          }
        });
        tbody.appendChild(tr);
      });
      updatePager();
      lucide.createIcons();
    } catch (error) {
      $("#runs tbody").innerHTML = `<tr><td colspan="5" class="status-failed">${error.message}</td></tr>`;
    } finally {
      if (spinner) spinner.hidden = true;
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

      let result = await apiCall("/api/v1/runs", { method: "POST", body: JSON.stringify(body) });
      result = await pollStatus("/api/v1/runs", result);

      renderRunResult(result);
      runsState.offset = 0;
      loadRuns();
    } catch (error) {
      alert(error.message);
    } finally {
      btn.disabled = false;
      spinner.hidden = true;
    }
  });

  // 3D Wing Builder Form Submission
  $("#wing-builder-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = $("#wing-run-btn");
    const spinner = $("#wing-spinner");
    btn.disabled = true;
    spinner.hidden = false;
    try {
      const span = parseFloat($("#wing-span").value);
      const sweep = parseFloat($("#wing-sweep").value);
      const dihedral = parseFloat($("#wing-dihedral").value);
      const twist = parseFloat($("#wing-twist").value);
      const rootNaca = $("#wing-root-naca").value.trim();
      const rootChord = parseFloat($("#wing-root-chord").value);
      const tipNaca = $("#wing-tip-naca").value.trim();
      const tipChord = parseFloat($("#wing-tip-chord").value);
      const speedType = $("#wing-speed-type").value;
      const speedVal = parseFloat($("#wing-speed-val").value);
      const aoa = parseFloat($("#wing-aoa").value);
      const analysisMode = $("#wing-analysis-mode").value;
      const resume = $("#wing-resume").checked;

      // Construct a string format matching the regex expectations in offline.py
      let intentText = `3D wing, span ${span}m, root NACA ${rootNaca} chord ${rootChord}m, tip NACA ${tipNaca} chord ${tipChord}m`;
      intentText += `, sweep ${sweep} deg, dihedral ${dihedral} deg, twist ${twist} deg`;
      if (speedType === "velocity") {
        intentText += `, velocity ${speedVal} m/s`;
      } else {
        intentText += `, mach ${speedVal}`;
      }
      intentText += ` at alpha ${aoa} deg`;

      const body = {
        intent_text: intentText,
        resume: resume,
        analysis_mode: analysisMode,
      };

      let result = await apiCall("/api/v1/runs", { method: "POST", body: JSON.stringify(body) });
      result = await pollStatus("/api/v1/runs", result);

      renderRunResult(result);
      runsState.offset = 0;
      loadRuns();
    } catch (error) {
      alert(`Wing Synthesis Error: ${error.message}`);
    } finally {
      btn.disabled = false;
      spinner.hidden = true;
    }
  });

  function getVariables(containerId) {
      const variables = {};
      $$(`#${containerId} .variable-row`).forEach(row => {
          const key = row.querySelector(".variable-key").value.trim();
          const valuesStr = row.querySelector(".variable-values").value.trim();
          if (key && valuesStr) {
              try {
                  variables[key] = JSON.parse(valuesStr);
                  if (!Array.isArray(variables[key])) throw new Error();
              } catch {
                  variables[key] = valuesStr.split(',').map(s => {
                      const str = s.trim();
                      const num = parseFloat(str);
                      return isNaN(num) ? str : num;
                  });
              }
          }
      });
      return variables;
  }

  $("#study-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = $("#run-study-btn");
      const spinner = $("#study-spinner");
      btn.disabled = true;
      spinner.hidden = false;
      try {
          const body = {
              study_name: $("#study-name").value,
              base_intent: JSON.parse($("#study-base-intent").value),
              variables: getVariables("study-variables"),
          };
          let result = await apiCall("/api/v1/studies", { method: "POST", body: JSON.stringify(body) });
          result = await pollStatus("/api/v1/studies", result);

          renderStudyResult(result);
          loadRuns();
      } catch (error) {
          alert(`Study Error: ${error.message}. Ensure base intent is valid JSON.`);
      } finally {
          btn.disabled = false;
          spinner.hidden = true;
      }
  });

  $("#opt-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = $("#run-opt-btn");
      const spinner = $("#opt-spinner");
      btn.disabled = true;
      spinner.hidden = false;
      try {
          const body = {
              objective: $("#opt-objective").value,
              target_cl: $("#opt-objective").value === 'target_cl' ? parseFloat($("#opt-target-cl").value) : undefined,
              base_intent: JSON.parse($("#opt-base-intent").value),
              design_space: getVariables("opt-variables"),
          };
          let result = await apiCall("/api/v1/optimizations", { method: "POST", body: JSON.stringify(body) });

          if (result.status) {
             result = await pollStatus("/api/v1/optimizations", result);
          }

          renderOptResult(result);
          loadRuns();
      } catch (error) {
          alert(`Optimization Error: ${error.message}. Ensure base intent is valid JSON.`);
      } finally {
          btn.disabled = false;
          spinner.hidden = true;
      }
  });

  // Tabs selection
  $$(".tab-link").forEach(button => {
    button.addEventListener("click", () => {
      const tab = button.dataset.tab;
      $$(".tab-link").forEach(b => b.classList.remove("active"));
      $$(".tab-content").forEach(c => c.hidden = c.id !== tab);
      button.classList.add("active");
      $(`#${tab}`).hidden = false;
    });
  });

  // Dynamic forms
  function addVariableRow(containerId) {
    const container = $(`#${containerId}`);
    const row = document.createElement("div");
    row.className = "variable-row";
    row.innerHTML = `
      <input type="text" class="variable-key" placeholder="e.g. flow.reynolds_target">
      <input type="text" class="variable-values" placeholder="e.g. [1e6, 2e6] or 1e6, 2e6">
      <button type="button" class="remove-btn"><i data-lucide="trash-2" style="width:0.85rem; height:0.85rem;"></i></button>
    `;
    row.querySelector(".remove-btn").addEventListener("click", () => row.remove());
    container.appendChild(row);
    lucide.createIcons();
  }
  $("#add-study-variable").addEventListener("click", () => addVariableRow("study-variables"));
  $("#add-opt-variable").addEventListener("click", () => addVariableRow("opt-variables"));

  $("#opt-objective").addEventListener("change", (e) => {
      $("#opt-target-cl-wrapper").style.display = e.target.value === "target_cl" ? "block" : "none";
  });

  // History search and filter
  $("#runs-search").addEventListener("input", (e) => {
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

  // Table sorting setup
  $$("#stages th[data-sort]").forEach(th => {
      th.addEventListener("click", () => sortTable("stages", th.dataset.sort, th.dataset.sort === "ms"));
  });

  $$("#xfoil-results th[data-sort]").forEach(th => {
      th.addEventListener("click", () => sortTable("xfoil-results", th.dataset.sort, true));
  });

  // Initial startup
  loadVersion();
  loadRuns();
  lucide.createIcons();
})();
