"""
Módulo de entrenamiento del modelo de Machine Learning.

Nota de rendimiento: pandas, numpy y scikit-learn se importan dentro de
las funciones que los necesitan (entrenar_modelo, predecir) para evitar
cargarlos al arrancar gunicorn, lo que en instancias con poca RAM
(ej. Render Free 512MB) causa SIGKILL antes de que el servidor responda.
"""

import os
from django.conf import settings


# ── Rutas ─────────────────────────────────────────────────────────────────────
MODELS_DIR = os.path.join(settings.BASE_DIR, 'ml_models')
MODEL_PATH  = os.path.join(MODELS_DIR, 'risk_model.pkl')

# ── Features del modelo ───────────────────────────────────────────────────────
NUMERIC_FEATURES = [
    'edad', 'imc', 'glucosa', 'colesterol',
    'presion_sistolica', 'presion_diastolica',
    'frecuencia_cardiaca', 'saturacion_oxigeno', 'temperatura',
]
CATEGORICAL_FEATURES = ['sexo', 'actividad_fisica']
BOOL_FEATURES = ['fumador', 'consumo_alcohol', 'antecedentes_familiares']
ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES + BOOL_FEATURES
TARGET = 'riesgo_enfermedad'


def _get_pipeline():
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    preprocessor = ColumnTransformer(transformers=[
        ('num', StandardScaler(), NUMERIC_FEATURES),
        ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), CATEGORICAL_FEATURES),
        ('bool', 'passthrough', BOOL_FEATURES),
    ])

    return Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('classifier', RandomForestClassifier(
            n_estimators=150, max_depth=12, min_samples_split=5,
            random_state=42, n_jobs=-1, class_weight='balanced',
        ))
    ])


def entrenar_modelo():
    import joblib
    import pandas as pd
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
    from clinical_records.models import Patient

    os.makedirs(MODELS_DIR, exist_ok=True)

    qs = Patient.objects.values(*ALL_FEATURES, TARGET)
    df = pd.DataFrame.from_records(qs)

    if len(df) < 50:
        raise ValueError("Datos insuficientes.")

    for col in BOOL_FEATURES: df[col] = df[col].astype(int)
    for col in NUMERIC_FEATURES: df[col] = df[col].fillna(df[col].median())
    for col in CATEGORICAL_FEATURES: df[col] = df[col].fillna(df[col].mode()[0])

    df[TARGET] = df[TARGET].replace('Crítico', 'Alto')
    X, y = df[ALL_FEATURES], df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    pipeline = _get_pipeline()
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    metricas = _calcular_metricas(y_test, y_pred, pipeline, X_train)
    joblib.dump(pipeline, MODEL_PATH)

    metricas.update({'registros_entrenamiento': len(X_train), 'registros_prueba': len(X_test)})
    return metricas


def _calcular_metricas(y_test, y_pred, pipeline, X_train):
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

    labels = sorted(list(set(y_test)))
    clf = pipeline.named_steps['classifier']

    return {
        'accuracy': round(accuracy_score(y_test, y_pred), 4),
        'precision': round(precision_score(y_test, y_pred, average='weighted', zero_division=0), 4),
        'recall': round(recall_score(y_test, y_pred, average='weighted', zero_division=0), 4),
        'f1_score': round(f1_score(y_test, y_pred, average='weighted', zero_division=0), 4),
        'matriz_confusion': confusion_matrix(y_test, y_pred, labels=labels).tolist(),
        'etiquetas_confusion': labels,
    }

def predecir(df_input) -> dict:
    import joblib

    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError("Modelo no entrenado.")

    pipeline = joblib.load(MODEL_PATH)
    
    # 1. Asegurar orden de columnas
    df_input = df_input[ALL_FEATURES].copy()
    
    # 2. FORZADO DE TIPOS EXPLÍCITO (Esto elimina el TypeError)
    for col in NUMERIC_FEATURES:
        df_input[col] = df_input[col].astype(float)
    
    for col in CATEGORICAL_FEATURES:
        df_input[col] = df_input[col].astype(object) # OneHotEncoder necesita object
        
    for col in BOOL_FEATURES:
        df_input[col] = df_input[col].astype(int)

    # 3. Predicción
    riesgo = pipeline.predict(df_input)[0]
    proba = pipeline.predict_proba(df_input)[0]
    clases = list(pipeline.classes_)

    return {
        'riesgo_predicho': riesgo,
        'probabilidades': {cls: round(float(p), 4) for cls, p in zip(clases, proba)},
        'modelo_usado': 'RandomForestClassifier',
    }