"""Reconocimiento de texto (OCR) con Tesseract, para páginas de PDF cuyo texto es parte de una imagen.

Requiere DOS cosas (la biblioteca de Python es solo el puente hacia el programa):
  1. La biblioteca de Python:   pip install pytesseract
  2. El programa Tesseract:
       * Windows: instalador de UB Mannheim (https://github.com/UB-Mannheim/tesseract/wiki). Se instala en
         C:\\Program Files\\Tesseract-OCR. En el instalador conviene tildar el idioma "Spanish" (Additional language data).
       * Si Tesseract está en otra carpeta, defina la variable de entorno TESSERACT_CMD con la ruta de tesseract.exe.
       * Versión portátil: una carpeta "Tesseract-OCR" junto a la aplicación (ver config.BASE_DIR) se usa antes que
         cualquier otra; así el OCR viaja con el pendrive.

Este módulo no depende de la interfaz: recibe la ruta de una imagen y devuelve el texto.
Importarlo no ejecuta nada (pytesseract se importa al usarlo, así la aplicación arranca aunque falte).
"""
import os
import shutil
import sys

INSTRUCCIONES = ("OCR no disponible: instale el programa Tesseract "
                 "(https://github.com/UB-Mannheim/tesseract/wiki) y reinicie la aplicación.")
INSTRUCCIONES_PIP = "OCR no disponible: falta la biblioteca de Python. Ejecute:  pip install pytesseract"

_RUTAS_WINDOWS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Tesseract-OCR", "tesseract.exe"),
)
_PREFERENCIA_IDIOMAS = ("eng+spa", "spa", "eng")
_TIMEOUT_S = 60
_cache_idioma = {}          # ejecutable -> idioma elegido


class OcrError(Exception):
    """El OCR no pudo ejecutarse (falta algo, falló o tardó demasiado). El mensaje se puede mostrar al usuario."""


def _ruta_portatil():
    """tesseract.exe dentro de <carpeta de la aplicación>\\Tesseract-OCR, si existe (instalación portátil)."""
    try:
        from config import BASE_DIR
    except ImportError:
        return None
    return os.path.join(BASE_DIR, "Tesseract-OCR", "tesseract.exe" if sys.platform.startswith("win") else "tesseract")


def buscar_tesseract():
    """Ruta del programa Tesseract, o None si no está instalado."""
    candidatos = [os.environ.get("TESSERACT_CMD"), _ruta_portatil(), shutil.which("tesseract")]
    if sys.platform.startswith("win"):
        candidatos += list(_RUTAS_WINDOWS)
    for ruta in candidatos:
        if ruta and os.path.isfile(ruta):
            return ruta
    return None


def _preparar():
    """Devuelve el módulo pytesseract configurado con la ruta del programa."""
    try:
        import pytesseract
    except ImportError:
        raise OcrError(INSTRUCCIONES_PIP)
    exe = buscar_tesseract()
    if not exe:
        raise OcrError(INSTRUCCIONES)
    pytesseract.pytesseract.tesseract_cmd = exe
    return pytesseract, exe


def _idioma(pytesseract, exe):
    """Mejor combinación de idiomas instalada (inglés + español si están; si no, lo que haya)."""
    if exe not in _cache_idioma:
        elegido = None
        try:
            instalados = set(pytesseract.get_languages(config=""))
            for opcion in _PREFERENCIA_IDIOMAS:
                if set(opcion.split("+")) <= instalados:
                    elegido = opcion
                    break
            if elegido is None and instalados - {"osd"}:
                elegido = sorted(instalados - {"osd"})[0]
        except Exception:
            pass                         # sin lista de idiomas se usa el predeterminado de Tesseract
        _cache_idioma[exe] = elegido
    return _cache_idioma[exe]


def _limpiar(texto):
    lineas = [" ".join(l.split()) for l in texto.replace("\x0c", "").splitlines()]
    return "\n".join(l for l in lineas if l).strip()


def reconocer_texto(ruta_imagen):
    """Texto reconocido en la imagen (cadena vacía si no encontró nada). Lanza OcrError si no se pudo ejecutar."""
    pytesseract, exe = _preparar()
    idioma = _idioma(pytesseract, exe)
    from PIL import Image
    try:
        with Image.open(ruta_imagen) as imagen:
            imagen.load()
            # psm 6: bloque de texto; si no encuentra nada, psm 11: texto suelto (rótulos dispersos en un diagrama)
            for psm in ("6", "11"):
                try:
                    bruto = pytesseract.image_to_string(imagen, lang=idioma, config=f"--psm {psm}", timeout=_TIMEOUT_S)
                except pytesseract.TesseractNotFoundError:
                    raise OcrError(INSTRUCCIONES)
                except pytesseract.TesseractError as e:
                    raise OcrError(f"Tesseract devolvió un error: {str(e)[:200]}")
                except RuntimeError:                     # pytesseract lanza RuntimeError al agotar el tiempo
                    raise OcrError("El OCR tardó demasiado y se canceló.")
                texto = _limpiar(bruto)
                if texto:
                    return texto
    except OSError as e:
        raise OcrError(f"No se pudo abrir la imagen para el OCR: {e}")
    return ""
