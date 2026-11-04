"""Las consultas cuadran entre sí y con la base."""
from __future__ import annotations

import pytest


def test_por_estado_suma_lo_mismo_que_la_base(uno):
    assert uno("select count(*) from r_entrega_por_estado") == 27
    assert uno("select sum(pedidos_entregados) from r_entrega_por_estado") == \
        uno("select count(*) from pedidos where entregado")
    assert uno("select sum(pedidos_tarde) from r_entrega_por_estado") == \
        uno("select count(*) from pedidos where entregado and dias_retraso > 0")
    assert uno("select round(sum(pct_de_todos_los_retrasos)) from r_entrega_por_estado") == 100


def test_porcentajes_entre_0_y_100(con):
    columnas = con.execute("""
        select table_name, column_name from information_schema.columns
        where table_name like 'r\\_%' escape '\\' and column_name like 'pct\\_%' escape '\\'
    """).fetchall()
    assert columnas, "No encontré columnas de porcentaje"
    for tabla, col in columnas:
        fuera = con.execute(f"select count(*) from {tabla} where {col} < 0 or {col} > 100").fetchone()[0]
        assert fuera == 0, f"{tabla}.{col} tiene porcentajes fuera de 0-100"


def test_nota_por_dia_cubre_todas_las_entregas_con_resena(uno):
    assert uno("select sum(pedidos) from r_nota_por_dia_retraso") == \
        uno("select count(*) from pedidos join resenas using (pedido_id) where entregado")
    assert uno("select sum(pedidos) from r_pendiente_nota") == \
        uno("select sum(pedidos) from r_nota_por_dia_retraso")


def test_la_nota_baja_con_el_retraso(uno):
    a_tiempo = uno("select nota_prom from r_pendiente_nota where tramo like '1.%'")
    poco = uno("select nota_prom from r_pendiente_nota where tramo like '2.%'")
    mucho = uno("select nota_prom from r_pendiente_nota where tramo like '3.%'")
    assert a_tiempo > poco > mucho


def test_vendedores_y_concentracion(uno):
    assert uno("select min(pedidos_entregados) from r_vendedores") >= 30
    assert uno("select count(distinct cuartil_retraso) from r_vendedores") == 4
    # La concentración crece con el corte y no pasa del 100 %.
    assert uno("""select bool_and(pct_de_los_retrasos >= anterior) from (
                    select pct_de_los_retrasos,
                           lag(pct_de_los_retrasos, 1, 0) over (order by pct_vendedores) as anterior
                    from r_concentracion_retrasos)""")
    assert uno("select sum(pedidos_tarde) from r_despacho") <= uno("select sum(pedidos_tarde) from r_vendedores") + 10_000


def test_etapas_suman_el_total(uno):
    # aprobar + despachar + transportar = total (con 0,2 días de margen por redondeo).
    assert uno("""select max(abs(dias_aprobar_pago + dias_vendedor_despacha + dias_transportadora - dias_total))
                  from r_etapas""") <= 0.2


def test_flete_por_rango_cubre_los_pedidos_con_productos(uno):
    assert uno("select sum(pedidos) from r_flete_por_rango_precio") == uno("select count(*) from pedido_valor")
    assert uno("select round(sum(pct_pedidos)) from r_flete_por_rango_precio") == 100


def test_cohortes(uno):
    assert uno("select min(pct_activos) from r_cohortes where mes_desde_primera = 0") == 100
    assert uno("select max(pct_activos) from r_cohortes where mes_desde_primera > 0") < 5
    assert uno("select count(distinct cohorte) from r_cohortes") == 20


def test_rfm(uno):
    assert uno("select count(*) from rfm_clientes") == uno("select count(distinct cliente_id) from compras_validas")
    assert uno("select sum(clientes) from r_rfm_segmentos") == uno("select count(*) from rfm_clientes")
    assert uno("select round(sum(pct_clientes)) from r_rfm_segmentos") == 100
    assert uno("select count(*) from rfm_clientes where r not between 1 and 5 or m not between 1 and 5") == 0


def test_recompra_diferencia_significativa(hallazgos):
    assert hallazgos["recompra_primera_a_tiempo"][0] > hallazgos["recompra_primera_tarde"][0]
    assert hallazgos["z_recompra"][0] > 1.96


def test_mes_a_mes(uno):
    assert uno("select count(*) from r_mes_a_mes") == 20
    assert uno("select count(*) from r_mes_a_mes where cambio_pedidos is null") == 1


@pytest.mark.parametrize("clave", ["pct_tarde", "flete_pct_total", "nota_a_tiempo"])
def test_hallazgos_no_vacios(hallazgos, clave):
    assert hallazgos[clave][0] is not None
