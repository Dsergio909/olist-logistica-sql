-- =============================================================================
-- 06_cohortes_recompra.sql · ¿Los clientes vuelven a comprar?
-- Cohorte = mes de la primera compra de cada persona (customer_unique_id).
-- Resultados:
--   r_cohortes                  % de cada cohorte que vuelve a comprar en el
--                               mes 0 (el mismo mes), 1, 2, 3... de la primera compra.
--   r_recompra_primera_entrega  ¿vuelven menos los que recibieron tarde su
--                               primer pedido? Con prueba z de dos proporciones.
-- Uso pedidos de todos los estados menos cancelados y no disponibles.
-- Volver a comprar = una compra en OTRO DÍA. 281 clientes tienen dos pedidos en el
-- mismo segundo (una compra partida en dos) y otros 573 hicieron otro pedido el
-- mismo día, horas después. Lo cuento como la misma visita a la tienda: si se
-- contaran, la recompra sería 2,8 % en vez de 2,2 %.
-- =============================================================================

create or replace table compras_validas as
select * from pedidos where estado_pedido not in ('canceled', 'unavailable');

create or replace table primera_compra as
select cliente_id, pedido_id, fecha_compra, mes_compra as cohorte, entregado, dias_retraso,
       fecha_entrega_cliente
from compras_validas
qualify row_number() over (partition by cliente_id order by fecha_compra, pedido_id) = 1;

-- Solo cuentan las compras de OTRO día (no la primera): así el mes 0 muestra a
-- los que volvieron dentro del mismo mes, que son el 17 % de los que vuelven.
-- Antes el mes 0 incluía la primera compra y daba siempre 100 %, y escondía esas
-- recompras (corregido en la revisión del 4-nov).
create or replace table r_cohortes as
with actividad as (
    select distinct c.cliente_id, f.cohorte,
           date_diff('month', f.cohorte, c.mes_compra) as mes_desde_primera
    from compras_validas c
    join primera_compra f using (cliente_id)
    where c.fecha_compra::date > f.fecha_compra::date
      and c.mes_compra <= date '2018-08-01'                            -- último mes completo
),
tamano as (
    select cohorte, count(*) as clientes from primera_compra group by 1
),
-- Todas las celdas que sí se pudieron observar (hasta ago-2018), también las que
-- tuvieron 0 clientes de vuelta: si faltan, cualquier promedio sale inflado.
grilla as (
    select t.cohorte, t.clientes, m.mes_desde_primera
    from tamano t
    cross join generate_series(0, 12) as m(mes_desde_primera)
    where t.cohorte between date '2017-01-01' and date '2018-08-01'
      and t.cohorte + to_months(m.mes_desde_primera) <= date '2018-08-01'
)
select g.cohorte,
       g.clientes                                           as clientes_cohorte,
       g.mes_desde_primera,
       count(a.cliente_id)                                  as clientes_que_volvieron,
       round(100.0 * count(a.cliente_id) / g.clientes, 2)   as pct_volvieron
from grilla g
left join actividad a using (cohorte, mes_desde_primera)
group by g.cohorte, g.clientes, g.mes_desde_primera
order by g.cohorte, g.mes_desde_primera;

-- ¿Influye la primera entrega? Todos se miden con la MISMA ventana: 180 días
-- después de RECIBIR el primer pedido (una compra hecha antes de recibirlo no
-- puede ser una reacción al retraso: eran 257 de 2.260). Solo primeros pedidos
-- entregados antes de marzo de 2018, para que la ventana quepa en los datos.
-- Por qué la ventana fija (corregido en la revisión del 4-nov): los retrasos se
-- concentraron en nov-2017 y feb-mar-2018, así que esos clientes tenían menos meses
-- de datos para volver (297 días contra 347 en promedio). Sin la ventana fija, la
-- diferencia salía más grande de lo que es.
create or replace table r_recompra_primera_entrega as
with base as (
    select f.cliente_id,
           f.dias_retraso > 0 as primera_tarde,
           exists (select 1 from compras_validas c
                   where c.cliente_id = f.cliente_id
                     and c.fecha_compra > f.fecha_entrega_cliente              -- después de recibir
                     and c.fecha_compra <= f.fecha_entrega_cliente + interval 180 day) as volvio
    from primera_compra f
    where f.entregado and f.fecha_entrega_cliente < timestamp '2018-03-01'
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
