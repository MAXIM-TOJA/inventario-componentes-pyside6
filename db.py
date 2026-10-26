"""Capa de acceso a datos (SQLite).

Todas las consultas de la aplicación viven aquí: la interfaz no abre
conexiones propias, llama a las funciones de este módulo.

Importar este módulo no toca el disco. La base se crea al llamar a
inicializar_base_de_datos().

Convención de filtros: un filtro en None (o vacío) significa "sin filtrar".
La interfaz es quien traduce sus textos comodín ("-- Todos los Tipos --", etc.)
a None antes de llamar.
"""
import math
import sqlite3
from contextlib import contextmanager
from datetime import date

import catalogo
from config import DB_PATH
from utilidades import limpiar_prefijo


@contextmanager
def conexion():
    """Abre una conexión con las claves foráneas activadas y la cierra al salir.

    PRAGMA foreign_keys se aplica por conexión en SQLite; sin esta línea el
    ON DELETE CASCADE declarado en el esquema no se ejecuta.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
    finally:
        conn.close()


# -------------------------------------------------------------------
# Esquema
# -------------------------------------------------------------------
def inicializar_base_de_datos():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS productos_fabricantes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            producto_id TEXT,
            tipo_componente TEXT,
            categoria TEXT,
            subcategoria TEXT,
            item_especifico TEXT,
            descripcion TEXT,
            fabricante TEXT,
            chip_principal TEXT,
            interfaz_comunicacion TEXT,
            pines_relevantes TEXT,
            encapsulado TEXT,
            stock INTEGER,
            precio REAL,
            ubicacion TEXT,
            obsolescencia TEXT,
            proveedor_exterior TEXT,
            precio_exterior REAL,
            moneda_exterior TEXT,   -- Asegúrate de añadir esta
            proveedor_local TEXT,
            precio_local REAL,
            moneda_local TEXT       -- Y esta
        )
    """)
    conn.commit()
    
    cursor.execute("PRAGMA table_info(productos_fabricantes)")
    columnas = [col[1] for col in cursor.fetchall()]
    if "qr_path" not in columnas:
        cursor.execute("ALTER TABLE productos_fabricantes ADD COLUMN qr_path TEXT")
    if "precio_exterior" not in columnas:
        cursor.execute("ALTER TABLE productos_fabricantes ADD COLUMN precio_exterior REAL DEFAULT 0.0")
    if "proveedor_exterior" not in columnas:
        cursor.execute("ALTER TABLE productos_fabricantes ADD COLUMN proveedor_exterior TEXT")
    if "precio_local" not in columnas:
        cursor.execute("ALTER TABLE productos_fabricantes ADD COLUMN precio_local REAL DEFAULT 0.0")
    if "proveedor_local" not in columnas:
        cursor.execute("ALTER TABLE productos_fabricantes ADD COLUMN proveedor_local TEXT")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS archivos_componentes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            componente_id INTEGER NOT NULL,
            tipo_archivo TEXT NOT NULL,
            nombre_amigable TEXT NOT NULL,
            ruta_archivo TEXT NOT NULL,
            FOREIGN KEY (componente_id) REFERENCES productos_fabricantes (id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parametros_electricos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            componente_id INTEGER NOT NULL,
            parametro_clave TEXT NOT NULL,
            parametro_valor TEXT NOT NULL,
            FOREIGN KEY (componente_id) REFERENCES productos_fabricantes (id) ON DELETE CASCADE
        )
    """)
    # Catálogo de clasificación: una fila por camino tipo > categoría > subcategoría > ítem.
    # Un nivel sin definir se guarda como '' (así un tipo recién creado existe aunque no tenga hijos).
    # COLLATE NOCASE: "Arduino Uno" y "ARDUINO UNO" son la misma entrada.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS catalogo_clasificacion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL COLLATE NOCASE,
            categoria TEXT NOT NULL DEFAULT '' COLLATE NOCASE,
            subcategoria TEXT NOT NULL DEFAULT '' COLLATE NOCASE,
            item TEXT NOT NULL DEFAULT '' COLLATE NOCASE,
            UNIQUE (tipo, categoria, subcategoria, item)
        )
    """)
    # Listas de los desplegables (fabricante, interfaz, pines, encapsulado, moneda).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS listas_valores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lista TEXT NOT NULL,
            valor TEXT NOT NULL COLLATE NOCASE,
            orden INTEGER NOT NULL DEFAULT 0,
            UNIQUE (lista, valor)
        )
    """)
    # Parámetros disponibles por nodo de la taxonomía (se heredan hacia abajo).
    # El nodo es el camino tipo > categoría > subcategoría > ítem, con '' en los niveles que no aplican.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS plantillas_parametros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL COLLATE NOCASE,
            categoria TEXT NOT NULL DEFAULT '' COLLATE NOCASE,
            subcategoria TEXT NOT NULL DEFAULT '' COLLATE NOCASE,
            item TEXT NOT NULL DEFAULT '' COLLATE NOCASE,
            parametro TEXT NOT NULL COLLATE NOCASE,
            orden INTEGER NOT NULL DEFAULT 0,
            UNIQUE (tipo, categoria, subcategoria, item, parametro)
        )
    """)
    # Cotizaciones: cuántas unidades de cada moneda equivalen a 1 USD (la moneda base). Las carga el usuario.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cotizaciones (
            moneda TEXT PRIMARY KEY COLLATE NOCASE,
            por_usd REAL,
            fecha TEXT
        )
    """)
    conn.commit()
    _sembrar(conn)
    conn.commit()
    conn.close()


# -------------------------------------------------------------------
# Siembra inicial de las tablas de catálogo y listas
# -------------------------------------------------------------------
NIVELES = ("tipo", "categoria", "subcategoria", "item")                       # columnas del catálogo
_COL_COMPONENTE = ("tipo_componente", "categoria", "subcategoria", "item_especifico")  # mismas, en productos_fabricantes

# lista -> (columnas de productos_fabricantes que la usan, ¿guarda varios valores separados por ", "?)
LISTAS = {
    "fabricante": (("fabricante",), False),
    "interfaz": (("interfaz_comunicacion",), True),
    "pines": (("pines_relevantes",), True),
    "encapsulado": (("encapsulado",), True),
    "moneda": (("moneda_exterior", "moneda_local"), False),
    "proveedor_local": (("proveedor_local",), False),
    "proveedor_exterior": (("proveedor_exterior",), False),
}
SIN_DATO = "N/A"
MONEDA_BASE = "USD"   # las cotizaciones se expresan como unidades de cada moneda por 1 USD
# listas que siempre empiezan con «N/A» (sin dato)
LISTAS_CON_SIN_DATO = ("fabricante", "interfaz", "pines", "encapsulado", "proveedor_local", "proveedor_exterior")


def _ruta(valores):
    """Normaliza un camino de hasta 4 niveles a una tupla de 4 textos ('' = nivel sin definir).

    Devuelve None si no hay tipo. Un nivel vacío o comodín ("-- Todos --") corta el camino.
    """
    ruta = []
    for i in range(4):
        v = str(valores[i]).strip() if i < len(valores) and valores[i] is not None else ""
        if v.startswith("--"):
            v = ""
        if i == 0 and v:
            v = limpiar_prefijo(v)
        if not v:
            break
        ruta.append(v)
    if not ruta:
        return None
    return tuple(ruta) + ("",) * (4 - len(ruta))


def _insertar_ruta(conn, ruta):
    """Agrega un camino al catálogo (si no existe) y quita los marcadores de nivel que ya tienen hijos."""
    n = sum(1 for x in ruta if x)
    if n < 4:   # un camino corto solo hace falta si todavía no tiene nada debajo
        cond = " AND ".join(f"{c}=?" for c in NIVELES[:n]) + f" AND {NIVELES[n]}<>''"
        if conn.execute(f"SELECT 1 FROM catalogo_clasificacion WHERE {cond}", ruta[:n]).fetchone():
            return
    conn.execute("INSERT OR IGNORE INTO catalogo_clasificacion (tipo, categoria, subcategoria, item) VALUES (?,?,?,?)", ruta)
    for k in range(1, n):
        ancestro = ruta[:k] + ("",) * (4 - k)
        conn.execute("DELETE FROM catalogo_clasificacion WHERE tipo=? AND categoria=? AND subcategoria=? AND item=?", ancestro)


def _valores_de(texto, multiple):
    """Valores sueltos de un campo de componente (los de selección múltiple se guardan como 'A, B, C')."""
    texto = str(texto or "").strip()
    partes = [p.strip() for p in texto.split(",")] if multiple else [texto]
    return [p for p in partes if p and p.upper() != SIN_DATO and not p.startswith("--")]


def _agregar_valor(conn, lista, valor):
    conn.execute("""INSERT OR IGNORE INTO listas_valores (lista, valor, orden)
                    VALUES (?, ?, COALESCE((SELECT MAX(orden) FROM listas_valores WHERE lista=?), 0) + 1)""",
                 (lista, valor, lista))


def _asegurar_sin_dato(conn):
    """«N/A» encabeza las listas que lo llevan (también en bases creadas antes de que existiera en ellas)."""
    for lista in LISTAS_CON_SIN_DATO:
        conn.execute("INSERT OR IGNORE INTO listas_valores (lista, valor, orden) VALUES (?, ?, 0)", (lista, SIN_DATO))


def _sembrar(conn):
    """Carga el contenido inicial. Cada tabla se siembra solo si está vacía, así lo que el usuario
    borre o renombre después no vuelve a aparecer. También incorpora lo que ya hay en los componentes."""
    if conn.execute("SELECT COUNT(*) FROM catalogo_clasificacion").fetchone()[0] == 0:
        rutas = []
        for tipo, cats in catalogo.CATALOGO_PREDEFINIDO_4N.items():
            for cat, subs in cats.items():
                for sub, items in subs.items():
                    for item in items:
                        rutas.append((tipo, cat, sub, item))
        for fila in conn.execute("SELECT DISTINCT tipo_componente, categoria, subcategoria, item_especifico FROM productos_fabricantes"):
            rutas.append(fila)
        for r in rutas:
            ruta = _ruta(r)
            if ruta:
                _insertar_ruta(conn, ruta)

    for lista, (columnas, multiple) in LISTAS.items():
        if conn.execute("SELECT COUNT(*) FROM listas_valores WHERE lista=?", (lista,)).fetchone()[0] == 0:
            for v in catalogo.LISTAS_PREDEFINIDAS.get(lista, []):
                _agregar_valor(conn, lista, v)
            for col in columnas:
                for (texto,) in conn.execute(f"SELECT DISTINCT {col} FROM productos_fabricantes").fetchall():
                    for v in _valores_de(texto, multiple):
                        _agregar_valor(conn, lista, v)
    _asegurar_sin_dato(conn)
    conn.execute("INSERT OR IGNORE INTO cotizaciones (moneda, por_usd, fecha) VALUES (?, 1.0, NULL)", (MONEDA_BASE,))

    if conn.execute("SELECT COUNT(*) FROM plantillas_parametros").fetchone()[0] == 0:
        for ruta, parametros in catalogo.PARAMETROS_PREDEFINIDOS.items():
            nodo = _ruta(ruta)
            for orden, parametro in enumerate(parametros, start=1):
                conn.execute("INSERT OR IGNORE INTO plantillas_parametros (tipo, categoria, subcategoria, item, parametro, orden) VALUES (?,?,?,?,?,?)",
                             nodo + (parametro, orden))


# -------------------------------------------------------------------
# Consultas para los desplegables en cascada (leen el catálogo)
# -------------------------------------------------------------------
def _listar_nivel(nivel, previos):
    """Nombres distintos del nivel `nivel` (0..3). `previos`: valores de los niveles anteriores; None/'' = cualquiera."""
    col = NIVELES[nivel]
    donde, params = [f"{col}<>''"], []
    for c, v in zip(NIVELES[:nivel], previos):
        if v:
            donde.append(f"{c}=?")
            params.append(v)
    with conexion() as conn:
        cursor = conn.execute(f"SELECT DISTINCT {col} FROM catalogo_clasificacion WHERE {' AND '.join(donde)} ORDER BY {col}", params)
        return [r[0] for r in cursor.fetchall()]


def listar_tipos():
    return _listar_nivel(0, ())


def listar_categorias(tipo=None):
    """Categorías del catálogo; con `tipo` solo las de ese tipo."""
    return _listar_nivel(1, (tipo,))


def listar_subcategorias(tipo=None, cat=None):
    """Subcategorías del catálogo; cada filtro presente se aplica."""
    return _listar_nivel(2, (tipo, cat))


def listar_items(tipo=None, cat=None, subcat=None):
    """Ítems del catálogo; cada filtro presente se aplica."""
    return _listar_nivel(3, (tipo, cat, subcat))


# -------------------------------------------------------------------
# Administración del catálogo de clasificación
# -------------------------------------------------------------------
def _validar_nombre(nombre):
    nombre = str(nombre or "").strip()
    if not nombre:
        raise ValueError("El nombre no puede estar vacío.")
    if nombre.startswith("--"):
        raise ValueError("El nombre no puede empezar con «--».")
    return nombre


def _condicion_ruta(ruta, columnas):
    """('c1=? AND c2=?', params) para los niveles dados en `ruta`."""
    return " AND ".join(f"{c}=?" for c in columnas[:len(ruta)]), list(ruta)


def listar_catalogo():
    """Todos los caminos del catálogo: lista de (tipo, categoría, subcategoría, ítem); '' = nivel sin definir."""
    with conexion() as conn:
        return conn.execute("SELECT tipo, categoria, subcategoria, item FROM catalogo_clasificacion ORDER BY tipo, categoria, subcategoria, item").fetchall()


def agregar_catalogo(ruta):
    """Agrega un nodo al catálogo. `ruta`: nombres desde el tipo hasta el nivel nuevo (1 a 4).
    Devuelve la ruta tal como quedó (el tipo sin número de prefijo). Lanza ValueError si no es válido."""
    ruta = tuple(_validar_nombre(x) for x in ruta)
    if not 1 <= len(ruta) <= 4:
        raise ValueError("La clasificación tiene como máximo 4 niveles.")
    completa = _ruta(ruta)
    with conexion() as conn:
        try:
            _insertar_ruta(conn, completa)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return tuple(x for x in completa if x)


def contar_componentes_catalogo(ruta):
    """Cuántos componentes están clasificados bajo ese nodo."""
    cond, params = _condicion_ruta(ruta, _COL_COMPONENTE)
    with conexion() as conn:
        return conn.execute(f"SELECT COUNT(*) FROM productos_fabricantes WHERE {cond}", params).fetchone()[0]


def renombrar_catalogo(ruta, nuevo):
    """Cambia el nombre del último nivel de `ruta`, en el catálogo y en los componentes que lo usan.

    Si ya existe un nodo con ese nombre bajo el mismo padre, los dos se unen.
    Devuelve la ruta nueva del nodo.
    """
    ruta = tuple(ruta)
    n = len(ruta) - 1
    nuevo = _validar_nombre(limpiar_prefijo(nuevo) if n == 0 else nuevo)
    viejo = ruta[n]
    cond_cat, params = _condicion_ruta(ruta, NIVELES)
    cond_comp, _ = _condicion_ruta(ruta, _COL_COMPONENTE)
    with conexion() as conn:
        try:
            if nuevo.lower() == viejo.lower():
                # Solo cambia mayúsculas/minúsculas: no puede haber choque, es la misma entrada.
                conn.execute(f"UPDATE catalogo_clasificacion SET {NIVELES[n]}=? WHERE {cond_cat}", [nuevo] + params)
            else:
                conn.execute(f"UPDATE OR IGNORE catalogo_clasificacion SET {NIVELES[n]}=? WHERE {cond_cat}", [nuevo] + params)
                # lo que no pudo cambiar chocó con una entrada existente: ya está representado por ella
                conn.execute(f"DELETE FROM catalogo_clasificacion WHERE {cond_cat}", params)
            # los parámetros del nodo (y de los que cuelgan de él) lo acompañan
            if nuevo.lower() == viejo.lower():
                conn.execute(f"UPDATE plantillas_parametros SET {NIVELES[n]}=? WHERE {cond_cat}", [nuevo] + params)
            else:
                conn.execute(f"UPDATE OR IGNORE plantillas_parametros SET {NIVELES[n]}=? WHERE {cond_cat}", [nuevo] + params)
                conn.execute(f"DELETE FROM plantillas_parametros WHERE {cond_cat}", params)
            if n >= 1:   # 'nombre' repite el último nivel definido; se mantiene al día
                conn.execute(f"UPDATE productos_fabricantes SET nombre=?, producto_id=? WHERE nombre=? AND {cond_comp}",
                             [nuevo, nuevo, viejo] + params)
            conn.execute(f"UPDATE productos_fabricantes SET {_COL_COMPONENTE[n]}=? WHERE {cond_comp}", [nuevo] + params)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return ruta[:-1] + (nuevo,)


def eliminar_catalogo(ruta):
    """Quita el nodo (y todo lo que cuelga de él, con sus parámetros) del catálogo. Los componentes conservan su clasificación escrita."""
    ruta = tuple(ruta)
    cond, params = _condicion_ruta(ruta, NIVELES)
    with conexion() as conn:
        try:
            conn.execute(f"DELETE FROM catalogo_clasificacion WHERE {cond}", params)
            conn.execute(f"DELETE FROM plantillas_parametros WHERE {cond}", params)
            if len(ruta) > 1:   # si el padre se quedó sin hijos, sigue existiendo como nodo
                _insertar_ruta(conn, _ruta(ruta[:-1]))
            conn.commit()
        except Exception:
            conn.rollback()
            raise


# -------------------------------------------------------------------
# Parámetros por clasificación (con herencia)
# -------------------------------------------------------------------
def ruta_de_clasificacion(tipo, cat, subcat, item):
    """Camino de un componente como tupla de 0 a 4 nombres (se corta en el primer nivel vacío o comodín «-- … --»)."""
    ruta = _ruta((tipo, cat, subcat, item))
    return tuple(x for x in ruta if x) if ruta else ()


def _nodo(ruta):
    """Ruta de 1 a 4 nombres -> tupla de 4 con '' en los niveles que faltan."""
    ruta = tuple(str(x).strip() for x in ruta)
    if not 1 <= len(ruta) <= 4 or not all(ruta):
        raise ValueError("Elija primero un nodo de la clasificación.")
    return ruta + ("",) * (4 - len(ruta))


def listar_plantillas():
    """Todos los parámetros definidos: lista de (ruta del nodo, parámetro), en el orden de cada nodo."""
    with conexion() as conn:
        filas = conn.execute("SELECT tipo, categoria, subcategoria, item, parametro FROM plantillas_parametros ORDER BY tipo, categoria, subcategoria, item, orden, id").fetchall()
    return [(tuple(x for x in f[:4] if x), f[4]) for f in filas]


def listar_parametros_plantilla(ruta):
    """Parámetros propios de ese nodo (sin los heredados)."""
    with conexion() as conn:
        return [r[0] for r in conn.execute(
            "SELECT parametro FROM plantillas_parametros WHERE tipo=? AND categoria=? AND subcategoria=? AND item=? ORDER BY orden, id", _nodo(ruta))]


def parametros_heredados(ruta):
    """Parámetros que corresponden a un componente de esa clasificación: [(parámetro, ruta del nodo que lo define)].

    Van de lo general a lo particular (primero los del tipo, al final los del último nivel) y un
    nombre repetido se muestra una sola vez, con el nodo más general que lo define.
    """
    ruta = tuple(ruta)
    resultado, vistos = [], set()
    for k in range(1, len(ruta) + 1):
        for parametro in listar_parametros_plantilla(ruta[:k]):
            if parametro.lower() not in vistos:
                vistos.add(parametro.lower())
                resultado.append((parametro, ruta[:k]))
    return resultado


def agregar_parametro_plantilla(ruta, parametro):
    """Agrega un parámetro al nodo y devuelve el nombre tal como quedó (si ya existía, el existente)."""
    nodo = _nodo(ruta)
    parametro = _validar_nombre(parametro)
    with conexion() as conn:
        conn.execute("""INSERT OR IGNORE INTO plantillas_parametros (tipo, categoria, subcategoria, item, parametro, orden)
                        VALUES (?,?,?,?,?, COALESCE((SELECT MAX(orden) FROM plantillas_parametros WHERE tipo=? AND categoria=? AND subcategoria=? AND item=?), 0) + 1)""",
                     nodo + (parametro,) + nodo)
        conn.commit()
        return conn.execute("SELECT parametro FROM plantillas_parametros WHERE tipo=? AND categoria=? AND subcategoria=? AND item=? AND parametro=?", nodo + (parametro,)).fetchone()[0]


def renombrar_parametro_plantilla(ruta, viejo, nuevo):
    """Cambia el nombre de un parámetro de ese nodo. No toca los valores ya guardados en los componentes."""
    nodo = _nodo(ruta)
    nuevo = _validar_nombre(nuevo)
    with conexion() as conn:
        try:
            conn.execute("UPDATE plantillas_parametros SET parametro=? WHERE tipo=? AND categoria=? AND subcategoria=? AND item=? AND parametro=?", (nuevo,) + nodo + (viejo,))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            raise ValueError(f"«{nuevo}» ya existe en ese nodo.")


def eliminar_parametro_plantilla(ruta, parametro):
    """Quita un parámetro de ese nodo. Los valores ya guardados en los componentes se conservan."""
    nodo = _nodo(ruta)
    with conexion() as conn:
        conn.execute("DELETE FROM plantillas_parametros WHERE tipo=? AND categoria=? AND subcategoria=? AND item=? AND parametro=?", nodo + (parametro,))
        conn.commit()


# -------------------------------------------------------------------
# Listas de valores de los desplegables (fabricante, interfaz, pines, encapsulado, moneda)
# -------------------------------------------------------------------
def listar_valores(lista):
    """Valores de la lista, en el orden en que se cargaron."""
    with conexion() as conn:
        cursor = conn.execute("SELECT valor FROM listas_valores WHERE lista=? ORDER BY orden, id", (lista,))
        return [r[0] for r in cursor.fetchall()]


def _validar_valor(lista, valor):
    valor = _validar_nombre(valor)
    if valor.upper() == SIN_DATO:
        raise ValueError(f"«{SIN_DATO}» ya existe y no se puede modificar.")
    if LISTAS[lista][1] and "," in valor:
        raise ValueError("En esta lista no se permiten comas (se usan para separar las opciones elegidas).")
    return valor


def agregar_valor(lista, valor):
    """Agrega un valor a la lista y devuelve el texto tal como quedó guardado
    (si ya existía con otras mayúsculas, devuelve el existente). Lanza ValueError si no es válido."""
    valor = _validar_valor(lista, valor)
    with conexion() as conn:
        _agregar_valor(conn, lista, valor)
        conn.commit()
        return conn.execute("SELECT valor FROM listas_valores WHERE lista=? AND valor=?", (lista, valor)).fetchone()[0]


def _usos(conn, lista, valor):
    """[(id_componente, columna, texto)] de los componentes que tienen ese valor en la lista."""
    columnas, multiple = LISTAS[lista]
    usos = []
    for col in columnas:
        if multiple:
            filas = conn.execute(f"SELECT id, {col} FROM productos_fabricantes WHERE {col} LIKE ?", (f"%{valor}%",)).fetchall()
            usos += [(i, col, t) for i, t in filas if valor in [p.strip() for p in str(t).split(",")]]
        else:
            usos += [(i, col, valor) for (i,) in conn.execute(f"SELECT id FROM productos_fabricantes WHERE {col}=?", (valor,)).fetchall()]
    return usos


def contar_uso_valor(lista, valor):
    """Cuántos componentes usan ese valor."""
    with conexion() as conn:
        return len({i for i, _, _ in _usos(conn, lista, valor)})


def renombrar_valor(lista, viejo, nuevo):
    """Cambia un valor de la lista y también en los componentes que lo usan. Lanza ValueError si no es válido."""
    if str(viejo).upper() == SIN_DATO:
        raise ValueError(f"«{SIN_DATO}» no se puede modificar.")
    nuevo = _validar_valor(lista, nuevo)
    columnas, multiple = LISTAS[lista]
    with conexion() as conn:
        try:
            usos = _usos(conn, lista, viejo)     # antes de tocar nada
            try:
                conn.execute("UPDATE listas_valores SET valor=? WHERE lista=? AND valor=?", (nuevo, lista, viejo))
            except sqlite3.IntegrityError:
                raise ValueError(f"«{nuevo}» ya existe en la lista.")
            if lista == "moneda":
                conn.execute("UPDATE OR IGNORE cotizaciones SET moneda=? WHERE moneda=?", (nuevo, viejo))
            for i, col, texto in usos:
                if multiple:
                    texto = ", ".join(nuevo if p.strip() == viejo else p.strip() for p in str(texto).split(","))
                    conn.execute(f"UPDATE productos_fabricantes SET {col}=? WHERE id=?", (texto, i))
                else:
                    conn.execute(f"UPDATE productos_fabricantes SET {col}=? WHERE id=?", (nuevo, i))
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def eliminar_valor(lista, valor):
    """Quita el valor de la lista. Los componentes que ya lo tienen conservan el texto."""
    if str(valor).upper() == SIN_DATO:
        raise ValueError(f"«{SIN_DATO}» no se puede eliminar.")
    with conexion() as conn:
        conn.execute("DELETE FROM listas_valores WHERE lista=? AND valor=?", (lista, valor))
        conn.commit()


# -------------------------------------------------------------------
# Componentes
# -------------------------------------------------------------------
def buscar_componentes(tipo=None, cat=None, subcat=None, item=None, texto=None):
    """Filas para la grilla principal (19 columnas, el orden importa a la interfaz)."""
    query = """
            SELECT id, nombre, chip_principal, tipo_componente, categoria, subcategoria, item_especifico, 
                   descripcion, fabricante, interfaz_comunicacion, pines_relevantes, stock, precio, ubicacion, qr_path,
                   precio_exterior, proveedor_exterior, precio_local, proveedor_local
            FROM productos_fabricantes WHERE 1=1
        """
    params = []

    if tipo:
        query += " AND tipo_componente=?"
        params.append(tipo)
    if cat:
        query += " AND categoria=?"
        params.append(cat)
    if subcat:
        query += " AND subcategoria=?"
        params.append(subcat)
    if item:
        query += " AND item_especifico=?"
        params.append(item)

    if texto:
        query += " AND (nombre LIKE ? OR descripcion LIKE ? OR fabricante LIKE ? OR chip_principal LIKE ? OR proveedor_exterior LIKE ? OR proveedor_local LIKE ?)"
        p = f"%{texto}%"
        params.extend([p, p, p, p, p, p])

    with conexion() as conn:
        cursor = conn.execute(query, params)
        return cursor.fetchall()


def obtener_componente(comp_id):
    """Todas las columnas del componente como diccionario, o None si no existe."""
    with conexion() as conn:
        cursor = conn.execute("SELECT * FROM productos_fabricantes WHERE id=?", (comp_id,))
        col_names = [description[0] for description in cursor.description]
        row_data = cursor.fetchone()
    return dict(zip(col_names, row_data)) if row_data else None


def obtener_datos_etiqueta(item_id):
    """(chip_principal, item_especifico, descripcion, ubicacion, fabricante, stock) o None."""
    with conexion() as conn:
        cursor = conn.execute("SELECT chip_principal, item_especifico, descripcion, ubicacion, fabricante, stock FROM productos_fabricantes WHERE id=?", (item_id,))
        return cursor.fetchone()


def _valores_componente(d):
    """Valores de la fila en el orden exacto que esperan el UPDATE y el INSERT."""
    return (d['nombre'], d['nombre'], d['tipo_componente'], d['categoria'], d['subcategoria'], d['item_especifico'],
            d['descripcion'], d['fabricante'], d['chip_principal'],
            d['interfaz_comunicacion'], d['pines_relevantes'], d['encapsulado'],
            d['stock'], d['precio'], d['ubicacion'],
            d['precio_exterior'], d['moneda_exterior'], d['proveedor_exterior'],
            d['precio_local'], d['moneda_local'], d['proveedor_local'], d['obsolescencia'])


def guardar_componente(comp_id, datos, archivos, parametros):
    """Inserta (comp_id=None) o actualiza un componente con sus archivos y parámetros.

    Todo ocurre en una sola transacción: si algo falla se revierte y se vuelve
    a lanzar la excepción. Devuelve el id del componente.

    datos:      dict con las columnas del componente (producto_id se toma de 'nombre').
    archivos:   lista de (tipo_archivo, nombre_amigable, ruta_archivo).
    parametros: lista de (clave, valor); las claves vacías se ignoran.
    """
    with conexion() as conn:
        cursor = conn.cursor()
        try:
            valores = _valores_componente(datos)
            if comp_id is not None:
                cursor.execute("""
                    UPDATE productos_fabricantes 
                    SET nombre=?, producto_id=?, tipo_componente=?, categoria=?, subcategoria=?, item_especifico=?, 
                        descripcion=?, fabricante=?, chip_principal=?, interfaz_comunicacion=?, pines_relevantes=?, 
                        encapsulado=?, stock=?, precio=?, ubicacion=?,
                        precio_exterior=?, moneda_exterior=?, proveedor_exterior=?, 
                        precio_local=?, moneda_local=?, proveedor_local=?, obsolescencia=?
                    WHERE id=?
                """, valores + (comp_id,))
            else:
                cursor.execute("""
                    INSERT INTO productos_fabricantes 
                    (nombre, producto_id, tipo_componente, categoria, subcategoria, item_especifico, 
                     descripcion, fabricante, chip_principal, interfaz_comunicacion, pines_relevantes, 
                     encapsulado, stock, precio, ubicacion,
                     precio_exterior, moneda_exterior, proveedor_exterior, 
                     precio_local, moneda_local, proveedor_local, obsolescencia)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, valores)
                comp_id = cursor.lastrowid

            # Archivos múltiples (imágenes, datasheets, tutoriales)
            cursor.execute("DELETE FROM archivos_componentes WHERE componente_id=?", (comp_id,))
            for tipo, nombre, ruta in archivos:
                cursor.execute("""
                    INSERT INTO archivos_componentes (componente_id, tipo_archivo, nombre_amigable, ruta_archivo)
                    VALUES (?, ?, ?, ?)
                """, (comp_id, tipo, nombre, ruta))

            # Parámetros eléctricos / especificaciones
            cursor.execute("DELETE FROM parametros_electricos WHERE componente_id=?", (comp_id,))
            for clave, valor in parametros:
                if clave.strip():
                    cursor.execute("""
                        INSERT INTO parametros_electricos (componente_id, parametro_clave, parametro_valor)
                        VALUES (?, ?, ?)
                    """, (comp_id, clave.strip(), valor.strip()))

            # Lo escrito a mano pasa a formar parte del catálogo y de las listas (crece según la necesidad)
            ruta = _ruta((datos.get('tipo_componente'), datos.get('categoria'), datos.get('subcategoria'), datos.get('item_especifico')))
            if ruta:
                _insertar_ruta(conn, ruta)
            for lista, (columnas, multiple) in LISTAS.items():
                for col in columnas:
                    for v in _valores_de(datos.get(col), multiple):
                        _agregar_valor(conn, lista, v)

            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return comp_id


def eliminar_componente(comp_id):
    """Borra el componente. Con foreign_keys activo, el CASCADE borra sus filas de archivos y parámetros."""
    with conexion() as conn:
        conn.execute("DELETE FROM productos_fabricantes WHERE id=?", (comp_id,))
        conn.commit()


# -------------------------------------------------------------------
# Inventario valorizable y cotizaciones
# -------------------------------------------------------------------
def listar_inventario():
    """Todos los componentes con lo necesario para valorizar el stock: lista de diccionarios."""
    columnas = ("id", "tipo_componente", "categoria", "subcategoria", "item_especifico", "chip_principal", "descripcion",
                "fabricante", "stock", "precio_local", "moneda_local", "precio_exterior", "moneda_exterior")
    with conexion() as conn:
        filas = conn.execute(f"SELECT {', '.join(columnas)} FROM productos_fabricantes "
                             "ORDER BY tipo_componente, categoria, subcategoria, item_especifico, chip_principal, id").fetchall()
    return [dict(zip(columnas, f)) for f in filas]


def listar_cotizaciones():
    """[(moneda, unidades por 1 USD o None si falta, fecha o None)]: USD primero, luego las monedas de la lista
    y las que usan los componentes."""
    with conexion() as conn:
        guardadas = {m.lower(): (por_usd, fecha) for m, por_usd, fecha in conn.execute("SELECT moneda, por_usd, fecha FROM cotizaciones")}
        usadas = [m for (m,) in conn.execute(
            "SELECT moneda_local FROM productos_fabricantes UNION SELECT moneda_exterior FROM productos_fabricantes ORDER BY 1")]
        listadas = [v for (v,) in conn.execute("SELECT valor FROM listas_valores WHERE lista='moneda' ORDER BY orden, id")]
    monedas = [MONEDA_BASE]
    for m in listadas + usadas:
        m = str(m or "").strip()
        if m and m.lower() not in {x.lower() for x in monedas}:
            monedas.append(m)
    return [(m,) + guardadas.get(m.lower(), (None, None)) for m in monedas]


def guardar_cotizacion(moneda, por_usd, fecha=None):
    """Guarda cuántas unidades de `moneda` equivalen a 1 USD (None = borrar la cotización). La fecha por defecto es hoy.
    Lanza ValueError si el valor no es válido."""
    moneda = _validar_nombre(moneda)
    if moneda.upper() == MONEDA_BASE:
        raise ValueError(f"{MONEDA_BASE} es la moneda base: vale siempre 1.")
    if por_usd is not None:
        try:
            por_usd = float(por_usd)
        except (TypeError, ValueError):
            raise ValueError("La cotización debe ser un número.")
        if not math.isfinite(por_usd) or por_usd <= 0:
            raise ValueError("La cotización debe ser un número mayor que cero.")
    fecha = fecha or date.today().isoformat()
    with conexion() as conn:
        conn.execute("""INSERT INTO cotizaciones (moneda, por_usd, fecha) VALUES (?, ?, ?)
                        ON CONFLICT(moneda) DO UPDATE SET por_usd=excluded.por_usd, fecha=excluded.fecha""", (moneda, por_usd, fecha))
        conn.commit()


# -------------------------------------------------------------------
# Archivos adjuntos (solo filas de la base; los archivos físicos son de otro módulo)
# -------------------------------------------------------------------
def listar_archivos(comp_id):
    """Lista de (tipo_archivo, nombre_amigable, ruta_archivo)."""
    with conexion() as conn:
        cursor = conn.execute("SELECT tipo_archivo, nombre_amigable, ruta_archivo FROM archivos_componentes WHERE componente_id=? ORDER BY id", (comp_id,))
        return cursor.fetchall()


def listar_archivos_con_id(comp_id):
    """Lista de (id, tipo_archivo, ruta_archivo), para verificar que existan en disco."""
    with conexion() as conn:
        cursor = conn.execute("SELECT id, tipo_archivo, ruta_archivo FROM archivos_componentes WHERE componente_id = ? ORDER BY id", (comp_id,))
        return cursor.fetchall()


def listar_rutas_archivos():
    """Todas las rutas de archivos adjuntos registradas (de todos los componentes), sin repetir."""
    with conexion() as conn:
        cursor = conn.execute("SELECT DISTINCT ruta_archivo FROM archivos_componentes WHERE ruta_archivo IS NOT NULL AND ruta_archivo <> ''")
        return [fila[0] for fila in cursor.fetchall()]


def listar_todos_los_archivos():
    """Lista de (id, ruta_archivo) de todos los adjuntos (usado por la migración al almacén por hash)."""
    with conexion() as conn:
        cursor = conn.execute("SELECT id, ruta_archivo FROM archivos_componentes ORDER BY id")
        return cursor.fetchall()


def actualizar_rutas_archivos(cambios):
    """Cambia la ruta de varios adjuntos en una sola transacción. `cambios`: lista de (id, ruta_nueva)."""
    with conexion() as conn:
        try:
            conn.executemany("UPDATE archivos_componentes SET ruta_archivo = ? WHERE id = ?",
                             [(ruta, i) for i, ruta in cambios])
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def eliminar_archivos_por_id(ids):
    """Borra filas de archivos_componentes por su id."""
    with conexion() as conn:
        conn.executemany("DELETE FROM archivos_componentes WHERE id = ?", [(i,) for i in ids])
        conn.commit()


# -------------------------------------------------------------------
# Parámetros eléctricos
# -------------------------------------------------------------------
def listar_parametros(comp_id):
    """Lista de (parametro_clave, parametro_valor)."""
    with conexion() as conn:
        cursor = conn.execute("SELECT parametro_clave, parametro_valor FROM parametros_electricos WHERE componente_id=?", (comp_id,))
        return cursor.fetchall()
