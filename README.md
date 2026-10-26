# Inventario de componentes electrónicos
### Edición PySide6 + pypdfium2

Aplicación de escritorio, portátil y sin servidor, para llevar el inventario de componentes electrónicos de un
taller, un laboratorio o un aficionado: qué hay, dónde está, cuánto vale, con qué documentación y cómo se etiqueta.

> Existe una edición equivalente con **PyQt5 + PyMuPDF**: [inventario-componentes-pyqt5](https://github.com/MAXIM-TOJA/inventario-componentes-pyqt5).

**Contenido:** [Motivación](#motivación) · [Funcionalidades](#funcionalidades) · [Alcance](#alcance) ·
[Portabilidad](#portabilidad) · [Estructura](#estructura-del-código-y-por-qué) · [Instalación](#instalación-y-arranque) ·
[Ejecutable](#ejecutable-para-windows) · [Licencia](#licencia)

---

## Motivación
Un inventario de electrónica tiene un problema particular: cada componente viene con **documentación pesada y
repetida** (datasheets, tutoriales, esquemas, fotos) y con **muchos datos variables** (un capacitor y un
microcontrolador no se describen igual). Las planillas de cálculo no resuelven bien ninguna de las dos cosas. La
aplicación nació para resolverlas con tres ideas:

1. **Clasificar en cuatro niveles** (Tipo › Categoría › Subcategoría › Ítem) con un catálogo editable. Cada nodo
   del catálogo define qué parámetros técnicos corresponden (por ejemplo, «Tensión de operación» para
   microcontroladores), y los niveles inferiores **heredan** los de los superiores.
2. **Guardar cada documento una sola vez**, identificado por la huella **SHA-256** de su contenido. Si el mismo
   datasheet se adjunta a diez componentes, o como datasheet y como tutorial, ocupa lugar una vez y no se
   pierde ni se duplica por renombrar archivos.
3. **Que todo viaje junto**: base de datos, documentos y programa en una carpeta, sin instalación, sin servicios
   ni cuenta en línea. Se puede llevar en un pendrive.

## Funcionalidades
**Inventario**
- Alta, edición y baja de componentes: chip principal, fabricante, ubicación física, stock, precios local y
  exterior (con moneda), proveedores, interfaces, pines relevantes, encapsulado, obsolescencia y descripción.
- Búsqueda por nombre, descripción, fabricante o chip, y **filtros en cascada** por Tipo, Categoría, Subcategoría e Ítem.
- **Parámetros eléctricos y técnicos** por componente, con plantillas heredadas desde el catálogo.
- Entrada de datos controlada: listas desplegables editables (fabricantes, interfaces, pines, encapsulados,
  monedas, proveedores) y texto en mayúsculas para mantener los datos homogéneos.

**Documentación**
- Cuatro tipos de adjuntos por componente: **imágenes, datasheets, tutoriales y esquemas**, varios de cada tipo.
- **Visor de PDF** integrado, con zoom, páginas, **selección y copia de texto** y **recorte de regiones** como imagen.
  Desde el texto seleccionado se pueden completar campos de la ficha (chip, descripción, ubicación).
- **Editor de imágenes** con recorte y guardado.
- **OCR opcional** (Tesseract): si una página de un datasheet es una imagen escaneada, la selección reconoce el texto.
- Los documentos sin uso se mueven a una papelera interna al arrancar; nunca se borran de forma definitiva solos.

**Valorización y etiquetas**
- **Capital en existencia** en una moneda base, con cotizaciones que carga el usuario, subtotales por clasificación,
  detalle por componente y **exportación a Excel**.
- **Etiquetas en PDF** con código QR, a medida de la hoja (tamaño, separación, cantidad de copias, celda de inicio),
  con guías de corte y previsualización antes de imprimir.

## Alcance
**Lo que la aplicación es:** una herramienta de **un solo usuario, local y sin conexión**, para un inventario de
cientos o pocos miles de componentes, con su documentación a mano.

**Lo que no es (hoy):**
- No es multiusuario ni multiequipo: no hay cuentas, permisos ni sincronización. La base es un archivo SQLite;
  abrirlo desde dos equipos a la vez no está contemplado.
- No lleva **historial de movimientos** de stock (entradas y salidas): el stock es un valor por componente.
- No se conecta a distribuidores (precios o disponibilidad en línea) ni lee códigos de barras.
- No hace copias de seguridad automáticas: la copia es copiar la carpeta de datos (ver más abajo).
- Está pensada y usada en **Windows**. En otros sistemas no se ha probado.
- Sin Tesseract instalado, el OCR no está disponible; todo lo demás funciona igual.

## Portabilidad
- **Una carpeta lo contiene todo.** Al arrancar, la aplicación toma como base su propia carpeta (la del script, o la
  del `.exe` si está empaquetada) y crea junto a ella `Base_Inventario\` (la base SQLite), `adjuntos\` (los
  documentos por huella) y `Etiquetas\` (los PDF generados). No usa el registro de Windows ni rutas fijas.
- **Las rutas guardadas son relativas** a `adjuntos\`, de modo que mover o copiar la carpeta a otro equipo o a un
  pendrive, o cambiarle el nombre, no rompe los vínculos con los documentos.
- **Sin instalación ni servidor:** SQLite viene con Python; no hay motor de base de datos que configurar.
- **Copia de seguridad = copiar la carpeta** (o solo `Base_Inventario\` y `adjuntos\`).
- **OCR portátil:** si junto al programa hay una carpeta `Tesseract-OCR\`, la aplicación la usa; si no, busca
  Tesseract en el sistema. Se puede llevar también en el pendrive.
- **Ejecutable:** con PyInstaller se genera una carpeta que se copia al pendrive y se ejecuta con doble clic, sin
  Python instalado en el equipo de destino.

## Estructura del código y por qué
El programa nació como un único archivo de unas 3000 líneas. Se refactorizó en **capas**, para poder modificarlo
y agregar extensiones sin romper el resto: cada capa solo usa a las que están debajo.

```
interfaz/                ventanas y diálogos (un módulo por ventana)
capital.py               valorización y planilla de Excel (sin interfaz)
pdf_motor.py             lectura de PDF con pypdfium2 (sin interfaz)
almacenamiento.py        documentos por huella SHA-256
ocr.py                   reconocimiento de texto (Tesseract)
utilidades.py            funciones de texto
db.py                    toda la lógica SQLite: el único lugar con SQL
catalogo.py, config.py   datos de referencia y rutas portátiles
app_inventario.py        arranque
migrar_a_hash.py         migración única de adjuntos antiguos al almacén por huella
```
- **Todo el SQL está en `db.py`:** la interfaz nunca consulta la base directamente, así se puede cambiar el
  almacenamiento sin tocar las ventanas.
- **Lo que no necesita pantalla no la usa:** el cálculo del capital y la capa de documentos funcionan sin la
  interfaz, y se pueden probar o reutilizar solos.
- **Extender es agregar un módulo** en `interfaz/` (una ventana nueva) o una función en la capa que corresponda.
- **Por qué PySide6 + pypdfium2:** esta edición reemplaza las bibliotecas con copyleft fuerte (PyQt5 y PyMuPDF) por PySide6 (LGPL) y pypdfium2 (Apache 2.0 / BSD), para tener libertad de elegir la licencia de la aplicación. Toda la lectura de PDF está aislada en `pdf_motor.py`, sin Qt, y se puede probar por separado.

La carpeta `manuales/` incluye el **Manual de usuario**, el **Manual de instalación** y el **Manual técnico** (con
cada módulo, la estructura de la base de datos y el código fuente), en PDF y Word.

## Instalación y arranque
Requisitos: Windows y **Python 3.13**. Desde la carpeta que contiene `app_inventario.py`:

```
python -m pip install -r requirements.txt
python app_inventario.py
```
Bibliotecas: PySide6, pypdfium2, ReportLab, qrcode, Pillow, pytesseract y openpyxl. Opcional: **Tesseract OCR** para leer texto en páginas escaneadas. Si `pip` no se
reconoce, usa siempre `python -m pip`. Un entorno virtual es opcional.

## Ejecutable para Windows
```
python -m PyInstaller --noconfirm --clean --windowed --name Inventario app_inventario.py
```
Se genera `dist\Inventario\`. Para distribuirlo, genéralo en carpeta (no en un solo archivo): la LGPL de Qt exige que el usuario pueda reemplazar sus bibliotecas. Los ejecutables ya compilados están en la sección **Releases** del repositorio.

## Licencia
Distribuida bajo la **GNU GPL v3** (ver [`LICENSE`](LICENSE)). PySide6 es LGPL v3 y pypdfium2 es Apache 2.0 / BSD, de modo que la licencia de la aplicación podría cambiarse. Esto es información general, no asesoramiento legal.
Detalle de las bibliotecas de terceros en [`LICENCIAS_DE_TERCEROS.md`](LICENCIAS_DE_TERCEROS.md).
Copyright (c) 2026 Maxim Toja.
