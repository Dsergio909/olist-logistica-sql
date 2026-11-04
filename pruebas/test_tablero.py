"""El tablero de Power BI (PBIP) está completo y coincide con su generador."""
from __future__ import annotations

import json
import re

import generar_pbip as g
import pytest

from conftest import RAIZ

PBI = RAIZ / "powerbi"
VISUALES = sorted((PBI / "OlistLogistica.Report" / "definition" / "pages").rglob("visual.json"))


def campos(nodo):
    """Recorre un JSON y devuelve cada Column y Measure que use un gráfico."""
    if isinstance(nodo, dict):
        for tipo in ("Column", "Measure"):
            if tipo in nodo and "Property" in nodo[tipo]:
                ref = nodo[tipo]["Expression"].get("SourceRef", {})
                if "Entity" in ref:
                    yield tipo, ref["Entity"], nodo[tipo]["Property"]
        for v in nodo.values():
            yield from campos(v)
    elif isinstance(nodo, list):
        for v in nodo:
            yield from campos(v)


def test_hay_4_paginas_y_todos_los_json_se_leen():
    paginas = json.loads((PBI / "OlistLogistica.Report/definition/pages/pages.json").read_text(encoding="utf-8"))
    assert paginas["pageOrder"] == ["logistica", "vendedores", "clientes", "resenas"]
    assert len(VISUALES) >= 30
    for ruta in PBI.rglob("*.json"):
        json.loads(ruta.read_text(encoding="utf-8"))


def test_cada_grafico_usa_campos_que_existen():
    medidas = {nombre for _, nombre, *_ in g.MEDIDAS}
    columnas = {(t, c) for t, cols in g.COLUMNAS.items() for c, *_ in cols}
    faltan = []
    for ruta in VISUALES:
        for tipo, tabla, prop in campos(json.loads(ruta.read_text(encoding="utf-8"))):
            if tipo == "Measure" and prop not in medidas:
                faltan.append(f"{ruta.parent.name}: medida {prop}")
            if tipo == "Column" and (tabla, prop) not in columnas:
                faltan.append(f"{ruta.parent.name}: columna {tabla}[{prop}]")
    assert not faltan, faltan


def test_las_medidas_dax_citan_columnas_y_medidas_que_existen():
    medidas = {nombre for _, nombre, *_ in g.MEDIDAS}
    columnas = {(t, c) for t, cols in g.COLUMNAS.items() for c, *_ in cols}
    for _, nombre, formula, *_ in g.MEDIDAS:
        for tabla, col in re.findall(r"(\w+)\[(\w+)\]", formula):
            assert (tabla, col) in columnas, f"{nombre}: {tabla}[{col}] no existe"
        for ref in re.findall(r"(?<![\w\]])\[([^\]]+)\]", formula):
            assert ref in medidas, f"{nombre}: la medida [{ref}] no existe"


def test_modelo_y_medidas_md_al_dia():
    tmdl = (PBI / "OlistLogistica.SemanticModel/definition/tables/Medidas.tmdl").read_text(encoding="utf-8")
    md = (RAIZ / "dax" / "medidas.md").read_text(encoding="utf-8")
    for _, nombre, formula, *_ in g.MEDIDAS:
        assert f"### {nombre}" in md, f"dax/medidas.md no tiene {nombre}: corre powerbi/generar_pbip.py"
        assert formula in md
        assert g.nombre_tmdl(nombre) in tmdl, f"Medidas.tmdl no tiene {nombre}: corre powerbi/generar_pbip.py"


# Las otras tablas toman sus columnas tal cual del origen (Parquet, CSV o #table).
@pytest.mark.parametrize("tabla", ["Pedidos", "PedidoVendedor", "Vendedores"])
def test_power_query_devuelve_las_columnas_del_modelo(tabla):
    """Las columnas del final de cada consulta M son las del modelo (si no, Power BI falla al actualizar)."""
    seleccion = re.search(r"Final = Table\.SelectColumns\(\w+, \{(.*?)\}\)", g.M[tabla], re.S).group(1)
    en_m = re.findall(r'"(\w+)"', seleccion)
    assert en_m == [c for c, *_ in g.COLUMNAS[tabla]]


def test_pbix_pesa_menos_de_50_mb():
    pbix = PBI / "OlistLogistica.pbix"
    assert pbix.exists()
    assert pbix.stat().st_size < 50 * 1024 * 1024


def test_un_solo_color_de_acento():
    """Diseño sobrio: un acento (verde), grises y rojo solo para "tarde"."""
    colores = set()
    for ruta in VISUALES:
        colores |= set(re.findall(r"#[0-9A-Fa-f]{6}", ruta.read_text(encoding="utf-8")))
    permitidos = {g.ACENTO, g.GRIS, g.TEXTO, g.TEXTO_SUAVE, g.ROJO, "#c9d1d9", "#d0d7de", "#f6f8fa", "#FFFFFF"}
    assert colores <= permitidos, colores - permitidos
