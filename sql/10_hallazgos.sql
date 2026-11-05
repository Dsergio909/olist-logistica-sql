-- =============================================================================
-- 10_hallazgos.sql · Las cifras que cito en el README
-- Cada número del README sale de esta tabla. La prueba
-- pruebas/test_readme.py revisa que el README diga exactamente estos valores,
-- así no se puede colar una cifra inventada ni una vieja.
-- Resultado: r_hallazgos (clave, valor, decimales, descripcion).
-- =============================================================================

create or replace table r_hallazgos as
with base as (
    select count(*)                                            as pedidos,
           count(*) filter (where entregado)                   as entregados,
           count(*) filter (where entregado and dias_retraso > 0) as tarde,
           avg(dias_entrega) filter (where entregado)          as dias_entrega,
           avg(dias_prometidos) filter (where entregado)       as dias_prometidos,
           -- La fecha prometida siempre viene a las 00:00. Si se comparan horas, todo
           -- lo que llega el mismo día prometido cuenta como tarde (así lo hacen muchos
           -- análisis de Olist). Yo comparo días; esta cifra es para explicar la diferencia.
           count(*) filter (where entregado and fecha_entrega_cliente > fecha_prometida) as tarde_por_hora
    from pedidos
),
rj as (
    select round(100.0 * pedidos_entregados / sum(pedidos_entregados) over (), 1) as pct_entregas,
           pct_de_todos_los_retrasos as pct_retrasos, estado
    from r_entrega_por_estado
),
recompra as (
    select round(100.0 * count(*) filter (where n > 1) / count(*), 1) as pct
    from (select cliente_id, count(distinct fecha_compra::date) as n from compras_validas group by 1)
),
filas(orden, clave, valor, decimales, descripcion) as (
    select 1,  'pedidos_total',          pedidos::double, 0, 'Pedidos en los datos' from base union all
    select 2,  'pedidos_entregados',     entregados, 0, 'Pedidos entregados con fecha' from base union all
    select 3,  'pedidos_tarde',          tarde, 0, 'Entregados después de la fecha prometida' from base union all
    select 4,  'pct_tarde',              round(100.0 * tarde / entregados, 1), 1, '% de entregas tarde' from base union all
    select 33, 'ruta_sp_rj_pct_tarde', pct_tarde, 1, '% tarde en la ruta São Paulo -> Rio de Janeiro (pedidos de un vendedor)'
           from r_rutas where ruta = 'SP -> RJ' union all
    select 34, 'ruta_sp_rj_pedidos', pedidos, 0, 'Pedidos de SP -> RJ, la segunda ruta con más pedidos'
           from r_rutas where ruta = 'SP -> RJ' union all
    select 35, 'ruta_sp_sp_pct_tarde', pct_tarde, 1, '% tarde en la ruta São Paulo -> São Paulo, la de más pedidos'
           from r_rutas where ruta = 'SP -> SP' union all
    select 27, 'pct_tarde_contando_mismo_dia', round(100.0 * tarde_por_hora / entregados, 1), 1,
               '% tarde si también cuenta lo que llega el mismo día prometido' from base union all
    select 5,  'dias_entrega_prom',      round(dias_entrega, 1), 1, 'Días promedio de la compra a la entrega' from base union all
    select 6,  'dias_prometidos_prom',   round(dias_prometidos, 1), 1, 'Días promedio que promete Olist' from base union all
    select 7,  'pct_retrasos_vendedor_a_tiempo', pct_de_los_retrasos, 1,
               '% de los pedidos tarde en que el vendedor despachó a tiempo'
           from r_despacho where despacho = 'Vendedor despachó a tiempo' union all
    select 8,  'dias_transportadora_tarde', dias_transportadora, 1, 'Días en la transportadora, pedidos tarde'
           from r_etapas where resultado = 'Llegó tarde' union all
    select 9,  'dias_transportadora_a_tiempo', dias_transportadora, 1, 'Días en la transportadora, pedidos a tiempo'
           from r_etapas where resultado = 'A tiempo' union all
    select 10, 'tamano_pct_tarde_min', min(pct_tarde), 1, '% tarde del grupo de tamaño de vendedor que menos se atrasa'
           from r_retraso_por_tamano union all
    select 11, 'tamano_pct_tarde_max', max(pct_tarde), 1, '% tarde del grupo de tamaño de vendedor que más se atrasa'
           from r_retraso_por_tamano union all
    select 29, 'peores10_pct_tarde', pct_tarde, 1, '% tarde del 10 % de vendedores (30+ pedidos) con peor tasa'
           from r_peores_vendedores union all
    select 30, 'peores10_pct_retrasos', pct_de_los_retrasos, 1, '% de todos los retrasos que tiene ese 10 %'
           from r_peores_vendedores union all
    select 12, 'rj_pct_entregas', pct_entregas, 1, '% de las entregas que van a Rio de Janeiro' from rj where estado = 'RJ' union all
    select 13, 'rj_pct_retrasos', pct_retrasos, 1, '% de los retrasos que van a Rio de Janeiro' from rj where estado = 'RJ' union all
    select 14, 'nota_a_tiempo', nota_prom, 2, 'Nota promedio si llega a tiempo'
           from r_pendiente_nota where tramo = '1. A tiempo' union all
    select 15, 'puntos_por_dia_1_a_6', round(-puntos_por_dia, 2), 2, 'Puntos de nota que se pierden por cada día tarde (1 a 6 días)'
           from r_pendiente_nota where tramo = '2. De 1 a 6 días tarde' union all
    select 16, 'nota_7_dias_o_mas', nota_prom, 2, 'Nota promedio con 7 o más días de retraso'
           from r_pendiente_nota where tramo = '3. 7 o más días tarde' union all
    select 28, 'pct_respondio_antes_7_mas', pct_respondio_antes_de_recibir, 1,
               '% de reseñas con 7 o más días de retraso que el cliente respondió antes de recibir el paquete'
           from r_pendiente_nota where tramo = '3. 7 o más días tarde' union all
    select 31, 'nota_respondio_antes_1_a_6', nota_si_respondio_antes, 2,
               'Nota con 1 a 6 días de retraso si respondió antes de recibir'
           from r_pendiente_nota where tramo = '2. De 1 a 6 días tarde' union all
    select 32, 'nota_respondio_despues_1_a_6', nota_si_respondio_despues, 2,
               'Nota con 1 a 6 días de retraso si respondió después de recibir'
           from r_pendiente_nota where tramo = '2. De 1 a 6 días tarde' union all
    select 17, 'flete_pct_total', (select round(100.0 * sum(flete) / sum(precio), 1)
                                   from pedido_valor join pedidos using (pedido_id) where entregado), 1,
               'Flete como % del precio, todos los pedidos' union all
    select 18, 'pct_pedidos_menos_50', pct_pedidos, 1, '% de pedidos de menos de R$50'
           from r_flete_por_rango_precio where orden_rango = 1 union all
    select 19, 'flete_pct_menos_50', pct_ponderado, 1, 'Flete como % del precio en pedidos de menos de R$50'
           from r_flete_por_rango_precio where orden_rango = 1 union all
    select 20, 'pct_flete_mayor_menos_50', pct_flete_mayor_que_precio, 1, '% de esos pedidos donde el flete cuesta más que el producto'
           from r_flete_por_rango_precio where orden_rango = 1 union all
    select 21, 'pct_clientes_recompran', pct, 1, '% de clientes que compraron en más de un día' from recompra union all
    select 22, 'recompra_primera_a_tiempo', pct_volvio, 2, '% que volvió en 180 días si la primera entrega llegó a tiempo'
           from r_recompra_primera_entrega where grupo = 'Primera entrega a tiempo' union all
    select 23, 'recompra_primera_tarde', pct_volvio, 2, '% que volvió en 180 días si la primera entrega llegó tarde'
           from r_recompra_primera_entrega where grupo = 'Primera entrega tarde' union all
    select 24, 'z_recompra', z_diferencia, 2, 'Prueba z de la diferencia (desde 1,96 se descarta la casualidad al 95 %)'
           from r_recompra_primera_entrega where grupo = 'Primera entrega tarde' union all
    select 25, 'rfm_ticket_alto_pct_clientes', pct_clientes, 1, '% de clientes: una sola compra, de ticket alto (40 % que más gasta), hace más de 6 meses'
           from r_rfm_segmentos where segmento = '5. Ticket alto que no volvió' union all
    select 26, 'rfm_ticket_alto_pct_monto', pct_monto, 1, '% del dinero que dejaron esos clientes'
           from r_rfm_segmentos where segmento = '5. Ticket alto que no volvió'
)
select orden, clave, valor, decimales, descripcion from filas order by orden;
