-- =============================================================================
-- 09_mes_a_mes.sql · ¿Cuándo se dispararon los retrasos?
-- De enero de 2017 a agosto de 2018 (los meses con datos completos).
-- Técnica: LAG para comparar con el mes anterior y promedio móvil de 3 meses.
-- Resultado: r_mes_a_mes.
-- =============================================================================

create or replace table r_mes_a_mes as
with mensual as (
    select mes_compra                                        as mes,
           count(*)                                          as pedidos,
           count(*) filter (where entregado)                 as entregados,
           count(*) filter (where entregado and dias_retraso > 0) as tarde,
           avg(dias_entrega) filter (where entregado)        as dias_entrega_prom
    from pedidos
    where mes_compra between date '2017-01-01' and date '2018-08-01'
    group by 1
),
notas as (
    select p.mes_compra as mes, avg(r.nota) as nota_prom
    from pedidos p join resenas r using (pedido_id)
    group by 1
)
select m.mes,
       m.pedidos,
       m.pedidos - lag(m.pedidos) over (order by m.mes)               as cambio_pedidos,
       round(100.0 * m.tarde / m.entregados, 1)                       as pct_tarde,
       round(avg(100.0 * m.tarde / m.entregados)
             over (order by m.mes rows between 2 preceding and current row), 1) as pct_tarde_movil_3m,
       round(m.dias_entrega_prom, 1)                                  as dias_entrega_prom,
       round(n.nota_prom, 2)                                          as nota_prom
from mensual m
left join notas n using (mes)
order by m.mes;
