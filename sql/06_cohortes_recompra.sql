-- =============================================================================
-- 06_cohortes_recompra.sql · ¿Los clientes vuelven a comprar?
-- Cohorte = mes de la primera compra de cada persona (customer_unique_id).
-- Resultados:
--   r_cohortes                  % de cada cohorte que vuelve a comprar en el
--                               mes 1, 2, 3... después de la primera compra.
--   r_recompra_primera_entrega  ¿vuelven menos los que recibieron tarde su
--                               primer pedido? Con prueba z de dos proporciones.
-- Uso pedidos de todos los estados menos cancelados y no disponibles.
-- =============================================================================

create or replace table compras_validas as
select * from pedidos where estado_pedido not in ('canceled', 'unavailable');

create or replace table primera_compra as
select cliente_id, pedido_id, fecha_compra, mes_compra as cohorte, entregado, dias_retraso
from compras_validas
qualify row_number() over (partition by cliente_id order by fecha_compra, pedido_id) = 1;

create or replace table r_cohortes as
with actividad as (
    select distinct c.cliente_id, f.cohorte,
           date_diff('month', f.cohorte, c.mes_compra) as mes_desde_primera
    from compras_validas c
    join primera_compra f using (cliente_id)
),
tamano as (
    select cohorte, count(*) as clientes from primera_compra group by 1
)
select a.cohorte,
       t.clientes                                           as clientes_cohorte,
       a.mes_desde_primera,
       count(*)                                             as clientes_activos,
       round(100.0 * count(*) / t.clientes, 2)              as pct_activos
from actividad a
join tamano t using (cohorte)
where a.cohorte between date '2017-01-01' and date '2018-08-01'   -- meses con datos completos
  and a.mes_desde_primera between 0 and 12
group by a.cohorte, t.clientes, a.mes_desde_primera
order by a.cohorte, a.mes_desde_primera;

-- ¿Influye la primera entrega? Solo primeras compras hasta febrero de 2018,
-- para que todos tengan al menos 6 meses para volver (los datos llegan a ago-2018).
create or replace table r_recompra_primera_entrega as
with base as (
    select f.cliente_id,
           f.dias_retraso > 0 as primera_tarde,
           exists (select 1 from compras_validas c
                   where c.cliente_id = f.cliente_id and c.pedido_id <> f.pedido_id
                     and c.fecha_compra > f.fecha_compra) as volvio
    from primera_compra f
    where f.entregado and f.fecha_compra < timestamp '2018-03-01'
),
grupos as (
    select primera_tarde, count(*) as clientes, count(*) filter (where volvio) as volvieron
    from base group by 1
),
total as (
    select sum(volvieron) * 1.0 / sum(clientes) as p,
           sum(clientes) filter (where primera_tarde)     as n_tarde,
           sum(clientes) filter (where not primera_tarde) as n_tiempo
    from grupos
)
select case when g.primera_tarde then 'Primera entrega tarde' else 'Primera entrega a tiempo' end as grupo,
       g.clientes,
       g.volvieron,
       round(100.0 * g.volvieron / g.clientes, 2) as pct_volvio,
       -- z de la diferencia entre los dos grupos (igual en las dos filas).
       round(( (select volvieron * 1.0 / clientes from grupos where not primera_tarde)
             - (select volvieron * 1.0 / clientes from grupos where primera_tarde) )
             / sqrt(t.p * (1 - t.p) * (1.0 / t.n_tarde + 1.0 / t.n_tiempo)), 2) as z_diferencia
from grupos g, total t
order by g.primera_tarde;
