"""Rutas de la aplicación.

Importar este módulo NO toca el disco. Las carpetas se crean al llamar a
asegurar_directorios(), que la aplicación invoca una sola vez al arrancar.
"""
import os
import sys

# Detectar si estamos ejecutando como un archivo compilado (.exe) o como script de Python
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# La base de datos se guarda dentro de la misma carpeta de la aplicación
DB_DIR = os.path.join(BASE_DIR, "Base_Inventario")
DB_PATH = os.path.join(DB_DIR, "inventario_electronica.sqlite3")

ATTACHMENTS_DIR = os.path.join(BASE_DIR, "adjuntos")
TMP_DIR = os.path.join(ATTACHMENTS_DIR, "tmp")

# Aquí se escribe el PDF de etiquetas generado (siempre el mismo lugar, sin importar desde dónde se ejecute la aplicación)
ETIQUETAS_DIR = os.path.join(BASE_DIR, "Etiquetas")


def asegurar_directorios():
    """Crea las carpetas que la aplicación espera encontrar (idempotente)."""
    os.makedirs(DB_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)
    os.makedirs(ETIQUETAS_DIR, exist_ok=True)
