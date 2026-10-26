"""Ventana para administrar el catálogo de clasificación y las listas de los desplegables.

No contiene consultas: todo el acceso a datos está en db.py.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QHeaderView,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

import db
from interfaz.arbol_parametros import ArbolParametros
from interfaz.widgets import aplicar_franjas

NOMBRES_NIVEL = ("Tipo", "Categoría", "Subcategoría", "Ítem")

# (clave en db.LISTAS, título de la pestaña, ayuda)
LISTAS = (
    ("fabricante", "🏭 Fabricantes", "Opciones del desplegable «Fabricante». También se puede escribir uno nuevo directamente en el formulario."),
    ("interfaz", "🔌 Interfaces", "Opciones de «Interfaz de comunicación». No se permiten comas."),
    ("pines", "📍 Pines relevantes", "Opciones de «Pines relevantes». No se permiten comas."),
    ("encapsulado", "📦 Encapsulados", "Opciones de «Encapsulado». No se permiten comas."),
    ("moneda", "💲 Monedas", "Monedas disponibles junto a los precios."),
    ("proveedor_local", "🏪 Proveedores locales", "Proveedores del país: opciones de «Proveedor Local». También se puede escribir uno nuevo en el formulario."),
    ("proveedor_exterior", "🌎 Proveedores del exterior", "Proveedores del exterior: opciones de «Proveedor Exterior». También se puede escribir uno nuevo en el formulario."),
)

ESTILO_BOTON = "font-weight: bold; padding: 5px 10px; color: white; background-color: %s;"


def _boton(texto, color, accion):
    b = QPushButton(texto)
    b.setAutoDefault(False)
    b.setStyleSheet(ESTILO_BOTON % color)
    b.clicked.connect(accion)
    return b


def _ayuda(texto):
    lbl = QLabel(texto)
    lbl.setWordWrap(True)
    lbl.setStyleSheet("color: #495057; padding: 2px;")
    return lbl


class _PestanaClasificacion(QWidget):
    """Árbol Tipo > Categoría > Subcategoría > Ítem."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(_ayuda(
            "Elija un nodo y pulse «Agregar» para crearle un hijo (sin selección se crea un Tipo nuevo). "
            "Renombrar actualiza también los componentes ya cargados; Eliminar solo quita la opción del catálogo "
            "(los componentes conservan lo que tienen escrito). Un Ítem es el producto concreto (p. ej. Arduino Uno); "
            "en las familias generales el producto real va en el Chip Principal."))

        self.arbol = QTreeWidget()
        self.arbol.setHeaderLabels(["Clasificación", "Nivel"])
        self.arbol.setColumnWidth(0, 520)
        aplicar_franjas(self.arbol)
        layout.addWidget(self.arbol)

        fila = QHBoxLayout()
        fila.addWidget(_boton("➕ Agregar", "#28a745", self.agregar))
        fila.addWidget(_boton("✏️ Renombrar", "#ffc107; color: #212529", self.renombrar))
        fila.addWidget(_boton("🗑️ Eliminar", "#dc3545", self.eliminar))
        fila.addStretch()
        layout.addLayout(fila)

        self.refrescar()

    # --- árbol -----------------------------------------------------
    def refrescar(self, abrir=None):
        """Reconstruye el árbol conservando los nodos abiertos; `abrir` es una ruta que se despliega y selecciona."""
        abiertos = set(self._rutas_abiertas())
        if abrir:
            abiertos |= {tuple(abrir[:k]) for k in range(1, len(abrir))}
        self.arbol.clear()
        nodos = {}
        for fila in db.listar_catalogo():
            ruta = ()
            for nivel, nombre in enumerate(fila):
                if not nombre:
                    break
                ruta += (nombre,)
                if ruta not in nodos:
                    padre = nodos.get(ruta[:-1]) or self.arbol.invisibleRootItem()
                    nodo = QTreeWidgetItem(padre, [nombre, NOMBRES_NIVEL[nivel]])
                    nodo.setData(0, Qt.ItemDataRole.UserRole, ruta)
                    nodos[ruta] = nodo
        for ruta, nodo in nodos.items():
            nodo.setExpanded(ruta in abiertos)
        if abrir and tuple(abrir) in nodos:
            self.arbol.setCurrentItem(nodos[tuple(abrir)])

    def _rutas_abiertas(self):
        pila = [self.arbol.topLevelItem(i) for i in range(self.arbol.topLevelItemCount())]
        while pila:
            nodo = pila.pop()
            if nodo.isExpanded():
                yield nodo.data(0, Qt.ItemDataRole.UserRole)
            pila.extend(nodo.child(i) for i in range(nodo.childCount()))

    def _ruta_elegida(self):
        nodo = self.arbol.currentItem()
        return tuple(nodo.data(0, Qt.ItemDataRole.UserRole)) if nodo else None

    # --- acciones --------------------------------------------------
    def agregar(self):
        padre = self._ruta_elegida() or ()
        if len(padre) >= 4:
            QMessageBox.information(self, "Agregar", "Un Ítem es el último nivel: no puede tener hijos.")
            return
        nivel = NOMBRES_NIVEL[len(padre)]
        nombre, ok = QInputDialog.getText(self, f"Nuevo {nivel}", f"Nombre del nuevo {nivel}:")
        if not ok or not nombre.strip():
            return
        try:
            nueva = db.agregar_catalogo(padre + (nombre.strip(),))
        except ValueError as e:
            QMessageBox.warning(self, "No se pudo agregar", str(e))
            return
        self.refrescar(abrir=nueva)

    def renombrar(self):
        ruta = self._ruta_elegida()
        if not ruta:
            QMessageBox.information(self, "Renombrar", "Elija primero un nodo del árbol.")
            return
        nivel = NOMBRES_NIVEL[len(ruta) - 1]
        usados = db.contar_componentes_catalogo(ruta)
        nuevo, ok = QInputDialog.getText(self, f"Renombrar {nivel}",
                                         f"Nuevo nombre para «{ruta[-1]}»" + (f"\n(se actualizarán {usados} componente(s))" if usados else "") + ":",
                                         text=ruta[-1])
        if not ok or not nuevo.strip() or nuevo.strip() == ruta[-1]:
            return
        try:
            nueva = db.renombrar_catalogo(ruta, nuevo.strip())
        except ValueError as e:
            QMessageBox.warning(self, "No se pudo renombrar", str(e))
            return
        self.refrescar(abrir=nueva)

    def eliminar(self):
        ruta = self._ruta_elegida()
        if not ruta:
            QMessageBox.information(self, "Eliminar", "Elija primero un nodo del árbol.")
            return
        usados = db.contar_componentes_catalogo(ruta)
        texto = f"¿Quitar «{ruta[-1]}» del catálogo"
        texto += " junto con todo lo que contiene?" if len(ruta) < 4 else "?"
        if usados:
            texto += f"\n\n{usados} componente(s) ya cargados conservan su clasificación; solo dejará de ofrecerse en los desplegables."
        if QMessageBox.question(self, "Eliminar", texto, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        db.eliminar_catalogo(ruta)
        self.refrescar(abrir=ruta[:-1] or None)


class _PestanaLista(QWidget):
    """Una lista de valores (fabricantes, interfaces, pines, encapsulados, monedas)."""

    def __init__(self, clave, ayuda, parent=None):
        super().__init__(parent)
        self.clave = clave
        layout = QVBoxLayout(self)
        layout.addWidget(_ayuda(ayuda + (" «N/A» es fija." if clave in db.LISTAS_CON_SIN_DATO else "")))

        self.lista = QListWidget()
        aplicar_franjas(self.lista)
        layout.addWidget(self.lista)

        fila = QHBoxLayout()
        fila.addWidget(_boton("➕ Agregar", "#28a745", self.agregar))
        fila.addWidget(_boton("✏️ Renombrar", "#ffc107; color: #212529", self.renombrar))
        fila.addWidget(_boton("🗑️ Eliminar", "#dc3545", self.eliminar))
        fila.addStretch()
        layout.addLayout(fila)

        self.refrescar()

    def refrescar(self, elegir=None):
        self.lista.clear()
        self.lista.addItems(db.listar_valores(self.clave))
        if elegir:
            for fila in range(self.lista.count()):
                if self.lista.item(fila).text() == elegir:
                    self.lista.setCurrentRow(fila)
                    break

    def _valor_elegido(self):
        item = self.lista.currentItem()
        return item.text() if item else None

    def agregar(self):
        valor, ok = QInputDialog.getText(self, "Agregar", "Nuevo valor:")
        if not ok or not valor.strip():
            return
        try:
            guardado = db.agregar_valor(self.clave, valor)
        except ValueError as e:
            QMessageBox.warning(self, "No se pudo agregar", str(e))
            return
        self.refrescar(elegir=guardado)

    def renombrar(self):
        viejo = self._valor_elegido()
        if viejo is None:
            QMessageBox.information(self, "Renombrar", "Elija primero un valor de la lista.")
            return
        usados = db.contar_uso_valor(self.clave, viejo)
        nuevo, ok = QInputDialog.getText(self, "Renombrar",
                                         f"Nuevo nombre para «{viejo}»" + (f"\n(se actualizarán {usados} componente(s))" if usados else "") + ":",
                                         text=viejo)
        if not ok or not nuevo.strip() or nuevo.strip() == viejo:
            return
        try:
            db.renombrar_valor(self.clave, viejo, nuevo)
        except ValueError as e:
            QMessageBox.warning(self, "No se pudo renombrar", str(e))
            return
        self.refrescar(elegir=nuevo.strip())

    def eliminar(self):
        valor = self._valor_elegido()
        if valor is None:
            QMessageBox.information(self, "Eliminar", "Elija primero un valor de la lista.")
            return
        if valor.upper() == db.SIN_DATO:
            QMessageBox.information(self, "Eliminar", f"«{db.SIN_DATO}» es fija y no se puede eliminar.")
            return
        usados = db.contar_uso_valor(self.clave, valor)
        texto = f"¿Quitar «{valor}» de la lista?"
        if usados:
            texto += f"\n\n{usados} componente(s) ya cargados conservan este valor; solo dejará de ofrecerse en el desplegable."
        if QMessageBox.question(self, "Eliminar", texto, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        db.eliminar_valor(self.clave, valor)
        self.refrescar()


class _PestanaParametros(QWidget):
    """Parámetros disponibles en cada nodo de la taxonomía (se heredan hacia abajo)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(_ayuda(
            "Elija un nodo y pulse «Agregar parámetro». Un componente hereda los parámetros de todos los niveles de su "
            "clasificación: lo común conviene definirlo en el Tipo o la Categoría, y lo particular en la Subcategoría o el Ítem. "
            "Renombrar o quitar un parámetro no modifica los valores ya cargados en los componentes."))

        self.arbol = ArbolParametros()
        layout.addWidget(self.arbol)

        self.lbl_heredados = _ayuda("")
        layout.addWidget(self.lbl_heredados)
        self.arbol.itemSelectionChanged.connect(self.mostrar_heredados)

        fila = QHBoxLayout()
        fila.addWidget(_boton("➕ Agregar parámetro", "#28a745", self.agregar))
        fila.addWidget(_boton("✏️ Renombrar", "#ffc107; color: #212529", self.renombrar))
        fila.addWidget(_boton("🗑️ Quitar", "#dc3545", self.quitar))
        fila.addStretch()
        layout.addLayout(fila)
        self.mostrar_heredados()

    def refrescar(self):
        """Se vuelve a leer todo (el catálogo pudo cambiar en la otra pestaña)."""
        self.arbol.refrescar(abrir=self.arbol.nodo_actual())
        self.mostrar_heredados()

    def mostrar_heredados(self):
        nodo = self.arbol.nodo_actual()
        if not nodo:
            self.lbl_heredados.setText("Elija un nodo para ver todos los parámetros que le corresponden.")
            return
        heredados = db.parametros_heredados(nodo)
        detalle = "; ".join(p + ("" if o == nodo else f" (de {o[-1]})") for p, o in heredados) or "ninguno"
        self.lbl_heredados.setText(f"Parámetros de «{nodo[-1]}» con los heredados ({len(heredados)}): {detalle}")

    def agregar(self):
        nodo = self.arbol.nodo_actual()
        if not nodo:
            QMessageBox.information(self, "Agregar parámetro", "Elija primero un nodo del árbol.")
            return
        nombre, ok = QInputDialog.getText(self, "Nuevo parámetro", f"Nombre del parámetro para «{nodo[-1]}»:")
        if not ok or not nombre.strip():
            return
        try:
            db.agregar_parametro_plantilla(nodo, nombre)
        except ValueError as e:
            QMessageBox.warning(self, "No se pudo agregar", str(e))
            return
        self.arbol.refrescar(abrir=nodo)
        self.mostrar_heredados()

    def renombrar(self):
        elegido = self.arbol.parametro_actual()
        if not elegido:
            QMessageBox.information(self, "Renombrar", "Elija primero un parámetro (los que tienen 📏).")
            return
        nodo, viejo = elegido
        nuevo, ok = QInputDialog.getText(self, "Renombrar parámetro", f"Nuevo nombre para «{viejo}»:", text=viejo)
        if not ok or not nuevo.strip() or nuevo.strip() == viejo:
            return
        try:
            db.renombrar_parametro_plantilla(nodo, viejo, nuevo)
        except ValueError as e:
            QMessageBox.warning(self, "No se pudo renombrar", str(e))
            return
        self.arbol.refrescar(abrir=nodo)
        self.mostrar_heredados()

    def quitar(self):
        elegido = self.arbol.parametro_actual()
        if not elegido:
            QMessageBox.information(self, "Quitar", "Elija primero un parámetro (los que tienen 📏).")
            return
        nodo, nombre = elegido
        if QMessageBox.question(self, "Quitar", f"¿Quitar «{nombre}» de «{nodo[-1]}»?\n\nLos valores ya cargados en componentes se conservan.",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        db.eliminar_parametro_plantilla(nodo, nombre)
        self.arbol.refrescar(abrir=nodo)
        self.mostrar_heredados()


class _PestanaCotizaciones(QWidget):
    """Cotizaciones de las monedas respecto del USD (base del cálculo de capital)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(_ayuda(
            "Escriba cuántas unidades de cada moneda equivalen a 1 USD (por ejemplo, UYU 40,50 significa 1 USD = 40,50 UYU). "
            "La fecha se registra sola cuando cambia el valor. Con estas cotizaciones se calcula el capital en existencia; "
            "una moneda sin cotización no suma. El USD es la moneda base y siempre vale 1. "
            "Las monedas se agregan en la pestaña «Monedas»."))

        self.tabla = QTableWidget()
        aplicar_franjas(self.tabla)
        self.tabla.setColumnCount(3)
        self.tabla.setHorizontalHeaderLabels(["Moneda", "Unidades por 1 USD", "Actualizada"])
        self.tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabla.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.tabla)

        fila = QHBoxLayout()
        fila.addWidget(_boton("💾 Guardar cotizaciones", "#28a745", self.guardar))
        fila.addStretch()
        layout.addLayout(fila)
        self.refrescar()

    @staticmethod
    def _texto(por_usd):
        return "" if por_usd is None else f"{por_usd:.10g}"

    def refrescar(self, conservar=True):
        """Vuelve a leer las cotizaciones (las monedas pudieron cambiar en otra pestaña); con `conservar`, sin perder lo que se está escribiendo."""
        pendientes = {}
        for i in range(self.tabla.rowCount() if conservar else 0):
            moneda, celda = self.tabla.item(i, 0).text(), self.tabla.item(i, 1)
            if celda.text() != self._texto(getattr(self, "guardadas", {}).get(moneda)):
                pendientes[moneda] = celda.text()
        filas = db.listar_cotizaciones()
        self.guardadas = {m: p for m, p, _ in filas}
        self.tabla.setRowCount(len(filas))
        for i, (moneda, por_usd, fecha) in enumerate(filas):
            valor = pendientes.get(moneda, self._texto(por_usd))
            celdas = (QTableWidgetItem(moneda), QTableWidgetItem(valor), QTableWidgetItem(fecha or ""))
            for columna, celda in enumerate(celdas):
                if columna != 1 or moneda.upper() == db.MONEDA_BASE:
                    celda.setFlags(celda.flags() & ~Qt.ItemFlag.ItemIsEditable)     # solo se edita el valor (y no el del USD)
                self.tabla.setItem(i, columna, celda)

    def guardar(self):
        """Valida todo antes de guardar nada; solo escribe (y fecha) las cotizaciones que cambiaron."""
        cambios = []
        for i in range(self.tabla.rowCount()):
            moneda = self.tabla.item(i, 0).text()
            if moneda.upper() == db.MONEDA_BASE:
                continue
            texto = self.tabla.item(i, 1).text().strip().replace(",", ".")
            try:
                valor = float(texto) if texto else None
            except ValueError:
                QMessageBox.warning(self, "Cotización no válida", f"La cotización de {moneda} no es un número: «{self.tabla.item(i, 1).text()}».")
                return
            if valor is not None and not valor > 0:
                QMessageBox.warning(self, "Cotización no válida", f"La cotización de {moneda} debe ser mayor que cero.")
                return
            if valor != self.guardadas.get(moneda):
                cambios.append((moneda, valor))
        for moneda, valor in cambios:
            db.guardar_cotizacion(moneda, valor)
        self.refrescar(conservar=False)
        QMessageBox.information(self, "Cotizaciones", f"Se actualizaron {len(cambios)} cotización(es)." if cambios else "No hubo cambios.")


class DialogoAdministrarCatalogos(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📚 Listas y Catálogo")
        self.setWindowState(Qt.WindowState.WindowMaximized)   # siempre abre maximizada

        layout = QVBoxLayout(self)
        pestanas = QTabWidget()
        pestanas.addTab(_PestanaClasificacion(), "🗂️ Clasificación")
        self.pestana_parametros = _PestanaParametros()
        pestanas.addTab(self.pestana_parametros, "📏 Parámetros")
        for clave, titulo, ayuda in LISTAS:
            pestanas.addTab(_PestanaLista(clave, ayuda), titulo)
        self.pestana_cotizaciones = _PestanaCotizaciones()
        pestanas.addTab(self.pestana_cotizaciones, "💱 Cotizaciones")
        pestanas.currentChanged.connect(lambda _: (self.pestana_parametros.refrescar(), self.pestana_cotizaciones.refrescar()))
        layout.addWidget(pestanas)

        cerrar = QPushButton("Cerrar")
        cerrar.setAutoDefault(False)
        cerrar.clicked.connect(self.accept)
        layout.addWidget(cerrar, alignment=Qt.AlignmentFlag.AlignRight)
