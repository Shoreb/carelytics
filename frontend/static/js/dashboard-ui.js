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
  const role = AuthManager.getUserRole();
  const info = ROLE_INFO[role] || ROLE_INFO.medico;

  document.getElementById('nav-username').textContent = name;
  document.getElementById('nav-role-icon').className = `fa-solid ${info.icon} fa-xs`;

  const pill = document.getElementById('nav-role-pill');
  pill.textContent = info.label;
  pill.classList.add(`role-pill--${role}`);

  const banner = document.getElementById('role-banner');
  banner.classList.add(`role-banner--${role}`);
  document.getElementById('role-banner-text').innerHTML = info.banner;

  applyRoleVisibility(role);

  const activeLink = document.querySelector('.sidebar-link.active');
  if (activeLink && activeLink.style.display === 'none') {
    const overviewLink = document.querySelector('[onclick*="overview"]');
    overviewLink.classList.add('active');
    document.getElementById('section-overview').classList.add('active');
  }

  const now = new Date();
  document.getElementById('header-date').textContent =
    `${now.toLocaleDateString('es-CO', { weekday:'long', year:'numeric', month:'long', day:'numeric' })}`;

  loadExtraKPIs();
  setupETLButtons();
  setupMLButtons();
  setupPatientSearch();
});


/* ── Extra KPIs (sexo, edad) ────────────────────────────────────── */
async function loadExtraKPIs() {
  const data = await API.get('/api/dashboard/kpis/');
  if (!data) return;

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

/* ── Reporte de mapeo de columnas ───────────────────────────────── */
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
    tbody.innerHTML = '<tr><td colspan="13" style="text-align:center;color:var(--muted);padding:2rem;">Sin pacientes. Ejecuta el ETL primero.</td></tr>';
    return;
  }

  const riesgoCls = { 'Bajo':'riesgo-bajo','Medio':'riesgo-medio','Alto':'riesgo-alto','Crítico':'riesgo-critico' };
  tbody.innerHTML = results.map(p => `
    <tr>
      <td style="font-family:monospace;font-size:.78rem;">${p.identificacion}</td>
      <td style="font-weight:600;">${p.nombre}</td>
      <td>${p.edad}</td>
      <td>${p.sexo === 'M' ? 'Masc.' : p.sexo === 'F' ? 'Fem.' : 'Otro'}</td>
      <td>${p.imc != null ? Number(p.imc).toFixed(1) : '—'}</td>
      <td>${p.glucosa != null ? Number(p.glucosa).toFixed(1) : '—'}</td>
      <td>${p.presion_sistolica ?? '—'}</td>
      <td>${p.presion_diastolica ?? '—'}</td>
      <td>${p.saturacion_oxigeno != null ? Number(p.saturacion_oxigeno).toFixed(1) + '%' : '—'}</td>
      <td>${p.frecuencia_cardiaca ?? '—'}</td>
      <td>${p.diagnostico_preliminar}</td>
      <td><span class="riesgo-badge ${riesgoCls[p.riesgo_enfermedad] || ''}">${p.riesgo_enfermedad}</span></td>
      <td class="patient-actions-cell">
        <button class="btn-action btn-action--view" title="Ver expediente" onclick="verPaciente(${JSON.stringify(p).replace(/"/g, '&quot;')})">
          <i class="fa-solid fa-eye"></i>
        </button>
        <button class="btn-action btn-action--predict" title="Predicción ML" onclick="predecirPaciente(${JSON.stringify(p).replace(/"/g, '&quot;')})">
          <i class="fa-solid fa-brain"></i>
        </button>
      </td>
    </tr>
  `).join('');
}

/* ── Modal: Ver Paciente ────────────────────────────────────────── */
function verPaciente(p) {
  const modal = new bootstrap.Modal(document.getElementById('modalVerPaciente'));
  document.getElementById('modalVerPacienteLabel').textContent = `Expediente — ${p.nombre}`;

  const riesgoCls = { 'Bajo':'riesgo-bajo','Medio':'riesgo-medio','Alto':'riesgo-alto','Crítico':'riesgo-critico' };
  const sexoLabel = p.sexo === 'M' ? 'Masculino' : p.sexo === 'F' ? 'Femenino' : 'Otro';

  const fila = (icon, label, value) => value != null && value !== '' && value !== '—' ? `
    <div class="paciente-detail-row">
      <span class="paciente-detail-icon"><i class="fa-solid ${icon}"></i></span>
      <span class="paciente-detail-label">${label}</span>
      <span class="paciente-detail-value">${value}</span>
    </div>` : '';

  document.getElementById('modal-ver-paciente-body').innerHTML = `
    <div class="paciente-detail-header">
      <div class="paciente-detail-avatar">
        <i class="fa-solid ${p.sexo === 'F' ? 'fa-user-nurse' : 'fa-user-injured'}"></i>
      </div>
      <div>
        <div class="paciente-detail-name">${p.nombre}</div>
        <div class="paciente-detail-id">ID: ${p.identificacion}</div>
        <span class="riesgo-badge ${riesgoCls[p.riesgo_enfermedad] || ''}" style="margin-top:.4rem;display:inline-block;">${p.riesgo_enfermedad}</span>
      </div>
    </div>

    <div class="paciente-detail-section-title"><i class="fa-solid fa-id-card"></i> Datos Personales</div>
    <div class="paciente-detail-grid">
      ${fila('fa-cake-candles', 'Edad', p.edad + ' años')}
      ${fila('fa-venus-mars', 'Sexo', sexoLabel)}
      ${fila('fa-calendar-day', 'Fecha Consulta', p.fecha_consulta || '—')}
    </div>

    <div class="paciente-detail-section-title"><i class="fa-solid fa-heart-pulse"></i> Signos Vitales</div>
    <div class="paciente-detail-grid">
      ${fila('fa-droplet', 'Glucosa', p.glucosa != null ? Number(p.glucosa).toFixed(1) + ' mg/dL' : null)}
      ${fila('fa-gauge-high', 'P. Sistólica', p.presion_sistolica != null ? p.presion_sistolica + ' mmHg' : null)}
      ${fila('fa-gauge', 'P. Diastólica', p.presion_diastolica != null ? p.presion_diastolica + ' mmHg' : null)}
      ${fila('fa-lungs', 'Saturación O₂', p.saturacion_oxigeno != null ? Number(p.saturacion_oxigeno).toFixed(1) + '%' : null)}
      ${fila('fa-heart', 'Frec. Cardíaca', p.frecuencia_cardiaca != null ? p.frecuencia_cardiaca + ' bpm' : null)}
      ${fila('fa-temperature-half', 'Temperatura', p.temperatura != null ? Number(p.temperatura).toFixed(1) + ' °C' : null)}
    </div>

    <div class="paciente-detail-section-title"><i class="fa-solid fa-weight-scale"></i> Antropometría</div>
    <div class="paciente-detail-grid">
      ${fila('fa-weight-scale', 'Peso', p.peso != null ? Number(p.peso).toFixed(1) + ' kg' : null)}
      ${fila('fa-ruler-vertical', 'Altura', p.altura != null ? Number(p.altura).toFixed(2) + ' m' : null)}
      ${fila('fa-chart-simple', 'IMC', p.imc != null ? Number(p.imc).toFixed(1) : null)}
      ${fila('fa-flask', 'Colesterol', p.colesterol != null ? Number(p.colesterol).toFixed(1) + ' mg/dL' : null)}
    </div>

    <div class="paciente-detail-section-title"><i class="fa-solid fa-person-walking"></i> Hábitos</div>
    <div class="paciente-detail-grid">
      ${fila('fa-person-running', 'Actividad Física', p.actividad_fisica)}
      ${fila('fa-smoking', 'Fumador', p.fumador ? 'Sí' : 'No')}
      ${fila('fa-wine-glass', 'Consumo Alcohol', p.consumo_alcohol ? 'Sí' : 'No')}
      ${fila('fa-dna', 'Antec. Familiares', p.antecedentes_familiares ? 'Sí' : 'No')}
    </div>

    <div class="paciente-detail-section-title"><i class="fa-solid fa-stethoscope"></i> Diagnóstico Clínico</div>
    <div class="paciente-detail-grid">
      ${fila('fa-file-medical', 'Diagnóstico', p.diagnostico_preliminar)}
      ${fila('fa-triangle-exclamation', 'Nivel de Riesgo', p.riesgo_enfermedad)}
    </div>
  `;

  modal.show();
}

/* ── Modal: Predicción Individual ──────────────────────────────── */
async function predecirPaciente(p) {
  const modal = new bootstrap.Modal(document.getElementById('modalPrediccion'));
  document.getElementById('modalPrediccionLabel').textContent = `Predicción ML — ${p.nombre}`;
  document.getElementById('modal-prediccion-body').innerHTML = `
    <div class="cl-modal__loading">
      <span class="spinner-border spinner-border-sm"></span> Calculando predicción para <strong>${p.nombre}</strong>…
    </div>`;
  modal.show();

  const body = {
    edad:               p.edad,
    glucosa:            p.glucosa != null ? parseFloat(p.glucosa) : null,
    presion_sistolica:  p.presion_sistolica,
    presion_diastolica: p.presion_diastolica,
    imc:                p.imc != null ? parseFloat(p.imc) : null,
    colesterol:         p.colesterol != null ? parseFloat(p.colesterol) : null,
    saturacion_oxigeno: p.saturacion_oxigeno != null ? parseFloat(p.saturacion_oxigeno) : null,
    frecuencia_cardiaca: p.frecuencia_cardiaca,
    temperatura:        p.temperatura != null ? parseFloat(p.temperatura) : null,
    sexo:               p.sexo,
    actividad_fisica:   p.actividad_fisica,
    fumador:            p.fumador,
    antecedentes_familiares: p.antecedentes_familiares,
    consumo_alcohol:    p.consumo_alcohol,
  };

  const result = await API.post('/api/predicciones/', body);

  if (!result?.riesgo_predicho) {
    document.getElementById('modal-prediccion-body').innerHTML = `
      <div class="cl-modal__error">
        <i class="fa-solid fa-circle-exclamation"></i>
        <p>${result?.error || 'No se pudo calcular la predicción. Verifica que el modelo esté entrenado.'}</p>
      </div>`;
    return;
  }

  const riesgo = result.riesgo_predicho;
  const probas = result.probabilidades || {};

  const riesgoConfig = {
    'Bajo':    { color: '#619438', bg: '#eef5e8', icon: 'fa-circle-check',
                 msg: 'Los indicadores clínicos del paciente están dentro de parámetros normales.' },
    'Medio':   { color: '#92400e', bg: '#fffbeb', icon: 'fa-circle-exclamation',
                 msg: 'El paciente presenta factores de riesgo moderados. Se recomienda seguimiento periódico.' },
    'Alto':    { color: '#c2410c', bg: '#fff7ed', icon: 'fa-triangle-exclamation',
                 msg: 'El paciente presenta múltiples factores de riesgo. Se recomienda evaluación médica próxima.' },
    'Crítico': { color: '#ef4444', bg: '#fef2f2', icon: 'fa-heart-pulse',
                 msg: 'Riesgo crítico detectado. El paciente requiere atención médica inmediata.' },
  };
  const cfg = riesgoConfig[riesgo] || riesgoConfig['Medio'];

  const factores = [];
  if (body.presion_sistolica > 140) factores.push('Hipertensión sistólica');
  if (body.glucosa > 126) factores.push('Glucosa elevada');
  if (body.saturacion_oxigeno < 92) factores.push('Saturación O₂ baja');
  if (body.imc > 30) factores.push('Obesidad (IMC elevado)');
  if (body.fumador) factores.push('Fumador activo');
  if (body.antecedentes_familiares) factores.push('Antecedentes familiares');
  if (body.edad > 60) factores.push('Edad avanzada');

  const probaOrdenada = Object.entries(probas)
    .sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.4rem;font-size:.82rem;">
        <span style="font-weight:${k === riesgo ? '700' : '400'};color:${k === riesgo ? cfg.color : 'var(--ink-soft)'};">${k}</span>
        <div style="display:flex;align-items:center;gap:.5rem;flex:1;margin:0 .75rem;">
          <div style="flex:1;height:6px;background:var(--border);border-radius:3px;">
            <div style="width:${(v*100).toFixed(1)}%;height:100%;background:${k === riesgo ? cfg.color : 'var(--border)'};border-radius:3px;transition:width .4s;"></div>
          </div>
        </div>
        <span style="font-weight:600;min-width:42px;text-align:right;">${(v*100).toFixed(1)}%</span>
      </div>`
    ).join('');

  const riesgoCls = { 'Bajo':'riesgo-bajo','Medio':'riesgo-medio','Alto':'riesgo-alto','Crítico':'riesgo-critico' };

  document.getElementById('modal-prediccion-body').innerHTML = `
    <div class="prediccion-paciente-info">
      <i class="fa-solid fa-user-injured" style="color:var(--purple);font-size:1.1rem;"></i>
      <div>
        <strong>${p.nombre}</strong>
        <span style="color:var(--muted);font-size:.82rem;margin-left:.5rem;">ID: ${p.identificacion} · ${p.edad} años · ${p.sexo === 'M' ? 'Masculino' : p.sexo === 'F' ? 'Femenino' : 'Otro'}</span>
      </div>
      <span class="riesgo-badge ${riesgoCls[p.riesgo_enfermedad] || ''}" style="margin-left:auto;">
        Registro: ${p.riesgo_enfermedad}
      </span>
    </div>

    <div class="ml-result visible" style="background:${cfg.bg};border-color:${cfg.color}40;margin-top:1rem;">
      <p style="font-size:.8rem;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.07em;margin-bottom:.5rem;">Resultado de la predicción</p>
      <div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.6rem;">
        <i class="fa-solid ${cfg.icon}" style="color:${cfg.color};font-size:1.3rem;"></i>
        <span style="color:${cfg.color};font-size:1.6rem;font-weight:800;">Riesgo ${riesgo}</span>
      </div>
      <p style="font-size:.875rem;color:var(--ink-soft);margin-bottom:1rem;">${cfg.msg}</p>

      <p style="font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-bottom:.6rem;">
        Probabilidad por nivel de riesgo
      </p>
      ${probaOrdenada}

      ${factores.length ? `
        <div style="margin-top:1rem;padding-top:.75rem;border-top:1px solid var(--border);">
          <p style="font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-bottom:.5rem;">
            Factores de riesgo detectados
          </p>
          <div style="display:flex;flex-wrap:wrap;gap:.35rem;">
            ${factores.map(f => `
              <span style="font-size:.75rem;font-weight:600;background:${cfg.bg};color:${cfg.color};border:1px solid ${cfg.color}30;border-radius:100px;padding:.2rem .65rem;">${f}</span>
            `).join('')}
          </div>
        </div>` : ''}
    </div>
  `;
}

/* ── Confusion matrix renderer ─────────────────────────────────── */
function renderConfusionMatrix(matrix, labels) {
  if (!matrix || !labels || !matrix.length) return;

  const card = document.getElementById('confusion-card');
  const wrap = document.getElementById('confusion-matrix-wrap');
  card.style.display = 'block';

  const maxVal = Math.max(...matrix.flat());
  const n = labels.length;

  function cellStyle(value) {
    if (maxVal === 0) return 'background:#f3eeff;color:var(--ink);';
    const t = value / maxVal;
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

/* ── Load existing ML metrics on section entry ──────────────────── */
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
    const RANGOS = {
      edad:               { min: 0,    max: 120,  label: 'Edad (años)' },
      glucosa:            { min: 20,   max: 700,  label: 'Glucosa (mg/dL)' },
      presion_sistolica:  { min: 40,   max: 250,  label: 'Presión Sistólica (mmHg)' },
      presion_diastolica: { min: 20,   max: 150,  label: 'Presión Diastólica (mmHg)' },
      imc:                { min: 8,    max: 80,   label: 'IMC' },
      colesterol:         { min: 50,   max: 600,  label: 'Colesterol (mg/dL)' },
      saturacion_oxigeno: { min: 50,   max: 100,  label: 'Saturación O₂ (%)' },
      frecuencia_cardiaca:{ min: 20,   max: 220,  label: 'Frecuencia Cardíaca (bpm)' },
      temperatura:        { min: 35,   max: 42,   label: 'Temperatura (°C)' },
    };

    const campos = {
      edad:               parseInt(document.getElementById('ml-edad').value),
      glucosa:            parseFloat(document.getElementById('ml-glucosa').value),
      presion_sistolica:  parseInt(document.getElementById('ml-presion').value),
      presion_diastolica: parseInt(document.getElementById('ml-presion-diastolica').value),
      imc:                parseFloat(document.getElementById('ml-imc').value),
      colesterol:         parseFloat(document.getElementById('ml-colesterol').value),
      saturacion_oxigeno: parseFloat(document.getElementById('ml-saturacion').value),
      frecuencia_cardiaca:parseInt(document.getElementById('ml-frecuencia').value),
      temperatura:        parseFloat(document.getElementById('ml-temperatura').value),
    };

    const vacios = Object.entries(campos)
      .filter(([k, v]) => v === '' || isNaN(v) || document.getElementById(
        k === 'presion_sistolica' ? 'ml-presion' :
        k === 'presion_diastolica' ? 'ml-presion-diastolica' :
        k === 'saturacion_oxigeno' ? 'ml-saturacion' :
        k === 'frecuencia_cardiaca' ? 'ml-frecuencia' :
        `ml-${k}`
      ).value.trim() === '')
      .map(([k]) => RANGOS[k]?.label || k);

    if (vacios.length > 0) {
      toast(`Completa los campos obligatorios: ${vacios.join(', ')}`, 'error');
      return;
    }

    const fueraRango = Object.entries(campos)
      .filter(([k, v]) => RANGOS[k] && (v < RANGOS[k].min || v > RANGOS[k].max))
      .map(([k]) => `${RANGOS[k].label} (rango: ${RANGOS[k].min}–${RANGOS[k].max})`);

    if (fueraRango.length > 0) {
      toast(`Valores fuera de rango clínico:\n${fueraRango.join('\n')}`, 'error');
      return;
    }

    const body = {
      ...campos,
      sexo:                    document.getElementById('ml-sexo').value,
      actividad_fisica:        document.getElementById('ml-actividad').value,
      fumador:                 document.getElementById('ml-fumador').value === 'true',
      antecedentes_familiares: document.getElementById('ml-antecedentes').value === 'true',
      consumo_alcohol:         document.getElementById('ml-alcohol').value === 'true',
    };

    const btn = document.getElementById('btn-predict');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Calculando…';

    const result = await API.post('/api/predicciones/', body);

    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-magnifying-glass-chart"></i> Calcular riesgo';

    if (result?.riesgo_predicho) {
      const riesgo = result.riesgo_predicho;
      const probas = result.probabilidades || {};
      const div = document.getElementById('ml-result');
      div.classList.add('visible');

      const riesgoConfig = {
        'Bajo':    { color: '#619438', bg: '#eef5e8', icon: 'fa-circle-check',
                     msg: 'Los indicadores clínicos del paciente están dentro de parámetros normales.' },
        'Medio':   { color: '#92400e', bg: '#fffbeb', icon: 'fa-circle-exclamation',
                     msg: 'El paciente presenta factores de riesgo moderados. Se recomienda seguimiento periódico.' },
        'Alto':    { color: '#c2410c', bg: '#fff7ed', icon: 'fa-triangle-exclamation',
                     msg: 'El paciente presenta múltiples factores de riesgo. Se recomienda evaluación médica próxima.' },
        'Crítico': { color: '#ef4444', bg: '#fef2f2', icon: 'fa-heart-pulse',
                     msg: 'Riesgo crítico detectado. El paciente requiere atención médica inmediata.' },
      };
      const cfg = riesgoConfig[riesgo] || riesgoConfig['Medio'];

      const factores = [];
      if (body.presion_sistolica > 140) factores.push('Hipertensión sistólica');
      if (body.glucosa > 126) factores.push('Glucosa elevada');
      if (body.saturacion_oxigeno < 92) factores.push('Saturación O₂ baja');
      if (body.imc > 30) factores.push('Obesidad (IMC elevado)');
      if (body.fumador) factores.push('Fumador activo');
      if (body.antecedentes_familiares) factores.push('Antecedentes familiares');
      if (body.edad > 60) factores.push('Edad avanzada');

      const probaOrdenada = Object.entries(probas)
        .sort((a, b) => b[1] - a[1])
        .map(([k, v]) => `
          <div style="display:flex;justify-content:space-between;align-items:center;
                      margin-bottom:.4rem;font-size:.82rem;">
            <span style="font-weight:${k === riesgo ? '700' : '400'};
                         color:${k === riesgo ? cfg.color : 'var(--ink-soft)'};">${k}</span>
            <div style="display:flex;align-items:center;gap:.5rem;flex:1;margin:0 .75rem;">
              <div style="flex:1;height:6px;background:var(--border);border-radius:3px;">
                <div style="width:${(v*100).toFixed(1)}%;height:100%;
                            background:${k === riesgo ? cfg.color : 'var(--border)'};
                            border-radius:3px;transition:width .4s;"></div>
              </div>
            </div>
            <span style="font-weight:600;min-width:42px;text-align:right;">${(v*100).toFixed(1)}%</span>
          </div>`
        ).join('');

      document.getElementById('ml-result').style.background = cfg.bg;
      document.getElementById('ml-result').style.borderColor = cfg.color + '40';

      document.getElementById('ml-result-riesgo').innerHTML = `
        <div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.6rem;">
          <i class="fa-solid ${cfg.icon}" style="color:${cfg.color};font-size:1.3rem;"></i>
          <span style="color:${cfg.color};font-size:1.6rem;font-weight:800;">Riesgo ${riesgo}</span>
        </div>
        <p style="font-size:.875rem;color:var(--ink-soft);margin-bottom:1rem;">${cfg.msg}</p>
      `;

      document.getElementById('ml-result-probas').innerHTML = `
        <p style="font-size:.75rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:.06em;color:var(--muted);margin-bottom:.6rem;">
          Probabilidad por nivel de riesgo
        </p>
        ${probaOrdenada}
        ${factores.length ? `
          <div style="margin-top:1rem;padding-top:.75rem;border-top:1px solid var(--border);">
            <p style="font-size:.75rem;font-weight:700;text-transform:uppercase;
                      letter-spacing:.06em;color:var(--muted);margin-bottom:.5rem;">
              Factores de riesgo detectados
            </p>
            <div style="display:flex;flex-wrap:wrap;gap:.35rem;">
              ${factores.map(f => `
                <span style="font-size:.75rem;font-weight:600;background:${cfg.bg};
                             color:${cfg.color};border:1px solid ${cfg.color}30;
                             border-radius:100px;padding:.2rem .65rem;">${f}</span>
              `).join('')}
            </div>
          </div>` : ''}
      `;
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
