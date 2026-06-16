#!/usr/bin/env bash
# Script de build para Render.
# Render lo ejecuta automáticamente antes de arrancar el servidor.

set -o errexit  # Detiene el script si algún comando falla

echo "==> Instalando dependencias..."
pip install -r requirements.txt

echo "==> Recolectando archivos estáticos..."
python manage.py collectstatic --no-input

echo "==> Aplicando migraciones..."
python manage.py migrate

echo "==> Creando usuarios base (si no existen)..."
python manage.py crear_usuarios_base

echo "==> Build completado."