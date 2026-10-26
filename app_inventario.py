"""Punto de entrada de la aplicación de inventario de componentes electrónicos.

Solo prepara carpetas y base de datos y abre la ventana principal.
"""
import sys

from PySide6.QtWidgets import QApplication

import almacenamiento
import db
from config import asegurar_directorios
from interfaz.ventana_principal import AppInventario

# Crear las carpetas necesarias y luego la base de datos (mismo orden que antes)
asegurar_directorios()
db.inicializar_base_de_datos()

# Mover a la papelera los documentos del almacén que ningún componente usa (no borra nada).
# Un fallo aquí no debe impedir abrir la aplicación.
try:
    almacenamiento.limpiar_huerfanos(db.listar_rutas_archivos())
except Exception as e:
    print(f"No se pudo revisar el almacén de documentos: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # ---> APLICAR ESTILO GLOBAL DE NEGRITA <---
    app.setStyleSheet("QWidget { font-weight: bold; }")

    window = AppInventario()
    window.show()
    sys.exit(app.exec())
