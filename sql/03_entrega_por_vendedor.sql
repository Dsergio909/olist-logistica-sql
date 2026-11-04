-- =============================================================================
-- 03_entrega_por_vendedor.sql · ¿Qué vendedores cumplen?
-- Un pedido puede tener varios vendedores; aquí la unidad es "pedido de un
-- vendedor" (lo que despacha cada uno).
--   despacho_tarde = el vendedor entregó a la transportadora un día después de
--                    su fecha límite (shipping_limit_date), en días de calendario
--                    como "tarde". Antes se comparaban horas y entregar el último
--                    día por la tarde contaba como tarde (corregido el 4-nov).
-- Resultados:
--   r_vendedores           vendedores con 30 o más pedidos entregados.
--   r_concentracion_retrasos  qué parte de los retrasos se llevan los que más acumulan.
--   r_retraso_por_tamano     ¿los vendedores grandes llegan más tarde que los chicos?
--   r_peores_vendedores      el 10 % de vendedores (30+ pedidos) con peor tasa.
-- Técnica: CTE, NTILE, RANK, PERCENT_RANK y suma acumulada con ventana.
-- =============================================================================

create or replace table vendedor_pedidos as
select pv.vendedor_id,
       pv.pedido_id,
       p.dias_entrega,
       p.dias_retraso,
       p.dias_retraso > 0                                   as tarde,
       p.fecha_entrega_transportadora::date > pv.fecha_limite_despacho::date as despacho_tarde,
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
       -- 1 = el 25 % que más cumple, 4 = el 25 % que menos cumple. Con PERCENT_RANK
       -- los vendedores con la misma fracción de retrasos quedan en el mismo cuartil
       -- (NTILE los partía).
       least(4, 1 + floor(4 * percent_rank() over (order by v.pedidos_tarde * 1.0 / v.pedidos_entregados)))::int as cuartil_retraso
from por_vendedor v
join vendedores s using (vendedor_id)
where v.pedidos_entregados >= 30
order by puesto_por_retraso, vendedor_id;

-- Concentración: ordeno a todos los vendedores por cantidad de retrasos y voy
-- sumando. ¿Cuántos retrasos y cuántos pedidos se llevan los primeros?
-- Solo pedidos de un vendedor: Olist da una sola fecha de entrega por pedido, así
-- que en un pedido de dos vendedores no se sabe cuál causó el retraso (y el pedido
-- se contaría dos veces). Son el 98,7 % de los pedidos entregados.
create or replace table r_concentracion_retrasos as
with por_vendedor as (
    select vp.vendedor_id, count(*) as pedidos, count(*) filter (where vp.tarde) as tarde
    from vendedor_pedidos vp
    join pedido_valor v using (pedido_id)
    where v.vendedores = 1
    group by 1
),
acumulado as (
    select *,
           -- A igual número de retrasos, primero el que tiene menos pedidos (peor tasa).
           row_number() over (order by tarde desc, pedidos asc, vendedor_id) as puesto,
           count(*)    over ()                                                as total_vendedores,
           sum(tarde)  over (order by tarde desc, pedidos asc, vendedor_id rows unbounded preceding) as tarde_acum,
           sum(pedidos) over (order by tarde desc, pedidos asc, vendedor_id rows unbounded preceding) as pedidos_acum,
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

-- Ordenar por cantidad de retrasos siempre pone arriba a los que más venden. La
-- pregunta justa es por tasa: ¿llegan más tarde los vendedores grandes?
create or replace table r_retraso_por_tamano as
with por_vendedor as (
    select vp.vendedor_id, count(*) as pedidos, count(*) filter (where vp.tarde) as tarde
    from vendedor_pedidos vp
    join pedido_valor v using (pedido_id)
    where v.vendedores = 1
    group by 1
)
select case when pedidos < 10   then 1 when pedidos < 50  then 2
            when pedidos < 200  then 3 when pedidos < 1000 then 4 else 5 end as orden_tamano,
       case when pedidos < 10   then 'Menos de 10 pedidos' when pedidos < 50 then '10 a 49'
            when pedidos < 200  then '50 a 199' when pedidos < 1000 then '200 a 999'
            else '1.000 o más' end                                      as tamano_vendedor,
       count(*)                                                         as vendedores,
       sum(pedidos)                                                     as pedidos,
       round(100.0 * sum(tarde) / sum(pedidos), 1)                      as pct_tarde
from por_vendedor
group by 1, 2
order by 1;

-- Los peores por tasa: el 10 % de los vendedores con 30 o más pedidos que más
-- llega tarde. ¿Qué parte de todos los retrasos se llevan?
create or replace table r_peores_vendedores as
with por_vendedor as (
    select vp.vendedor_id, count(*) as pedidos, count(*) filter (where vp.tarde) as tarde
    from vendedor_pedidos vp
    join pedido_valor v using (pedido_id)
    where v.vendedores = 1
    group by 1
),
grandes as (
    select *,
           row_number() over (order by tarde * 1.0 / pedidos desc, pedidos desc, vendedor_id) as puesto,
           count(*) over () as total
    from por_vendedor
    where pedidos >= 30
)
select count(*)                                                            as vendedores,
       sum(pedidos)                                                        as pedidos,
       round(100.0 * sum(tarde) / sum(pedidos), 1)                         as pct_tarde,
       round(100.0 * sum(tarde) / (select sum(tarde) from por_vendedor), 1)   as pct_de_los_retrasos,
       round(100.0 * sum(pedidos) / (select sum(pedidos) from por_vendedor), 1) as pct_de_los_pedidos
from grandes
where puesto <= ceil(total * 0.10);
