"""Almacenamiento de documentos por contenido (hash SHA-256).

Punto único por el que la aplicación guarda, comprueba y retira archivos
adjuntos. La interfaz no toca el disco por su cuenta: llama a este módulo.

Cómo se guardan los documentos (etapa 7)
----------------------------------------
* Cada documento se guarda UNA sola vez, con el nombre de su huella SHA-256:
      adjuntos/almacen/<2 primeros caracteres>/<huella><extensión>
  Dos documentos con el mismo contenido (aunque tengan distinto nombre o se
  suban a distintos componentes) ocupan un único archivo.
* La base de datos guarda la ruta RELATIVA a la carpeta `adjuntos`
  (por ejemplo "almacen/ab/ab12...ef.pdf"), con barras "/". Así la carpeta de
  la aplicación se puede mover o copiar a otro equipo sin romper nada.
  El nombre que ve el usuario ("LM358.pdf") queda en la columna
  `nombre_amigable`, no en el disco.
* La escritura es atómica: se copia a un archivo temporal dentro del almacén,
  se calcula la huella en la misma pasada y recién entonces se renombra al
  nombre definitivo. Un corte a mitad de copia nunca deja un documento a medias.
* Quitar un documento de un componente NO borra el archivo (otro componente
  puede estar usándolo). Los archivos que ya nadie referencia se mueven a
  `adjuntos/papelera` al arrancar la aplicación (limpiar_huerfanos); nada se
  borra de forma definitiva.
* La cantidad de usos (conteo de referencias) no se guarda aparte: se obtiene
  de la base de datos, que es la fuente de verdad.

Las rutas que maneja la interfaz en memoria son absolutas; `resolver` convierte
la ruta guardada en la base de datos y `para_guardar` hace el camino inverso.

Importar este módulo no toca el disco.
"""
import hashlib
import os
import re
import shutil
import time
import uuid

from config import ATTACHMENTS_DIR, ETIQUETAS_DIR, TMP_DIR

NOMBRE_ALMACEN = "almacen"
ALMACEN_DIR = os.path.join(ATTACHMENTS_DIR, NOMBRE_ALMACEN)
PAPELERA_DIR = os.path.join(ATTACHMENTS_DIR, "papelera")
_SUBCARPETA_TEMPORAL = "_tmp"          # dentro del almacén, para copias en curso
_TAM_BLOQUE = 1024 * 1024
_EXTENSION_VALIDA = re.compile(r"^\.[a-z0-9]{1,10}$")


# -------------------------------------------------------------------
# Nombres y rutas
# -------------------------------------------------------------------
def nombre_archivo(chip, resto):
    """'<chip saneado>_<resto>': el chip solo conserva letras y números (lo demás pasa a '_')."""
    return f"{re.sub(r'[^a-zA-Z0-9]', '_', chip)}_{resto}"


def ruta_temporal(nombre):
    """Ruta de un archivo de trabajo en adjuntos/tmp."""
    return os.path.join(TMP_DIR, nombre)


def ruta_pdf_etiquetas():
    """Ruta fija (carpeta `Etiquetas`) del PDF de etiquetas generado; crea la carpeta si falta."""
    os.makedirs(ETIQUETAS_DIR, exist_ok=True)
    return os.path.join(ETIQUETAS_DIR, "Etiquetas_Inventario.pdf")


def resolver(ruta):
    """Ruta guardada en la base de datos -> ruta absoluta en disco.

    Las rutas absolutas (documentos anteriores a la etapa 7) se devuelven tal cual;
    las relativas se interpretan respecto de la carpeta `adjuntos`.
    """
    if not ruta or os.path.isabs(ruta):
        return ruta
    return os.path.join(ATTACHMENTS_DIR, *re.split(r"[\\/]", ruta))


def resolver_archivos(filas):
    """Aplica `resolver` a la ruta de cada fila (tipo, nombre, ruta) leída de la base."""
    return [(tipo, nombre, resolver(ruta)) for tipo, nombre, ruta in filas]


def esta_en_almacen(ruta):
    """True si la ruta (absoluta o relativa) apunta dentro del almacén por hash."""
    if not ruta:
        return False
    absoluta = os.path.normcase(os.path.abspath(resolver(ruta)))
    almacen = os.path.normcase(os.path.abspath(ALMACEN_DIR))
    return absoluta.startswith(almacen + os.sep)


def _relativa(ruta_absoluta):
    return os.path.relpath(ruta_absoluta, ATTACHMENTS_DIR).replace(os.sep, "/")


# -------------------------------------------------------------------
# Huella y escritura en el almacén
# -------------------------------------------------------------------
def calcular_hash(ruta):
    """Huella SHA-256 (hexadecimal) del contenido de un archivo."""
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(_TAM_BLOQUE), b""):
            h.update(bloque)
    return h.hexdigest()


def _extension(origen):
    ext = os.path.splitext(origen)[1].lower()
    return ext if _EXTENSION_VALIDA.match(ext) else ""


def _buscar_existente(carpeta, huella):
    """Archivo ya guardado con esa huella (con cualquier extensión), o None."""
    if not os.path.isdir(carpeta):
        return None
    for nombre in os.listdir(carpeta):
        if nombre == huella or (nombre.startswith(huella) and nombre[len(huella)] == "."):
            return os.path.join(carpeta, nombre)
    return None


def incorporar(origen):
    """Guarda el archivo `origen` en el almacén. Devuelve (ruta_relativa, huella).

    Si ya existe un documento con el mismo contenido no se escribe nada y se
    devuelve el existente. La copia es atómica (ver el encabezado del módulo).
    """
    carpeta_tmp = os.path.join(ALMACEN_DIR, _SUBCARPETA_TEMPORAL)
    os.makedirs(carpeta_tmp, exist_ok=True)
    temporal = os.path.join(carpeta_tmp, uuid.uuid4().hex + ".part")
    h = hashlib.sha256()
    try:
        with open(origen, "rb") as entrada, open(temporal, "wb") as salida:
            for bloque in iter(lambda: entrada.read(_TAM_BLOQUE), b""):
                h.update(bloque)
                salida.write(bloque)
            salida.flush()
            os.fsync(salida.fileno())
        huella = h.hexdigest()
        carpeta = os.path.join(ALMACEN_DIR, huella[:2])
        os.makedirs(carpeta, exist_ok=True)

        existente = _buscar_existente(carpeta, huella)
        if existente and os.path.getsize(existente) == os.path.getsize(temporal):
            os.remove(temporal)
            destino = existente
        else:
            # No existía, o el existente está incompleto/dañado: se reemplaza de forma atómica.
            destino = existente or os.path.join(carpeta, huella + _extension(origen))
            os.replace(temporal, destino)
    except BaseException:
        if os.path.exists(temporal):
            os.remove(temporal)
        raise
    return _relativa(destino), huella


def preparar_adjunto(origen):
    """Registra un archivo elegido por el usuario. Devuelve (ruta, nombre_original).

    No copia nada todavía: el documento entra al almacén cuando se guarda el
    componente (`para_guardar`). Así, si el usuario cancela, no queda basura.
    """
    return origen, os.path.basename(origen)


def para_guardar(ruta):
    """Ruta en memoria -> ruta que se guarda en la base de datos.

    * Ya está en el almacén: se devuelve su ruta relativa.
    * Es un archivo existente fuera del almacén: se incorpora y se devuelve la relativa.
    * No existe (referencia rota): se devuelve sin cambios, para no perder el registro.
    """
    if not ruta:
        return ruta
    absoluta = resolver(ruta)
    if esta_en_almacen(absoluta):
        return _relativa(os.path.abspath(absoluta))
    if os.path.isfile(absoluta):
        return incorporar(absoluta)[0]
    return ruta


# -------------------------------------------------------------------
# Imágenes de trabajo
# -------------------------------------------------------------------
def guardar_imagen(imagen, destino):
    """Guarda una imagen en la ruta que eligió el usuario, creando la carpeta si falta."""
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    if imagen.save(destino) is False:      # Qt devuelve False (sin excepción) si no pudo escribir
        raise OSError("no se pudo escribir el archivo (¿extensión o permisos?)")


def guardar_temporal(imagen, nombre, formato=None):
    """Guarda una imagen en adjuntos/tmp y devuelve la ruta. `formato` es opcional (p. ej. 'PNG')."""
    ruta = ruta_temporal(nombre)
    if formato:
        imagen.save(ruta, formato)
    else:
        imagen.save(ruta)
    return ruta


# -------------------------------------------------------------------
# Consulta
# -------------------------------------------------------------------
def existe(ruta):
    """True si el archivo existe en disco (acepta ruta absoluta o relativa a `adjuntos`)."""
    return os.path.exists(resolver(ruta))


def listar_almacen():
    """Rutas absolutas de todos los documentos del almacén (sin las copias en curso)."""
    encontrados = []
    if not os.path.isdir(ALMACEN_DIR):
        return encontrados
    for carpeta, subcarpetas, archivos in os.walk(ALMACEN_DIR):
        subcarpetas[:] = [d for d in subcarpetas if d != _SUBCARPETA_TEMPORAL]
        encontrados += [os.path.join(carpeta, a) for a in archivos]
    return sorted(encontrados)


def verificar_almacen():
    """Recalcula la huella de cada documento. Devuelve [(ruta, problema)] (vacía si todo está bien)."""
    problemas = []
    for ruta in listar_almacen():
        esperado = os.path.splitext(os.path.basename(ruta))[0]
        if calcular_hash(ruta) != esperado:
            problemas.append((ruta, "el contenido no coincide con su huella"))
    return problemas


# -------------------------------------------------------------------
# Mantenimiento
# -------------------------------------------------------------------
def huerfanos(rutas_en_uso):
    """Documentos del almacén que ninguna fila de la base referencia."""
    usadas = {os.path.normcase(os.path.abspath(resolver(r))) for r in (rutas_en_uso or []) if r}
    return [r for r in listar_almacen() if os.path.normcase(os.path.abspath(r)) not in usadas]


def limpiar_huerfanos(rutas_en_uso, antiguedad_minima_s=3600):
    """Mueve a `adjuntos/papelera` los documentos sin uso. Devuelve las rutas movidas.

    * No borra nada de forma definitiva: la papelera se vacía a mano.
    * Respeta los archivos recientes (por defecto menos de 1 hora) por si otra
      instancia de la aplicación los acaba de subir y todavía no los guardó.
    * Retira también copias temporales abandonadas (más de 1 día).
    """
    ahora = time.time()
    movidos = []
    for ruta in huerfanos(rutas_en_uso):
        if ahora - os.path.getmtime(ruta) < antiguedad_minima_s:
            continue
        os.makedirs(PAPELERA_DIR, exist_ok=True)
        destino = os.path.join(PAPELERA_DIR, os.path.basename(ruta))
        if os.path.exists(destino):
            base, ext = os.path.splitext(destino)
            destino = f"{base}.{int(ahora)}{ext}"
        shutil.move(ruta, destino)
        movidos.append(ruta)
        print(f"Documento sin uso movido a la papelera: {ruta}")
        try:
            os.rmdir(os.path.dirname(ruta))      # solo si quedó vacía
        except OSError:
            pass
    carpeta_tmp = os.path.join(ALMACEN_DIR, _SUBCARPETA_TEMPORAL)
    if os.path.isdir(carpeta_tmp):
        for nombre in os.listdir(carpeta_tmp):
            ruta = os.path.join(carpeta_tmp, nombre)
            if ahora - os.path.getmtime(ruta) > 86400:
                os.remove(ruta)
    return movidos
