-- =============================================================================
-- 05_demora_vs_resena.sql · ¿Cuánto baja la nota con cada día de retraso?
-- Una reseña por pedido (la más reciente, ver 00_base). Solo pedidos entregados.
-- Resultados:
--   r_nota_por_dia_retraso  nota promedio por día de retraso (de -10 a 20+).
--   r_pendiente_nota        cuántos puntos cuesta cada día, por tramo,
--                           con regresión lineal (REGR_SLOPE).
-- =============================================================================

create or replace table entregas_con_nota as
select p.pedido_id, p.dias_retraso, r.nota,
       -- El cliente RESPONDIÓ antes de recibir el paquete (no la fecha en que Olist
       -- envió la encuesta, que es otra columna: corregido en la revisión del 4-nov).
       r.fecha_respuesta < p.fecha_entrega_cliente as respondio_antes
from pedidos p
join resenas r using (pedido_id)
where p.entregado;

create or replace table r_nota_por_dia_retraso as
with tramos as (
    select greatest(least(dias_retraso, 20), -10) as dia,   -- se agrupan las puntas
           nota
    from entregas_con_nota
)
select dia                                              as dias_retraso,
       case when dia = -10 then '10 o más días antes'
            when dia =  20 then '20 o más días tarde'
            when dia =  -1 then '1 día antes'
            when dia <   0 then (-dia)::varchar || ' días antes'
            when dia =   0 then 'el día prometido'
            when dia =   1 then '1 día tarde'
            else dia::varchar || ' días tarde' end   as etiqueta,
       count(*)                                         as pedidos,
       round(avg(nota), 2)                              as nota_prom,
       round(100.0 * count(*) filter (where nota <= 2) / count(*), 1) as pct_nota_1_o_2
from tramos
group by 1
order by 1;

create or replace table r_pendiente_nota as
select tramo,
       count(*)                                  as pedidos,
       round(avg(nota), 2)                       as nota_prom,
       -- Solo entre -20 y +20 días: hay pedidos de -147 y +188 días que, solos,
       -- aplanaban la pendiente de los tramos abiertos.
       round(regr_slope(nota, dias_retraso) filter (where dias_retraso between -20 and 20), 3) as puntos_por_dia,
       round(corr(nota, dias_retraso) filter (where dias_retraso between -20 and 20), 3)       as correlacion,
       -- ¿Respondió la encuesta antes de que le llegara el paquete? ¿Qué nota puso?
       round(100.0 * count(*) filter (where respondio_antes) / count(*), 1) as pct_respondio_antes_de_recibir,
       round(avg(nota) filter (where respondio_antes), 2)                   as nota_si_respondio_antes,
       round(avg(nota) filter (where not respondio_antes), 2)               as nota_si_respondio_despues
from (
    select *,
           case when dias_retraso <= 0 then '1. A tiempo'
                when dias_retraso <= 6 then '2. De 1 a 6 días tarde'
                else '3. 7 o más días tarde' end as tramo
    from entregas_con_nota
)
group by 1
order by 1;
