"""Compara las cifras del PDF del tablero (Power BI) con los resultados del SQL.

Uso:
    pip install -r requirements-comprobar.txt   (trae pypdfium2)
    python scripts/comparar_tablero.py

Power BI calcula con Power Query y DAX; el SQL, con DuckDB. Son dos caminos
distintos sobre los mismos datos, así que las cifras tienen que ser iguales.
Lee el texto de tablero.pdf y busca en cada página las cifras que salen de
salidas/. Termina con error si falta alguna.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pypdfium2 as pdfium

RAIZ = Path(__file__).resolve().parent.parent


def leer(nombre: str) -> list[dict]:
    with (RAIZ / "salidas" / f"{nombre}.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def es(valor: float, decimales: int, pct: bool = False) -> str:
    texto = f"{valor:,.{decimales}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return texto + ("%" if pct else "")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    h = {r["clave"]: float(r["valor"]) for r in leer("r_hallazgos")}
    estados = leer("r_entrega_por_estado")
    despacho = {r["despacho"]: r for r in leer("r_despacho")}
    rfm = {r["segmento"]: r for r in leer("r_rfm_segmentos")}
    flete = leer("r_flete_por_rango_precio")
    nota_dia = leer("r_nota_por_dia_retraso")

    esperado = {
        1: {"Pedidos entregados": es(h["pedidos_entregados"], 0), "% tarde": es(h["pct_tarde"], 1, True),
            "Días de entrega": es(h["dias_entrega_prom"], 1), "Días prometidos": es(h["dias_prometidos_prom"], 1),
            "Días transportadora (tarde)": es(h["dias_transportadora_tarde"], 1),
            "Días transportadora (a tiempo)": es(h["dias_transportadora_a_tiempo"], 1)},
        2: {"% de los retrasos con despacho a tiempo": es(h["pct_retrasos_vendedor_a_tiempo"], 1, True)},
        3: {"% que vuelve a comprar": es(h["pct_clientes_recompran"], 1, True),
            "Flete % del precio": es(h["flete_pct_total"], 1, True),
            "Recompra, primera a tiempo": es(h["recompra_primera_a_tiempo"], 2, True),
            "Recompra, primera tarde": es(h["recompra_primera_tarde"], 2, True)},
        4: {"Nota si llega a tiempo": es(h["nota_a_tiempo"], 2), "Nota 7 o más días tarde": es(h["nota_7_dias_o_mas"], 2)},
    }
    # Los 27 estados se ven en la barra de la página 1.
    for r in estados:
        esperado[1][f"% tarde {r['estado']}"] = es(float(r["pct_tarde"]), 1, True)
    for r in flete:
        esperado[3][f"Flete {r['rango_precio']}"] = es(float(r["pct_ponderado"]), 1, True)
    for seg, r in rfm.items():
        esperado[3][f"RFM {seg} % clientes"] = es(float(r["pct_clientes"]), 1, True)
        esperado[3][f"RFM {seg} % dinero"] = es(float(r["pct_monto"]), 1, True)
    for r in nota_dia:
        esperado[4][f"Nota con {r['dias_retraso']} días"] = es(float(r["nota_prom"]), 2)
    # Despacho: el tablero cuenta todos los pedidos de vendedor; el SQL r_despacho solo los de un vendedor.
    # Por eso aquí solo comparo el 72,2 %, que en los dos se calcula sobre pedidos de un vendedor.
    _ = despacho

    pdf = pdfium.PdfDocument(RAIZ / "tablero.pdf")
    errores = total = 0
    for numero, cifras in esperado.items():
        texto = pdf[numero - 1].get_textpage().get_text_range()
        for nombre, valor in cifras.items():
            total += 1
            ok = valor in texto
            errores += not ok
            if not ok:
                print(f"FALTA página {numero}: {nombre} = {valor}")
    print(f"{total - errores} de {total} cifras del tablero coinciden con el SQL.")
    return 1 if errores else 0


if __name__ == "__main__":
    raise SystemExit(main())
