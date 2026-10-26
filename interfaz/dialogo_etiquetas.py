"""Diálogo de impresión de etiquetas y generación de su PDF."""
import qrcode

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout
)
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

import almacenamiento
import db
from interfaz.visor_pdf import DialogoVisorPDF


# -------------------------------------------------------------------
# VENTANA: IMPRESIÓN DE ETIQUETAS
# -------------------------------------------------------------------
class DialogoImpresionEtiquetas(QDialog):
    def __init__(self, componentes, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Impresión de Etiquetas")
        self.componentes = componentes
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        title = QLabel("Cola de Impresión y Dimensiones de Etiqueta")
        title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        layout.addWidget(title)

        # --- Selector de Tamaño de Papel ---
        box_papel = QHBoxLayout()
        box_papel.addWidget(QLabel("Formato de Papel:"))
        self.combo_papel = QComboBox()
        self.combo_papel.addItems(["A4 (210 x 297 mm)", "Letter / Carta (215.9 x 279.4 mm)"])
        box_papel.addWidget(self.combo_papel)
        layout.addLayout(box_papel)

        box_medidas = QGridLayout()
        box_medidas.addWidget(QLabel("Ancho (mm):"), 0, 0)
        self.spin_w = QDoubleSpinBox()
        self.spin_w.setRange(10.0, 300.0)
        self.spin_w.setValue(40.0)
        box_medidas.addWidget(self.spin_w, 0, 1)

        box_medidas.addWidget(QLabel("Alto (mm):"), 0, 2)
        self.spin_h = QDoubleSpinBox()
        self.spin_h.setRange(10.0, 300.0)
        self.spin_h.setValue(25.0)
        box_medidas.addWidget(self.spin_h, 0, 3)

        box_medidas.addWidget(QLabel("Separación H (mm):"), 1, 0)
        self.spin_gap_x = QDoubleSpinBox()
        self.spin_gap_x.setRange(0.0, 50.0)
        self.spin_gap_x.setValue(2.0)
        box_medidas.addWidget(self.spin_gap_x, 1, 1)

        box_medidas.addWidget(QLabel("Separación V (mm):"), 1, 2)
        self.spin_gap_y = QDoubleSpinBox()
        self.spin_gap_y.setRange(0.0, 50.0)
        self.spin_gap_y.setValue(2.0)
        box_medidas.addWidget(self.spin_gap_y, 1, 3)

        layout.addLayout(box_medidas)

        self.spin_boxes = {}
        for item in self.componentes:
            hbox = QHBoxLayout()
            lbl = QLabel(f"{item['nombre']} ({item['ubicacion']})")
            
            # SpinBox para la cantidad de etiquetas (copias)
            spin_copias = QSpinBox()
            spin_copias.setRange(1, 100)
            spin_copias.setValue(1)
            spin_copias.setFixedWidth(55)
            
            # SpinBox para las unidades por bolsa
            spin_unidades = QSpinBox()
            spin_unidades.setRange(1, 10000)
            spin_unidades.setValue(1)
            spin_unidades.setFixedWidth(65)
            
            hbox.addWidget(lbl)
            hbox.addStretch()
            hbox.addWidget(QLabel("Copias:"))
            hbox.addWidget(spin_copias)
            hbox.addWidget(QLabel("Unid/Bolsa:"))
            hbox.addWidget(spin_unidades)
            
            layout.addLayout(hbox)
            # Guardamos ambos selectores en la tupla para leerlos en generar_pdf
            self.spin_boxes[item['id']] = (item, spin_copias, spin_unidades)

        hbox_start = QHBoxLayout()
        hbox_start.addWidget(QLabel("Comenzar en la celda N°:"))
        self.spin_start = QSpinBox()
        self.spin_start.setRange(1, 100)
        self.spin_start.setValue(1)
        self.spin_start.setFixedWidth(70)
        hbox_start.addStretch()
        hbox_start.addWidget(self.spin_start)
        layout.addLayout(hbox_start)

        layout.addSpacing(5)
        btn_pdf = QPushButton("📄 Generar PDF de Etiquetas")
        btn_pdf.setAutoDefault(False); btn_pdf.setDefault(False)
        btn_pdf.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 8px;")
        btn_pdf.clicked.connect(self.generar_pdf)
        layout.addWidget(btn_pdf)
        
        self.setLayout(layout)
        self.adjustSize()      # esta ventana se ajusta a su contenido (no se maximiza)

    @staticmethod
    def _dibujar_guias_de_corte(c, cols, rows, label_w, label_h, gap_x, gap_y, margin_x, margin_y, page_h):
        """Líneas a rayas por el punto medio de cada separación (y a media separación de los bordes exteriores)
        para indicar por dónde troquelar. Con separación 0 coinciden con el borde de las etiquetas."""
        ancho = cols * label_w + (cols - 1) * gap_x
        alto = rows * label_h + (rows - 1) * gap_y
        izq, der = margin_x - gap_x / 2, margin_x + ancho + gap_x / 2
        sup, inf = page_h - margin_y + gap_y / 2, page_h - margin_y - alto - gap_y / 2
        c.saveState()
        c.setStrokeColorRGB(0.45, 0.45, 0.45)
        c.setLineWidth(0.4)
        c.setDash(3, 2)
        for k in range(cols + 1):
            x = margin_x + k * (label_w + gap_x) - gap_x / 2
            c.line(x, inf, x, sup)
        for k in range(rows + 1):
            y = page_h - margin_y - k * (label_h + gap_y) + gap_y / 2
            c.line(izq, y, der, y)
        c.restoreState()

    def generar_pdf(self):
        output_pdf = almacenamiento.ruta_pdf_etiquetas()
        
        # 1. Obtener tamaño de hoja según la selección del ComboBox
        if self.combo_papel.currentIndex() == 0:
            page_size = A4
        else:
            page_size = letter
            
        page_w, page_h = page_size
        
        # 2. Leer dimensiones y espaciados
        label_w = self.spin_w.value() * mm
        label_h = self.spin_h.value() * mm
        gap_x = self.spin_gap_x.value() * mm
        gap_y = self.spin_gap_y.value() * mm
        
        # 3. Calcular automáticamente columnas, filas y celdas por página
        min_margin = 5 * mm
        cols = max(1, int((page_w - (2 * min_margin) + gap_x) // (label_w + gap_x)))
        rows = max(1, int((page_h - (2 * min_margin) + gap_y) // (label_h + gap_y)))
        total_cells_per_page = cols * rows

        # 4. Cálculo dinámico de márgenes para centrar la grilla perfectamente
        ancho_total_grilla = (cols * label_w) + ((cols - 1) * gap_x)
        alto_total_grilla = (rows * label_h) + ((rows - 1) * gap_y)
        
        margin_x = max(2 * mm, (page_w - ancho_total_grilla) / 2)
        margin_y = max(2 * mm, (page_h - alto_total_grilla) / 2)

        c = canvas.Canvas(output_pdf, pagesize=page_size)
        current_cell = self.spin_start.value() - 1

        styles = getSampleStyleSheet()
        style_chip = ParagraphStyle('ChipStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=9)
        style_item = ParagraphStyle('ItemStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=6.5, leading=8)
        style_desc = ParagraphStyle('DescStyle', parent=styles['Normal'], fontName='Helvetica-Oblique', fontSize=6, leading=7.5)
        style_ubic = ParagraphStyle('UbicStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=6.5, leading=8)
        style_unidades = ParagraphStyle('UnidStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=6.5, leading=8) # <--- Agrega esta línea aquí

        
        for item_id, (item, spin_copias, spin_unidades) in self.spin_boxes.items():
            copias = spin_copias.value()
            unidades_por_bolsa = spin_unidades.value()
        
            if copias <= 0:
                continue
            
            row_db = db.obtener_datos_etiqueta(item_id)

            chip_prin = row_db[0] if row_db and row_db[0] else item.get('nombre', 'N/A')
            item_esp = row_db[1] if row_db and row_db[1] else 'N/A'
            desc_completa = row_db[2] if row_db and row_db[2] else 'N/A'
            ubicacion = row_db[3] if row_db and row_db[3] else item.get('ubicacion', 'N/A')
            stock = row_db[5] if row_db and row_db[5] is not None else 0

            texto_qr = f"CHIP: {chip_prin} | ITEM: {item_esp} | DESC: {desc_completa[:35]} | STOCK: {stock} | UBIC: {ubicacion}"
            
            qr = qrcode.QRCode(version=1, box_size=1, border=1)
            qr.add_data(texto_qr)
            qr.make(fit=True)
            img_qr = qr.make_image(fill_color="black", back_color="white")
            
            path_qr_tmp = almacenamiento.guardar_temporal(img_qr, f"qr_temp_{item_id}.png")

            for _ in range(copias):
                if current_cell >= total_cells_per_page:
                    self._dibujar_guias_de_corte(c, cols, rows, label_w, label_h, gap_x, gap_y, margin_x, margin_y, page_h)
                    c.showPage()
                    current_cell = 0

                col = current_cell % cols
                # Calculamos la fila de arriba hacia abajo (0 es la primera fila superior)
                row = current_cell // cols
                
                x = margin_x + col * (label_w + gap_x)
                # Invertimos el eje Y para que baje desde el margen superior de la hoja
                y = page_h - margin_y - (row + 1) * label_h - row * gap_y

                c.rect(x, y, label_w, label_h)

                m = 1.0 * mm
                qr_size = min(label_h - (2 * m), label_h * 0.45)
                qr_y = y + (label_h - qr_size) / 2
                c.drawImage(path_qr_tmp, x + label_w - qr_size - m, qr_y, width=qr_size, height=qr_size)

                text_width = label_w - qr_size - (3 * m)
                text_x = x + m

                desc_cortada = desc_completa[:70] + "..." if len(desc_completa) > 70 else desc_completa

                p_chip = Paragraph(f"<b>{chip_prin}</b>", style_chip)
                p_item = Paragraph(f"Ítem: {item_esp}", style_item)
                p_desc = Paragraph(f"{desc_cortada}", style_desc)  # <--- Usar la versión recortada
                p_ubic = Paragraph(f"Ubic: {ubicacion}", style_ubic)
                p_unid = Paragraph(f"Bolsa: <b>{unidades_por_bolsa} unids.</b>", style_unidades)
 
                w_c, h_c = p_chip.wrap(text_width, label_h)
                w_i, h_i = p_item.wrap(text_width, label_h)
                w_d, h_d = p_desc.wrap(text_width, label_h)
                w_u, h_u = p_ubic.wrap(text_width, label_h)
                w_un, h_un = p_unid.wrap(text_width, label_h)

                curr_y = y + label_h - m
                
                curr_y -= h_c
                p_chip.drawOn(c, text_x, curr_y)
                
                curr_y -= (h_i + 0.5 * mm)
                p_item.drawOn(c, text_x, curr_y)
                
                curr_y -= (h_d + 0.5 * mm)
                p_desc.drawOn(c, text_x, curr_y)
                
                curr_y -= (h_u + 0.5 * mm)
                p_ubic.drawOn(c, text_x, curr_y)

                curr_y -= (h_un + 0.3 * mm)
                p_unid.drawOn(c, text_x, curr_y)

                current_cell += 1

        self._dibujar_guias_de_corte(c, cols, rows, label_w, label_h, gap_x, gap_y, margin_x, margin_y, page_h)
        c.save()
        QMessageBox.information(self, "PDF Creado", f"Se generó el archivo:\n{output_pdf}")
        visor = DialogoVisorPDF(output_pdf, None, self, es_modo_etiquetas=True)
        visor.show()
