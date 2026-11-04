-- =============================================================================
-- 03_entrega_por_vendedor.sql · ¿Qué vendedores cumplen?
-- Un pedido puede tener varios vendedores; aquí la unidad es "pedido de un
-- vendedor" (lo que despacha cada uno).
--   despacho_tarde = el vendedor entregó a la transportadora después de su
--                    fecha límite (shipping_limit_date).
-- Resultados:
--   r_vendedores           vendedores con 30 o más pedidos entregados.
--   r_concentracion_retrasos  qué parte de los retrasos se llevan los peores.
-- Técnica: CTE, NTILE, RANK, PERCENT_RANK y suma acumulada con ventana.
-- =============================================================================

create or replace table vendedor_pedidos as
select pv.vendedor_id,
       pv.pedido_id,
       p.dias_entrega,
       p.dias_retraso,
       p.dias_retraso > 0                                   as tarde,
       p.fecha_entrega_transportadora > pv.fecha_limite_despacho as despacho_tarde,
       r.nota
from pedido_vendedor pv
join pedidos p using (pedido_id)
left join resenas r using (pedido_id)
where p.entregado;

create or replace table r_vendedores as
with por_vendedor as (
    select vendedor_id,
           count(*)                                    as pedidos_entregados,
           count(*) filter (where tarde)               as pedidos_tarde,
           count(*) filter (where despacho_tarde)      as despachos_tarde,
           avg(dias_entrega)                           as dias_entrega_prom,
           avg(nota)                                   as nota_prom
    from vendedor_pedidos
    group by 1
)
select v.vendedor_id,
       s.vendedor_estado,
       v.pedidos_entregados,
       v.pedidos_tarde,
       round(100.0 * v.pedidos_tarde / v.pedidos_entregados, 1)   as pct_tarde,
       round(100.0 * v.despachos_tarde / v.pedidos_entregados, 1) as pct_despacho_tarde,
       round(v.dias_entrega_prom, 1)                               as dias_entrega_prom,
       round(v.nota_prom, 2)                                       as nota_prom,
       rank() over (order by v.pedidos_tarde * 1.0 / v.pedidos_entregados desc) as puesto_por_retraso,
       -- 1 = el 25 % que más cumple, 4 = el 25 % que menos cumple.
       ntile(4) over (order by v.pedidos_tarde * 1.0 / v.pedidos_entregados, v.vendedor_id) as cuartil_retraso
from por_vendedor v
join vendedores s using (vendedor_id)
where v.pedidos_entregados >= 30
order by puesto_por_retraso, vendedor_id;

-- Concentración: ordeno a todos los vendedores por cantidad de retrasos y voy
-- sumando. ¿Cuántos retrasos y cuántos pedidos se llevan los primeros?
create or replace table r_concentracion_retrasos as
with por_vendedor as (
    select vendedor_id, count(*) as pedidos, count(*) filter (where tarde) as tarde
    from vendedor_pedidos group by 1
),
acumulado as (
    select *,
           row_number() over (order by tarde desc, pedidos desc, vendedor_id) as puesto,
           count(*)    over ()                                                as total_vendedores,
           sum(tarde)  over (order by tarde desc, pedidos desc, vendedor_id rows unbounded preceding) as tarde_acum,
           sum(pedidos) over (order by tarde desc, pedidos desc, vendedor_id rows unbounded preceding) as pedidos_acum,
           sum(tarde)  over () as tarde_total,
           sum(pedidos) over () as pedidos_total
    from por_vendedor
),
cortes as (select unnest([1, 5, 10, 20]) as pct_vendedores)
select c.pct_vendedores,
       max(a.puesto)                                              as vendedores,
       max(a.tarde_acum)                                          as pedidos_tarde,
       round(100.0 * max(a.tarde_acum) / max(a.tarde_total), 1)   as pct_de_los_retrasos,
       round(100.0 * max(a.pedidos_acum) / max(a.pedidos_total), 1) as pct_de_los_pedidos
from cortes c
join acumulado a on a.puesto <= ceil(a.total_vendedores * c.pct_vendedores / 100.0)
group by 1
order by 1;
