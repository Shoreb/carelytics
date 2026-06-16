# Carelytics

**Plataforma Inteligente de Analítica Clínica para Detección de Riesgo Médico**

Carelytics es una aplicación web FullStack desarrollada para **HealthAnalytics IPS** que automatiza el procesamiento de datos clínicos mediante un pipeline ETL completo, analítica estadística y modelos de Machine Learning para predecir y clasificar el riesgo médico de pacientes.

---

## Tabla de contenidos

- [Descripción general](#descripción-general)
- [Stack tecnológico](#stack-tecnológico)
- [Arquitectura](#arquitectura)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Instalación local](#instalación-local)
- [Variables de entorno](#variables-de-entorno)
- [Flujo de uso](#flujo-de-uso)
- [API REST](#api-rest)
- [Roles y permisos](#roles-y-permisos)
- [Módulo ETL](#módulo-etl)
- [Módulo Machine Learning](#módulo-machine-learning)
- [Despliegue en producción](#despliegue-en-producción)

---

## Descripción general

La IPS recibe diariamente miles de registros clínicos con inconsistencias: campos vacíos, duplicados, valores fuera de rango y errores ortográficos en diagnósticos. Carelytics resuelve esto con:

- **ETL automatizado** que extrae, limpia y carga el dataset clínico en base de datos con trazabilidad completa.
- **Dashboard clínico** con KPIs en tiempo real: pacientes críticos, hipertensos, diabéticos, distribución de IMC y segmentación por edad y sexo.
- **Modelo RandomForest** entrenado sobre datos reales para predecir el nivel de riesgo (Bajo / Medio / Alto / Crítico) de cada paciente.
- **Exportación** de reportes en PDF, Excel y CSV.
- **Control de acceso por roles** (Administrador, Médico, Analista) con autenticación JWT.

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12 · Django 5.x · Django REST Framework |
| Autenticación | djangorestframework-simplejwt |
| ETL | Pandas · NumPy · OpenPyXL |
| Machine Learning | scikit-learn (RandomForestClassifier) · joblib |
| Base de datos | PostgreSQL (producción) · SQLite (desarrollo) |
| Frontend | HTML5 · Bootstrap 5 · Chart.js · Vanilla JS |
| Exportación | ReportLab (PDF) · OpenPyXL (Excel) |
| Documentación API | drf-spectacular (OpenAPI 3.0 / Swagger) |
| Servidor producción | Gunicorn · WhiteNoise |

---

## Arquitectura

```
carelytics-main/
│
├── frontend/                    ← Capa de presentación
│   ├── templates/               ← index.html · login.html · dashboard.html
│   └── static/js/               ← auth.js · dashboard.js
│
├── backend/                     ← Monolito Django (sirve frontend + API)
│   ├── config/                  ← settings.py · urls.py · wsgi.py
│   ├── authentication/          ← JWT personalizado con claims de rol
│   ├── clinical_records/        ← Modelo Patient · CRUD · KPIs · Reportes
│   ├── etl/                     ← Pipeline ETL · ETLLog · exploracion.py
│   ├── ml/                      ← Trainer RandomForest · Predicción
│   ├── dashboard/               ← Analytics · Críticos · Segmentación
│   ├── build.sh                 ← Script de build para Render
│   ├── runtime.txt              ← Python 3.12.7
│   └── requirements.txt
│
└── datasets/
    └── dataset_clinico_etl_1800_registros.xlsx
```

**Flujo de datos:**

```
Dataset (.xlsx)
      ↓
  EXTRACT → Lee archivo local o subido por el usuario
      ↓
  TRANSFORM → Limpieza · Validación de rangos clínicos · Cálculo IMC · Clasificación de riesgo
      ↓
  LOAD → bulk_create atómico en PostgreSQL + registro en ETLLog
      ↓
  ML → RandomForest entrenado sobre datos limpios → Predicción por paciente
      ↓
  Dashboard → KPIs · Gráficas · Exportación PDF/Excel/CSV
```

---

## Estructura del proyecto

```
backend/
├── authentication/
│   ├── views.py                 ← CustomTokenObtainPairView (JWT con rol)
│   ├── permissions.py           ← QueryParamJWTAuthentication (descargas)
│   └── management/commands/
│       └── crear_usuarios_base.py
│
├── clinical_records/
│   ├── models.py                ← Patient (21 campos clínicos)
│   ├── serializers.py
│   └── views.py                 ← PatientViewSet · DashboardKPIView
│                                   HealthReportView · PredictionView
│
├── etl/
│   ├── models.py                ← ETLLog (auditoría de ejecuciones)
│   ├── exploracion.py           ← Funciones puras de limpieza clínica
│   ├── views.py                 ← ETLRunView · ETLHistorialView
│   └── serializers.py
│
├── ml/
│   ├── trainer.py               ← Pipeline sklearn · entrenar · predecir
│   └── views.py                 ← MLEntrenarView · PrediccionView
│
└── dashboard/
    └── views.py                 ← AnalyticsView · CriticosView · SegmentacionView
```

---

## Instalación local

### Requisitos previos

- Python 3.12+
- Git

### 1. Clonar el repositorio

```bash
git clone https://github.com/TU_USUARIO/carelytics.git
cd carelytics/backend
```

### 2. Crear entorno virtual

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / Mac
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

```bash
cp .env.example .env
# Edita .env si quieres usar PostgreSQL en lugar de SQLite
```

### 5. Aplicar migraciones y crear usuarios

```bash
python manage.py migrate
python manage.py crear_usuarios_base
```

### 6. Verificar la instalación

```bash
python manage.py check
```

Debe terminar con `System check identified no issues`.

### 7. Iniciar el servidor

```bash
python manage.py runserver
```

Abrir en el navegador: **http://127.0.0.1:8000**

---

## Variables de entorno

Crea un archivo `.env` en `backend/` con las siguientes variables:

```env
# Seguridad
SECRET_KEY=django-insecure-cambia-esto-en-produccion
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

# Base de datos
# SQLite (desarrollo — no requiere instalación):
DATABASE_URL=sqlite:///db.sqlite3

# PostgreSQL (producción):
# DATABASE_URL=postgresql://usuario:contraseña@host:5432/nombre_bd

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
```

---

## Flujo de uso

Una vez iniciado el servidor, el flujo recomendado es:

### Paso 1 — Ejecutar el ETL

Desde el dashboard (botón **Ejecutar ETL**) o desde la terminal:

```bash
python manage.py cargar_clinicos
```

El dataset debe estar en `datasets/dataset_clinico_etl_1800_registros.xlsx`. El ETL procesará 1 800 registros, eliminará duplicados, corregirá inconsistencias y los cargará en la base de datos.

### Paso 2 — Entrenar el modelo ML

Desde el dashboard → sección **Predicción ML** → botón **Entrenar modelo**.

O vía API:
```bash
curl -X POST http://127.0.0.1:8000/api/ml/entrenar/ \
  -H "Authorization: Bearer <token>"
```

### Paso 3 — Explorar el dashboard

El dashboard se actualiza automáticamente con los datos cargados. Incluye:

- KPIs clínicos en tiempo real
- Gráficas de distribución de riesgo, diagnósticos, sexo y grupos etarios
- Tabla de pacientes con búsqueda y filtros
- Historial de ejecuciones ETL
- Predicción individual de riesgo

---

## API REST

Todos los endpoints requieren autenticación JWT excepto `/api/auth/login/`.

### Autenticación

```http
POST /api/auth/login/
Content-Type: application/json

{
  "username": "admin",
  "password": "admin123"
}
```

Respuesta:
```json
{
  "access": "<jwt_token>",
  "refresh": "<refresh_token>"
}
```

Usar el `access` token en el header de todas las peticiones:
```
Authorization: Bearer <jwt_token>
```

### Endpoints disponibles

| Método | Endpoint | Descripción | Roles |
|---|---|---|---|
| `POST` | `/api/auth/login/` | Login → devuelve JWT | Todos |
| `POST` | `/api/auth/token/refresh/` | Renovar token | Todos |
| `GET` | `/api/dashboard/kpis/` | KPIs clínicos completos | Todos |
| `GET` | `/api/dashboard/analytics/` | Estadística descriptiva | Admin · Analista |
| `GET` | `/api/dashboard/criticos/` | Lista de pacientes críticos | Admin · Analista |
| `GET` | `/api/dashboard/segmentacion/` | Segmentación cruzada | Admin · Analista |
| `POST` | `/api/etl/run/` | Ejecutar pipeline ETL | Admin · Analista |
| `GET` | `/api/etl/historial/` | Historial de ejecuciones | Admin · Analista |
| `POST` | `/api/ml/entrenar/` | Entrenar RandomForest | Admin · Analista |
| `GET` | `/api/ml/metricas/` | Métricas del modelo | Admin · Analista |
| `POST` | `/api/predicciones/` | Predecir riesgo de un paciente | Admin · Analista |
| `GET` | `/api/pacientes/` | Lista paginada de pacientes | Admin · Médico |
| `GET` | `/api/reportes/?formato=pdf` | Exportar PDF/Excel/CSV | Todos |
| `GET` | `/api/schema/swagger-ui/` | Documentación Swagger | Todos |

### Ejemplo — Predicción de riesgo

```http
POST /api/predicciones/
Authorization: Bearer <token>
Content-Type: application/json

{
  "edad": 55,
  "glucosa": 145.0,
  "presion_sistolica": 150,
  "imc": 29.5,
  "colesterol": 220.0,
  "saturacion_oxigeno": 96.0,
  "frecuencia_cardiaca": 88,
  "temperatura": 37.0,
  "sexo": "M",
  "actividad_fisica": "Baja",
  "fumador": true,
  "antecedentes_familiares": true,
  "presion_diastolica": 95,
  "consumo_alcohol": false
}
```

Respuesta:
```json
{
  "riesgo_predicho": "Alto",
  "probabilidades": {
    "Alto": 0.6133,
    "Bajo": 0.0867,
    "Medio": 0.3000
  },
  "modelo_usado": "RandomForestClassifier"
}
```

---

## Roles y permisos

El sistema tiene tres roles. El rol se asigna mediante grupos de Django y se incluye como claim en el JWT.

| Sección | Administrador | Médico | Analista |
|---|---|---|---|
| Overview clínico | ✅ | ✅ | ✅ |
| Pipeline ETL | ✅ | ❌ | ✅ |
| Expedientes de pacientes | ✅ | ✅ | ❌ |
| Predicción ML | ✅ | ❌ | ✅ |
| Analytics estadístico | ✅ | ❌ | ✅ |
| Exportar reportes | ✅ | ✅ | ✅ |



---

## Módulo ETL

### Dataset

El dataset incluye **1 800 registros clínicos simulados** con errores intencionales:

- Valores nulos (`glucosa = NULL`, `peso = NULL`)
- Tipos incorrectos (`edad = "Treinta"`, `presión = "Alta"`)
- Valores atípicos (`peso = 420 kg`, `temperatura = 28 °C`)
- Duplicados de pacientes
- Errores ortográficos en diagnósticos (`"hipertencion"`, `"hipertensíon"`)

### Reglas de limpieza aplicadas

| Problema | Tratamiento |
|---|---|
| Duplicados | `drop_duplicates` por `id_paciente` |
| Texto en campos numéricos | `pd.to_numeric(errors='coerce')` → imputación por mediana |
| Valores atípicos | Reemplazo por `NaN` según rangos clínicos, luego imputación |
| Errores ortográficos | Normalización mediante diccionario de equivalencias |
| Nulos en categóricos | Imputación por moda |
| IMC | Calculado automáticamente: `peso / altura²` |
| Riesgo clínico | Clasificado por reglas: Crítico / Alto / Medio / Bajo |

### Criterios de clasificación de riesgo

| Nivel | Criterios |
|---|---|
| **Crítico** | Presión sistólica > 180 **ó** Glucosa > 300 **ó** Saturación < 85% |
| **Alto** | 2 o más de: PS > 140, glucosa > 140, IMC > 35, fumador > 60 años, antecedentes |
| **Medio** | 2 o más de: PS > 120, glucosa > 100, IMC > 30, fumador, edad > 65 |
| **Bajo** | No cumple criterios anteriores |

Cada ejecución queda registrada en `ETLLog` con: fecha, usuario, registros leídos/duplicados/inválidos/cargados, tiempo de ejecución y estado.

---

## Módulo Machine Learning

### Modelo

**RandomForestClassifier** (scikit-learn) con las siguientes características:

- `n_estimators=150`, `max_depth=12`, `class_weight='balanced'`
- Preprocesamiento: `StandardScaler` para numéricas, `OneHotEncoder` para categóricas
- Todo encapsulado en un `Pipeline` de scikit-learn y serializado con `joblib`

### Variables predictoras

`edad`, `imc`, `glucosa`, `colesterol`, `presion_sistolica`, `presion_diastolica`, `frecuencia_cardiaca`, `saturacion_oxigeno`, `temperatura`, `sexo`, `actividad_fisica`, `fumador`, `consumo_alcohol`, `antecedentes_familiares`

### Métricas reportadas

`Accuracy`, `Precision`, `Recall`, `F1-Score`, `Matriz de confusión`

> **Nota:** el modelo serializado (`ml_models/risk_model.pkl`) no se incluye en el repositorio. Debe entrenarse tras ejecutar el ETL usando el botón "Entrenar modelo" en el dashboard o el endpoint `/api/ml/entrenar/`.

---

## Despliegue en producción

La aplicación está desplegada usando **Render** (backend) + **Supabase** (PostgreSQL).

### Variables de entorno en producción

```env
SECRET_KEY=<clave-secreta-larga-y-aleatoria>
DEBUG=False
ALLOWED_HOSTS=tu-dominio.onrender.com
DATABASE_URL=postgresql://usuario:contraseña@host:5432/postgres
CORS_ALLOWED_ORIGINS=https://tu-dominio.onrender.com
```

### Start command (Render)

```bash
gunicorn config.wsgi:application --workers 1 --threads 4 --timeout 120 --worker-class gthread
```

### Build command (Render)

```bash
./build.sh
```

El script `build.sh` ejecuta automáticamente:
1. `pip install -r requirements.txt`
2. `python manage.py collectstatic --no-input`
3. `python manage.py migrate`
4. `python manage.py crear_usuarios_base`

---

*Proyecto FullStack + Data Analytics + ETL + Machine Learning — HealthAnalytics IPS · Junio 2026*
