"""Widgets propios reutilizables."""
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QInputDialog, QLineEdit, QListWidget, QMenu, QMessageBox,
                             QTableWidget, QTreeWidget, QWidgetAction)


COLOR_FILA_A = "#FFF9D9"      # amarillo pálido
COLOR_FILA_B = "#E3ECF2"      # celeste grisáceo
COLOR_ALERTA = "#F8D7DA"      # rosado: filas con problemas (distinto de las dos franjas)


def aplicar_franjas(widget):
    """Pinta las filas de una grilla (tabla, árbol o lista) en colores alternados, con selección azul."""
    nombre = next(n for n, tipo in (("QTableWidget", QTableWidget), ("QTreeWidget", QTreeWidget), ("QListWidget", QListWidget))
                  if isinstance(widget, tipo))      # el selector del estilo vale también para las subclases
    widget.setAlternatingRowColors(True)
    widget.setStyleSheet(f"""
        {nombre} {{
            background-color: {COLOR_FILA_A};
            alternate-background-color: {COLOR_FILA_B};
            gridline-color: #CBD2D6;
            color: #1B2631;
        }}
        {nombre}::item:selected {{
            background-color: #007bff;
            color: #ffffff;
        }}
    """)


class LineEditSeguro(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyleSheet("background-color: #ffffff; color: #000000; border: 1px solid #ccc; padding: 3px;")

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            event.ignore()
        else:
            super().keyPressEvent(event)


# -------------------------------------------------------------------
# COMBOBOX CON CHECKBOXES MÚLTIPLES UNIVERSAL
# -------------------------------------------------------------------
class ComboBoxMultiCheckbox(QComboBox):
    """Desplegable con casillas. Si se da `on_nueva`, el menú ofrece «Agregar nueva opción…».

    on_nueva(texto) debe guardar la opción donde corresponda y devolver el texto definitivo
    (o lanzar ValueError con el motivo si no es válida).
    """
    def __init__(self, items, parent=None, on_nueva=None):
        super().__init__(parent)
        self.items = items
        self.checkboxes = {}
        self._on_nueva = on_nueva
        self._separador = None

        self.setStyleSheet("background-color: #ffffff; color: #000000;")
        self.menu_desplegable = QMenu(self)

        for item_texto in self.items:
            self._crear_casilla(item_texto)

        if on_nueva is not None:
            self._separador = self.menu_desplegable.addSeparator()
            accion_nueva = self.menu_desplegable.addAction("➕ Agregar nueva opción…")
            accion_nueva.triggered.connect(self._pedir_nueva_opcion)

        self.setMaxVisibleItems(20)
        self.actualizar_texto_seleccionado()

    def _crear_casilla(self, texto):
        chk = QCheckBox(texto, self.menu_desplegable)
        chk.stateChanged.connect(self.actualizar_texto_seleccionado)
        self.checkboxes[texto] = chk

        action = QWidgetAction(self.menu_desplegable)
        action.setDefaultWidget(chk)
        if self._separador is not None:
            self.menu_desplegable.insertAction(self._separador, action)   # antes del «Agregar nueva…»
        else:
            self.menu_desplegable.addAction(action)
        return chk

    def agregar_opcion(self, texto, marcar=False):
        """Agrega una opción al menú (si no estaba) y, con `marcar`, la deja elegida."""
        chk = self.checkboxes.get(texto) or self._crear_casilla(texto)
        if marcar:
            chk.setChecked(True)

    def _pedir_nueva_opcion(self):
        texto, aceptado = QInputDialog.getText(self, "Nueva opción", "Nombre de la nueva opción:")
        if not aceptado or not texto.strip():
            return
        try:
            definitivo = self._on_nueva(texto)
        except ValueError as e:
            QMessageBox.warning(self, "Opción no válida", str(e))
            return
        self.agregar_opcion(definitivo, marcar=True)

    def showPopup(self):
        point = self.mapToGlobal(QPoint(0, self.height()))
        self.menu_desplegable.exec(point)

    def actualizar_texto_seleccionado(self):
        seleccionadas = []
        chk_na = self.checkboxes.get("N/A")
        sender_chk = self.sender()

        if sender_chk == chk_na and chk_na and chk_na.isChecked():
            for texto, chk in self.checkboxes.items():
                if texto != "N/A":
                    chk.blockSignals(True)
                    chk.setChecked(False)
                    chk.blockSignals(False)
        elif sender_chk and sender_chk != chk_na and chk_na and chk_na.isChecked():
            if sender_chk.isChecked():
                chk_na.blockSignals(True)
                chk_na.setChecked(False)
                chk_na.blockSignals(False)

        for texto, chk in self.checkboxes.items():
            if chk.isChecked():
                seleccionadas.append(texto)

        texto_final = ", ".join(seleccionadas) if seleccionadas else "N/A"
        if not seleccionadas and chk_na:
            chk_na.blockSignals(True)
            chk_na.setChecked(True)
            chk_na.blockSignals(False)
            texto_final = "N/A"

        self.blockSignals(True)
        self.clear()
        self.addItem(texto_final)
        self.setCurrentIndex(0)
        self.blockSignals(False)

    def text(self):
        return self.itemText(0)

    def set_seleccionadas(self, texto_guardado):
        if not texto_guardado:
            texto_guardado = "N/A"
        
        elementos = [e.strip() for e in str(texto_guardado).split(",")]
        for e in elementos:
            if e and e not in self.checkboxes:
                self.agregar_opcion(e)       # valor guardado que ya no está en la lista: se conserva
        for texto, chk in self.checkboxes.items():
            chk.blockSignals(True)
            chk.setChecked(texto in elementos)
            chk.blockSignals(False)
        
        if "N/A" in elementos and len(elementos) == 1:
            if "N/A" in self.checkboxes:
                self.checkboxes["N/A"].setChecked(True)

        self.actualizar_texto_seleccionado()
