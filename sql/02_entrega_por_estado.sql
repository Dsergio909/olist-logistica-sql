-- =============================================================================
-- 02_entrega_por_estado.sql · Entrega real contra la prometida, por estado
-- ¿En qué estados del cliente llega tarde el pedido y cuánto colchón promete
-- Olist? Solo pedidos entregados.
-- Resultado: r_entrega_por_estado (27 estados de Brasil).
-- Técnica: CTE, agregados con FILTER y funciones de ventana (RANK y
-- participación sobre el total con SUM() OVER ()).
-- =============================================================================

create or replace table r_entrega_por_estado as
with entregados as (
    select * from pedidos where entregado
),
por_estado as (
    select cliente_estado                                   as estado,
           count(*)                                         as pedidos_entregados,
           count(*) filter (where dias_retraso > 0)         as pedidos_tarde,
           avg(dias_entrega)                                as dias_entrega_prom,
           median(dias_entrega)                             as dias_entrega_mediana,
           avg(dias_prometidos)                             as dias_prometidos_prom,
           avg(dias_retraso) filter (where dias_retraso > 0) as dias_retraso_prom_si_tarde
    from entregados
    group by 1
),
-- Punto del mapa: mediana de las coordenadas de los códigos postales del estado.
centro as (
    select geolocation_state as estado,
           median(geolocation_lat) as lat,
           median(geolocation_lng) as lng
    from geo_cp group by 1
)
select e.estado,
       e.pedidos_entregados,
       e.pedidos_tarde,
       round(100.0 * e.pedidos_tarde / e.pedidos_entregados, 1)          as pct_tarde,
       round(e.dias_entrega_prom, 1)                                      as dias_entrega_prom,
       round(e.dias_entrega_mediana, 1)                                   as dias_entrega_mediana,
       round(e.dias_prometidos_prom, 1)                                   as dias_prometidos_prom,
       -- Colchón: cuántos días antes de lo prometido llega en promedio.
       round(e.dias_prometidos_prom - e.dias_entrega_prom, 1)             as colchon_dias,
       round(e.dias_retraso_prom_si_tarde, 1)                             as dias_retraso_prom_si_tarde,
       rank() over (order by e.pedidos_tarde * 1.0 / e.pedidos_entregados desc) as puesto_por_retraso,
       round(100.0 * e.pedidos_tarde / sum(e.pedidos_tarde) over (), 1) as pct_de_todos_los_retrasos,
       round(c.lat, 4) as lat,
       round(c.lng, 4) as lng
from por_estado e
left join centro c using (estado)
order by puesto_por_retraso, estado;
