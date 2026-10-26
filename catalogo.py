"""Datos de referencia iniciales: taxonomía, listas de valores y parámetros por clasificación.

Solo contiene constantes (sin lógica ni dependencias). La taxonomía y las listas
son la SEMILLA de las tablas catalogo_clasificacion, listas_valores y plantillas_parametros: se copian a
la base una sola vez; después se administran desde la aplicación.
"""

# ===================================================================
# CATÁLOGO PREDEFINIDO CON TAXONOMÍA EXPERTA DE SISTEMAS EMBEBIDOS
# ===================================================================
CATALOGO_PREDEFINIDO_4N = {
    "Sistemas Embebidos": {
        "Microcontroladores y Plataformas de Prototipado (MCU Boards)": {
            "Microcontroladores de Propósito General": ["Arduino Uno", "Arduino Nano", "Arduino Mega"],
            "SoCs de Conectividad / IoT": ["ESP32", "ESP8266", "Raspberry Pi Pico"],
        },
        "Computadoras de Placa Única (SBC - Single Board Computers)": {
            "Computadoras de Propósito General": ["Raspberry Pi 4", "Raspberry Pi 5", "Raspberry Pi 3 Model B+"],
            "Módulos y Accesorios SBC": ["Módulos de expansión", "Placas de interfaz para SBC"],
        },
    },
    "Componentes Pasivos": {
        "Resistivos": {
            "Resistencias Fijas": ["Película de Carbón", "Película Metálica", "Alambre Bobinado (Potencia)"],
            "Resistencias Variables": ["Potenciómetros rotativos", "Potenciómetros deslizantes", "Trimmers (Ajuste fino)"],
            "Sensores Resistivos": ["Termistores NTC / PTC", "Fotorresistencias (LDR)", "FSR (Fuerza)"],
        },
        "Capacitivos (Condensadores)": {
            "Cerámicos": ["Cerámicos de disco", "Cerámicos multicapa (MLCC)"],
            "Electrolíticos": ["Electrolíticos de Aluminio", "Condensadores de Tántalo"],
            "Película Plástica": ["Poliéster (MKT)", "Polipropileno (MKP)"],
        },
        "Inductivos y Magnéticos": {
            "Inductores Fijos": ["Bobinas de núcleo de aire", "Inductores apantallados SMD"],
            "Transformadores": ["Transformadores reductores", "Transformadores toroidales"],
        },
    },
    "Componentes Activos": {
        "Semiconductores Discretos": {
            "Diodos": ["Diodos Rectificadores", "Diodos Zener", "Diodos Schottky", "Diodos LED", "Diodos DIAC", "Diodos TVS"],
            "Transistores Bipolares (BJT)": ["NPN de uso general", "PNP de uso general", "Darlington"],
            "Transistores de Efecto de Campo": ["MOSFET Canal N", "MOSFET Canal P", "JFET"],
            "Tiristores": ["SCR", "TRIAC"],
        },
        "Circuitos Integrados (ICs)": {
            "Analógicos / Lineales": ["Amplificadores Operacionales", "Reguladores de Tensión Lineales", "Comparadores"],
            "Digitales": ["Lógica Estándar", "Microcontroladores", "Memorias RAM/ROM"],
            "Mixtos y de Potencia": ["Conversores A/D y D/A", "Drivers para Motores", "Gestión de Energía"],
        },
    },
    "Electromecánicos y Conexión": {
        "Dispositivos de Conmutación y Protección": {
            "Interruptores y Pulsadores": ["Pulsadores táctiles", "Interruptores deslizantes/palanca"],
            "Relés": ["Relés electromecánicos", "Relés de estado sólido (SSR)"],
            "Protecciones": ["Fusibles de vidrio/cerámica", "Termistores PTC de protección"],
        },
        "Conectores y Bornes": {
            "Bornes y Pines": ["Headers de pines macho/hembra", "Borneras de tornillo"],
            "Conectores de Interfaz": ["Conectores USB", "Conectores Jack DC", "Conectores RJ45"],
        },
    },
    "Optoelectrónica y Sensores": {
        "Displays y Visualización": {
            "Displays Numéricos": ["Displays de 7 segmentos", "Matrices LED"],
            "Pantallas": ["Pantallas LCD I2C", "Pantallas OLED gráficas"],
        },
        "Sensores no resistivos": {
            "Magnéticos y Posición": ["Sensores de efecto Hall", "Encoders rotativos"],
            "Físicos y Entorno": ["Micrófonos", "Sensores ultrasónicos", "IMUs", "Sensores ToF"],
        },
    },
}
# TAXONOMIA_GENERAL_INVENTARIO

# ===================================================================
# LISTAS DE VALORES (semilla inicial). Al crear la base se copian a la tabla
# listas_valores; desde ahí se administran desde la aplicación.
# ===================================================================
LISTAS_PREDEFINIDAS = {
    "fabricante": [
        "N/A", "Samsung Electronics", "Intel Corporation", "Texas Instruments (TI)", "STMicroelectronics",
        "Infineon Technologies", "NXP Semiconductors", "Analog Devices (ADI)", "Microchip Technology",
        "ON Semiconductor (onsemi)", "Renesas Electronics", "Broadcom", "Qualcomm", "MediaTek",
        "TSMC", "GlobalFoundries", "NVIDIA", "AMD", "Raspberry Pi Foundation", "Arduino", "Espressif Systems",
    ],
    "interfaz": [
        "N/A", "I2C", "SPI", "UART / USART", "USB", "Ethernet (RJ45)", "CAN Bus", "1-Wire",
        "RS-232", "RS-485", "Wi-Fi", "Bluetooth / BLE", "Zigbee", "LoRa", "PCIe", "HDMI", "MIPI DSI/CSI",
    ],
    "pines": [
        "N/A", "VCC", "VDD", "+5V", "+3.3V", "GND", "VSS", "VEE", "VREF",
        "SDA", "SCL", "MOSI", "MISO", "SCLK / SCK", "CS / SS", "TX", "RX", "CANH", "CANL",
        "D+ (DP)", "D- (DM)", "EN / CE", "RST / RESET", "INT / IRQ", "CLK / OSC", "MODE / AD0",
        "AIN / VIN", "AOUT / VOUT", "PWM", "GPIO", "Colector (C)", "Emisor (E)", "Base (B)",
        "Drenador (D)", "Surtidor (S)", "Puerta / Compuerta (G)", "Ánodo (A)", "Cátodo (K)", "IN", "OUT",
    ],
    "encapsulado": [
        "N/A", "DIP-8", "DIP-14", "DIP-16", "DIP-18", "DIP-20", "DIP-24", "DIP-28", "DIP-40",
        "SIP-3", "SIP-5", "SIP-7", "SIP-9", "TO-92", "TO-126", "TO-220", "TO-247",
        "SOIC-8", "SOIC-14", "SOIC-16", "SOIC-20", "SOIC-24", "SOT-23", "SOT-89", "SOT-223",
        "SSOP-16", "SSOP-20", "TSSOP-8", "TSSOP-16", "TSSOP-20", "TQFP-32", "TQFP-44",
        "TQFP-64", "LQFP-100", "QFN-16", "QFN-24", "QFN-32", "QFN-48", "BGA-144", "BGA-256",
        "BGA-400", "AXIAL-0.3", "AXIAL-0.4", "AXIAL-0.6", "RADIAL-2.5", "RADIAL-5.0",
        "RADIAL-7.5", "SMD-0402", "SMD-0603", "SMD-0805", "SMD-1206", "SMD-1210", "LED-3mm", "LED-5mm", "PLCC-2",
    ],
    "moneda": ["USD", "UYU", "BRL", "ARS"],
    "proveedor_local": ["N/A"],
    "proveedor_exterior": ["N/A"],
}

# ===================================================================
# PARÁMETROS POR CLASIFICACIÓN (semilla inicial de la tabla plantillas_parametros)
#
# Cada clave es un camino de la taxonomía: (Tipo,), (Tipo, Categoría), (Tipo, Categoría, Subcategoría)
# o hasta el Ítem. Un componente HEREDA los parámetros de todos los niveles por los que pasa su
# clasificación y suma los de su propio nivel: lo común se define arriba, lo particular abajo.
# ===================================================================
_EMB = "Sistemas Embebidos"
_MCU = (_EMB, "Microcontroladores y Plataformas de Prototipado (MCU Boards)")
_SBC = (_EMB, "Computadoras de Placa Única (SBC - Single Board Computers)")
_PAS = "Componentes Pasivos"
_RES = (_PAS, "Resistivos")
_CAP = (_PAS, "Capacitivos (Condensadores)")
_IND = (_PAS, "Inductivos y Magnéticos")
_ACT = "Componentes Activos"
_DIS = (_ACT, "Semiconductores Discretos")
_CIS = (_ACT, "Circuitos Integrados (ICs)")
_ELM = "Electromecánicos y Conexión"
_CON = (_ELM, "Dispositivos de Conmutación y Protección")
_CNX = (_ELM, "Conectores y Bornes")
_OPT = "Optoelectrónica y Sensores"
_DSP = (_OPT, "Displays y Visualización")
_SEN = (_OPT, "Sensores no resistivos")

PARAMETROS_PREDEFINIDOS = {
    # --- Sistemas Embebidos ---
    (_EMB,): ["Tensión de Operación (V)", "Corriente de Consumo (mA)", "Temperatura de Operación (°C)"],
    _MCU: ["Microcontrolador / SoC", "Frecuencia de Reloj (MHz)", "Memoria Flash", "Memoria RAM",
           "Tensión Lógica de E/S (V)", "Corriente por GPIO (mA)", "Cantidad de Pines GPIO", "Interfaces de Comunicación"],
    _MCU + ("Microcontroladores de Propósito General",): ["Entradas Analógicas (ADC)", "Salidas PWM", "Conector de Programación / USB"],
    _MCU + ("SoCs de Conectividad / IoT",): ["Conectividad Inalámbrica (Wi-Fi/BLE)", "Entradas Analógicas (ADC)", "Salidas PWM", "Consumo en Reposo (µA)"],
    _SBC: ["Procesador (CPU)", "Frecuencia de CPU (GHz)", "Memoria RAM (GB)", "Almacenamiento (SD/eMMC)",
           "Alimentación de Entrada (V/A)", "Tensión de GPIO (V)", "Interfaces de Red (Wi-Fi/Ethernet)", "Puertos USB / Video"],
    _SBC + ("Computadoras de Propósito General",): ["Sistema Operativo Soportado", "Consumo Máximo (W)"],
    _SBC + ("Módulos y Accesorios SBC",): ["Compatibilidad (Modelos de SBC)", "Interfaz de Conexión (GPIO/CSI/DSI/USB)"],

    # --- Componentes Pasivos ---
    (_PAS,): ["Tolerancia (%)", "Temperatura de Operación (°C)"],
    _RES: ["Valor Nominal (Ω)", "Potencia Nominal (W)"],
    _RES + ("Resistencias Fijas",): ["Tecnología / Material", "Coeficiente de Temperatura (ppm/°C)", "Tensión Máxima de Trabajo (V)"],
    _RES + ("Resistencias Variables",): ["Curva (Lineal/Logarítmica)", "Cantidad de Vueltas", "Tipo de Eje / Montaje"],
    _RES + ("Sensores Resistivos",): ["Rango de Medición", "Valor Beta / Sensibilidad", "Tiempo de Respuesta"],
    _CAP: ["Capacitancia (F/µF/nF/pF)", "Tensión Máxima Vdc (V)"],
    _CAP + ("Cerámicos",): ["Dieléctrico (C0G/X7R/Y5V)", "Tamaño / Paso"],
    _CAP + ("Electrolíticos",): ["ESR (Ω)", "Corriente de Ripple (mA)", "Vida Útil (horas)", "Polaridad"],
    _CAP + ("Película Plástica",): ["Dieléctrico (MKT/MKP)", "Tensión AC Máxima (V)", "Paso (mm)"],
    _IND + ("Inductores Fijos",): ["Inductancia (H/mH/µH)", "Corriente de Saturación Isat (A)", "Corriente Nominal (A)",
                                  "Resistencia DCR (Ω)", "Frecuencia de Resonancia (MHz)"],
    _IND + ("Transformadores",): ["Tensión Primaria (V)", "Tensión Secundaria (V)", "Potencia (VA)", "Relación de Transformación", "Frecuencia (Hz)"],

    # --- Componentes Activos ---
    (_ACT,): ["Temperatura de Operación (°C)"],
    _DIS: ["Potencia Máxima Pd (W)"],
    _DIS + ("Diodos",): ["Corriente Directa If (A)", "Tensión Inversa Vrrm (V)", "Caída Directa Vf (V)", "Tensión Zener Vz (V)",
                         "Tiempo de Recuperación trr (ns)", "Color / Longitud de Onda (LED)"],
    _DIS + ("Transistores Bipolares (BJT)",): ["Tensión Vceo (V)", "Corriente de Colector Ic (A)", "Ganancia hFE (β)",
                                              "Frecuencia de Transición ft (MHz)", "Polaridad (NPN/PNP)"],
    _DIS + ("Transistores de Efecto de Campo",): ["Tensión Vds (V)", "Corriente de Drenador Id (A)", "Resistencia Rds(on) (Ω)",
                                                 "Tensión Umbral Vgs(th) (V)", "Capacitancia de Entrada Ciss (pF)", "Canal (N/P)"],
    _DIS + ("Tiristores",): ["Tensión de Bloqueo Vdrm (V)", "Corriente Nominal It (A)", "Corriente de Disparo Igt (mA)", "Corriente de Mantenimiento Ih (mA)"],
    _CIS: ["Tensión de Alimentación Vcc (V)", "Corriente de Reposo Icc (mA)"],
    _CIS + ("Analógicos / Lineales",): ["Ancho de Banda (MHz)", "Slew Rate (V/µs)", "Número de Canales", "Tensión de Salida (V)", "Corriente de Salida Máxima (mA)"],
    _CIS + ("Digitales",): ["Familia Lógica (TTL/CMOS)", "Frecuencia Máxima (MHz)", "Retardo de Propagación (ns)", "Capacidad de Memoria"],
    _CIS + ("Mixtos y de Potencia",): ["Resolución (bits)", "Tasa de Muestreo (SPS)", "Corriente de Salida Máxima (A)",
                                      "Frecuencia de Conmutación (kHz)", "Eficiencia (%)"],

    # --- Electromecánicos y Conexión ---
    (_ELM,): ["Temperatura de Operación (°C)", "Vida Útil Estimada (Ciclos)"],
    _CON: ["Tensión Máxima (VAC/VDC)", "Corriente Máxima (A)"],
    _CON + ("Interruptores y Pulsadores",): ["Configuración de Contactos (SPST/SPDT)", "Tipo de Accionamiento", "Resistencia de Contacto (mΩ)"],
    _CON + ("Relés",): ["Tensión de Bobina Vcoil (V)", "Resistencia de Bobina (Ω)", "Tipo de Contacto (SPDT/DPDT)",
                        "Tensión de Control (Entrada VDC)", "Tipo de Conmutación (Zero-Cross/Random)"],
    _CON + ("Protecciones",): ["Capacidad de Ruptura (A)", "Tiempo de Respuesta (Lento/Rápido)"],
    _CNX: ["Cantidad de Pines / Vías", "Paso (mm)", "Corriente por Contacto (A)", "Tensión Nominal (V)"],
    _CNX + ("Bornes y Pines",): ["Género (Macho/Hembra)", "Tipo de Montaje (THT/SMD)"],
    _CNX + ("Conectores de Interfaz",): ["Tipo de Conector (USB-A/B/C, Jack, RJ45)", "Tipo de Montaje (THT/SMD)", "Diámetro / Polaridad (Jack DC)"],

    # --- Optoelectrónica y Sensores ---
    (_OPT,): ["Tensión de Alimentación Vcc (V)", "Temperatura de Operación (°C)"],
    _DSP: ["Consumo de Corriente (mA)"],
    _DSP + ("Displays Numéricos",): ["Cantidad de Dígitos", "Tipo (Ánodo/Cátodo Común)", "Color", "Tamaño del Dígito (mm)"],
    _DSP + ("Pantallas",): ["Tamaño (pulgadas)", "Resolución (px)", "Controlador (SSD1306/HD44780)", "Interfaz (I2C/SPI/Paralelo)", "Color / Retroiluminación"],
    _SEN: ["Interfaz (I2C/SPI/Analógica)", "Rango de Medición", "Resolución / Precisión", "Consumo de Corriente (mA)"],
    _SEN + ("Magnéticos y Posición",): ["Tipo de Salida (Digital/Analógica)", "Pulsos por Vuelta (Encoders)", "Sensibilidad (mV/mT)"],
    _SEN + ("Físicos y Entorno",): ["Magnitud Medida", "Tiempo de Respuesta", "Frecuencia de Muestreo (Hz)"],
}
