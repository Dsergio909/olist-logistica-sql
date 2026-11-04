-- =============================================================================
-- 07_rfm.sql · RFM: qué clientes compran seguido y cuánto
--   R (recencia)  = días desde la última compra hasta el día después del último
--                   pedido de los datos.
--   F (frecuencia)= número de pedidos.
--   M (monto)     = total pagado.
-- Como el 97 % compra una sola vez, F no se puede partir en quintiles: uso
-- 1 pedido, 2 pedidos y 3 o más. R y M sí van en quintiles (NTILE(5)).
-- Resultados: rfm_clientes (una fila por cliente, la usa Power BI) y
--             r_rfm_segmentos (resumen por segmento).
-- =============================================================================

create or replace table rfm_clientes as
with pagos_pedido as (
    select order_id as pedido_id, sum(payment_value) as pagado from pagos_crudos group by 1
),
por_cliente as (
    select c.cliente_id,
           max(c.fecha_compra)                       as ultima_compra,
           count(distinct c.pedido_id)               as frecuencia,
           coalesce(sum(g.pagado), 0)                as monto
    from compras_validas c
    left join pagos_pedido g using (pedido_id)
    group by 1
),
fecha_corte as (select max(fecha_compra)::date + 1 as corte from compras_validas),
puntajes as (
    select p.*,
           date_diff('day', p.ultima_compra::date, f.corte)   as recencia_dias,
           6 - ntile(5) over (order by p.ultima_compra desc, p.cliente_id) as r,   -- 5 = compró hace poco
           case when p.frecuencia >= 3 then 3 else p.frecuencia end as f,
           ntile(5) over (order by p.monto, p.cliente_id)       as m                -- 5 = gasta más
    from por_cliente p, fecha_corte f
)
select cliente_id, recencia_dias, frecuencia, round(monto, 2) as monto, r, f, m,
       case
           when f >= 2 and r >= 4                 then '1. Fieles activos'
           when f >= 2                            then '2. Fieles dormidos'
           when f = 1 and m = 5 and r >= 4        then '3. Nuevos de ticket alto'
           when f = 1 and r >= 4                  then '4. Nuevos'
           when f = 1 and m >= 4                  then '5. Ticket alto que no volvió'
           else                                        '6. Una compra y se fueron'
       end as segmento
from puntajes;

create or replace table r_rfm_segmentos as
select segmento,
       count(*)                                              as clientes,
       round(100.0 * count(*) / sum(count(*)) over (), 1)   as pct_clientes,
       round(sum(monto), 0)                                  as monto_total,
       round(100.0 * sum(monto) / sum(sum(monto)) over (), 1) as pct_monto,
       round(avg(monto), 2)                                  as monto_prom,
       round(avg(frecuencia), 2)                             as pedidos_prom,
       round(avg(recencia_dias))                             as recencia_prom_dias
from rfm_clientes
group by 1
order by 1;
