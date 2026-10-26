"""Ventana con el capital en existencia: subtotales por clasificación, detalle y exportación a Excel."""
import os
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget
)

import capital
from interfaz.widgets import COLOR_ALERTA, aplicar_franjas

COLUMNAS_DETALLE = ("Tipo", "Categoría", "Subcategoría", "Ítem", "Chip Principal", "Stock", "Precio usado", "Moneda",
                    "Origen", "Unit. (USD)", "Total (USD)", "Estado")


def _celda(texto, derecha=False, alerta=False):
    celda = QTableWidgetItem(str(texto))
    celda.setFlags(celda.flags() & ~Qt.ItemFlag.ItemIsEditable)
    if derecha:
        celda.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    if alerta:
        celda.setBackground(QColor(COLOR_ALERTA))
    return celda


class DialogoCapital(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("💰 Capital en existencia")
        self.setWindowState(Qt.WindowState.WindowMaximized)   # siempre abre maximizada
        self.datos = None
        self._carpeta = os.path.expanduser("~")

        layout = QVBoxLayout(self)
        self.lbl_total = QLabel("")
        self.lbl_total.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        layout.addWidget(self.lbl_total)
        self.lbl_avisos = QLabel("")
        self.lbl_avisos.setWordWrap(True)
        layout.addWidget(self.lbl_avisos)

        self.pestanas = QTabWidget()
        self.arbol = QTreeWidget()
        self.arbol.setHeaderLabels(["Clasificación", "Componentes", "Unidades", "Capital (USD)", "% del total"])
        self.arbol.setColumnWidth(0, 460)
        aplicar_franjas(self.arbol)
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(len(COLUMNAS_DETALLE))
        self.tabla.setHorizontalHeaderLabels(list(COLUMNAS_DETALLE))
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSortingEnabled(False)
        aplicar_franjas(self.tabla)
        self.pestanas.addTab(self.arbol, "Subtotales por clasificación")
        self.pestanas.addTab(self.tabla, "Detalle de componentes")
        layout.addWidget(self.pestanas)

        botones = QHBoxLayout()
        btn_actualizar = QPushButton("🔄 Actualizar")
        btn_actualizar.setAutoDefault(False)
        btn_actualizar.clicked.connect(self.cargar)
        btn_excel = QPushButton("📊 Exportar a Excel")
        btn_excel.setAutoDefault(False)
        btn_excel.setStyleSheet("background-color: #198754; color: white; font-weight: bold; padding: 6px;")
        btn_excel.clicked.connect(self.exportar)
        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.setAutoDefault(False)
        btn_cerrar.clicked.connect(self.close)
        botones.addWidget(btn_actualizar)
        botones.addStretch()
        botones.addWidget(btn_excel)
        botones.addWidget(btn_cerrar)
        layout.addLayout(botones)
        self.cargar()

    # --- datos -----------------------------------------------------
    def cargar(self):
        self.datos = datos = capital.calcular()
        total = datos["total_usd"]
        self.lbl_total.setText(f"Capital total: USD {capital.formato_monto(total)}   ·   {datos['unidades']} unidades en {len(datos['filas'])} componentes")
        avisos = []
        if datos["sin_precio"]:
            avisos.append(f"{datos['sin_precio']} componente(s) sin precio")
        if datos["sin_cotizacion"]:
            avisos.append(f"{datos['sin_cotizacion']} sin cotización de {', '.join(datos['monedas_sin_cotizacion'])} "
                          "(cárguela en «📚 Listas y Catálogo» › «💱 Cotizaciones»)")
        self.lbl_avisos.setText("⚠ No suman al capital: " + "; ".join(avisos) if avisos else "")
        self.lbl_avisos.setStyleSheet("color: #856404;")
        self._llenar_arbol(datos, total)
        self._llenar_detalle(datos["filas"])

    def _llenar_arbol(self, datos, total):
        self.arbol.clear()
        nodos, camino_de = {}, {}
        for camino, monto, cantidad, unidades in capital.subtotales(datos["filas"]):
            padre = nodos.get(camino[:-1]) or self.arbol.invisibleRootItem()
            porcentaje = f"{monto / total * 100:.1f} %" if total else ""
            nodo = QTreeWidgetItem(padre, [camino[-1], str(cantidad), str(unidades), capital.formato_monto(monto), porcentaje])
            for col in (1, 2, 3, 4):
                nodo.setTextAlignment(col, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            nodos[camino] = nodo
            camino_de[id(nodo)] = camino
        for nodo in nodos.values():
            nodo.setExpanded(len(camino_de[id(nodo)]) == 1)

    def _llenar_detalle(self, filas):
        self.tabla.setRowCount(len(filas))
        orden = sorted(filas, key=lambda f: tuple((f[k] or "").lower() for k in ("tipo_componente", "categoria", "subcategoria", "item_especifico", "chip_principal")))
        for i, f in enumerate(orden):
            v = f["valor"]
            alerta = v["estado"] != capital.ESTADO_OK
            valores = [f["tipo_componente"] or capital.SIN_DEFINIR, f["categoria"] or capital.SIN_DEFINIR,
                       f["subcategoria"] or capital.SIN_DEFINIR, f["item_especifico"] or capital.SIN_DEFINIR,
                       f["chip_principal"] or "", f["stock"] or 0,
                       capital.formato_monto(v["precio"]) if v["precio"] else "", v["moneda"], v["origen"],
                       capital.formato_monto(v["unitario_usd"]) if v["unitario_usd"] is not None else "",
                       capital.formato_monto(v["total_usd"]) if v["unitario_usd"] is not None else "", v["estado"]]
            for j, valor in enumerate(valores):
                self.tabla.setItem(i, j, _celda(valor, derecha=j in (5, 6, 9, 10), alerta=alerta))

    # --- exportación -----------------------------------------------
    def exportar(self):
        datos = self.datos or capital.calcular()
        if not datos["filas"]:
            QMessageBox.information(self, "Exportar capital", "No hay componentes cargados.")
            return
        sugerido = os.path.join(self._carpeta, f"Capital_Inventario_{date.today():%Y-%m-%d}.xlsx")
        destino, _ = QFileDialog.getSaveFileName(self, "Guardar planilla de capital", sugerido, "Planilla de Excel (*.xlsx)")
        if not destino:
            return
        if not destino.lower().endswith(".xlsx"):
            destino += ".xlsx"
        try:
            capital.exportar_xlsx(destino, datos)
        except capital.ExportError as e:
            QMessageBox.critical(self, "No se pudo generar la planilla", str(e))
            return
        except OSError as e:
            QMessageBox.critical(self, "No se pudo guardar el archivo",
                                 f"{e}\n\nSi la planilla está abierta en Excel, ciérrela y vuelva a intentarlo.")
            return
        self._carpeta = os.path.dirname(destino)
        QMessageBox.information(self, "Capital exportado", f"Planilla guardada en:\n{destino}")
