"""Funciones de texto sin dependencias de la interfaz."""
import re


def limpiar_prefijo(texto):
    if not texto:
        return ""
    texto_limpio = re.sub(r'^\d+[\s\.\-_]*', '', str(texto)).strip()
    return texto_limpio if texto_limpio else str(texto).strip()


def sin_comodin(valor, *comodines):
    """Devuelve None si el valor está vacío o es un texto comodín ("-- Todos --"); si no, el valor."""
    if not valor or valor in comodines:
        return None
    return valor
