"""Editor y visor de imágenes (recorte y guardado)."""
import os

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget
)

import almacenamiento


# -------------------------------------------------------------------
# EDITOR / VISOR AVANZADO DE IMAGEN
# -------------------------------------------------------------------
_FILTRO_GUARDAR = "Imágenes PNG (*.png);;Imágenes JPG (*.jpg *.jpeg);;Todos los archivos (*.*)"
_ultima_carpeta = None      # última carpeta elegida al guardar: el siguiente diálogo empieza ahí


def pedir_destino_y_guardar(parent, imagen, sufijo, titulo_dialogo, chip="componente"):
    """Pide al usuario la carpeta y el nombre, guarda `imagen` ahí y avisa. Devuelve la ruta, o None si
    canceló o falló. Es el único camino de guardado de recortes e imágenes (visor de PDF y visor de imagen)."""
    global _ultima_carpeta
    nombre_sugerido = almacenamiento.nombre_archivo(chip or "componente", sufijo)
    if _ultima_carpeta and os.path.isdir(_ultima_carpeta):
        ruta_inicial = os.path.join(_ultima_carpeta, nombre_sugerido)
    else:
        ruta_inicial = os.path.join(os.path.expanduser("~"), nombre_sugerido)     # primera vez: carpeta personal

    destino, _ = QFileDialog.getSaveFileName(parent, titulo_dialogo, ruta_inicial, _FILTRO_GUARDAR)
    if not destino:
        return None                      # canceló: no se guarda nada
    if not os.path.splitext(destino)[1]:
        destino += ".png"                # sin extensión Qt no sabe en qué formato escribir

    try:
        almacenamiento.guardar_imagen(imagen, destino)
    except Exception as e:
        QMessageBox.critical(parent, "Error al guardar", f"No se pudo guardar la imagen en:\n{destino}\n\n{e}")
        return None
    _ultima_carpeta = os.path.dirname(os.path.abspath(destino))
    QMessageBox.information(parent, "Imagen guardada", f"La imagen se guardó en:\n{destino}")
    return destino


class DialogoEditorImagen(QDialog):
    """Visor de imagen con recorte. Guardar (región o entera) hace UNA sola cosa: pide la carpeta y el
    nombre, y escribe el archivo ahí. No registra la imagen en ningún componente: eso lo decide el usuario después.
    `dialogo_componente` (opcional) solo sirve para proponer un nombre de archivo con el chip."""

    def __init__(self, image_path, parent=None, titulo=None, dialogo_componente=None):
        super().__init__(parent)
        self.image_path = image_path
        self.dialogo_componente = dialogo_componente
        self.setWindowTitle(f"✂️ Editor y Visor de Imagen - {titulo or os.path.basename(image_path)}")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowMaximizeButtonHint)
        self.setWindowState(Qt.WindowState.WindowMaximized)   # siempre abre maximizada
        
        self.pixmap_original = QPixmap(image_path)
        self.zoom_factor = 1.0      
        self.begin = QPoint()
        self.end = QPoint()
        self.selected_rect = QRect()
        self.resultado_imagen = None
        self.drawing = False

        layout = QVBoxLayout(self)

        # --- BARRA SUPERIOR UNIFICADA (ZOOM, GUARDAR Y CANCELAR) ---
        top_bar_layout = QHBoxLayout()

        # 1. Controles de Zoom
        self.lbl_zoom_info = QLabel("🔍 Zoom: 100%")
        self.lbl_zoom_info.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        
        btn_zoom_mas = QPushButton("🔍➕ Ampliar")
        btn_zoom_mas.setAutoDefault(False); btn_zoom_mas.setDefault(False)
        btn_zoom_mas.setStyleSheet("background-color: #007bff; color: white; font-weight: bold;")

        btn_zoom_menos = QPushButton("🔍➖ Reducir")
        btn_zoom_menos.setAutoDefault(False); btn_zoom_menos.setDefault(False)
        btn_zoom_menos.setStyleSheet("background-color: #007bff; color: white; font-weight: bold;")

        btn_zoom_reset = QPushButton("↺ 100%")
        btn_zoom_reset.setAutoDefault(False); btn_zoom_reset.setDefault(False)
        btn_zoom_reset.setStyleSheet("background-color: #6c757d; color: white; font-weight: bold;")

        btn_zoom_mas.clicked.connect(self.aumentar_zoom)
        btn_zoom_menos.clicked.connect(self.reducir_zoom)
        btn_zoom_reset.clicked.connect(self.reset_zoom)

        # 2. Botones de Guardar
        btn_guardar_recorte = QPushButton("✅ Guardar Región")
        btn_guardar_recorte.setAutoDefault(False); btn_guardar_recorte.setDefault(False)
        btn_guardar_recorte.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
        btn_guardar_recorte.clicked.connect(self.guardar_recorte)
        
        btn_guardar_entera = QPushButton("💾 Guardar Entera")
        btn_guardar_entera.setAutoDefault(False); btn_guardar_entera.setDefault(False)
        btn_guardar_entera.setStyleSheet("background-color: #17a2b8; color: white; font-weight: bold;")
        btn_guardar_entera.clicked.connect(self.guardar_completa)

        # 3. Botón Cancelar (quedará al extremo derecho)
        btn_cancelar = QPushButton("❌ Cancelar")
        btn_cancelar.setAutoDefault(False); btn_cancelar.setDefault(False)
        btn_cancelar.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold;")
        btn_cancelar.clicked.connect(self.close)

        # --- APLICAR ALTURA UNIFORME A TODOS LOS BOTONES ---
        for btn in [btn_zoom_mas, btn_zoom_menos, btn_zoom_reset, btn_guardar_recorte, btn_guardar_entera, btn_cancelar]:
            btn.setFixedHeight(35)

        # Agregar elementos al layout superior en orden horizontal
        top_bar_layout.addWidget(self.lbl_zoom_info)
        top_bar_layout.addSpacing(10)
        top_bar_layout.addWidget(btn_zoom_mas)
        top_bar_layout.addWidget(btn_zoom_menos)
        top_bar_layout.addWidget(btn_zoom_reset)
        top_bar_layout.addSpacing(15)
        top_bar_layout.addWidget(btn_guardar_recorte)
        top_bar_layout.addWidget(btn_guardar_entera)
        top_bar_layout.addStretch()  # Espaciador flexible que empuja el botón cancelar a la derecha
        top_bar_layout.addWidget(btn_cancelar)

        layout.addLayout(top_bar_layout)
        # -------------------------------------------------------------

        lbl_info = QLabel("💡 Arrastre el mouse para seleccionar un área de recorte, o guarde directamente sin seleccionar para conservar toda la imagen.")
        lbl_info.setStyleSheet("background-color: #e9ecef; color: #333; padding: 8px; font-weight: bold; border-radius: 4px;")
        layout.addWidget(lbl_info)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.canvas_widget = QWidget()
        self.actualizar_pixmap_escalado()
        
        self.canvas_widget.paintEvent = self.canvas_paint_event
        self.canvas_widget.mousePressEvent = self.canvas_mouse_press
        self.canvas_widget.mouseMoveEvent = self.canvas_mouse_move
        self.canvas_widget.mouseReleaseEvent = self.canvas_mouse_release
        
        self.scroll_area.setWidget(self.canvas_widget)
        layout.addWidget(self.scroll_area)

    def actualizar_pixmap_escalado(self):
        nuevo_ancho = int(self.pixmap_original.width() * self.zoom_factor)
        nuevo_alto = int(self.pixmap_original.height() * self.zoom_factor)
        self.pixmap_escalado = self.pixmap_original.scaled(nuevo_ancho, nuevo_alto, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.canvas_widget.setMinimumSize(self.pixmap_escalado.size())
        self.canvas_widget.update()

    def aumentar_zoom(self):
        if self.zoom_factor < 4.0:
            self.zoom_factor += 0.25
            self.lbl_zoom_info.setText(f"🔍 Zoom: {int(self.zoom_factor * 100)}%")
            self.actualizar_pixmap_escalado()

    def reducir_zoom(self):
        if self.zoom_factor > 0.5:
            self.zoom_factor -= 0.25
            self.lbl_zoom_info.setText(f"🔍 Zoom: {int(self.zoom_factor * 100)}%")
            self.actualizar_pixmap_escalado()

    def reset_zoom(self):
        self.zoom_factor = 1.0
        self.lbl_zoom_info.setText("🔍 Zoom: 100%")
        self.actualizar_pixmap_escalado()

    def canvas_paint_event(self, event):
        painter = QPainter(self.canvas_widget)
        painter.drawPixmap(0, 0, self.pixmap_escalado)
        if not self.selected_rect.isNull():
            pen = QPen(Qt.GlobalColor.red, 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.selected_rect)

    def canvas_mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.begin = event.position().toPoint()
            self.end = self.begin
            self.selected_rect = QRect()
            self.drawing = True
            self.canvas_widget.update()

    def canvas_mouse_move(self, event):
        if self.drawing and (event.buttons() & Qt.MouseButton.LeftButton):
            self.end = event.position().toPoint()
            self.selected_rect = QRect(self.begin, self.end).normalized()
            self.canvas_widget.update()

    def canvas_mouse_release(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drawing = False
            if not self.selected_rect.isNull() and self.selected_rect.width() > 5 and self.selected_rect.height() > 5:
                self.selected_rect = self.selected_rect.intersected(self.pixmap_escalado.rect())
                self.canvas_widget.update()

    def guardar_recorte(self):
        if not self.selected_rect.isNull() and self.selected_rect.width() > 5:
            x = int(self.selected_rect.x() / self.zoom_factor)
            y = int(self.selected_rect.y() / self.zoom_factor)
            w = int(self.selected_rect.width() / self.zoom_factor)
            h = int(self.selected_rect.height() / self.zoom_factor)
            rect_real = QRect(x, y, w, h).intersected(self.pixmap_original.rect())
            self._guardar(self.pixmap_original.copy(rect_real), "recorte.png", "Guardar Recorte Como...")
        else:
            self.guardar_completa()      # sin región marcada se guarda la imagen entera

    def guardar_completa(self):
        self._guardar(self.pixmap_original, "completa.png", "Guardar Imagen Completa Como...")

    def _guardar(self, imagen, sufijo, titulo_dialogo):
        """Guarda con `pedir_destino_y_guardar`; si se guardó, cierra el visor (si canceló, queda abierto)."""
        comp = self.dialogo_componente
        chip = comp.txt_chip.text().strip() if comp is not None else ""
        if pedir_destino_y_guardar(self, imagen, sufijo, titulo_dialogo, chip):
            self.resultado_imagen = imagen
            self.close()
