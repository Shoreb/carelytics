/* ══════════════════════════════════════════════════════════════════
   Dashboard extra: navigation, patients, ETL log, ML, analytics
   (complementa dashboard.js sin reemplazarlo)
══════════════════════════════════════════════════════════════════ */

const API = {
  headers: () => ({
    'Authorization': `Bearer ${AuthManager.getToken()}`,
    'Content-Type': 'application/json',
  }),
  async get(url) {
    const r = await fetch(url, { headers: this.headers() });
    if (r.status === 401) { AuthManager.logout(); return null; }
    return r.json();
  },
  async post(url, body) {
    const r = await fetch(url, { method: 'POST', headers: this.headers(), body: JSON.stringify(body) });
    if (r.status === 401) { AuthManager.logout(); return null; }
    return r.json();
  },
  async postForm(url, formData) {
    const token = AuthManager.getToken();
    const r = await fetch(url, { method: 'POST', headers: { 'Authorization': `Bearer ${token}` }, body: formData });
    if (r.status === 401) { AuthManager.logout(); return null; }
    return r.json();
  }
};

/* ── Toast ─────────────────────────────────────────────────────── */
function toast(msg, type = 'success') {
  const el = document.createElement('div');
  el.className = `toast-msg toast-msg--${type}`;
  el.innerHTML = `<i class="fa-solid fa-${type === 'success' ? 'check-circle' : 'circle-exclamation'}"></i> ${msg}`;
  document.getElementById('toast-wrap').appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

/* ── Section navigation ─────────────────────────────────────────── */
function showSection(name, btn) {
  document.querySelectorAll('.section-block').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.sidebar-link').forEach(b => b.classList.remove('active'));
  document.getElementById(`section-${name}`).classList.add('active');
  if (btn) btn.classList.add('active');

  if (name === 'etl')       loadETLHistory();
  if (name === 'pacientes') loadPatients();
  if (name === 'analytics') loadAnalytics();
  if (name === 'ml')        loadMLMetrics();
}

/* ── Role metadata ──────────────────────────────────────────────── */
const ROLE_INFO = {
  administrador: {
    label: 'Administrador',
    icon: 'fa-user-shield',
    banner: '<strong>Administrador</strong> · Tienes gestión completa: ETL, pacientes, predicción ML, analytics y reportes.',
  },
  medico: {
    label: 'Médico',
    icon: 'fa-user-doctor',
    banner: '<strong>Médico</strong> · Tu acceso está enfocado en visualización clínica: pipeline ETL (solo lectura del overview) y expedientes de pacientes.',
  },
  analista: {
    label: 'Analista',
    icon: 'fa-chart-line',
    banner: '<strong>Analista</strong> · Tu acceso está enfocado en datos: ejecución del pipeline ETL, predicción ML y analytics.',
  },
};

/* ── Hide/show sidebar items and action buttons based on role ─────── */
function applyRoleVisibility(role) {
  document.querySelectorAll('[data-roles]').forEach(el => {
    const allowed = el.dataset.roles.split(',');
    if (!allowed.includes(role)) {
      el.style.display = 'none';
    }
  });
}

/* ── User info in navbar ────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  const name = AuthManager.getUserName();
  const role = AuthManager.getUserRole(); // 'administrador' | 'medico' | 'analista'
  const info = ROLE_INFO[role] || ROLE_INFO.medico;

  document.getElementById('nav-username').textContent = name;
  document.getElementById('nav-role-icon').className = `fa-solid ${info.icon} fa-xs`;

  const pill = document.getElementById('nav-role-pill');
  pill.textContent = info.label;
  pill.classList.add(`role-pill--${role}`);

  // Context banner in overview
  const banner = document.getElementById('role-banner');
  banner.classList.add(`role-banner--${role}`);
  document.getElementById('role-banner-text').innerHTML = info.banner;

  // Hide sections / buttons not available for this role
  applyRoleVisibility(role);

  // If the active section got hidden (edge case), fall back to overview
  const activeLink = document.querySelector('.sidebar-link.active');
  if (activeLink && activeLink.style.display === 'none') {
    const overviewLink = document.querySelector('[onclick*="overview"]');
    overviewLink.classList.add('active');
    document.getElementById('section-overview').classList.add('active');
  }

  // Date header
  const now = new Date();
  document.getElementById('header-date').textContent =
    `${now.toLocaleDateString('es-CO', { weekday:'long', year:'numeric', month:'long', day:'numeric' })}`;

  // Load extra charts after dashboard.js runs
  loadExtraKPIs();
  setupETLButtons();
  setupMLButtons();
  setupPatientSearch();
});


/* ── Extra KPIs (sexo, edad) ────────────────────────────────────── */
async function loadExtraKPIs() {
  const data = await API.get('/api/dashboard/kpis/');
  if (!data) return;

  // Sexo chart
  const sexo = data.por_sexo || {};
  new Chart(document.getElementById('chart-sexo'), {
    type: 'doughnut',
    data: {
      labels: Object.keys(sexo).map(k => k === 'M' ? 'Masculino' : k === 'F' ? 'Femenino' : 'Otro'),
      datasets: [{ data: Object.values(sexo),
        backgroundColor: ['#6728b1','#619438','#f59e0b'],
        borderWidth: 2, borderColor: '#ffffff' }]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
  });

  // Edad chart
  const edad = data.grupos_edad || {};
  new Chart(document.getElementById('chart-edad'), {
    type: 'bar',
    data: {
      labels: Object.keys(edad),
      datasets: [{
        label: 'Pacientes',
        data: Object.values(edad),
        backgroundColor: 'rgba(103,40,177,.75)',
        borderRadius: 6,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true }, x: { grid: { display: false } } }
    }
  });
}

/* ── ETL ────────────────────────────────────────────────────────── */
function setupETLButtons() {
  async function runETL(formData) {
    const btns = document.querySelectorAll('#btn-run-etl, #btn-run-etl-section');
    btns.forEach(b => { b.disabled = true; b.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Procesando…'; });
    try {
      const result = formData ? await API.postForm('/api/etl/run/', formData) : await API.post('/api/etl/run/', {});
      if (result && result.estado === 'exitoso') {
        toast(`ETL completado — ${result.registros_cargados} registros cargados en ${result.tiempo_segundos}s`);
        updateETLStats(result);
        renderColumnReport(result.columnas_reconocidas, result.columnas_ignoradas);
        loadETLHistory();
      } else {
        toast(result?.error || 'Error en el ETL', 'error');
        hideColumnReport();
      }
    } catch (e) {
      toast('Error de conexión con el servidor', 'error');
    } finally {
      btns.forEach(b => { b.disabled = false; b.innerHTML = '<i class="fa-solid fa-rotate"></i> Ejecutar ETL'; });
    }
  }

  document.getElementById('btn-run-etl')?.addEventListener('click', () => runETL());
  document.getElementById('btn-run-etl-section')?.addEventListener('click', () => runETL());

  document.getElementById('etl-file-input')?.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append('archivo', file);
    await runETL(fd);
    e.target.value = '';
  });
}

function updateETLStats(result) {
  document.getElementById('etl-stat-leidos').textContent     = result.registros_leidos ?? '—';
  document.getElementById('etl-stat-cargados').textContent   = result.registros_cargados ?? '—';
  document.getElementById('etl-stat-duplicados').textContent = result.registros_duplicados ?? '—';
}

/* ── Reporte de mapeo de columnas (útil para datasets externos) ───── */
function renderColumnReport(reconocidas, ignoradas) {
  let card = document.getElementById('column-report-card');
  if (!card) {
    card = document.createElement('div');
    card.id = 'column-report-card';
    card.className = 'card';
    card.style.marginBottom = '1.5rem';
    const statsGrid = document.getElementById('etl-stats-grid');
    statsGrid.insertAdjacentElement('afterend', card);
  }

  const reconocidasHtml = (reconocidas || []).map(c =>
    `<span class="col-chip col-chip--ok"><i class="fa-solid fa-check fa-xs"></i> ${c}</span>`
  ).join('');

  const ignoradasHtml = (ignoradas && ignoradas.length)
    ? (ignoradas || []).map(c =>
        `<span class="col-chip col-chip--warn"><i class="fa-solid fa-circle-question fa-xs"></i> ${c}</span>`
      ).join('')
    : '<span style="font-size:.8rem;color:var(--muted);">Ninguna — todas las columnas del archivo fueron reconocidas.</span>';

  card.innerHTML = `
    <div class="card__header">
      <div>
        <div class="card__title">Mapeo de columnas del archivo</div>
        <div class="card__sub">Así interpretó el sistema las columnas de tu dataset</div>
      </div>
    </div>
    <div style="margin-bottom:1rem;">
      <p style="font-size:.78rem;font-weight:700;color:var(--green);text-transform:uppercase;letter-spacing:.05em;margin-bottom:.6rem;">
        Reconocidas (${(reconocidas || []).length})
      </p>
      <div style="display:flex;flex-wrap:wrap;gap:.4rem;">${reconocidasHtml}</div>
    </div>
    <div>
      <p style="font-size:.78rem;font-weight:700;color:var(--amber);text-transform:uppercase;letter-spacing:.05em;margin-bottom:.6rem;">
        Ignoradas (${(ignoradas || []).length})
      </p>
      <div style="display:flex;flex-wrap:wrap;gap:.4rem;">${ignoradasHtml}</div>
      ${(ignoradas && ignoradas.length) ? '<p style="font-size:.75rem;color:var(--muted);margin-top:.6rem;">Estas columnas no se reconocieron como un campo clínico del sistema y no se cargaron. Si esperabas que se usaran, verifica el nombre de la columna en tu archivo.</p>' : ''}
    </div>
  `;
  card.style.display = 'block';
}

function hideColumnReport() {
  const card = document.getElementById('column-report-card');
  if (card) card.style.display = 'none';
}

async function loadETLHistory() {
  const data = await API.get('/api/etl/historial/');
  const tbody = document.getElementById('etl-log-tbody');
  if (!data || data.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:var(--muted);padding:2rem;">Sin ejecuciones registradas. Ejecute el ETL primero.</td></tr>';
    return;
  }
  tbody.innerHTML = data.map(log => `
    <tr>
      <td>${log.id}</td>
      <td>${new Date(log.fecha_ejecucion).toLocaleString('es-CO')}</td>
      <td>${log.usuario_nombre}</td>
      <td style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${log.fuente_datos}">${log.fuente_datos}</td>
      <td>${log.registros_leidos}</td>
      <td>${log.registros_cargados}</td>
      <td>${log.registros_duplicados}</td>
      <td>${log.tiempo_ejecucion_seg}</td>
      <td><span class="badge-estado badge-${log.estado}"><i class="fa-solid fa-circle fa-xs"></i>${log.estado}</span></td>
    </tr>
  `).join('');
}

/* ── Patients ───────────────────────────────────────────────────── */
let patientsPage = 1;
const PAGE_SIZE = 20;

function setupPatientSearch() {
  let timer;
  document.getElementById('patient-search').addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(() => { patientsPage = 1; loadPatients(); }, 400);
  });
  document.getElementById('patient-riesgo-filter').addEventListener('change', () => {
    patientsPage = 1; loadPatients();
  });
}

async function loadPatients() {
  const search = document.getElementById('patient-search').value.trim();
  const riesgo = document.getElementById('patient-riesgo-filter').value;
  let url = `/api/pacientes/?page=${patientsPage}`;
  if (search) url += `&search=${encodeURIComponent(search)}`;
  if (riesgo) url += `&riesgo=${encodeURIComponent(riesgo)}`;

  const data = await API.get(url);
  const tbody = document.getElementById('patients-tbody');

  const results = data?.results || data || [];
  if (!results.length) {
    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:var(--muted);padding:2rem;">Sin pacientes. Ejecuta el ETL primero.</td></tr>';
    return;
  }

  const riesgoCls = { 'Bajo':'riesgo-bajo','Medio':'riesgo-medio','Alto':'riesgo-alto','Crítico':'riesgo-critico' };
  tbody.innerHTML = results.map(p => `
    <tr>
      <td style="font-family:monospace;font-size:.78rem;">${p.identificacion}</td>
      <td style="font-weight:600;">${p.nombre}</td>
      <td>${p.edad}</td>
      <td>${p.sexo === 'M' ? 'M' : p.sexo === 'F' ? 'F' : 'O'}</td>
      <td>${p.imc ?? '—'}</td>
      <td>${p.glucosa ?? '—'}</td>
      <td>${p.presion_sistolica ?? '—'}</td>
      <td>${p.diagnostico_preliminar}</td>
      <td><span class="riesgo-badge ${riesgoCls[p.riesgo_enfermedad] || ''}">${p.riesgo_enfermedad}</span></td>
    </tr>
  `).join('');
}

/* ── Confusion matrix renderer ─────────────────────────────────── */
function renderConfusionMatrix(matrix, labels) {
  if (!matrix || !labels || !matrix.length) return;

  const card = document.getElementById('confusion-card');
  const wrap = document.getElementById('confusion-matrix-wrap');
  card.style.display = 'block';

  const maxVal = Math.max(...matrix.flat());
  const n = labels.length;

  // Escala de un solo color (morado), como un heatmap de matplotlib.
  // La intensidad depende únicamente del valor de la celda, no de si
  // está en la diagonal — igual que "Confusion matrix, without normalization".
  function cellStyle(value) {
    if (maxVal === 0) return 'background:#f3eeff;color:var(--ink);';
    const t = value / maxVal; // 0..1
    const r = Math.round(243 + (103 - 243) * t);
    const g = Math.round(238 + (40  - 238) * t);
    const b = Math.round(255 + (177 - 255) * t);
    const textColor = t > 0.55 ? '#ffffff' : 'var(--ink)';
    return `background:rgb(${r},${g},${b});color:${textColor};`;
  }

  let html = `<div class="cm-title">Matriz de confusión (sin normalizar)</div>`;
  html += `<div class="cm-container"><div>`;

  html += `<div class="cm-grid-wrap">`;
  html += `<div class="cm-ylabel">Valor real</div>`;
  html += `<div class="cm-rows">`;

  matrix.forEach((row, i) => {
    html += `<div class="cm-row">`;
    html += `<div class="cm-row-label">${labels[i]}</div>`;
    row.forEach((value) => {
      html += `<div class="cm-cell" style="${cellStyle(value)}">${value}</div>`;
    });
    html += `</div>`;
  });

  html += `</div></div>`;

  html += `<div class="cm-cols-footer">`;
  labels.forEach(l => html += `<div class="cm-col-label">${l}</div>`);
  html += `</div>`;
  html += `<div class="cm-xlabel">Predicción del modelo</div>`;

  html += `</div>`;

  const tickCount = 5;
  let ticksHtml = '';
  for (let k = tickCount - 1; k >= 0; k--) {
    const val = Math.round((maxVal / (tickCount - 1)) * k);
    ticksHtml += `<span>${val}</span>`;
  }

  html += `
    <div class="cm-colorbar-wrap" style="--cm-bar-height:${n * 78}px;">
      <div class="cm-colorbar"></div>
      <div class="cm-colorbar-ticks">${ticksHtml}</div>
    </div>
  `;

  html += `</div>`;

  wrap.innerHTML = html;
}

/* ── Load existing ML metrics on section entry (if model already trained) ── */
async function loadMLMetrics() {
  const result = await API.get('/api/ml/metricas/');
  if (result?.accuracy !== undefined) {
    document.getElementById('ml-accuracy').textContent  = `${(result.accuracy*100).toFixed(1)}%`;
    document.getElementById('ml-precision').textContent = `${(result.precision*100).toFixed(1)}%`;
    document.getElementById('ml-recall').textContent    = `${(result.recall*100).toFixed(1)}%`;
    document.getElementById('ml-f1').textContent        = `${(result.f1_score*100).toFixed(1)}%`;
    renderConfusionMatrix(result.matriz_confusion, result.etiquetas_confusion);
  }
}

/* ── ML ─────────────────────────────────────────────────────────── */
function setupMLButtons() {
  document.getElementById('btn-train-model').addEventListener('click', async () => {
    const btn = document.getElementById('btn-train-model');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Entrenando…';
    const result = await API.post('/api/ml/entrenar/', {});
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-dumbbell"></i> Entrenar modelo';
    if (result?.metricas) {
      const m = result.metricas;
      document.getElementById('ml-accuracy').textContent  = `${(m.accuracy*100).toFixed(1)}%`;
      document.getElementById('ml-precision').textContent = `${(m.precision*100).toFixed(1)}%`;
      document.getElementById('ml-recall').textContent    = `${(m.recall*100).toFixed(1)}%`;
      document.getElementById('ml-f1').textContent        = `${(m.f1_score*100).toFixed(1)}%`;
      renderConfusionMatrix(m.matriz_confusion, m.etiquetas_confusion);
      toast('Modelo entrenado exitosamente');
    } else {
      toast(result?.error || 'Error al entrenar', 'error');
    }
  });

  document.getElementById('btn-predict').addEventListener('click', async () => {
    const body = {
      edad:                 parseInt(document.getElementById('ml-edad').value) || 0,
      glucosa:              parseFloat(document.getElementById('ml-glucosa').value) || 0,
      presion_sistolica:    parseInt(document.getElementById('ml-presion').value) || 0,
      imc:                  parseFloat(document.getElementById('ml-imc').value) || 0,
      colesterol:           parseFloat(document.getElementById('ml-colesterol').value) || 0,
      saturacion_oxigeno:   parseFloat(document.getElementById('ml-saturacion').value) || 0,
      frecuencia_cardiaca:  parseInt(document.getElementById('ml-frecuencia').value) || 0,
      temperatura:          parseFloat(document.getElementById('ml-temperatura').value) || 0,
      sexo:                 document.getElementById('ml-sexo').value,
      actividad_fisica:     document.getElementById('ml-actividad').value,
      fumador:              document.getElementById('ml-fumador').value === 'true',
      antecedentes_familiares: document.getElementById('ml-antecedentes').value === 'true',
      presion_diastolica:   80,
      consumo_alcohol:      false,
    };
    const result = await API.post('/api/predicciones/', body);
    if (result?.riesgo_predicho) {
      const div = document.getElementById('ml-result');
      div.classList.add('visible');
      document.getElementById('ml-result-riesgo').textContent = `Riesgo: ${result.riesgo_predicho}`;
      const probas = result.probabilidades || {};
      document.getElementById('ml-result-probas').innerHTML =
        Object.entries(probas).map(([k,v]) =>
          `<span style="margin-right:1rem;"><strong>${k}:</strong> ${(v*100).toFixed(1)}%</span>`
        ).join('');
    } else {
      toast(result?.error || 'Error en la predicción. ¿Ya entrenaste el modelo?', 'error');
    }
  });
}

/* ── Analytics ──────────────────────────────────────────────────── */
async function loadAnalytics() {
  const data = await API.get('/api/dashboard/analytics/');
  const container = document.getElementById('analytics-content');
  if (!data || data.error) {
    container.innerHTML = `<div style="text-align:center;padding:2rem;color:var(--muted);">${data?.error || 'Sin datos'}</div>`;
    return;
  }

  const vars = data.variables || {};
  const rows = Object.entries(vars).map(([campo, stats]) => `
    <tr>
      <td style="font-weight:600;text-transform:capitalize;">${campo.replace(/_/g,' ')}</td>
      <td>${stats.promedio ?? '—'}</td>
      <td>${stats.std ?? '—'}</td>
      <td>${stats.minimo ?? '—'}</td>
      <td>${stats.maximo ?? '—'}</td>
    </tr>
  `).join('');

  container.innerHTML = `
    <div class="card">
      <div class="card__header">
        <div>
          <div class="card__title">Estadística descriptiva — ${data.total_registros} pacientes</div>
          <div class="card__sub">Moda diagnóstico: <strong>${data.modas?.diagnostico || '—'}</strong> · Moda riesgo: <strong>${data.modas?.riesgo || '—'}</strong></div>
        </div>
      </div>
      <div style="overflow-x:auto;">
        <table class="patients-table">
          <thead>
            <tr><th>Variable</th><th>Promedio</th><th>Desv. Estándar</th><th>Mínimo</th><th>Máximo</th></tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>
  `;
}

/* ── Download report ────────────────────────────────────────────── */
function downloadReport(formato) {
  const token = AuthManager.getToken();
  const url = `/api/reportes/?formato=${formato}&token=${token}`;
  const a = document.createElement('a');
  a.href = url; a.target = '_blank'; a.click();
}