-- =============================================================================
-- 08_rutas_y_etapas.sql · ¿Dónde se pierde el tiempo?
-- Resultados:
--   r_etapas         días de cada etapa (aprobar, despachar, transportar) en
--                    pedidos a tiempo contra pedidos tarde. Aquí se cuentan horas
--                    (días con decimales), para que las tres etapas sumen el total.
--   r_despacho       si el vendedor despacha tarde, ¿cuánto sube el retraso?
--   r_rutas          estado del vendedor -> estado del cliente (200+ pedidos).
--   r_mismo_estado   mismo estado contra otro estado.
-- =============================================================================

create or replace table r_etapas as
select case when dias_retraso > 0 then 'Llegó tarde' else 'A tiempo' end as resultado,
       count(*) as pedidos,
       round(avg(date_diff('second', fecha_compra, fecha_aprobacion) / 86400.0), 1)                       as dias_aprobar_pago,
       round(avg(date_diff('second', fecha_aprobacion, fecha_entrega_transportadora) / 86400.0), 1)       as dias_vendedor_despacha,
       round(avg(date_diff('second', fecha_entrega_transportadora, fecha_entrega_cliente) / 86400.0), 1)  as dias_transportadora,
       round(avg(date_diff('second', fecha_compra, fecha_entrega_cliente) / 86400.0), 1)                 as dias_total
from pedidos
where entregado
  and fecha_aprobacion is not null and fecha_entrega_transportadora is not null
group by 1
order by 1;

-- Solo pedidos de un vendedor, para que la fecha de la transportadora sea de él.
create or replace table r_despacho as
with base as (
    select vp.*
    from vendedor_pedidos vp
    join pedido_valor v using (pedido_id)
    where v.vendedores = 1 and vp.despacho_tarde is not null
)
select case when despacho_tarde then 'Vendedor despachó tarde' else 'Vendedor despachó a tiempo' end as despacho,
       count(*)                                                 as pedidos,
       count(*) filter (where tarde)                            as pedidos_tarde,
       round(100.0 * count(*) filter (where tarde) / count(*), 1) as pct_tarde,
       round(100.0 * count(*) filter (where tarde)
             / sum(count(*) filter (where tarde)) over (), 1)  as pct_de_los_retrasos
from base
group by 1
order by 1;

create or replace table rutas_base as
select s.vendedor_estado,
       p.cliente_estado,
       vp.pedido_id,
       vp.dias_entrega,
       vp.tarde,
       pv.flete,
       pv.precio
from vendedor_pedidos vp
join pedido_vendedor pv using (pedido_id, vendedor_id)
join pedido_valor v using (pedido_id)
join pedidos p using (pedido_id)
join vendedores s using (vendedor_id)
-- Solo pedidos de un vendedor: si hay dos, el pedido se contaría dos veces y su
-- fecha de entrega (una sola por pedido) se le cargaría a los dos.
where v.vendedores = 1;

create or replace table r_rutas as
select vendedor_estado || ' -> ' || cliente_estado          as ruta,
       vendedor_estado, cliente_estado,
       count(*)                                              as pedidos,
       round(avg(dias_entrega), 1)                           as dias_entrega_prom,
       round(100.0 * count(*) filter (where tarde) / count(*), 1) as pct_tarde,
       round(100.0 * sum(flete) / sum(precio), 1)            as flete_pct,
       dense_rank() over (order by count(*) desc)            as puesto_por_volumen
from rutas_base
group by all
having count(*) >= 200
order by pedidos desc, ruta;

create or replace table r_mismo_estado as
select case when vendedor_estado = cliente_estado then 'Mismo estado' else 'Otro estado' end as tipo_ruta,
       count(*)                                              as pedidos,
       round(avg(dias_entrega), 1)                           as dias_entrega_prom,
       round(100.0 * count(*) filter (where tarde) / count(*), 1) as pct_tarde,
       round(100.0 * sum(flete) / sum(precio), 1)            as flete_pct
from rutas_base
group by 1
order by 1;
