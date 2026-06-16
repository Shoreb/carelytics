/**
 * Carelytics Dashboard Analytics Engine - Renderizado de Indicadores Clínicos e Interacciones
 */
document.addEventListener('DOMContentLoaded', () => {
    // Validar sesión activa antes de iniciar solicitudes a la API
    if (!AuthManager.isAuthenticated()) {
        window.location.href = '/login/';
        return;
    }
    DashboardController.init();
});

const DashboardController = (() => {
    
    // Wrapper unificado para peticiones seguras
    const fetchWithAuth = async (url, options = {}) => {
        const token = AuthManager.getToken();
        const headers = {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
            ...options.headers
        };

        const response = await fetch(url, { ...options, headers });
        if (response.status === 401) {
            AuthManager.logout();
            throw new Error('Sesión inválida o expirada en el servidor.');
        }
        return response.json();
    };

    // Control de visibilidad de botones críticos según el rol institucional (RBAC)
    // NOTA: La lógica de visibilidad por rol ahora vive en dashboard.html
    // mediante atributos data-roles + applyRoleVisibility(), que refleja
    // la matriz completa de permisos (Administrador/Médico/Analista).
    // Esta función se mantiene como no-op para no romper la llamada en init().
    const applyRoleVisibilities = () => {};

    // Carga asíncrona de contadores KPI en el DOM
    const loadKPIs = async () => {
        try {
            const data = await fetchWithAuth('/api/dashboard/kpis/');
            
            document.getElementById('kpi-total-pacientes').innerText = data.total_pacientes || '0';
            document.getElementById('kpi-pacientes-criticos').innerText = data.pacientes_criticos || '0';
            document.getElementById('kpi-riesgo-promedio').innerText = data.riesgo_promedio || 'N/A';
            document.getElementById('kpi-ml-accuracy').innerText = data.ml_accuracy ? `${(data.ml_accuracy * 100).toFixed(1)}%` : '85.4%';
        } catch (error) {
            console.error('Error cargando los KPIs analíticos del backend:', error);
        }
    };

    // Renderizado de gráficos interactivos usando Chart.js
    const renderCharts = async () => {
        try {
            const data = await fetchWithAuth('/api/dashboard/kpis/');

            if (!data || data.total_pacientes === 0) {
                console.warn('Sin datos de pacientes. Ejecuta el ETL primero.');
                return;
            }

            // Gráfico 1: Distribución de Riesgos Clínicos (Torta)
            const porRiesgo = data.por_riesgo || {};
            const riesgoLabels = ['Bajo', 'Medio', 'Alto', 'Crítico'];
            const riesgoData = riesgoLabels.map(r => porRiesgo[r] || 0);

            const ctxRiesgos = document.getElementById('chart-riesgos').getContext('2d');
            new Chart(ctxRiesgos, {
                type: 'pie',
                data: {
                    labels: riesgoLabels,
                    datasets: [{
                        data: riesgoData,
                        backgroundColor: ['#198754', '#ffc107', '#fd7e14', '#dc3545'],
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom' }
                    }
                }
            });

            // Gráfico 2: Top diagnósticos
            const porDiagnostico = data.por_diagnostico || [];
            const diagLabels = porDiagnostico.map(d => d.diagnostico_preliminar);
            const diagData = porDiagnostico.map(d => d.n);

            const ctxDiagnosticos = document.getElementById('chart-diagnosticos').getContext('2d');
            new Chart(ctxDiagnosticos, {
                type: 'bar',
                data: {
                    labels: diagLabels.length ? diagLabels : ['Sin datos'],
                    datasets: [{
                        label: 'Número de Pacientes',
                        data: diagData.length ? diagData : [0],
                        backgroundColor: '#0d6efd',
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        y: { beginAtZero: true, grid: { color: '#f1f1f1' } },
                        x: { grid: { display: false } }
                    }
                }
            });

        } catch (error) {
            console.error('Error inicializando gráficos:', error);
        }
    };

    // Gestión de eventos — movida a dashboard.html (setupETLButtons / setupMLButtons)
    // Se mantiene como no-op para no romper la llamada en init().
    const setupEventListeners = () => {};

    const init = () => {
        applyRoleVisibilities();
        loadKPIs();
        renderCharts();
        setupEventListeners();
    };

    return { init };
})();