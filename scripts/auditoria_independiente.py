"""Recalcula las cifras clave con Python puro, sin DuckDB y desde los CSV de Kaggle.

Uso:
    python scripts/auditoria_independiente.py

Sirve para comprobar el SQL por otro camino: lee los CSV originales de
datos_crudos/ con el módulo csv (no los Parquet) y compara cada cifra con
salidas/r_hallazgos.csv. Si una no coincide, termina con error.
"""
from __future__ import annotations

import csv
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CRUDOS = RAIZ / "datos_crudos"


def leer(nombre: str):
    with (CRUDOS / f"{nombre}.csv").open(encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def fecha(texto: str):
    return datetime.strptime(texto, "%Y-%m-%d %H:%M:%S") if texto else None


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    cliente_de = {r["customer_id"]: (r["customer_unique_id"], r["customer_state"]) for r in leer("olist_customers_dataset")}
    pedidos = {}
    for r in leer("olist_orders_dataset"):
        compra, entrega, promesa = fecha(r["order_purchase_timestamp"]), fecha(r["order_delivered_customer_date"]), fecha(r["order_estimated_delivery_date"])
        entregado = r["order_status"] == "delivered" and entrega is not None
        pedidos[r["order_id"]] = {
            "cliente": cliente_de[r["customer_id"]][0], "estado": cliente_de[r["customer_id"]][1],
            "status": r["order_status"], "compra": compra, "entregado": entregado,
            "transportadora": fecha(r["order_delivered_carrier_date"]),
            "dias_entrega": (entrega - compra).total_seconds() / 86400 if entregado else None,
            "dias_prometidos": (promesa - compra).total_seconds() / 86400 if entregado else None,
            "retraso": (entrega.date() - promesa.date()).days if entregado else None,
        }
    entregados = [p for p in pedidos.values() if p["entregado"]]
    tarde = [p for p in entregados if p["retraso"] > 0]

    # Reseña más reciente por pedido
    mejor = {}
    for r in leer("olist_order_reviews_dataset"):
        clave = (r["review_answer_timestamp"], r["review_creation_date"])
        actual = mejor.get(r["order_id"])
        if actual is None or clave > actual[0] or (clave == actual[0] and r["review_id"] < actual[2]):
            mejor[r["order_id"]] = (clave, int(r["review_score"]), r["review_id"])
    nota = {k: v[1] for k, v in mejor.items()}

    # Ítems por pedido y por pedido-vendedor
    precio, flete = defaultdict(float), defaultdict(float)
    limite, vendedores_pedido = {}, defaultdict(set)
    for r in leer("olist_order_items_dataset"):
        precio[r["order_id"]] += float(r["price"])
        flete[r["order_id"]] += float(r["freight_value"])
        vendedores_pedido[r["order_id"]].add(r["seller_id"])
        clave = (r["order_id"], r["seller_id"])
        limite[clave] = max(limite.get(clave, ""), r["shipping_limit_date"])

    # 7. Pedidos tarde (de un solo vendedor) en que el vendedor despachó a tiempo
    tarde_un_vendedor = tarde_despacho_ok = 0
    for (pid, _), lim in limite.items():
        p = pedidos[pid]
        if p["entregado"] and len(vendedores_pedido[pid]) == 1 and p["transportadora"] and p["retraso"] > 0:
            tarde_un_vendedor += 1
            tarde_despacho_ok += p["transportadora"] <= fecha(lim)

    # 15. Pendiente de la nota entre 1 y 6 días tarde (mínimos cuadrados)
    pares = [(p["retraso"], nota[k]) for k, p in pedidos.items() if p["entregado"] and k in nota and 1 <= p["retraso"] <= 6]
    xm = statistics.fmean(x for x, _ in pares)
    ym = statistics.fmean(y for _, y in pares)
    pendiente = sum((x - xm) * (y - ym) for x, y in pares) / sum((x - xm) ** 2 for x, _ in pares)

    # 18-20. Flete en pedidos de menos de R$50
    baratos = [k for k in precio if precio[k] < 50]

    # 21-23. Recompra (sin cancelados ni no disponibles)
    validos = {k: p for k, p in pedidos.items() if p["status"] not in ("canceled", "unavailable")}
    por_cliente = defaultdict(list)
    for k, p in validos.items():
        por_cliente[p["cliente"]].append((p["compra"], k))
    volvio = {"a_tiempo": [0, 0], "tarde": [0, 0]}
    for compras in por_cliente.values():
        compras.sort()
        primera_fecha, primera = compras[0]
        p = pedidos[primera]
        if p["entregado"] and primera_fecha < datetime(2018, 3, 1):
            grupo = "tarde" if p["retraso"] > 0 else "a_tiempo"
            volvio[grupo][0] += 1
            volvio[grupo][1] += any(f > primera_fecha for f, _ in compras[1:])

    rj = sum(p["estado"] == "RJ" for p in entregados)
    rj_tarde = sum(p["estado"] == "RJ" for p in tarde)
    calculado = {
        "pedidos_total": len(pedidos),
        "pedidos_entregados": len(entregados),
        "pedidos_tarde": len(tarde),
        "pct_tarde": round(100 * len(tarde) / len(entregados), 1),
        "dias_entrega_prom": round(statistics.fmean(p["dias_entrega"] for p in entregados), 1),
        "dias_prometidos_prom": round(statistics.fmean(p["dias_prometidos"] for p in entregados), 1),
        "pct_retrasos_vendedor_a_tiempo": round(100 * tarde_despacho_ok / tarde_un_vendedor, 1),
        "rj_pct_entregas": round(100 * rj / len(entregados), 1),
        "rj_pct_retrasos": round(100 * rj_tarde / len(tarde), 1),
        "nota_a_tiempo": round(statistics.fmean(nota[k] for k, p in pedidos.items() if p["entregado"] and k in nota and p["retraso"] <= 0), 2),
        "puntos_por_dia_1_a_6": round(-pendiente, 2),
        "nota_7_dias_o_mas": round(statistics.fmean(nota[k] for k, p in pedidos.items() if p["entregado"] and k in nota and p["retraso"] >= 7), 2),
        "flete_pct_total": round(100 * sum(flete.values()) / sum(precio.values()), 1),
        "pct_pedidos_menos_50": round(100 * len(baratos) / len(precio), 1),
        "flete_pct_menos_50": round(100 * sum(flete[k] for k in baratos) / sum(precio[k] for k in baratos), 1),
        "pct_flete_mayor_menos_50": round(100 * sum(flete[k] >= precio[k] for k in baratos) / len(baratos), 1),
        "pct_clientes_recompran": round(100 * sum(len(c) > 1 for c in por_cliente.values()) / len(por_cliente), 1),
        "recompra_primera_a_tiempo": round(100 * volvio["a_tiempo"][1] / volvio["a_tiempo"][0], 2),
        "recompra_primera_tarde": round(100 * volvio["tarde"][1] / volvio["tarde"][0], 2),
    }

    with (RAIZ / "salidas" / "r_hallazgos.csv").open(encoding="utf-8") as f:
        sql = {r["clave"]: float(r["valor"]) for r in csv.DictReader(f)}
    errores = 0
    for clave, valor in calculado.items():
        ok = abs(valor - sql[clave]) < 1e-9
        errores += not ok
        print(f"{'OK ' if ok else 'MAL'} {clave:34} Python {valor:>12}   SQL {sql[clave]:>12}")
    print(f"\n{len(calculado) - errores} de {len(calculado)} cifras coinciden.")
    return 1 if errores else 0


if __name__ == "__main__":
    raise SystemExit(main())
