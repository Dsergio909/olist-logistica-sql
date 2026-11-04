"""Lo que está en el repo es lo que sale del código.

1. Los CSV de salidas/ son idénticos a los que produce el SQL hoy.
2. Cada cifra de r_hallazgos aparece tal cual en los dos README.
"""
from __future__ import annotations

import re

import correr_sql
import pytest

from conftest import RAIZ


def test_salidas_al_dia(con, tmp_path):
    tablas = correr_sql.guardar(con, tmp_path)
    for tabla in tablas:
        nuevo = (tmp_path / f"{tabla}.csv").read_text(encoding="utf-8")
        guardado = (RAIZ / "salidas" / f"{tabla}.csv").read_text(encoding="utf-8")
        assert nuevo == guardado, f"salidas/{tabla}.csv está desactualizado: corre scripts/correr_sql.py"
    sobrantes = {p.stem for p in (RAIZ / "salidas").glob("r_*.csv")} - set(tablas)
    assert not sobrantes, f"Hay CSV viejos en salidas/: {sobrantes}"


def formato(valor: float, decimales: int, idioma: str) -> str:
    texto = f"{valor:,.{decimales}f}"          # 99,441 · 6.8
    if idioma == "es":                         # 99.441 · 6,8
        texto = texto.replace(",", "_").replace(".", ",").replace("_", ".")
    return texto


def aparece(numero: str, texto: str) -> bool:
    """El número aparece entero: '8,0' no cuenta si solo está dentro de '48,0'."""
    return re.search(rf"(?<![\d.,]){re.escape(numero)}(?![\d]|[.,]\d)", texto) is not None


@pytest.mark.parametrize("archivo,idioma", [("README.md", "es"), ("README.en.md", "en")])
def test_readme_cita_las_cifras_de_los_datos(hallazgos, archivo, idioma):
    texto = (RAIZ / archivo).read_text(encoding="utf-8")
    faltan = [f"{clave} = {formato(v, d, idioma)}" for clave, (v, d) in hallazgos.items()
              if not aparece(formato(v, d, idioma), texto)]
    assert not faltan, f"{archivo} no cita estas cifras de r_hallazgos: {faltan}"


SECCION = {"es": ("# Olist", "## Cómo explicarlo"), "en": ("# Olist", "## How to explain")}
# Números de la sección que no son resultados: el umbral de la prueba z.
NO_SON_RESULTADOS = {"1,96", "1.96"}


@pytest.mark.parametrize("archivo,idioma", [("README.md", "es"), ("README.en.md", "en")])
def test_cada_cifra_de_los_hallazgos_sale_de_los_datos(hallazgos, archivo, idioma):
    texto = (RAIZ / archivo).read_text(encoding="utf-8")
    inicio, fin = SECCION[idioma]
    seccion = texto[texto.index(inicio):texto.index(fin)]
    sep_dec = "," if idioma == "es" else "."
    sep_mil = "." if idioma == "es" else ","
    patron = rf"(?<![\d.,])\d{{1,3}}(?:\{sep_mil}\d{{3}})+(?![\d])|(?<![\d.,])\d+\{sep_dec}\d+(?![\d])"
    validos = {formato(v, d, idioma) for v, d in hallazgos.values()} | NO_SON_RESULTADOS
    sueltos = sorted(set(re.findall(patron, seccion)) - validos)
    assert not sueltos, f"{archivo}: estas cifras no salen de r_hallazgos: {sueltos}"


def test_formato():
    assert formato(99441, 0, "es") == "99.441"
    assert formato(6.8, 1, "es") == "6,8"
    assert formato(99441, 0, "en") == "99,441"
