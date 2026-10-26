"""Árbol de la taxonomía con los parámetros propios de cada nodo.

Lo usan la ventana de parámetros del componente (consulta) y la ventana de
administración (edición). No tiene consultas propias: lee de db.py.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

import db
from interfaz.widgets import aplicar_franjas

NOMBRES_NIVEL = ("Tipo", "Categoría", "Subcategoría", "Ítem")
ROL_RUTA = Qt.ItemDataRole.UserRole          # camino del nodo (tupla de nombres)
ROL_TIPO = Qt.ItemDataRole.UserRole + 1      # 'nodo' o 'param'
ROL_NOMBRE = Qt.ItemDataRole.UserRole + 2    # nombre del parámetro (solo en 'param')


class ArbolParametros(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["Clasificación  /  📏 Parámetros propios", "Propios"])
        self.setColumnWidth(0, 430)
        aplicar_franjas(self)
        self.refrescar()

    def refrescar(self, abrir=None):
        """Reconstruye el árbol conservando los nodos abiertos.

        `abrir`: camino que se despliega y se deja seleccionado (si no existe, el nodo más
        profundo que sí exista de ese camino).
        """
        abiertos = set(self._rutas_abiertas())
        abrir = tuple(abrir) if abrir else ()
        abiertos |= {abrir[:k] for k in range(1, len(abrir) + 1)}
        self.clear()

        propios = {}
        for ruta, parametro in db.listar_plantillas():
            propios.setdefault(ruta, []).append(parametro)

        rutas = set()
        for fila in db.listar_catalogo():
            camino = tuple(x for x in fila if x)
            rutas |= {camino[:k] for k in range(1, len(camino) + 1)}
        for camino in propios:
            rutas |= {camino[:k] for k in range(1, len(camino) + 1)}

        nodos = {}
        # ordenar por camino deja cada padre antes que sus hijos
        for ruta in sorted(rutas, key=lambda r: tuple(x.lower() for x in r)):
            padre = nodos.get(ruta[:-1]) or self.invisibleRootItem()
            cantidad = len(propios.get(ruta, []))
            nodo = QTreeWidgetItem(padre, [ruta[-1], str(cantidad) if cantidad else ""])
            nodo.setData(0, ROL_RUTA, ruta)
            nodo.setData(0, ROL_TIPO, "nodo")
            nodo.setToolTip(0, f"{NOMBRES_NIVEL[len(ruta) - 1]}: {' › '.join(ruta)}")
            nodos[ruta] = nodo
            for parametro in propios.get(ruta, []):
                hoja = QTreeWidgetItem(nodo, ["📏 " + parametro, ""])
                hoja.setData(0, ROL_RUTA, ruta)
                hoja.setData(0, ROL_TIPO, "param")
                hoja.setData(0, ROL_NOMBRE, parametro)

        for ruta, nodo in nodos.items():
            nodo.setExpanded(ruta in abiertos)
        for k in range(len(abrir), 0, -1):
            if abrir[:k] in nodos:
                self.setCurrentItem(nodos[abrir[:k]])
                break

    def _rutas_abiertas(self):
        pila = [self.topLevelItem(i) for i in range(self.topLevelItemCount())]
        while pila:
            nodo = pila.pop()
            if nodo.data(0, ROL_TIPO) == "nodo" and nodo.isExpanded():
                yield nodo.data(0, ROL_RUTA)
            pila.extend(nodo.child(i) for i in range(nodo.childCount()))

    def nodo_actual(self):
        """Camino del nodo elegido (si hay un parámetro elegido, el de su nodo), o None."""
        item = self.currentItem()
        return tuple(item.data(0, ROL_RUTA)) if item else None

    def parametro_actual(self):
        """(camino, nombre) si lo elegido es un parámetro; si no, None."""
        item = self.currentItem()
        if item and item.data(0, ROL_TIPO) == "param":
            return tuple(item.data(0, ROL_RUTA)), item.data(0, ROL_NOMBRE)
        return None
