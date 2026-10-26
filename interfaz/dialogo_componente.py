"""Diálogo de alta y edición de un componente."""
import qrcode

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPixmap, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget
)

import almacenamiento
import db
from interfaz.dialogo_parametros import DialogoParametrosElectricos
from interfaz.editor_imagen import DialogoEditorImagen
from interfaz.visor_pdf import abrir_documento
from interfaz.widgets import ComboBoxMultiCheckbox, LineEditSeguro
from utilidades import limpiar_prefijo, sin_comodin


# -------------------------------------------------------------------
# VENTANA: ALTA Y EDICIÓN DE COMPONENTE ANTERIOR
# -------------------------------------------------------------------
class DialogoNuevoComponente(QDialog):
    def __init__(self, datos_componente=None, parent=None):
        super().__init__(parent)
        self.datos_componente = datos_componente
        self.is_editing = datos_componente is not None
        
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowMaximizeButtonHint | Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowCloseButtonHint)
        self.setWindowTitle("✏️ Editar Componente" if self.is_editing else "+ Nuevo Componente")
        self.setWindowState(Qt.WindowState.WindowMaximized)   # siempre abre maximizada
        
        self.archivos_lista = []
        self.parametros_electricos_temp = []
        self.ventanas_hijas_abiertas = []
        self._estilos_originales = {}      # estilo de cada campo, para atenuarlo al deshabilitarlo
        self._cargando_datos = False       # True mientras se vuelcan los datos guardados al formulario
        self._marco_chip_encendido = False
        self._timer_chip = QTimer(self)    # hace parpadear el marco del Chip Principal al crear un componente
        self._timer_chip.timeout.connect(self._alternar_marco_chip)

        self.init_ui()
        self.cargar_combos_enlazados()

        if self.is_editing:
            self._cargando_datos = True
            try:
                self.cargar_datos_existentes()
            finally:
                self._cargando_datos = False
            self.bloquear_campos_completos()
        else:
            self.actualizar_habilitacion_campos()
            
        self.actualizar_qr_en_vivo()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        container_widget = QWidget()
        container_widget.setStyleSheet("background-color: #f8f9fa;")
        
        layout_principal = QVBoxLayout(container_widget)
        layout_principal.setContentsMargins(25, 20, 25, 20)
        layout_principal.setSpacing(15)
        self._construir_cabecera(layout_principal)
        self._construir_checkbox_edicion(layout_principal)
        self._construir_clasificacion(layout_principal)
        self._construir_proveedores(layout_principal)
        self._construir_precios(layout_principal)
        self._construir_obsolescencia(layout_principal)
        self._construir_boton_parametros(layout_principal)
        self._construir_archivos(layout_principal)
        self._construir_boton_guardar(layout_principal)
        self._activar_mayusculas()

        scroll_area.setWidget(container_widget)
        main_layout.addWidget(scroll_area)
        self.refrescar_combos_multianexo()

    def _construir_cabecera(self, layout_principal):
        """Miniatura, título del componente y vista previa del QR."""
        header_layout = QHBoxLayout()
        self.lbl_miniatura = QLabel("Sin Imagen")
        self.lbl_miniatura.setFixedSize(110, 110)
        self.lbl_miniatura.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_miniatura.setStyleSheet("background-color: #ffffff; color: #555; font-size: 11px; border: 1px solid #ccc;")
        header_layout.addWidget(self.lbl_miniatura)

        self.lbl_nombre_titulo = QLabel("NOMBRE DEL COMPONENTE")
        self.lbl_nombre_titulo.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.lbl_nombre_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_nombre_titulo.setStyleSheet("color: #000000;")
        header_layout.addWidget(self.lbl_nombre_titulo)

        qr_container = QVBoxLayout()
        qr_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_qr_preview = QLabel("QR Preview")
        self.lbl_qr_preview.setFixedSize(110, 110)
        self.lbl_qr_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_qr_preview.setStyleSheet("background-color: #ffffff; color: #555; font-size: 10px; border: 1px solid #ccc;")
        lbl_qr_titulo = QLabel("Código QR Etiqueta")
        lbl_qr_titulo.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        lbl_qr_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr_container.addWidget(self.lbl_qr_preview)
        qr_container.addWidget(lbl_qr_titulo)
        header_layout.addLayout(qr_container)

        layout_principal.addLayout(header_layout)
        layout_principal.addSpacing(10)

    def _construir_checkbox_edicion(self, layout_principal):
        """Casilla para habilitar la edición completa (solo al editar)."""
        if self.is_editing:
            self.chk_habilitar_edicion = QCheckBox("🔓 Habilitar edición completa (permitir modificar campos llenos)")
            self.chk_habilitar_edicion.setFont(QFont("Arial", 9, QFont.Weight.Bold))
            self.chk_habilitar_edicion.setStyleSheet("color: #007bff; margin-bottom: 5px;")
            self.chk_habilitar_edicion.stateChanged.connect(self.toggle_habilitar_edicion)
            layout_principal.addWidget(self.chk_habilitar_edicion)

    def _construir_clasificacion(self, layout_principal):
        """Clasificación, descripción y datos técnicos en cuadrícula."""
        self.combo_tipo = QComboBox(); self.combo_tipo.setEditable(True); self.combo_tipo.setPlaceholderText("Seleccione Tipo..."); self.combo_tipo.setMaximumWidth(280); self.combo_tipo.setStyleSheet("background-color: #ffffff; color: #000000;")
        self.combo_cat = QComboBox(); self.combo_cat.setEditable(True); self.combo_cat.setPlaceholderText("Seleccione Categoría..."); self.combo_cat.setMaximumWidth(280); self.combo_cat.setStyleSheet("background-color: #ffffff; color: #000000;")
        self.combo_subcat = QComboBox(); self.combo_subcat.setEditable(True); self.combo_subcat.setPlaceholderText("Seleccione Subcategoría..."); self.combo_subcat.setMaximumWidth(280); self.combo_subcat.setStyleSheet("background-color: #ffffff; color: #000000;")
        self.combo_item = QComboBox(); self.combo_item.setEditable(True); self.combo_item.setPlaceholderText("Seleccione Ítem Específico..."); self.combo_item.setMaximumWidth(280); self.combo_item.setStyleSheet("background-color: #ffffff; color: #000000;")

        self.combo_tipo.currentIndexChanged.connect(self.on_tipo_changed)
        self.combo_cat.currentIndexChanged.connect(self.on_cat_changed)
        self.combo_subcat.currentIndexChanged.connect(self.on_subcat_changed)
        self.combo_item.currentIndexChanged.connect(self.actualizar_qr_en_vivo)
        # Los cuatro combos de clasificación gobiernan qué campos están habilitados al crear un componente.
        self.combo_item.currentIndexChanged.connect(self.actualizar_habilitacion_campos)
        for combo in (self.combo_tipo, self.combo_cat, self.combo_subcat, self.combo_item):
            combo.editTextChanged.connect(self.actualizar_habilitacion_campos)

        self.txt_descripcion = QTextEdit()
        self.txt_descripcion.setPlaceholderText("Ej: Conv. Analógico-Digital I2C 16-bit...")
        self.txt_descripcion.setFixedHeight(60)
        self.txt_descripcion.setMaximumWidth(280)
        self.txt_descripcion.setStyleSheet("background-color: #ffffff; color: #000000;")
        self.txt_descripcion.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.txt_descripcion.textChanged.connect(self.formatear_descripcion_en_vivo)

        self.lbl_contador_desc = QLabel("Max caracteres imprimibles: 45 | Actuales: 0")
        self.lbl_contador_desc.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        self.lbl_contador_desc.setStyleSheet("color: #28a745;")

        layout_desc_container = QVBoxLayout()
        layout_desc_container.setSpacing(2)
        layout_desc_container.addWidget(self.txt_descripcion)
        layout_desc_container.addWidget(self.lbl_contador_desc)

        self.combo_fabricante = QComboBox()
        self.combo_fabricante.setEditable(True)
        self.combo_fabricante.addItems(db.listar_valores('fabricante'))
        self.combo_fabricante.setMaximumWidth(280)
        self.combo_fabricante.setStyleSheet("background-color: #ffffff; color: #000000;")

        self.txt_chip = LineEditSeguro()
        self.txt_chip.setPlaceholderText("Ej: HD44780")
        self.txt_chip.setMaximumWidth(280)
        self.txt_chip.setStyleSheet("background-color: #ffffff; color: #000000; border: 2px solid red; padding: 3px;")
        self.txt_chip.textChanged.connect(self.actualizar_titulo_componente)
        self.txt_chip.textChanged.connect(self.actualizar_habilitacion_campos)
        
        self.combo_interfaz = ComboBoxMultiCheckbox(db.listar_valores('interfaz'), on_nueva=lambda t: db.agregar_valor('interfaz', t))
        self.combo_interfaz.setMaximumWidth(280)

        self.combo_pines = ComboBoxMultiCheckbox(db.listar_valores('pines'), on_nueva=lambda t: db.agregar_valor('pines', t))
        self.combo_pines.setMaximumWidth(280)
        
        self.combo_encapsulado = ComboBoxMultiCheckbox(db.listar_valores('encapsulado'), on_nueva=lambda t: db.agregar_valor('encapsulado', t))
        self.combo_encapsulado.setMaximumWidth(280)
        
        self.txt_ubicacion = LineEditSeguro(); self.txt_ubicacion.setPlaceholderText("Ej: BOX-1"); self.txt_ubicacion.setMaximumWidth(280)
        self.txt_ubicacion.textChanged.connect(self.actualizar_qr_en_vivo)

        self.txt_stock = LineEditSeguro(); self.txt_stock.setPlaceholderText("Ej: 10"); self.txt_stock.setMaximumWidth(280)
        self.txt_stock.textChanged.connect(self.actualizar_qr_en_vivo)

        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)

        campos_pares = [
            (0, "1. Tipo de Componente:", self.combo_tipo, "7. Chip Principal:", self.txt_chip),
            (1, "2. Categoría:", self.combo_cat, "8. Interfaz de Comunicación:", self.combo_interfaz),
            (2, "3. Subcategoría:", self.combo_subcat, "9. Pines Relevantes:", self.combo_pines),
            (3, "4. Ítem Específico:", self.combo_item, "10. Encapsulado:", self.combo_encapsulado),
            (4, "5. Descripción:", layout_desc_container, "11. Ubicación Física:", self.txt_ubicacion),
            (5, "6. Fabricante:", self.combo_fabricante, "12. Stock:", self.txt_stock)
        ]

        for row, lbl1_text, widget1, lbl2_text, widget2 in campos_pares:
            lbl1 = QLabel(lbl1_text); lbl1.setFont(QFont("Arial", 9, QFont.Weight.Bold))
            lbl2 = QLabel(lbl2_text); lbl2.setFont(QFont("Arial", 9, QFont.Weight.Bold))
            
            grid_layout.addWidget(lbl1, row, 0)
            if isinstance(widget1, QVBoxLayout):
                grid_layout.addLayout(widget1, row, 1)
            else:
                grid_layout.addWidget(widget1, row, 1)
                
            grid_layout.addWidget(lbl2, row, 2)
            grid_layout.addWidget(widget2, row, 3)

        layout_principal.addLayout(grid_layout)
        layout_principal.addSpacing(5)

    def _crear_combo_proveedor(self, lista):
        """Desplegable editable de proveedores (encabezado «N/A»); se puede escribir uno nuevo."""
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems(db.listar_valores(lista))
        combo.setStyleSheet("background-color: #ffffff; color: #000000;")
        return combo

    def _construir_proveedores(self, layout_principal):
        """Fila de proveedores (exterior y local)."""
        # --- Fila 1: Proveedores ---
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(10)

        lbl_pve = QLabel("Proveedor Exterior:"); lbl_pve.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        self.combo_proveedor_exterior = self._crear_combo_proveedor('proveedor_exterior')
        
        lbl_pvl = QLabel("Proveedor Local:"); lbl_pvl.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        self.combo_proveedor_local = self._crear_combo_proveedor('proveedor_local')

        row1_layout.addWidget(lbl_pve)
        row1_layout.addWidget(self.combo_proveedor_exterior, 2)
        row1_layout.addWidget(lbl_pvl)
        row1_layout.addWidget(self.combo_proveedor_local, 2)

        layout_principal.addLayout(row1_layout)
        layout_principal.addSpacing(5)

    def _construir_precios(self, layout_principal):
        """Fila de precios y monedas."""
# --- Fila 2: Precios, Monedas y Campos de Precio Compactos ---
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(5)  # Menor separación entre elementos contiguos

        lbl_pe = QLabel("Precio Exterior:"); lbl_pe.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        self.combo_moneda_ext = QComboBox()
        self.combo_moneda_ext.addItems(db.listar_valores('moneda'))
        self.combo_moneda_ext.setMaximumWidth(60)
        self.txt_precio_exterior = LineEditSeguro(); self.txt_precio_exterior.setPlaceholderText("0.00"); self.txt_precio_exterior.setMaximumWidth(70)

        lbl_pl = QLabel("Precio Local:"); lbl_pl.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        self.combo_moneda_local = QComboBox()
        self.combo_moneda_local.addItems(db.listar_valores('moneda'))
        self.combo_moneda_local.setMaximumWidth(60)
        self.txt_precio_local = LineEditSeguro(); self.txt_precio_local.setPlaceholderText("0.00"); self.txt_precio_local.setMaximumWidth(70)

# Obtener valores guardados solo si estamos editando y el diccionario existe
        if self.datos_componente:
            moneda_local_guardada = self.datos_componente.get('moneda_local', 'USD')
            moneda_ext_guardada = self.datos_componente.get('moneda_exterior', 'USD')
        else:
            moneda_local_guardada = 'USD'
            moneda_ext_guardada = 'USD'

        # Una moneda guardada que ya no esté en la lista se agrega al desplegable para no cambiarla sin querer
        moneda_local_guardada = moneda_local_guardada or 'USD'
        moneda_ext_guardada = moneda_ext_guardada or 'USD'
        for combo, moneda in ((self.combo_moneda_local, moneda_local_guardada), (self.combo_moneda_ext, moneda_ext_guardada)):
            if combo.findText(moneda) < 0:
                combo.addItem(moneda)
        self.combo_moneda_local.setCurrentText(moneda_local_guardada)
        self.combo_moneda_ext.setCurrentText(moneda_ext_guardada)

        # Añadimos los elementos del bloque exterior
        row2_layout.addWidget(lbl_pe)
        row2_layout.addWidget(self.combo_moneda_ext, 0)
        row2_layout.addWidget(self.txt_precio_exterior, 0)
        
        # Espacio de separación prudente entre el grupo exterior y el local
        row2_layout.addSpacing(25)

        # Añadimos los elementos del bloque local
        row2_layout.addWidget(lbl_pl)
        row2_layout.addWidget(self.combo_moneda_local, 0)
        row2_layout.addWidget(self.txt_precio_local, 0)
        
        # El stretch final empuja todo a la izquierda, evitando espacios vacíos gigantes entre los controles
        row2_layout.addStretch(1)

        layout_principal.addLayout(row2_layout)
        layout_principal.addSpacing(10)        # layout_principal.addLayout(grid_layout)

    def _construir_obsolescencia(self, layout_principal):
        """Botones de opción de obsolescencia."""
        # --- INICIO: Bloque de Radio Buttons para Obsolescencia ---
        
        obsolescencia_layout = QHBoxLayout()
        obsolescencia_layout.setSpacing(10)

        lbl_obsolescencia = QLabel("Obsolescencia:")
        lbl_obsolescencia.setFont(QFont("Arial", 9, QFont.Weight.Bold))

        self.rb_obsolescencia_si = QRadioButton("Sí")
        self.rb_obsolescencia_no = QRadioButton("No")

        self.grupo_obsolescencia = QButtonGroup(self)
        self.grupo_obsolescencia.addButton(self.rb_obsolescencia_si)
        self.grupo_obsolescencia.addButton(self.rb_obsolescencia_no)
        self.rb_obsolescencia_no.setChecked(True)  # Por defecto seleccionado "No"

        obsolescencia_layout.addWidget(lbl_obsolescencia)
        obsolescencia_layout.addWidget(self.rb_obsolescencia_si)
        obsolescencia_layout.addWidget(self.rb_obsolescencia_no)
        obsolescencia_layout.addStretch()# Empuja los radio buttons hacia la izquierda

        layout_principal.addLayout(obsolescencia_layout)
        layout_principal.addSpacing(10)
        # --- FIN: Bloque de Radio Buttons para Obsolescencia ---

    def _construir_boton_parametros(self, layout_principal):
        """Botón de parámetros eléctricos y técnicos avanzados."""
        self.btn_params_avanzados = QPushButton("⚡ Configurar Parámetros Eléctricos y Técnicos Avanzados")
        self.btn_params_avanzados.setAutoDefault(False); self.btn_params_avanzados.setDefault(False)
        self.btn_params_avanzados.setStyleSheet("background-color: #6f42c1; color: white; font-weight: bold; padding: 10px; font-size: 13px;")
        self.btn_params_avanzados.clicked.connect(self.abrir_dialogo_parametros_avanzados)
        layout_principal.addWidget(self.btn_params_avanzados)

    def _construir_archivos(self, layout_principal):
        """Sección de archivos múltiples (imágenes, datasheets, tutoriales, esquemas)."""
        layout_principal.addSpacing(10)
        lbl_adj = QLabel("Gestión de Archivos Múltiples (Imágenes, Datasheets, Tutoriales, Esquemas)")
        lbl_adj.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        layout_principal.addWidget(lbl_adj)

        self.chk_habilitar_quitar = QCheckBox("🗑️ Habilitar botón 'Quitar' en archivos múltiples")
        self.chk_habilitar_quitar.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        self.chk_habilitar_quitar.setStyleSheet("color: #dc3545; margin-bottom: 5px;")
        self.chk_habilitar_quitar.setChecked(False)
        self.chk_habilitar_quitar.stateChanged.connect(self.toggle_habilitar_quitar)
        layout_principal.addWidget(self.chk_habilitar_quitar)

        self.botones_quitar = []

        layout_principal.addLayout(self.create_seccion_multianexo("imagen", "📸 Imágenes:"))
        layout_principal.addLayout(self.create_seccion_multianexo("datasheet", "📄 Datasheets:"))
        layout_principal.addLayout(self.create_seccion_multianexo("tutorial", "📘 Tutoriales:"))
        layout_principal.addLayout(self.create_seccion_multianexo("esquema", "📐 Esquemas:"))

    def _construir_boton_guardar(self, layout_principal):
        """Botón de guardar o actualizar."""
        layout_principal.addSpacing(15)
        btn_text = "💾 Actualizar Registro" if self.is_editing else "💾 Guardar Registro Completo"
        btn_guardar = QPushButton(btn_text)
        btn_guardar.setAutoDefault(False); btn_guardar.setDefault(False)
        btn_guardar.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 12px; font-size: 14px;")
        btn_guardar.clicked.connect(self.guardar_todo_unificado)
        layout_principal.addWidget(btn_guardar)


    def recibir_parametros_avanzados(self, parametros):
        self.parametros_electricos_temp = parametros
        QMessageBox.information(self, "Parámetros Retenidos", f"Se han sincronizado {len(parametros)} parámetros eléctricos técnicos desde la ventana auxiliar.")

    def generar_texto_qr_actual(self):
        chip = self.txt_chip.text().strip() or "N/A"
        item = self.combo_item.currentText().strip()
        if not item or item.startswith("--"):
            item = "N/A"
        desc = self.txt_descripcion.toPlainText().strip()[:45] or "N/A"
        stock = self.txt_stock.text().strip() or "0"
        ubicacion = self.txt_ubicacion.text().strip() or "N/A"
        
        return f"CHIP: {chip} | ITEM: {item} | DESC: {desc} | STOCK: {stock} | UBIC: {ubicacion}"

    def actualizar_qr_en_vivo(self):
        texto_qr = self.generar_texto_qr_actual()
        qr = qrcode.QRCode(version=1, box_size=3, border=1)
        qr.add_data(texto_qr)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white")
        
        path_tmp = almacenamiento.guardar_temporal(img_qr, "qr_preview_actual.png")
        
        if almacenamiento.existe(path_tmp):
            pix = QPixmap(path_tmp).scaled(110, 110, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.lbl_qr_preview.setPixmap(pix)

    def formatear_descripcion_en_vivo(self):
        self.txt_descripcion.blockSignals(True)
        cursor = self.txt_descripcion.textCursor()
        pos_actual = cursor.position()
        
        texto_plano = self.txt_descripcion.toPlainText()
        if not self._cargando_datos:                 # lo que se escribe va en mayúsculas; lo guardado se muestra tal cual
            texto_plano = texto_plano.upper()
        largo = len(texto_plano)
        
        self.txt_descripcion.setPlainText(texto_plano)
        
        documento = self.txt_descripcion.document()
        cursor_formato = QTextCursor(documento)
        
        cursor_formato.setPosition(0)
        cursor_formato.setPosition(min(45, largo), QTextCursor.MoveMode.KeepAnchor)
        fmt_negrita = QTextCharFormat()
        fmt_negrita.setFontWeight(QFont.Weight.Bold)
        cursor_formato.mergeCharFormat(fmt_negrita)
        
        if largo > 45:
            cursor_formato.setPosition(45)
            cursor_formato.setPosition(largo, QTextCursor.MoveMode.KeepAnchor)
            fmt_normal = QTextCharFormat()
            fmt_normal.setFontWeight(QFont.Weight.Normal)
            cursor_formato.mergeCharFormat(fmt_normal)

        cursor.setPosition(min(pos_actual, largo))
        self.txt_descripcion.setTextCursor(cursor)
        self.txt_descripcion.blockSignals(False)

        if largo <= 45:
            self.lbl_contador_desc.setText(f"Max caracteres imprimibles: 45 | Actuales: {largo}")
            self.lbl_contador_desc.setStyleSheet("color: #28a745; font-weight: bold;")
        elif largo <= 60:
            self.lbl_contador_desc.setText(f"Max caracteres imprimibles: 45 | Actuales: {largo}")
            self.lbl_contador_desc.setStyleSheet("color: #e67e22; font-weight: bold;")
        else:
            self.lbl_contador_desc.setText(f"Max caracteres imprimibles: 45 | Actuales: {largo}")
            self.lbl_contador_desc.setStyleSheet("color: #dc3545; font-weight: bold;")
            
        self.actualizar_qr_en_vivo()

    
    def abrir_dialogo_parametros_avanzados(self):
        """Abre la ventana de parámetros ubicada en la clasificación que tiene el formulario en este momento."""
        ruta = db.ruta_de_clasificacion(
            limpiar_prefijo(self.combo_tipo.currentText()),
            self.combo_cat.currentText().strip(),
            self.combo_subcat.currentText().strip(),
            self.combo_item.currentText().strip(),
        )
        dialogo = DialogoParametrosElectricos(
            ruta=ruta,
            parametros_existentes=getattr(self, 'parametros_electricos_temp', []),
            parent=self
        )

        resultado = dialogo.exec()
        if getattr(resultado, 'value', resultado) == QDialog.DialogCode.Accepted.value:   # exec() devuelve int o enum según la versión
            self.parametros_electricos_temp = dialogo.parametros_resultado
            if hasattr(self, 'recibir_parametros_avanzados'):
                self.recibir_parametros_avanzados(self.parametros_electricos_temp)

    def create_seccion_multianexo(self, tipo, etiqueta_texto):
        hbox = QHBoxLayout()
        lbl = QLabel(etiqueta_texto)
        lbl.setFixedWidth(120)
        lbl.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        
        combo = QComboBox()
        combo.setMinimumWidth(250)
        combo.setMaximumWidth(280)
        combo.setStyleSheet("background-color: #ffffff; color: #000000;")
        
        if tipo == "imagen":
            self.combo_imagenes = combo
            combo.currentIndexChanged.connect(self.on_imagen_seleccionada)
        elif tipo == "datasheet":
            self.combo_datasheets = combo
        elif tipo == "tutorial":
            self.combo_tutoriales = combo
        elif tipo == "esquema":
            self.combo_esquemas = combo

        btn_add = QPushButton("➕ Agregar")
        btn_add.setAutoDefault(False); btn_add.setDefault(False)
        btn_add.setFixedWidth(90)
        btn_add.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 5px;")
        btn_add.clicked.connect(lambda checked, t=tipo: self.agregar_archivo_multianexo(t))

        btn_ver = QPushButton("👁️ Ver")
        btn_ver.setAutoDefault(False); btn_ver.setDefault(False)
        btn_ver.setFixedWidth(80)
        btn_ver.setStyleSheet("background-color: #007bff; color: white; font-weight: bold; padding: 5px;")
        btn_ver.clicked.connect(lambda checked, t=tipo: self.ver_archivo_multianexo(t))

        btn_del = QPushButton("🗑️ Quitar")
        btn_del.setAutoDefault(False); btn_del.setDefault(False)
        btn_del.setFixedWidth(80)
        btn_del.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold; padding: 5px;")
        btn_del.setEnabled(False)
        btn_del.clicked.connect(lambda checked, t=tipo: self.quitar_archivo_multianexo(t))
        self.botones_quitar.append(btn_del)

        hbox.addWidget(lbl)
        hbox.addWidget(combo)
        hbox.addWidget(btn_add)
        hbox.addWidget(btn_ver)
        hbox.addWidget(btn_del)
        return hbox

    def actualizar_titulo_componente(self, texto):
        nombre = texto.strip()
        if nombre:
            self.lbl_nombre_titulo.setText(nombre.upper())
        else:
            self.lbl_nombre_titulo.setText("NOMBRE DEL COMPONENTE")
        self.actualizar_qr_en_vivo()

    # -------------------------------------------------------------------
    # Habilitación de campos
    #   Nuevo componente: solo los 4 combos de clasificación hasta que los cuatro tengan valor.
    #   Edición: los 4 combos siempre bloqueados; el resto, solo los campos vacíos
    #            (o todos, con la casilla "Habilitar edición completa").
    #   Archivos: agregar siempre habilitado; "Quitar" solo con su casilla.
    # -------------------------------------------------------------------
    _GRIS = "; background-color: #e9ecef; color: #6c757d;"

    def _combos_clasificacion(self):
        return [self.combo_tipo, self.combo_cat, self.combo_subcat, self.combo_item]

    def _campos_dependientes(self):
        """Todos los campos del formulario salvo los 4 combos de clasificación."""
        return [
            self.txt_descripcion, self.combo_fabricante, self.txt_chip,
            self.combo_interfaz, self.combo_pines, self.combo_encapsulado,
            self.txt_ubicacion, self.txt_stock,
            self.combo_proveedor_exterior, self.txt_precio_exterior, self.combo_moneda_ext,
            self.combo_proveedor_local, self.txt_precio_local, self.combo_moneda_local,
            self.rb_obsolescencia_si, self.rb_obsolescencia_no,
            self.btn_params_avanzados,
        ]

    def _poner_habilitado(self, widget, habilitado):
        """Habilita o deshabilita un campo y lo atenúa (sus estilos propios no lo harían solos)."""
        original = self._estilos_originales.setdefault(id(widget), widget.styleSheet())
        widget.setEnabled(habilitado)
        if original:
            nuevo = original if habilitado else original + self._GRIS
            if widget.styleSheet() != nuevo:
                widget.setStyleSheet(nuevo)

    @staticmethod
    def _combo_definido(combo):
        """True si el combo tiene una selección real (no vacío ni '-- Todas las ... --')."""
        texto = combo.currentText().strip()
        return bool(texto) and not texto.startswith("--")

    def actualizar_habilitacion_campos(self, *_):
        """Componente nuevo, en tres pasos:
        1) solo los 4 combos de clasificación;
        2) con los 4 definidos, se habilita el Chip Principal (con el marco parpadeando);
        3) con el chip escrito, se habilita el resto de los campos.
        """
        if self.is_editing:
            return
        clasificacion = all(self._combo_definido(c) for c in self._combos_clasificacion())
        chip_escrito = bool(self.txt_chip.text().strip())
        self._poner_habilitado(self.txt_chip, clasificacion)
        for widget in self._campos_dependientes():
            if widget is not self.txt_chip:
                self._poner_habilitado(widget, clasificacion and chip_escrito)
        self._parpadeo_chip(clasificacion and not chip_escrito)

    # Marco grueso intermitente del Chip Principal (de 4 px, igual tamaño total que el estilo normal)
    _MARCO_CHIP_ON = "background-color: #ffffff; color: #000000; border: 4px solid #ff0000; padding: 1px;"
    _MARCO_CHIP_OFF = "background-color: #ffffff; color: #000000; border: 4px solid #f8f9fa; padding: 1px;"

    def _parpadeo_chip(self, activo):
        if activo:
            if not self._timer_chip.isActive():
                self._marco_chip_encendido = False
                self._alternar_marco_chip()
                self._timer_chip.start(500)
        else:
            self._timer_chip.stop()
            self._marco_chip_encendido = False

    def _alternar_marco_chip(self):
        if not self.txt_chip.isEnabled():
            return
        self._marco_chip_encendido = not self._marco_chip_encendido
        self.txt_chip.setStyleSheet(self._MARCO_CHIP_ON if self._marco_chip_encendido else self._MARCO_CHIP_OFF)

    # Mayúsculas al escribir
    @staticmethod
    def _a_mayusculas(line_edit):
        """Convierte a mayúsculas lo que el usuario escribe en un QLineEdit (no lo que se carga por programa)."""
        def convertir(texto, le=line_edit):
            if texto != texto.upper():
                pos = le.cursorPosition()
                le.setText(texto.upper())
                le.setCursorPosition(pos)
        line_edit.textEdited.connect(convertir)

    @staticmethod
    def _a_mayusculas_texto(text_edit):
        """Igual que _a_mayusculas, para un QTextEdit. Solo actúa mientras el usuario escribe (el campo tiene el foco)."""
        def convertir(te=text_edit):
            if not te.hasFocus():
                return
            texto = te.toPlainText()
            if texto != texto.upper():
                cursor = te.textCursor()
                pos = cursor.position()
                te.blockSignals(True)
                te.setPlainText(texto.upper())
                te.blockSignals(False)
                cursor = te.textCursor()
                cursor.setPosition(min(pos, len(te.toPlainText())))
                te.setTextCursor(cursor)
        text_edit.textChanged.connect(convertir)

    def _activar_mayusculas(self):
        """Chip, ubicación, proveedores, fabricante y descripción. (Tipo, categoría, subcategoría e ítem se eligen de listas.)"""
        for le in (self.txt_chip, self.txt_ubicacion, self.combo_proveedor_exterior.lineEdit(),
                   self.combo_proveedor_local.lineEdit(), self.combo_fabricante.lineEdit()):
            self._a_mayusculas(le)
        self._a_mayusculas_texto(self.txt_descripcion)

    def bloquear_campos_completos(self):
        d = self.datos_componente
        self.mapping_widgets = [
            (self.txt_descripcion, d.get('descripcion')),
            (self.combo_fabricante, d.get('fabricante')),
            (self.txt_chip, d.get('chip_principal')),
            (self.combo_interfaz, d.get('interfaz_comunicacion')),
            (self.combo_pines, d.get('pines_relevantes')),
            (self.combo_encapsulado, d.get('encapsulado')),
            (self.txt_ubicacion, d.get('ubicacion')),
            (self.txt_stock, d.get('stock')),
            (self.txt_precio_exterior, d.get('precio_exterior')),
            (self.combo_proveedor_exterior, d.get('proveedor_exterior')),
            (self.txt_precio_local, d.get('precio_local')),
            (self.combo_proveedor_local, d.get('proveedor_local'))
        ]
        for combo in self._combos_clasificacion():          # la clasificación no se modifica al editar
            self._poner_habilitado(combo, False)
        for widget, valor in self.mapping_widgets:
            self._poner_habilitado(widget, self._valor_pendiente(valor))
        self._sincronizar_monedas()

    @staticmethod
    def _valor_pendiente(valor):
        """True si el dato aún no se ingresó: vacío, 0, o 'N/A' (lo que guardan los combos de fabricante,
        interfaz, pines y encapsulado cuando no se eligió nada)."""
        texto = str(valor).strip() if valor is not None else ""
        return texto.upper() in ("", "0", "0.0", "N/A")

    def _sincronizar_monedas(self):
        """La moneda se puede cambiar cuando se puede cambiar su precio."""
        self._poner_habilitado(self.combo_moneda_ext, self.txt_precio_exterior.isEnabled())
        self._poner_habilitado(self.combo_moneda_local, self.txt_precio_local.isEnabled())

    def toggle_habilitar_edicion(self, state):
        habilitar_todo = (state == Qt.CheckState.Checked.value)
        if habilitar_todo:
            for widget, _ in self.mapping_widgets:          # no incluye los 4 combos de clasificación
                self._poner_habilitado(widget, True)
            self._sincronizar_monedas()
        else:
            self.bloquear_campos_completos()

    def toggle_habilitar_quitar(self, state):
        habilitar = (state == Qt.CheckState.Checked.value)
        for btn in self.botones_quitar:
            btn.setEnabled(habilitar)

    def agregar_imagen_desde_temporal(self, path_temp, filename):
        item_archivo = {
            'tipo': 'imagen',
            'nombre': filename,
            'ruta': path_temp,
            'en_bd': False
        }
        self.archivos_lista.append(item_archivo)
        self.refrescar_combos_multianexo()
        self.combo_imagenes.setCurrentIndex(self.combo_imagenes.count() - 1)

    def agregar_archivo_multianexo(self, tipo):
        if tipo == "imagen":
            filtro = "Imágenes (*.png *.jpg *.jpeg *.bmp *.webp)"
        elif tipo == "datasheet":
            filtro = "Archivos PDF (*.pdf)"
        elif tipo == "tutorial":
            filtro = "Archivos PDF (*.pdf)"
        elif tipo == "esquema":  
            filtro = "Imágenes (*.png *.jpg *.jpeg *.bmp *.webp)"

        path, _ = QFileDialog.getOpenFileName(self, f"Seleccionar {tipo.capitalize()}", "", filtro)
        if path:
            dest_path, base_name = almacenamiento.preparar_adjunto(path)

            item_archivo = {
                'tipo': tipo,
                'nombre': base_name,
                'ruta': dest_path,
                'en_bd': False
            }
            self.archivos_lista.append(item_archivo)
            self.refrescar_combos_multianexo()
            
            combo = self.combo_imagenes if tipo == "imagen" else (
                    self.combo_datasheets if tipo == "datasheet" else (
                    self.combo_tutoriales if tipo == "tutorial" else self.combo_esquemas))
            combo.setCurrentIndex(combo.count() - 1)
            QMessageBox.information(self, "Éxito", f"{tipo.capitalize()} agregado correctamente.")

    def ver_archivo_multianexo(self, tipo):
        # Asegúrate de incluir self.combo_esquemas en el selector por tipo
        combo = self.combo_imagenes if tipo == "imagen" else (
                self.combo_datasheets if tipo == "datasheet" else (
                self.combo_tutoriales if tipo == "tutorial" else self.combo_esquemas))
        
        idx = combo.currentIndex()
        if idx < 0 or combo.itemText(idx).startswith("--"):
            QMessageBox.information(self, "Información", f"No hay ningún {tipo} seleccionado para visualizar.")
            return
            
        ruta = combo.currentData()
        if ruta and almacenamiento.existe(ruta):
            # <--- AQUÍ ESTÁ LA CLAVE: Agregamos "esquema" junto a "imagen" para que use el visor gráfico
            if tipo in ["imagen", "esquema"]:
                editor = DialogoEditorImagen(ruta, self, titulo=combo.itemText(idx), dialogo_componente=self)
                self.ventanas_hijas_abiertas.append(editor)
                editor.show()
            else:
                visor = abrir_documento(self, ruta, combo.itemText(idx), parent_dialogo_componente=self)
                if visor is not None:
                    self.ventanas_hijas_abiertas.append(visor)
        else:
            QMessageBox.warning(self, "Error", "El archivo físico no se encuentra en la ruta especificada.")

    def quitar_archivo_multianexo(self, tipo):
        # 1. Seleccionar el combo correcto incluyendo "esquema"
        combo = self.combo_imagenes if tipo == "imagen" else (
                self.combo_datasheets if tipo == "datasheet" else (
                self.combo_tutoriales if tipo == "tutorial" else self.combo_esquemas))
        
        idx = combo.currentIndex()
        if idx < 0 or combo.itemText(idx).startswith("--"):
            return
            
        ruta_a_quitar = combo.currentData()
        
        # 2. El archivo físico NO se borra: otro componente puede estar usando el mismo documento.
        #    Los documentos que quedan sin uso se retiran al arrancar (almacenamiento.limpiar_huerfanos).
        # 3. Remover de la lista en memoria
        # Se compara también el tipo: el mismo documento (misma ruta) puede estar, por ejemplo, como datasheet y como tutorial.
        self.archivos_lista = [f for f in self.archivos_lista if not (f['ruta'] == ruta_a_quitar and f['tipo'] == tipo)]
        
        # 4. Refrescar los elementos visuales de todos los combos
        self.refrescar_combos_multianexo()

    def refrescar_combos_multianexo(self):
        for combo, tipo in [
            (self.combo_imagenes, 'imagen'), 
            (self.combo_datasheets, 'datasheet'), 
            (self.combo_tutoriales, 'tutorial'),
            (self.combo_esquemas, 'esquema')
        ]:
            seleccion_previa = combo.currentData()      # lo que el usuario tenía elegido
            combo.blockSignals(True)
            combo.clear()
            
            archivos_tipo = [f for f in self.archivos_lista if f['tipo'] == tipo]
            if archivos_tipo:
                for f in archivos_tipo:
                    combo.addItem(f['nombre'], f['ruta'])
                # Se conserva la elección si ese archivo sigue en la lista; si no, el primero
                indice = combo.findData(seleccion_previa) if seleccion_previa is not None else -1
                combo.setCurrentIndex(indice if indice >= 0 else 0)
            else:
                # Diccionario limpio para los textos por defecto exactos que necesitas
                textos_default = {
                    'imagen': '-- Sin imagen --',
                    'datasheet': '-- Sin datasheets --',
                    'tutorial': '-- Sin tutoriales --',
                    'esquema': '-- Sin esquemas --'
                }
                texto_defecto = textos_default.get(tipo, f"Sin {tipo}")
                
                combo.addItem(texto_defecto, None)
                combo.setCurrentIndex(0)
                
            combo.blockSignals(False)

        self.actualizar_miniatura_superior()

    def on_imagen_seleccionada(self, index):
        self.actualizar_miniatura_superior()

    def actualizar_miniatura_superior(self):
        if self.combo_imagenes.count() > 0 and self.combo_imagenes.currentData() is not None:
            ruta = self.combo_imagenes.currentData()
            if ruta and almacenamiento.existe(ruta):
                pix = QPixmap(ruta)
                pix_escalado = pix.scaledToHeight(110, Qt.TransformationMode.SmoothTransformation)
                self.lbl_miniatura.setPixmap(pix_escalado)
                self.lbl_miniatura.setFixedSize(pix_escalado.size())
                return
            if ruta:
                self.lbl_miniatura.setPixmap(QPixmap())          # quita la imagen anterior
                self.lbl_miniatura.setText("Archivo no encontrado")
                self.lbl_miniatura.setFixedSize(110, 110)
                return
        self.lbl_miniatura.setText("Sin Imagen")
        self.lbl_miniatura.setFixedSize(110, 110)

    def cargar_combos_enlazados(self):
        self.combo_tipo.blockSignals(True)
        self.combo_tipo.clear()
        for t in db.listar_tipos():
            self.combo_tipo.addItem(t)
        self.combo_tipo.setCurrentIndex(-1)
        self.combo_tipo.blockSignals(False)

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
        self.on_cat_changed()

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
        self.on_subcat_changed()

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
        self.actualizar_habilitacion_campos()
        self.actualizar_qr_en_vivo()

    def _poner_texto_combo(self, combo, valor):
        """Muestra `valor` en un combo editable (vacío = «N/A»); si no está en la lista, lo deja escrito."""
        valor = str(valor).strip() if valor is not None else ""
        valor = valor or "N/A"
        indice = combo.findText(valor)
        if indice >= 0:
            combo.setCurrentIndex(indice)
        else:
            combo.setEditText(valor)

    def cargar_datos_existentes(self):
        d = self.datos_componente
        
        self.combo_tipo.setEditText(limpiar_prefijo(str(d.get('tipo_componente', ''))))
        self.combo_cat.setEditText(str(d.get('categoria', '')))
        self.combo_subcat.setEditText(str(d.get('subcategoria', '')))
        self.combo_item.setEditText(str(d.get('item_especifico', '')))
        
        self.txt_descripcion.setPlainText(str(d.get('descripcion', '')))
        
        fab_val = str(d.get('fabricante', ''))
        idx_fab = self.combo_fabricante.findText(fab_val)
        if idx_fab >= 0:
            self.combo_fabricante.setCurrentIndex(idx_fab)
        else:
            self.combo_fabricante.setEditText(fab_val)

        self.txt_chip.setText(str(d.get('chip_principal', '')))
        
        interfaz_val = str(d.get('interfaz_comunicacion', ''))
        self.combo_interfaz.set_seleccionadas(interfaz_val)

        pines_val = str(d.get('pines_relevantes', ''))
        self.combo_pines.set_seleccionadas(pines_val)
        
        encap_val = str(d.get('encapsulado', ""))
        self.combo_encapsulado.set_seleccionadas(encap_val)

        self.txt_ubicacion.setText(str(d.get('ubicacion', '')))
        self.txt_stock.setText(str(d.get('stock', 0)))
        
        self.txt_precio_exterior.setText(str(d.get('precio_exterior', 0.0)))
        self._poner_texto_combo(self.combo_proveedor_exterior, d.get('proveedor_exterior'))
        self.txt_precio_local.setText(str(d.get('precio_local', 0.0)))
        self._poner_texto_combo(self.combo_proveedor_local, d.get('proveedor_local'))

        # Cargar la selección de los radio buttons de obsolescencia
        obsolescencia = str(d.get('obsolescencia', 'No')).strip()
        if obsolescencia in ["Sí", "Si", "1", 1]:
            self.rb_obsolescencia_si.setChecked(True)
        else:
            self.rb_obsolescencia_no.setChecked(True)

        componente_id = d.get('id')
        if componente_id:
            rows_archivos = db.listar_archivos(componente_id)
            self.archivos_lista = [{'tipo': t, 'nombre': n, 'ruta': r, 'en_bd': True} for t, n, r in almacenamiento.resolver_archivos(rows_archivos)]
            self.refrescar_combos_multianexo()

            self.parametros_electricos_temp = db.listar_parametros(componente_id)

    def guardar_todo_unificado(self):
        chip = self.txt_chip.text().strip() if hasattr(self, 'txt_chip') else ""
        if not chip:
            QMessageBox.warning(self, "Aviso Requerido", "Por favor ingrese el 'Chip Principal' antes de guardar el registro.")
            return

        datos = self._leer_campos_formulario(chip)

        try:
            # Primero, asegurate de capturar el texto actual de los QComboBox de moneda antes de armar los datos:
            moneda_ext_val = self.combo_moneda_ext.currentText()
            moneda_loc_val = self.combo_moneda_local.currentText()
            datos.update(moneda_exterior=moneda_ext_val, moneda_local=moneda_loc_val)

            comp_id = None
            if self.is_editing and self.datos_componente and 'id' in self.datos_componente:
                comp_id = self.datos_componente['id']   # editando: UPDATE; si no, INSERT

            archivos = self._archivos_para_guardar()

            parametros = self._parametros_para_guardar()

            comp_id = db.guardar_componente(comp_id, datos, archivos, parametros)
            QMessageBox.information(self, "Éxito", "Componente, archivos y especificaciones guardados correctamente.")
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Error de Guardado", f"Ocurrió un error al persistir la información: {str(e)}")

    def _texto_clasificacion(self, combo):
        """Texto del combo de clasificación. Al crear, si coincide (sin distinguir mayúsculas) con una
        entrada del catálogo se usa la ortografía del catálogo, para no crear «arduino uno» junto a «Arduino Uno»."""
        texto = combo.currentText().strip()
        if not self.is_editing and texto:
            indice = combo.findText(texto, Qt.MatchFlag.MatchFixedString)   # sin distinguir mayúsculas
            if indice > 0:      # 0 es el texto comodín «-- Todos … --»
                return combo.itemText(indice)
        return texto

    def _leer_campos_formulario(self, chip):
        """Lee los widgets del formulario y devuelve el dict de datos del componente (sin las monedas)."""
        tipo_val = limpiar_prefijo(self._texto_clasificacion(self.combo_tipo)) if hasattr(self, 'combo_tipo') else ""
        cat_val = self._texto_clasificacion(self.combo_cat) if hasattr(self, 'combo_cat') else ""
        subcat_val = self._texto_clasificacion(self.combo_subcat) if hasattr(self, 'combo_subcat') else ""
        item_val = self._texto_clasificacion(self.combo_item) if hasattr(self, 'combo_item') else ""
        nombre_val = item_val or subcat_val or cat_val or "Componente sin nombre"

        desc_val = self.txt_descripcion.toPlainText().strip() if hasattr(self, 'txt_descripcion') else ""
        
        stock_text = self.txt_stock.text().strip() if hasattr(self, 'txt_stock') else "0"
        stock = int(stock_text) if stock_text.isdigit() else 0

        # Precios y proveedores seguros
        try:
            precio_ext = float(self.txt_precio_exterior.text().strip()) if hasattr(self, 'txt_precio_exterior') and self.txt_precio_exterior.text().strip() else 0.0
        except ValueError:
            precio_ext = 0.0

        try:
            precio_loc = float(self.txt_precio_local.text().strip()) if hasattr(self, 'txt_precio_local') and self.txt_precio_local.text().strip() else 0.0
        except ValueError:
            precio_loc = 0.0

        prov_ext = self.combo_proveedor_exterior.currentText().strip() if hasattr(self, 'combo_proveedor_exterior') else ""
        prov_loc = self.combo_proveedor_local.currentText().strip() if hasattr(self, 'combo_proveedor_local') else ""
        
        try:
            precio_unico = float(self.txt_precio.text().strip()) if hasattr(self, 'txt_precio') and self.txt_precio.text().strip() else 0.0
        except ValueError:
            precio_unico = 0.0

        # Lecturas seguras de widgets que pueden ser ComboBox o LineEdit
        fabricante_val = self.combo_fabricante.currentText().strip() if hasattr(self, 'combo_fabricante') else (self.txt_fabricante.text().strip() if hasattr(self, 'txt_fabricante') else "")
        
        interfaz_val = self.combo_interfaz.currentText().strip() if hasattr(self, 'combo_interfaz') else (self.txt_interfaz.text().strip() if hasattr(self, 'txt_interfaz') else "N/A")
        
        pines_val = self.combo_pines.currentText().strip() if hasattr(self, 'combo_pines') else (self.txt_pines.text().strip() if hasattr(self, 'txt_pines') else "N/A")
        
        encapsulado_val = self.combo_encapsulado.currentText().strip() if hasattr(self, 'combo_encapsulado') else (self.txt_encapsulado.text().strip() if hasattr(self, 'txt_encapsulado') else "")

        ubicacion_val = self.txt_ubicacion.text().strip() if hasattr(self, 'txt_ubicacion') else ""

        # Capturar la obsolescencia ANTES de interactuar con la base de datos
        obsolescencia_val = "Sí" if hasattr(self, 'rb_obsolescencia_si') and self.rb_obsolescencia_si.isChecked() else "No"

        return {
            'nombre': nombre_val, 'tipo_componente': tipo_val, 'categoria': cat_val,
            'subcategoria': subcat_val, 'item_especifico': item_val, 'descripcion': desc_val,
            'fabricante': fabricante_val, 'chip_principal': chip,
            'interfaz_comunicacion': interfaz_val, 'pines_relevantes': pines_val,
            'encapsulado': encapsulado_val, 'stock': stock, 'precio': precio_unico,
            'ubicacion': ubicacion_val, 'precio_exterior': precio_ext,
            'proveedor_exterior': prov_ext, 'precio_local': precio_loc,
            'proveedor_local': prov_loc, 'obsolescencia': obsolescencia_val,
        }

    def _archivos_para_guardar(self):
        """Archivos múltiples (imágenes, datasheets, tutoriales) como tuplas (tipo, nombre, ruta en el almacén)."""
        archivos = []
        if hasattr(self, 'archivos_lista') and self.archivos_lista:
            # Cada documento entra al almacén por hash (o se reutiliza si ya existe).
            # Dos entradas con el mismo tipo y el mismo contenido se registran una sola vez.
            vistos = set()
            # La imagen elegida en el combo de imágenes pasa a ser la principal (logo del componente):
            # se guarda primera entre las imágenes y así se vuelve a mostrar al reabrir o consultar.
            principal = self.combo_imagenes.currentData() if hasattr(self, 'combo_imagenes') else None
            ordenados = sorted(self.archivos_lista,
                               key=lambda f: not (f['tipo'] == 'imagen' and principal is not None and f['ruta'] == principal))
            for f in ordenados:
                ruta = almacenamiento.para_guardar(f['ruta'])
                if (f['tipo'], ruta) not in vistos:
                    vistos.add((f['tipo'], ruta))
                    archivos.append((f['tipo'], f['nombre'], ruta))
        return archivos

    def _parametros_para_guardar(self):
        """Parámetros eléctricos / especificaciones como lista de (clave, valor)."""
        parametros = []
        if hasattr(self, 'parametros_electricos_temp') and self.parametros_electricos_temp:
            parametros = list(self.parametros_electricos_temp)
        return parametros

