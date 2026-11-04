"""Recalcula las cifras clave con Python puro, sin DuckDB y desde los CSV de Kaggle.

Uso:
    python scripts/auditoria_independiente.py

Sirve para comprobar el SQL por otro camino: lee los CSV originales de
datos_crudos/ con el módulo csv (no los Parquet) y compara cada cifra con
salidas/r_hallazgos.csv. Si una no coincide, termina con error.
"""
from __future__ import annotations

import csv
import math
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta
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
            "dias_entrega": (entrega.date() - compra.date()).days if entregado else None,          # días de calendario
            "dias_prometidos": (promesa.date() - compra.date()).days if entregado else None,
            "retraso": (entrega.date() - promesa.date()).days if entregado else None,
            "aprobacion": fecha(r["order_approved_at"]), "entrega": entrega, "promesa": promesa,
        }
    entregados = [p for p in pedidos.values() if p["entregado"]]
    tarde = [p for p in entregados if p["retraso"] > 0]

    # Reseña más reciente por pedido (y su fecha, para ver si se escribió antes de recibir)
    mejor = {}
    for r in leer("olist_order_reviews_dataset"):
        clave = (r["review_answer_timestamp"], r["review_creation_date"])
        actual = mejor.get(r["order_id"])
        if actual is None or clave > actual[0] or (clave == actual[0] and r["review_id"] < actual[2]):
            mejor[r["order_id"]] = (clave, int(r["review_score"]), r["review_id"], r["review_creation_date"][:10])
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
            # otro día y dentro de los 180 días siguientes a la primera compra
            volvio[grupo][1] += any(f.date() > primera_fecha.date() and f <= primera_fecha + timedelta(days=180)
                                    for f, _ in compras[1:])

    # 8-9. Días en la transportadora (pedidos con fecha de aprobación y de transportadora)
    def dias_transporte(tarde_o_no):
        return statistics.fmean((p["entrega"] - p["transportadora"]).total_seconds() / 86400 for p in entregados
                                if p["aprobacion"] and p["transportadora"] and (p["retraso"] > 0) == tarde_o_no)

    # 10-11. Concentración: el 5 % de vendedores con más pedidos tarde (pedido-vendedor entregado)
    por_vendedor = defaultdict(lambda: [0, 0])          # vendedor -> [pedidos, tarde]
    for (pid, vid) in limite:
        p = pedidos[pid]
        if p["entregado"] and len(vendedores_pedido[pid]) == 1:          # solo pedidos de un vendedor
            por_vendedor[vid][0] += 1
            por_vendedor[vid][1] += p["retraso"] > 0
    orden = sorted(por_vendedor.items(), key=lambda kv: (-kv[1][1], -kv[1][0], kv[0]))
    corte = math.ceil(len(orden) * 5 / 100)
    top_tarde = sum(v[1] for _, v in orden[:corte])
    top_pedidos = sum(v[0] for _, v in orden[:corte])
    total_tarde = sum(v[1] for _, v in orden)
    total_pedidos = sum(v[0] for _, v in orden)

    # 24. Prueba z de dos proporciones (proporción combinada)
    n1, x1 = volvio["a_tiempo"]
    n2, x2 = volvio["tarde"]
    pc = (x1 + x2) / (n1 + n2)
    z = (x1 / n1 - x2 / n2) / math.sqrt(pc * (1 - pc) * (1 / n1 + 1 / n2))

    # 25-26. RFM: segmento «ticket alto que no volvió» (f = 1, m >= 4, r <= 3)
    pagado = defaultdict(float)
    for r in leer("olist_order_payments_dataset"):
        pagado[r["order_id"]] += float(r["payment_value"])
    clientes = []
    for cid, compras in por_cliente.items():
        clientes.append((cid, max(f for f, _ in compras), len({f.date() for f, _ in compras}),
                         sum(pagado.get(k, 0.0) for _, k in compras)))
    n = len(clientes)

    def ntile(ordenados):
        """Igual que NTILE(5) de SQL: los primeros n % 5 grupos llevan una fila más."""
        base, resto = divmod(n, 5)
        salida, i = {}, 0
        for grupo in range(1, 6):
            tam = base + (1 if grupo <= resto else 0)
            for c in ordenados[i:i + tam]:
                salida[c[0]] = grupo
            i += tam
        return salida
    r_q = ntile(sorted(clientes, key=lambda c: (-c[1].timestamp(), c[0])))   # 1 = más reciente
    m_q = ntile(sorted(clientes, key=lambda c: (c[3], c[0])))                # 5 = gasta más
    segmento = [c for c in clientes if c[2] == 1 and m_q[c[0]] >= 4 and (6 - r_q[c[0]]) <= 3
                and not (m_q[c[0]] == 5 and (6 - r_q[c[0]]) >= 4)]
    monto_total = sum(c[3] for c in clientes)

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
        "pct_clientes_recompran": round(100 * sum(len({f.date() for f, _ in c}) > 1 for c in por_cliente.values()) / len(por_cliente), 1),
        "recompra_primera_a_tiempo": round(100 * volvio["a_tiempo"][1] / volvio["a_tiempo"][0], 2),
        "recompra_primera_tarde": round(100 * volvio["tarde"][1] / volvio["tarde"][0], 2),
        "dias_transportadora_tarde": round(dias_transporte(True), 1),
        "dias_transportadora_a_tiempo": round(dias_transporte(False), 1),
        "top5_pct_retrasos": round(100 * top_tarde / total_tarde, 1),
        "top5_pct_pedidos": round(100 * top_pedidos / total_pedidos, 1),
        "z_recompra": round(z, 2),
        "rfm_ticket_alto_pct_clientes": round(100 * len(segmento) / n, 1),
        "rfm_ticket_alto_pct_monto": round(100 * sum(c[3] for c in segmento) / monto_total, 1),
        "pct_resena_antes_7_mas": round(100 * statistics.fmean(
            mejor[k][3] < str(p["entrega"].date()) for k, p in pedidos.items() if p["entregado"] and k in mejor and p["retraso"] >= 7), 1),
        "pct_tarde_contando_mismo_dia": round(100 * sum(p["entrega"] > p["promesa"] for p in entregados) / len(entregados), 1),
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
