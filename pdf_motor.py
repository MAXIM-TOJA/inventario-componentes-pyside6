"""Capa de PDF (sin Qt): abre, dibuja, extrae texto y detecta enlaces usando pypdfium2.

Todas las coordenadas que entran y salen de este módulo están en PUNTOS de página con el origen ARRIBA a la
izquierda (como la pantalla). pdfium trabaja con el origen ABAJO a la izquierda; la conversión se hace aquí
dentro, de modo que la interfaz no necesita saberlo.

Licencia de la biblioteca: pypdfium2 es Apache-2.0 / BSD-3 (PDFium), sin copyleft.
"""
import ctypes
import re

import pypdfium2 as pdfium
import pypdfium2.raw as raw

_PATRON_URL = re.compile(r"(https?://[^\s]+|www\.[^\s]+)", re.IGNORECASE)


class Enlace:
    """Región rectangular de la página (arriba-izquierda) que abre `uri`."""
    __slots__ = ("x0", "y0", "x1", "y1", "uri")

    def __init__(self, x0, y0, x1, y1, uri):
        self.x0, self.y0, self.x1, self.y1, self.uri = x0, y0, x1, y1, uri

    def contiene(self, x, y):
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1


class DocumentoPDF:
    def __init__(self, ruta):
        self._pdf = pdfium.PdfDocument(ruta)

    def __len__(self):
        return len(self._pdf)

    def pagina(self, indice):
        return PaginaPDF(self._pdf[indice])

    def cerrar(self):
        try:
            self._pdf.close()
        except Exception:
            pass


class PaginaPDF:
    def __init__(self, pagina):
        self._p = pagina
        x0, y0, x1, y1 = pagina.get_cropbox() if hasattr(pagina, "get_cropbox") else pagina.get_bbox()
        self._ox, self._oy = x0, y0
        self.ancho = float(x1 - x0)
        self.alto = float(y1 - y0)
        self._texto = None
        self._enlaces = None

    # ---- geometría -------------------------------------------------
    def _recortar_a_pagina(self, x0, y0, x1, y1):
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        return max(0.0, x0), max(0.0, y0), min(self.ancho, x1), min(self.alto, y1)

    def _a_pdf(self, x0, y0, x1, y1):
        """(arriba-izq) -> (izq, abajo, der, arriba) en coordenadas pdfium."""
        return (self._ox + x0, self._oy + self.alto - y1, self._ox + x1, self._oy + self.alto - y0)

    def _de_pdf(self, izq, abajo, der, arriba):
        return (izq - self._ox, self.alto - (arriba - self._oy), der - self._ox, self.alto - (abajo - self._oy))

    # ---- dibujo ----------------------------------------------------
    def dibujar(self, escala=1.0, region=None):
        """Imagen PIL (RGB) de la página o de `region` (x0, y0, x1, y1) a la escala dada. None si la región es vacía."""
        if region is None:
            return self._p.render(scale=escala).to_pil().convert("RGB")
        x0, y0, x1, y1 = self._recortar_a_pagina(*region)
        if x1 - x0 < 0.5 or y1 - y0 < 0.5:
            return None
        crop = (x0, self.alto - y1, self.ancho - x1, y0)       # márgenes (izq, abajo, der, arriba) a quitar
        return self._p.render(scale=escala, crop=crop).to_pil().convert("RGB")

    # ---- texto -----------------------------------------------------
    def _textpage(self):
        if self._texto is None:
            self._texto = self._p.get_textpage()
        return self._texto

    def texto_en_region(self, x0, y0, x1, y1):
        """Texto de la región. Primero los caracteres cuyo centro cae dentro del marco; si no hay ninguno, los
        que el marco toca (un marco que corta una letra no debe dejar la selección vacía)."""
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        tp = self._textpage()
        n = tp.count_chars()
        if n == 0:
            return ""
        izq, abajo, der, arriba = self._a_pdf(x0, y0, x1, y1)
        dentro, tocados = [], []
        for i in range(n):
            c0, c1, c2, c3 = tp.get_charbox(i, loose=True)
            if c2 <= c0 or c3 <= c1:
                # sin caja (espacio, salto de línea): se decide después según los vecinos
                dentro.append((i, None))
                tocados.append((i, None))
                continue
            cx, cy = (c0 + c2) / 2, (c1 + c3) / 2
            if izq <= cx <= der and abajo <= cy <= arriba:
                dentro.append((i, (c0, c1, c2, c3)))
            if c0 < der and c2 > izq and c1 < arriba and c3 > abajo:
                tocados.append((i, (c0, c1, c2, c3)))
        texto = self._armar(dentro)
        return texto or self._armar(tocados)

    def _armar(self, indices):
        """Texto de los caracteres con caja que están en `indices`, más los espacios/saltos que quedan entre ellos."""
        tp = self._textpage()
        con_caja = [i for i, caja in indices if caja is not None]
        if not con_caja:
            return ""
        primero, ultimo = con_caja[0], con_caja[-1]
        elegidos = {i for i, caja in indices if caja is not None}
        partes = []
        for i in range(primero, ultimo + 1):
            if i in elegidos:
                partes.append(tp.get_text_range(i, 1))
            else:
                c = tp.get_text_range(i, 1)
                # los separadores (espacio, \r, \n) entre dos caracteres elegidos se conservan; el resto se omite
                if c in (" ", "\r", "\n", "\t", "\xa0"):
                    partes.append(c)
        texto = "".join(partes).replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
        lineas = [ln.strip() for ln in texto.split("\n")]
        return "\n".join(ln for ln in lineas if ln).strip()

    # ---- enlaces ---------------------------------------------------
    def enlaces(self):
        """Enlaces de la página: los detectados en el texto (http://..., www....) y los anotados en el PDF."""
        if self._enlaces is None:
            lista = []
            lista.extend(self._enlaces_de_texto())
            lista.extend(self._enlaces_anotados())
            self._enlaces = lista
        return self._enlaces

    def enlace_en(self, x, y):
        for e in self.enlaces():
            if e.contiene(x, y):
                return e
        return None

    def _enlaces_de_texto(self):
        salida = []
        tp = self._textpage()
        try:
            wl = raw.FPDFLink_LoadWebLinks(tp)
        except Exception:
            return salida
        if not wl:
            return salida
        try:
            for i in range(raw.FPDFLink_CountWebLinks(wl)):
                largo = raw.FPDFLink_GetURL(wl, i, None, 0)
                if largo <= 1:
                    continue
                buf = (ctypes.c_ushort * largo)()
                raw.FPDFLink_GetURL(wl, i, buf, largo)
                uri = bytes(bytearray(b for v in buf for b in (v & 255, v >> 8))).decode("utf-16le", "ignore").rstrip("\x00")
                if not uri:
                    continue
                if not uri.lower().startswith(("http://", "https://")):
                    uri = "http://" + uri
                for k in range(raw.FPDFLink_CountRects(wl, i)):
                    izq, arr, der, aba = (ctypes.c_double() for _ in range(4))
                    raw.FPDFLink_GetRect(wl, i, k, izq, arr, der, aba)
                    x0, y0, x1, y1 = self._de_pdf(izq.value, aba.value, der.value, arr.value)
                    salida.append(Enlace(x0, y0, x1, y1, uri))
        finally:
            raw.FPDFLink_CloseWebLinks(wl)
        return salida

    def _enlaces_anotados(self):
        """Enlaces definidos como anotaciones /Link con acción URI."""
        salida = []
        try:
            pagina = self._p.raw
            doc = self._p.pdf.raw
            for i in range(raw.FPDFPage_GetAnnotCount(pagina)):
                anot = raw.FPDFPage_GetAnnot(pagina, i)
                try:
                    if raw.FPDFAnnot_GetSubtype(anot) != raw.FPDF_ANNOT_LINK:
                        continue
                    enlace = raw.FPDFAnnot_GetLink(anot)
                    accion = raw.FPDFLink_GetAction(enlace)
                    if not accion or raw.FPDFAction_GetType(accion) != raw.PDFACTION_URI:
                        continue
                    largo = raw.FPDFAction_GetURIPath(doc, accion, None, 0)
                    if largo <= 1:
                        continue
                    buf = ctypes.create_string_buffer(largo)
                    raw.FPDFAction_GetURIPath(doc, accion, buf, largo)
                    uri = buf.value.decode("utf-8", "ignore")
                    rect = raw.FS_RECTF()
                    if not raw.FPDFAnnot_GetRect(anot, rect):
                        continue
                    x0, y0, x1, y1 = self._de_pdf(rect.left, rect.bottom, rect.right, rect.top)
                    if uri:
                        salida.append(Enlace(x0, y0, x1, y1, uri))
                finally:
                    raw.FPDFPage_CloseAnnot(anot)
        except Exception:
            pass
        return salida

    def cerrar(self):
        try:
            if self._texto is not None:
                self._texto.close()
            self._p.close()
        except Exception:
            pass
