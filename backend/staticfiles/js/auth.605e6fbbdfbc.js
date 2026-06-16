/**
 * Carelytics AuthManager - Gestión de JWT y Reglas de Negocio de Roles
 */
const AuthManager = (() => {
    const TOKEN_KEY = 'carelytics_access_token';
    const REFRESH_KEY = 'carelytics_refresh_token';

    const setTokens = (access, refresh) => {
        localStorage.setItem(TOKEN_KEY, access);
        localStorage.setItem(REFRESH_KEY, refresh);
    };

    const getToken = () => localStorage.getItem(TOKEN_KEY);

    const logout = () => {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(REFRESH_KEY);
        window.location.href = '/login/';
    };

    const decodeToken = () => {
        const token = getToken();
        if (!token) return null;
        try {
            const base64Url = token.split('.')[1];
            const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
            const jsonPayload = decodeURIComponent(window.atob(base64).split('').map(c => {
                return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
            }).join(''));
            return JSON.parse(jsonPayload);
        } catch (e) {
            return null;
        }
    };

    const isAuthenticated = () => {
        const payload = decodeToken();
        if (!payload) return false;
        const now = Math.floor(Date.now() / 1000);
        return payload.exp > now;
    };

    const getUserRole = () => {
        const payload = decodeToken();
        // Fallback preventivo a 'medico' si el backend no inyecta explícitamente el claim
        return payload && payload.role ? payload.role.toLowerCase() : 'medico'; 
    };

    const getUserName = () => {
        const payload = decodeToken();
        return payload && payload.username ? payload.username : 'Usuario Clínico';
    };

    const login = async (username, password) => {
        try {
            const response = await fetch('/api/auth/login/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password })
            });

            if (!response.ok) throw new Error('Error en autenticación institucional.');

            const data = await response.json();
            // Guarda el par de tokens devueltos por SimpleJWT de DRF
            setTokens(data.access, data.refresh);
            return true;
        } catch (error) {
            console.error('Error de autenticación:', error);
            return false;
        }
    };

    const updateNavbar = () => {
        const menu = document.getElementById('nav-menu');
        if (!menu) return;

        if (isAuthenticated()) {
            const role = getUserRole();
            const username = getUserName();
            let navigationLinks = '';

            // Renderizado condicional estricto por Roles (Requerimiento Técnico)
            if (role === 'administrador' || role === 'admin') {
                navigationLinks = `
                    <li class="nav-item"><a class="nav-link fw-medium px-3 text-dark" href="/dashboard/"><i class="fa-solid fa-chart-pie me-1"></i> Dashboard</a></li>
                    <li class="nav-item"><a class="nav-link fw-medium px-3 text-dark" href="/dashboard/#section-etl"><i class="fa-solid fa-database me-1"></i> Panel ETL</a></li>
                    <li class="nav-item"><a class="nav-link fw-medium px-3 text-dark" href="/dashboard/#section-pacientes"><i class="fa-solid fa-notes-medical me-1"></i> Pacientes</a></li>
                `;
            } else if (role === 'analista') {
                navigationLinks = `
                    <li class="nav-item"><a class="nav-link fw-medium px-3 text-dark" href="/dashboard/"><i class="fa-solid fa-chart-pie me-1"></i> Dashboard</a></li>
                    <li class="nav-item"><a class="nav-link fw-medium px-3 text-dark" href="/dashboard/#section-etl"><i class="fa-solid fa-database me-1"></i> Control ETL</a></li>
                `;
            } else if (role === 'medico') {
                navigationLinks = `
                    <li class="nav-item"><a class="nav-link fw-medium px-3 text-dark" href="/dashboard/"><i class="fa-solid fa-chart-pie me-1"></i> Vista Clínica</a></li>
                    <li class="nav-item"><a class="nav-link fw-medium px-3 text-dark" href="/dashboard/#section-pacientes"><i class="fa-solid fa-notes-medical me-1"></i> Expedientes Médicos</a></li>
                `;
            }

            menu.innerHTML = `
                ${navigationLinks}
                <li class="nav-item ms-3 me-2">
                    <span class="badge bg-primary bg-opacity-10 text-primary py-2 px-3 border border-primary border-opacity-25 rounded-pill">
                        <i class="fa-solid fa-user-md me-1"></i> ${username} (${role.toUpperCase()})
                    </span>
                </li>
                <li class="nav-item">
                    <button onclick="AuthManager.logout()" class="btn btn-outline-danger btn-sm fw-semibold px-3 rounded-pill">
                        <i class="fa-solid fa-power-off me-1"></i> Salir
                    </button>
                </li>
            `;
        } else {
            // Protección de rutas: Forzar login si intenta entrar a áreas privadas
            if (!window.location.pathname.includes('/login/')) {
                window.location.href = '/login/';
            }
            menu.innerHTML = `
                <li class="nav-item">
                    <a class="btn btn-primary btn-sm fw-semibold px-4 rounded-pill" href="/login/">Iniciar Sesión</a>
                </li>
            `;
        }
    };

    // Inicialización automática al cargar el DOM del documento
    document.addEventListener('DOMContentLoaded', () => {
        updateNavbar();
    });

    return {
        login,
        logout,
        getToken,
        isAuthenticated,
        getUserRole,
        getUserName,
        setTokens
    };
})();