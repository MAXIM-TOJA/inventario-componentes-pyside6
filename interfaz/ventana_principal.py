"""Ventana principal: búsqueda, listado y acciones sobre componentes."""
import qrcode

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont, QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget
)

import almacenamiento
import db
from interfaz.dialogo_capital import DialogoCapital
from interfaz.dialogo_catalogos import DialogoAdministrarCatalogos
from interfaz.dialogo_componente import DialogoNuevoComponente
from interfaz.dialogo_etiquetas import DialogoImpresionEtiquetas
from interfaz.dialogo_parametros import DialogoParametrosElectricos
from interfaz.visor_pdf import abrir_documento
from interfaz.widgets import aplicar_franjas
from utilidades import limpiar_prefijo, sin_comodin


# -------------------------------------------------------------------
# VENTANA PRINCIPAL DE LA APLICACIÓN
# -------------------------------------------------------------------
class AppInventario(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gestión de Inventario de Componentes")
        self.setWindowState(Qt.WindowState.WindowMaximized)   # siempre abre maximizada
        self.selected_component = None
        self.ventanas_hijas_principales = []
        self.init_ui()
        self.cargar_comboboxes_cascada()
        self.filtrar_tabla()

    def init_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout()

        panel_preview = QFrame()
        panel_preview.setFrameShape(QFrame.Shape.StyledPanel)
        panel_preview.setStyleSheet("background-color: #f8f9fa;")
        layout_preview = QHBoxLayout()

        self.lbl_imagen = QLabel("Sin Imagen")
        self.lbl_imagen.setFixedSize(140, 110)
        self.lbl_imagen.setStyleSheet("border: 1px solid #ccc; background-color: #ffffff;")
        self.lbl_imagen.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_preview.addWidget(self.lbl_imagen)

        layout_info = QVBoxLayout()
        self.lbl_titulo = QLabel("Seleccione un componente...")
        self.lbl_titulo.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.lbl_detalles = QLabel("Categoría: - | Subcat: - | Ítem: - \nUbicación: - | Stock: - | Precio: $\nChip: - | Interfaz: -\nDescripción: -")
        self.lbl_detalles.setStyleSheet("color: #495057;")
        self.lbl_detalles.setWordWrap(True)      # sin esto, una línea larga fija el ancho mínimo de la ventana y no entra en pantallas chicas
        layout_info.addWidget(self.lbl_titulo)
        layout_info.addWidget(self.lbl_detalles)
        layout_preview.addLayout(layout_info)

        # --- CREACIÓN DEL WIDGET PARA EL CÓDIGO QR ---
        self.lbl_qr = QLabel("Sin QR")
        self.lbl_qr.setFixedSize(110, 110)
        self.lbl_qr.setStyleSheet("border: 1px solid #ccc; background-color: #ffffff;")
        self.lbl_qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_preview.addWidget(self.lbl_qr)
        # ---------------------------------------------
        layout_docs = QVBoxLayout()
        tamanio_boton = QSize(120, 26)

        # Botón de Datasheets
        self.btn_open_ds = QPushButton("📄 Ver Datasheets")
        self.btn_open_ds.setFixedSize(tamanio_boton)
        self.btn_open_ds.setStyleSheet("background-color: #17a2b8; color: white; font-weight: bold; padding: 6px;")
        self.btn_open_ds.clicked.connect(lambda: self.abrir_archivo_asociado("datasheet"))

        # Botón de tutoriales
        self.btn_open_tut = QPushButton("📘 Ver Tutoriales")
        self.btn_open_tut.setFixedSize(tamanio_boton)
        self.btn_open_tut.setStyleSheet("background-color: #17a2b8; color: white; font-weight: bold; padding: 6px;")
        self.btn_open_tut.clicked.connect(lambda: self.abrir_archivo_asociado("tutorial"))

        # Botón de Esquemas
        self.btn_open_esq = QPushButton(" Ver Esquemas")
        self.btn_open_esq.setFixedSize(tamanio_boton)
        self.btn_open_esq.setStyleSheet("background-color: #17a2b8; color: white; font-weight: bold; padding: 6px;")
        self.btn_open_esq.clicked.connect(lambda: self.abrir_archivo_asociado("esquema"))

        # Botón de Parámetros Avanzados (Único y correctamente conectado)
        self.btn_ver_parametros = QPushButton("⚙️ Ver Parámetros")
        self.btn_ver_parametros.setFixedSize(tamanio_boton)
        self.btn_ver_parametros.setStyleSheet("background-color: #17a2b8; color: white; font-weight: bold; padding: 6px;")
        self.btn_ver_parametros.clicked.connect(self.abrir_dialogo_parametros_avanzados)

        # layout_docs.addStretch()
        layout_docs.addWidget(self.btn_open_ds)
        layout_docs.addWidget(self.btn_open_tut)
        layout_docs.addWidget(self.btn_open_esq) # <--- Añadido al panel lateral
        layout_docs.addWidget(self.btn_ver_parametros) # <--- Añadido al panel lateral correctamente
        
        layout_preview.addLayout(layout_docs)
        panel_preview.setLayout(layout_preview)
        main_layout.addWidget(panel_preview)

        box_filtros = QGroupBox("Filtros de Seleccion Indepediente")
        layout_filtros = QHBoxLayout()

        self.combo_tipo = QComboBox(); self.combo_tipo.setMaximumWidth(200); self.combo_tipo.setStyleSheet("background-color: #ffffff; color: #000000;")
        self.combo_cat = QComboBox(); self.combo_cat.setMaximumWidth(200); self.combo_cat.setStyleSheet("background-color: #ffffff; color: #000000;")
        self.combo_subcat = QComboBox(); self.combo_subcat.setMaximumWidth(200); self.combo_subcat.setStyleSheet("background-color: #ffffff; color: #000000;")
        self.combo_item = QComboBox(); self.combo_item.setMaximumWidth(200); self.combo_item.setStyleSheet("background-color: #ffffff; color: #000000;")

        self.combo_tipo.currentIndexChanged.connect(self.on_tipo_changed)
        self.combo_cat.currentIndexChanged.connect(self.on_cat_changed)
        self.combo_subcat.currentIndexChanged.connect(self.on_subcat_changed)
        self.combo_item.currentIndexChanged.connect(self.filtrar_tabla)

        layout_filtros.addWidget(QLabel("1. Tipo:"))
        layout_filtros.addWidget(self.combo_tipo)
        layout_filtros.addWidget(QLabel("2. Cat:"))
        layout_filtros.addWidget(self.combo_cat)
        layout_filtros.addWidget(QLabel("3. Sub:"))
        layout_filtros.addWidget(self.combo_subcat)
        layout_filtros.addWidget(QLabel("4. Ítem:"))
        layout_filtros.addWidget(self.combo_item)
        box_filtros.setLayout(layout_filtros)
        main_layout.addWidget(box_filtros)

        layout_acciones = QHBoxLayout()
        btn_eliminar = QPushButton("❌ Eliminar")
        btn_eliminar.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold; padding: 6px;")
        btn_eliminar.clicked.connect(self.eliminar_registro)
        layout_acciones.addWidget(btn_eliminar)

        self.txt_buscar = QLineEdit()
        self.txt_buscar.setPlaceholderText("🔍 Buscar por Nombre, Descripción, Fabricante, Chip...")
        self.txt_buscar.setStyleSheet("background-color: #ffffff; color: #000000;")
        self.txt_buscar.textChanged.connect(self.filtrar_tabla)
        layout_acciones.addWidget(self.txt_buscar)

        btn_nuevo = QPushButton("+ Nuevo")
        btn_nuevo.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 6px;")
        btn_nuevo.clicked.connect(self.abrir_nuevo_dialogo)

        btn_editar = QPushButton("✏️ Editar")
        btn_editar.setStyleSheet("background-color: #ffc107; color: #212529; font-weight: bold; padding: 6px;")
        btn_editar.clicked.connect(self.abrir_editar_dialogo)

        btn_imprimir = QPushButton("🖨️ Imprimir Selección")
        btn_imprimir.setStyleSheet("background-color: #000080; color: white; font-weight: bold; padding: 6px;")
        btn_imprimir.clicked.connect(self.abrir_impresion)

        btn_catalogos = QPushButton("📚 Listas y Catálogo")
        btn_catalogos.setStyleSheet("background-color: #6f42c1; color: white; font-weight: bold; padding: 6px;")
        btn_catalogos.clicked.connect(self.abrir_administrador_catalogos)

        btn_capital = QPushButton("💰 Capital")
        btn_capital.setStyleSheet("background-color: #198754; color: white; font-weight: bold; padding: 6px;")
        btn_capital.clicked.connect(self.abrir_capital)

        layout_acciones.addWidget(btn_nuevo)
        layout_acciones.addWidget(btn_editar)
        layout_acciones.addWidget(btn_catalogos)
        layout_acciones.addWidget(btn_capital)
        layout_acciones.addWidget(btn_imprimir)
        main_layout.addLayout(layout_acciones)

        self.table = QTableWidget()
        self.table.setColumnCount(19)
        self.table.setHorizontalHeaderLabels([
            "ID", "Nombre", "Chip Principal", "Tipo", "Categoría", "Subcategoría", "Ítem Específico", 
            "Descripción", "Fabricante", "Interfaz", "Pines", "Stock", "Precio ($)", "Ubicación", "QR Path",
            "Precio Ext.", "Prov. Ext.", "Precio Loc.", "Prov. Loc."
        ])
        self.table.setColumnHidden(0, True)
        self.table.setColumnHidden(1, True)
        self.table.setColumnHidden(14, True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self.on_row_selected)

        header = self.table.horizontalHeader()
        header.setStyleSheet("""
            QHeaderView::section {
                background-color: #000000 !important;
                color: #FFFFFF !important;
                font-weight: bold;
                font-size: 11px;
                padding: 6px;
                border: 1px solid #333333;
            }
        """)

        aplicar_franjas(self.table)

        main_layout.addWidget(self.table)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

    def cargar_comboboxes_cascada(self):
        self.combo_tipo.blockSignals(True)
        self.combo_tipo.clear()
        self.combo_tipo.addItem("-- Todos los Tipos --")
        for t in db.listar_tipos():
            self.combo_tipo.addItem(t)
        self.combo_tipo.blockSignals(False)
        self.on_tipo_changed()

    def on_tipo_changed(self):
        tipo = limpiar_prefijo(self.combo_tipo.currentText())
        self.combo_subcat.blockSignals(True); self.combo_subcat.clear(); self.combo_subcat.addItem("-- Todas las Subcat --"); self.combo_subcat.blockSignals(False)
        self.combo_item.blockSignals(True); self.combo_item.clear(); self.combo_item.addItem("-- Todos los Ítems --"); self.combo_item.blockSignals(False)

        categorias = db.listar_categorias(sin_comodin(tipo, "-- Todos los Tipos --"))

        self.combo_cat.blockSignals(True)
        self.combo_cat.clear()
        self.combo_cat.addItem("-- Todas las Categorías --")
        self.combo_cat.addItems(categorias)
        self.combo_cat.blockSignals(False)
        
        # Filtra inmediatamente al cambiar el Tipo
        self.filtrar_tabla()

    def on_cat_changed(self):
        tipo = limpiar_prefijo(self.combo_tipo.currentText())
        cat = self.combo_cat.currentText()
        self.combo_item.blockSignals(True); self.combo_item.clear(); self.combo_item.addItem("-- Todos los Ítems --"); self.combo_item.blockSignals(False)

        subcats = db.listar_subcategorias(sin_comodin(tipo, "-- Todos los Tipos --"), sin_comodin(cat, "-- Todas las Categorías --"))

        self.combo_subcat.blockSignals(True)
        self.combo_subcat.clear()
        self.combo_subcat.addItem("-- Todas las Subcat --")
        self.combo_subcat.addItems(subcats)
        self.combo_subcat.blockSignals(False)
        
        # Filtra inmediatamente al cambiar la Categoría
        self.filtrar_tabla()

    def on_subcat_changed(self):
        tipo = limpiar_prefijo(self.combo_tipo.currentText())
        cat = self.combo_cat.currentText()
        subcat = self.combo_subcat.currentText()

        items = db.listar_items(
            tipo=sin_comodin(tipo, "-- Todos los Tipos --"),
            cat=sin_comodin(cat, "-- Todas las Categorías --"),
            subcat=sin_comodin(subcat, "-- Todas las Subcat --"),
        )

        self.combo_item.blockSignals(True)
        self.combo_item.clear()
        self.combo_item.addItem("-- Todos los Ítems --")
        self.combo_item.addItems(items)
        self.combo_item.blockSignals(False)
        
        # Filtra inmediatamente al cambiar la Subcategoría
        self.filtrar_tabla()

    def filtrar_tabla(self):
        tipo = limpiar_prefijo(self.combo_tipo.currentText())
        cat = self.combo_cat.currentText()
        subcat = self.combo_subcat.currentText()
        item = self.combo_item.currentText()
        busqueda = self.txt_buscar.text().strip()

        rows = db.buscar_componentes(
            tipo=sin_comodin(tipo, "-- Todos los Tipos --"),
            cat=sin_comodin(cat, "-- Todas las Categorías --"),
            subcat=sin_comodin(subcat, "-- Todas las Subcat --"),
            item=sin_comodin(item, "-- Todos los Ítems --"),
            texto=busqueda,
        )

        self.table.setRowCount(0)
        for row_idx, row_data in enumerate(rows):
            self.table.insertRow(row_idx)
            
            # El índice 6 es el ítem específico exacto de la base de datos
            item_especifico_exacto = row_data[6] if len(row_data) > 6 and row_data[6] else ""
            
            for col_idx, value in enumerate(row_data):
                val_str = str(value if value is not None else "")
                if col_idx in [12, 15, 17]: # Precios
                    try:
                        val_str = f"{float(val_str):.2f}"
                    except ValueError:
                        pass
                item_table = QTableWidgetItem(val_str)
                item_table.setFlags(item_table.flags() & ~Qt.ItemFlag.ItemIsEditable)
                
                # INYECTAMOS EL ÍTEM ESPECÍFICO DE FORMA OCULTA EN CADA CELDA DE LA FILA
                item_table.setData(Qt.ItemDataRole.UserRole, item_especifico_exacto)
                
                self.table.setItem(row_idx, col_idx, item_table)
        self.table.resizeColumnsToContents()

    def limpiar_y_verificar_archivos(self, componente_id):
        if not componente_id:
            return

        # Obtener todos los archivos asociados al componente
        registros = db.listar_archivos_con_id(componente_id)

        ids_a_borrar = []
        for reg_id, tipo, ruta in registros:
            # Si la ruta está vacía o el archivo no existe físicamente en disco
            if not ruta or not almacenamiento.existe(ruta):
                ids_a_borrar.append(reg_id)

        # Purgar de la base de datos las referencias rotas de forma totalmente transparente
        if ids_a_borrar:
            db.eliminar_archivos_por_id(ids_a_borrar)

        # Volver a consultar los archivos limpios para la interfaz
        self.archivos_seleccionado = almacenamiento.resolver_archivos(db.listar_archivos(componente_id))
        
    def on_row_selected(self):
        selected_rows = self.table.selectionModel().selectedRows()
        
        # Si no hay nada seleccionado o se marcan múltiples filas, limpiamos la vista previa y la imagen
        if not selected_rows or len(selected_rows) > 1:
            self.selected_component = None
            self.lbl_titulo.setText("Seleccione un componente...")
            self.lbl_detalles.setText("Categoría: - | Subcat: - | Ítem: - \nUbicación: - | Stock: - | Precio: $\nChip: - | Interfaz: -\nDescripción: -")
            self.lbl_imagen.clear()
            self.lbl_imagen.setText("Sin Imagen")
            self.lbl_qr.clear()          # <--- Limpiar QR al deseleccionar
            self.lbl_qr.setText("Sin QR")  # <--- Texto por defecto
            return

        row = selected_rows[0].row()
        item_id = self.table.item(row, 0).text()

        # ---> LLAMADA CLAVE: Se ejecuta de forma invisible y automática al hacer clic <---
        self.limpiar_y_verificar_archivos(item_id)

        componente = db.obtener_componente(item_id)
        self.archivos_seleccionado = almacenamiento.resolver_archivos(db.listar_archivos(item_id))
        self.params_seleccionado = db.listar_parametros(item_id)

        if componente:
            self.selected_component = componente
            
            str_params = ""
            if self.params_seleccionado:
                lista_p = [f"{k}: {v}" for k, v in self.params_seleccionado if v.strip()]
                if lista_p:
                    str_params = f" | Parámetros: [{', '.join(lista_p)}]"

            self.lbl_titulo.setText(f"{self.selected_component.get('nombre', '')} - {self.selected_component.get('fabricante', '')}")
            
            try:
                precio_ext = float(self.selected_component.get('precio_exterior', 0) or 0)
            except (ValueError, TypeError):
                precio_ext = 0.00

            try:
                precio_loc = float(self.selected_component.get('precio_local', 0) or 0)
            except (ValueError, TypeError):
                precio_loc = 0.00

            prov_ext = self.selected_component.get('proveedor_exterior', '-') or '-'
            prov_loc = self.selected_component.get('proveedor_local', '-') or '-'

            detalles = (
                f"Categoría: {self.selected_component.get('categoria', '')} | Subcat: {self.selected_component.get('subcategoria', '')} | Ítem: {self.selected_component.get('item_especifico', '')}\n"
                f"Ubicación: {self.selected_component.get('ubicacion', '')} | Stock: {self.selected_component.get('stock', 0)} | Ext: ${precio_ext:.2f} ({prov_ext}) | Loc: ${precio_loc:.2f} ({prov_loc}){str_params}\n"
                f"Fabricante: {self.selected_component.get('fabricante', 'N/A')} | Chip: {self.selected_component.get('chip_principal', 'N/A')}\n"
                f"Interfaz: {self.selected_component.get('interfaz_comunicacion', 'N/A')} | Pines: {self.selected_component.get('pines_relevantes', 'N/A')}\n"
                f"Descripción: {self.selected_component.get('descripcion', '')[:45]}"
            )
            self.lbl_detalles.setText(detalles)

            foto_ruta = ""
            for t, nom, ruta in self.archivos_seleccionado:
                if t == 'imagen' and ruta and almacenamiento.existe(ruta):
                    foto_ruta = ruta
                    break

            if foto_ruta:
                pixmap = QPixmap(foto_ruta).scaled(140, 110, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.lbl_imagen.setPixmap(pixmap)
            else:
                self.lbl_imagen.clear()
                self.lbl_imagen.setText("Sin Imagen")

            chip = str(self.selected_component.get('chip_principal', '')).strip() or "N/A"
            item = str(self.selected_component.get('item_especifico', '')).strip()
            if not item or item.startswith("--"):
                item = "N/A"
            desc = str(self.selected_component.get('descripcion', '')[:45]).strip()[:45] or "N/A"
            stock = str(self.selected_component.get('stock', '0')).strip() or "0"
            ubicacion = str(self.selected_component.get('ubicacion', '')).strip() or "N/A"
            
            qr_texto = f"CHIP: {chip} | ITEM: {item} | DESC: {desc} | STOCK: {stock} | UBIC: {ubicacion}"
        
            try:
                import qrcode
                import io
                from PySide6.QtGui import QImage
                
                qr = qrcode.QRCode(version=1, box_size=3, border=1)
                qr.add_data(qr_texto)
                qr.make(fit=True)
                img_qr = qr.make_image(fill_color="black", back_color="white")
                
                buffer = io.BytesIO()
                img_qr.save(buffer, format="PNG")
                qimage = QImage.fromData(buffer.getvalue())
                pixmap_qr = QPixmap.fromImage(qimage)
                self.lbl_qr.setPixmap(pixmap_qr.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            except Exception as e:
                self.lbl_qr.setText("Error QR")

    def abrir_archivo_asociado(self, tipo):
        # Validación de seguridad: Verificar si hay un componente seleccionado en la grilla
        if not self.selected_component:
            QMessageBox.warning(self, "Atención", f"Por favor, seleccione un componente de la grilla para ver sus {tipo}s.")
            return

        if not hasattr(self, 'archivos_seleccionado') or not self.archivos_seleccionado:
            QMessageBox.information(self, "Información", f"No hay archivos de tipo '{tipo}' adjuntos para este componente.")
            return

        # Buscamos tanto la ruta como el nombre amigable que le diste al archivo
        filtrados = [(nom, ruta) for t, nom, ruta in self.archivos_seleccionado if t == tipo and almacenamiento.existe(ruta)]
        
        if not filtrados:
            QMessageBox.information(self, "Información", f"No se encontraron archivos físicos de tipo '{tipo}'.")
            return

        # CASO 1: Si hay un solo archivo, lo abre directamente como antes
        if len(filtrados) == 1:
            nombre_amigable, ruta_archivo = filtrados[0]
            visor = abrir_documento(self, ruta_archivo, nombre_amigable)
            if visor is not None:
                self.ventanas_hijas_principales.append(visor)
            return

        # CASO 2: Si hay MÚLTIPLES archivos, mostramos una ventanita de selección con sus nombres amigables
        nombres = [item[0] for item in filtrados]
        item_seleccionado, ok = QInputDialog.getItem(
            self, 
            f"Seleccionar {tipo.capitalize()}", 
            f"Este componente tiene varios {tipo}s. Elija uno para abrir:", 
            nombres, 
            0, 
            False
        )

        if ok and item_seleccionado:
            # Buscamos la ruta correspondiente al nombre amigable elegido
            ruta_elegida = next(ruta for nom, ruta in filtrados if nom == item_seleccionado)
            visor = abrir_documento(self, ruta_elegida, item_seleccionado)
            if visor is not None:
                self.ventanas_hijas_principales.append(visor)

    def abrir_nuevo_dialogo(self):
        """Flujo exclusivo y limpio para crear un componente nuevo."""
        dialogo = DialogoNuevoComponente(datos_componente=None, parent=self)
        self.ventanas_hijas_principales.append(dialogo)
        dialogo.show()
        dialogo.finished.connect(lambda: (self.cargar_comboboxes_cascada(), self.filtrar_tabla()))

    def abrir_administrador_catalogos(self):
        """Ventana para agregar, renombrar y quitar entradas del catálogo y de las listas de los desplegables."""
        DialogoAdministrarCatalogos(parent=self).exec()
        self.cargar_comboboxes_cascada()
        self.filtrar_tabla()

    def abrir_capital(self):
        """Muestra el capital en existencia en una grilla (con opción de exportarlo a Excel)."""
        DialogoCapital(self).exec()

    def abrir_dialogo_parametros_avanzados(self):
        """Consulta los parámetros guardados del componente seleccionado, junto al árbol de la taxonomía."""
        if not self.selected_component:
            QMessageBox.warning(self, "Atención", "Por favor, seleccione un componente de la grilla para ver sus parámetros.")
            return
        c = self.selected_component
        ruta = db.ruta_de_clasificacion(c.get('tipo_componente'), c.get('categoria'), c.get('subcategoria'), c.get('item_especifico'))
        dialogo = DialogoParametrosElectricos(
            ruta=ruta,
            parametros_existentes=getattr(self, 'params_seleccionado', []),
            solo_lectura=True,
            parent=self
        )
        dialogo.exec()

    def abrir_editar_dialogo(self):
        """Flujo exclusivo para editar un componente existente de la grilla."""
        if not self.selected_component:
            QMessageBox.warning(self, "Atención", "Por favor, seleccione un componente de la grilla para editar.")
            return

        dialogo = DialogoNuevoComponente(datos_componente=self.selected_component, parent=self)
        self.ventanas_hijas_principales.append(dialogo)
        dialogo.show()
        dialogo.finished.connect(lambda: (self.cargar_comboboxes_cascada(), self.filtrar_tabla()))

    def eliminar_registro(self):
        if not self.selected_component:
            QMessageBox.warning(self, "Atención", "Por favor, seleccione un componente para eliminar.")
            return
        confirm = QMessageBox.question(self, "Confirmar", f"¿Eliminar {self.selected_component['nombre']}?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            db.eliminar_componente(self.selected_component['id'])
            self.selected_component = None
            self.lbl_titulo.setText("Seleccione un componente...")
            self.lbl_detalles.setText("Categoría: - | Subcat: - | Ítem: - \nUbicación: - | Stock: - | Precio: $\nChip: - | Interfaz: -\nDescripción: -")
            self.lbl_imagen.clear()
            self.lbl_imagen.setText("Sin Imagen")
            self.cargar_comboboxes_cascada()
            self.filtrar_tabla()

    def abrir_impresion(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Atención", "Seleccione al menos un componente en la tabla para imprimir.")
            return

        componentes_imprimir = []
        for r in selected_rows:
            item_id = self.table.item(r.row(), 0).text()
            nombre = self.table.item(r.row(), 1).text()
            fabricante = self.table.item(r.row(), 8).text()
            encapsulado = "N/A"
            ubicacion = self.table.item(r.row(), 13).text()
            componentes_imprimir.append({
                'id': item_id, 'nombre': nombre, 'ubicacion': ubicacion, 
                'fabricante': fabricante, 'encapsulado': encapsulado
            })

        dialogo = DialogoImpresionEtiquetas(componentes_imprimir, self)
        self.ventanas_hijas_principales.append(dialogo)
        dialogo.show()
