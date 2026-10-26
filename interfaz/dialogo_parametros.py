"""Diálogo de parámetros eléctricos y técnicos de un componente.

A la izquierda, el árbol de la taxonomía con los parámetros disponibles en cada nodo;
a la derecha, la tabla de valores del componente. Un componente hereda los parámetros
de todos los niveles de su clasificación (ver db.parametros_heredados).
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget
)

import db
from interfaz.arbol_parametros import ArbolParametros
from interfaz.widgets import aplicar_franjas

PARAMETROS_GENERICOS = ["Tensión de Operación Vcc", "Corriente de Trabajo"]


# -------------------------------------------------------------------
# VENTANA AUXILIAR: PARÁMETROS ELÉCTRICOS (No modal / Independiente)
# -------------------------------------------------------------------
class DialogoParametrosElectricos(QDialog):
    def __init__(self, ruta=(), parametros_existentes=None, solo_lectura=False, parent=None):
        """`ruta`: clasificación del componente (hasta 4 nombres). `solo_lectura`: consulta sin edición."""
        super().__init__(parent)
        self.parent_dialog = parent
        self.ruta = tuple(ruta or ())
        self.solo_lectura = solo_lectura
        self.parametros_existentes = parametros_existentes or []
        self.parametros_resultado = []

        self.setWindowTitle("⚡ Parámetros Eléctricos y Técnicos" + (" (consulta)" if solo_lectura else ""))
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowMaximizeButtonHint)
        self.setWindowState(Qt.WindowState.WindowMaximized)   # siempre abre maximizada

        layout = QVBoxLayout(self)

        clasificacion = " › ".join(self.ruta) if self.ruta else "sin clasificación"
        lbl_info = QLabel(f"Clasificación del componente: {clasificacion}")
        lbl_info.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        lbl_info.setWordWrap(True)
        layout.addWidget(lbl_info)

        divisor = QSplitter(Qt.Orientation.Horizontal)
        divisor.addWidget(self._construir_panel_arbol())
        divisor.addWidget(self._construir_panel_tabla())
        divisor.setStretchFactor(0, 4)
        divisor.setStretchFactor(1, 5)
        layout.addWidget(divisor)

        if solo_lectura:
            btn_cerrar = QPushButton("Cerrar")
            btn_cerrar.setAutoDefault(False)
            btn_cerrar.setDefault(False)
            btn_cerrar.clicked.connect(self.close)
            layout.addWidget(btn_cerrar)
        else:
            btn_aceptar = QPushButton("✔ Confirmar y Volcar a Ventana Principal")
            btn_aceptar.setAutoDefault(False)
            btn_aceptar.setDefault(False)
            btn_aceptar.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 10px; font-size: 13px;")
            btn_aceptar.clicked.connect(self.aceptar_parametros)
            layout.addWidget(btn_aceptar)

        # Cargar los datos iniciales al arrancar la ventana
        self.cargar_datos_iniciales()

    # --- construcción ---------------------------------------------
    def _construir_panel_arbol(self):
        panel = QWidget()
        capa = QVBoxLayout(panel)
        capa.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("Parámetros disponibles según la clasificación:")
        lbl.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        capa.addWidget(lbl)

        self.arbol = ArbolParametros()
        self.arbol.refrescar(abrir=self.ruta)
        capa.addWidget(self.arbol)

        self.lbl_heredados = QLabel("")
        self.lbl_heredados.setWordWrap(True)
        self.lbl_heredados.setStyleSheet("color: #495057; padding: 2px;")
        capa.addWidget(self.lbl_heredados)
        self.arbol.itemSelectionChanged.connect(self.mostrar_heredados)
        self.mostrar_heredados()

        if not self.solo_lectura:
            btn_cargar = QPushButton("➡ Agregar a la tabla los parámetros del nodo elegido")
            btn_cargar.setAutoDefault(False)
            btn_cargar.setDefault(False)
            btn_cargar.setStyleSheet("background-color: #6f42c1; color: white; font-weight: bold; padding: 6px;")
            btn_cargar.clicked.connect(self.agregar_desde_nodo)
            capa.addWidget(btn_cargar)
        return panel

    def _construir_panel_tabla(self):
        panel = QWidget()
        capa = QVBoxLayout(panel)
        capa.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("Valores del componente:")
        lbl.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        capa.addWidget(lbl)

        self.tabla_params = QTableWidget()
        aplicar_franjas(self.tabla_params)
        self.tabla_params.setColumnCount(2)
        self.tabla_params.setHorizontalHeaderLabels(["Parámetro / Propiedad Técnica", "Valor Especificado"])
        self.tabla_params.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabla_params.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        if self.solo_lectura:
            self.tabla_params.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        capa.addWidget(self.tabla_params)

        if not self.solo_lectura:
            layout_botones_fila = QHBoxLayout()
            btn_agregar_fila = QPushButton("➕ Agregar Fila Personalizada")
            btn_agregar_fila.setAutoDefault(False)
            btn_agregar_fila.setDefault(False)
            btn_agregar_fila.setStyleSheet("background-color: #17a2b8; color: white; font-weight: bold; padding: 6px;")
            btn_agregar_fila.clicked.connect(lambda: self.agregar_fila())

            btn_eliminar_fila = QPushButton("🗑️ Quitar Fila Seleccionada")
            btn_eliminar_fila.setAutoDefault(False)
            btn_eliminar_fila.setDefault(False)
            btn_eliminar_fila.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold; padding: 6px;")
            btn_eliminar_fila.clicked.connect(self.eliminar_fila)

            layout_botones_fila.addWidget(btn_agregar_fila)
            layout_botones_fila.addWidget(btn_eliminar_fila)
            capa.addLayout(layout_botones_fila)
        return panel

    # --- árbol -----------------------------------------------------
    def mostrar_heredados(self):
        """Debajo del árbol: todos los parámetros que corresponden al nodo elegido, con el nodo que los define."""
        nodo = self.arbol.nodo_actual()
        if not nodo:
            self.lbl_heredados.setText("Elija un nodo para ver los parámetros que le corresponden.")
            return
        heredados = db.parametros_heredados(nodo)
        if not heredados:
            self.lbl_heredados.setText(f"«{nodo[-1]}» no tiene parámetros definidos.")
            return
        lineas = [f"• {parametro}" + ("" if origen == nodo else f"  (de {origen[-1]})") for parametro, origen in heredados]
        self.lbl_heredados.setText(f"Le corresponden {len(heredados)} parámetros:\n" + "\n".join(lineas))

    def agregar_desde_nodo(self):
        """Suma a la tabla los parámetros del nodo elegido que todavía no están (no toca los que ya tienen valor)."""
        nodo = self.arbol.nodo_actual()
        if not nodo:
            QMessageBox.information(self, "Parámetros", "Elija primero un nodo del árbol.")
            return
        presentes = {self.tabla_params.item(f, 0).text().strip().lower()
                     for f in range(self.tabla_params.rowCount()) if self.tabla_params.item(f, 0)}
        nuevos = [p for p, _ in db.parametros_heredados(nodo) if p.lower() not in presentes]
        if not nuevos:
            QMessageBox.information(self, "Parámetros", "La tabla ya tiene todos los parámetros de ese nodo.")
            return
        for parametro in nuevos:
            self.agregar_fila(parametro, "")

    # --- tabla -----------------------------------------------------
    def obtener_plantilla_por_contexto(self):
        """Nombres de los parámetros que corresponden a la clasificación del componente."""
        plantilla = [parametro for parametro, _ in db.parametros_heredados(self.ruta)] if self.ruta else []
        return plantilla or list(PARAMETROS_GENERICOS)

    def agregar_fila(self, clave="", valor=""):
        row = self.tabla_params.rowCount()
        self.tabla_params.insertRow(row)
        item_clave = QTableWidgetItem(str(clave))
        item_valor = QTableWidgetItem(str(valor))
        self.tabla_params.setItem(row, 0, item_clave)
        self.tabla_params.setItem(row, 1, item_valor)

    def eliminar_fila(self):
        row = self.tabla_params.currentRow()
        if row >= 0:
            self.tabla_params.removeRow(row)

    def cargar_datos_iniciales(self):
        # Si hay parámetros previos pero NO son los genéricos por defecto, los cargamos
        es_generico_viejo = False
        if self.parametros_existentes and len(self.parametros_existentes) == 2:
            nombres_viejos = [str(p[0]) for p in self.parametros_existentes]
            if all(n in nombres_viejos for n in PARAMETROS_GENERICOS):
                es_generico_viejo = True

        if self.parametros_existentes and not es_generico_viejo:
            self.tabla_params.setRowCount(len(self.parametros_existentes))
            for row, param in enumerate(self.parametros_existentes):
                nombre = param[0] if len(param) > 0 else ""
                valor = param[1] if len(param) > 1 else ""
                self.tabla_params.setItem(row, 0, QTableWidgetItem(str(nombre)))
                self.tabla_params.setItem(row, 1, QTableWidgetItem(str(valor)))
            return

        # Sin parámetros previos: se parte de los que corresponden a la clasificación (con herencia)
        if self.solo_lectura:
            return
        plantilla = self.obtener_plantilla_por_contexto()
        self.tabla_params.setRowCount(len(plantilla))
        for row, nombre_param in enumerate(plantilla):
            self.tabla_params.setItem(row, 0, QTableWidgetItem(str(nombre_param)))
            self.tabla_params.setItem(row, 1, QTableWidgetItem(""))

    def aceptar_parametros(self):
        self.parametros_resultado = []
        for row in range(self.tabla_params.rowCount()):
            item_c = self.tabla_params.item(row, 0)
            item_v = self.tabla_params.item(row, 1)
            if item_c and item_c.text().strip():
                val = item_v.text().strip() if item_v else ""
                self.parametros_resultado.append((item_c.text().strip(), val))

        if self.parent_dialog and hasattr(self.parent_dialog, 'recibir_parametros_avanzados'):
            self.parent_dialog.recibir_parametros_avanzados(self.parametros_resultado)

        self.close()
