"""Migra los documentos existentes al almacén por hash SHA-256 (etapa 7).

Uso (desde la carpeta de la aplicación):

    python migrar_a_hash.py                    # SOLO INFORMA qué haría; no cambia nada
    python migrar_a_hash.py --aplicar          # migra (antes hace una copia de la base de datos)
    python migrar_a_hash.py --aplicar --archivar-originales
                                               # además mueve los archivos viejos a adjuntos/originales_migrados

Qué hace, para cada documento registrado en la base de datos:
  1. Localiza el archivo (ruta absoluta antigua o ruta relativa a `adjuntos`).
  2. Lo copia al almacén con el nombre de su huella SHA-256. Si otro documento tiene
     exactamente el mismo contenido, comparten un único archivo.
  3. Cambia la ruta guardada en la base de datos por la ruta relativa del almacén.

Garantías:
  * Por defecto no modifica nada (modo informe).
  * Con --aplicar, primero copia la base de datos a un archivo .bak con fecha y hora.
  * Los archivos originales NO se borran. Con --archivar-originales se mueven (no se
    eliminan) a una carpeta aparte, y solo si ya están a salvo en el almacén.
  * Los documentos que no se encuentran en el disco quedan como estaban y se listan.
  * Se puede ejecutar varias veces: lo ya migrado se reconoce y no se repite.
"""
import argparse
import os
import shutil
import sqlite3
import sys
import time

import almacenamiento
import config
import db


def _respaldar_base():
    base = f"{config.DB_PATH}.bak_{time.strftime('%Y%m%d_%H%M%S')}"
    destino, n = base, 1
    while os.path.exists(destino):          # nunca pisar una copia anterior
        n += 1
        destino = f"{base}_{n}"
    origen = sqlite3.connect(config.DB_PATH)
    try:
        copia = sqlite3.connect(destino)
        try:
            origen.backup(copia)
        finally:
            copia.close()
    finally:
        origen.close()
    return destino


def migrar(aplicar=False, archivar_originales=False, salida=print):
    """Devuelve un dict con el resumen. Con aplicar=False no escribe nada (ni en disco ni en la base)."""
    filas = db.listar_todos_los_archivos()
    resumen = dict(filas=len(filas), ya_migrados=0, migrados=0, faltantes=[], errores=[],
                   documentos_unicos=0, bytes_originales=0, bytes_almacen=0, respaldo=None)
    cambios = []                      # (id, ruta_nueva)
    originales = {}                   # ruta absoluta vieja -> ruta relativa nueva
    vistos = {}                       # huella -> tamaño

    pendientes = [1 for _, r in filas if r and not almacenamiento.esta_en_almacen(r) and os.path.isfile(almacenamiento.resolver(r))]
    if aplicar and pendientes:                       # solo si hay algo que cambiar
        resumen["respaldo"] = _respaldar_base()
        salida(f"Copia de seguridad de la base: {resumen['respaldo']}")

    for fila_id, ruta in filas:
        absoluta = almacenamiento.resolver(ruta)
        if not ruta or not os.path.isfile(absoluta):
            resumen["faltantes"].append((fila_id, ruta))
            continue
        tam = os.path.getsize(absoluta)
        try:
            if almacenamiento.esta_en_almacen(absoluta):
                resumen["ya_migrados"] += 1
                huella = os.path.splitext(os.path.basename(absoluta))[0]
                nueva = ruta
            elif aplicar:
                nueva, huella = almacenamiento.incorporar(absoluta)
                originales[absoluta] = nueva
            else:
                huella = almacenamiento.calcular_hash(absoluta)
                nueva = None
        except Exception as e:                         # un archivo ilegible no detiene al resto
            resumen["errores"].append((fila_id, ruta, str(e)))
            continue
        if not almacenamiento.esta_en_almacen(absoluta):
            resumen["migrados"] += 1
            resumen["bytes_originales"] += tam
        if huella not in vistos:
            vistos[huella] = tam
            resumen["bytes_almacen"] += tam
        if nueva is not None and nueva != ruta:
            cambios.append((fila_id, nueva))

    resumen["documentos_unicos"] = len(vistos)

    if aplicar and cambios:
        db.actualizar_rutas_archivos(cambios)

    resumen["sin_archivar"] = []
    if aplicar and archivar_originales and not resumen["errores"]:
        base_adj = os.path.normcase(os.path.abspath(almacenamiento.ATTACHMENTS_DIR))
        carpeta = os.path.join(almacenamiento.ATTACHMENTS_DIR, "originales_migrados")
        for vieja, nueva in originales.items():
            if not (almacenamiento.existe(nueva) and os.path.isfile(vieja)):
                continue
            # Solo se archivan los originales que están dentro de la carpeta `adjuntos` de esta
            # aplicación. Los que están en otro lugar (p. ej. una instalación anterior) no se tocan.
            if not os.path.normcase(os.path.abspath(vieja)).startswith(base_adj + os.sep):
                resumen["sin_archivar"].append(vieja)
                continue
            destino = os.path.join(carpeta, os.path.relpath(vieja, almacenamiento.ATTACHMENTS_DIR))
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            if os.path.exists(destino):
                base, ext = os.path.splitext(destino)
                destino = f"{base}.{int(time.time())}{ext}"
            shutil.move(vieja, destino)
    return resumen


def _mb(n):
    return f"{n / (1024 * 1024):.2f} MB"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Migra los documentos al almacén por hash SHA-256.")
    ap.add_argument("--aplicar", action="store_true", help="realiza los cambios (sin esta opción solo informa)")
    ap.add_argument("--archivar-originales", action="store_true",
                    help="mueve los archivos viejos a adjuntos/originales_migrados (requiere --aplicar)")
    args = ap.parse_args(argv)
    if args.archivar_originales and not args.aplicar:
        ap.error("--archivar-originales requiere --aplicar")

    config.asegurar_directorios()
    db.inicializar_base_de_datos()
    print("MODO:", "APLICAR CAMBIOS" if args.aplicar else "INFORME (no se modifica nada)")
    r = migrar(aplicar=args.aplicar, archivar_originales=args.archivar_originales)

    print(f"\nRegistros de archivos en la base : {r['filas']}")
    print(f"Ya estaban en el almacén         : {r['ya_migrados']}")
    print(f"{'Migrados' if args.aplicar else 'Por migrar'}                         : {r['migrados']}")
    print(f"Documentos distintos (por hash)  : {r['documentos_unicos']}")
    print(f"Espacio de los originales        : {_mb(r['bytes_originales'])}")
    print(f"Espacio en el almacén            : {_mb(r['bytes_almacen'])}")
    if r["faltantes"]:
        print(f"\nNo se encontró el archivo de {len(r['faltantes'])} registro(s) (quedan sin cambios):")
        for fila_id, ruta in r["faltantes"]:
            print(f"   id {fila_id}: {ruta}")
    if r["errores"]:
        print(f"\nERRORES en {len(r['errores'])} registro(s):")
        for fila_id, ruta, msg in r["errores"]:
            print(f"   id {fila_id}: {ruta} -> {msg}")
    if r.get("sin_archivar"):
        print(f"\n{len(r['sin_archivar'])} original(es) están fuera de la carpeta 'adjuntos' de esta aplicación y NO se movieron:")
        for ruta in r["sin_archivar"]:
            print(f"   {ruta}")
    if not args.aplicar:
        print("\nPara migrar de verdad: python migrar_a_hash.py --aplicar")
    return 1 if r["errores"] else 0


if __name__ == "__main__":
    sys.exit(main())
