-- =============================================================================
-- 01_calidad_datos.sql · ¿Se puede confiar en los datos?
-- Antes de sacar conclusiones, cuento lo raro: fechas al revés, pedidos sin
-- productos, reseñas repetidas y pagos que no cuadran con la factura.
-- Resultado: r_calidad_datos (una fila por chequeo).
-- =============================================================================

create or replace table r_calidad_datos as
with pagos_por_pedido as (
    select order_id as pedido_id, sum(payment_value) as pagado
    from pagos_crudos group by 1
),
chequeos as (
    select 1 as orden, 'Pedidos en total' as chequeo,
           count(*) as cantidad, 'Base de todo el análisis' as que_hago
    from pedidos
    union all
    select 2, 'Pedidos entregados con fecha de entrega',
           count(*) filter (where entregado), 'Son los que uso para medir tiempos'
    from pedidos
    union all
    select 3, 'Estado entregado pero sin fecha de entrega',
           count(*) filter (where estado_pedido = 'delivered' and fecha_entrega_cliente is null),
           'Se excluyen de los tiempos'
    from pedidos
    union all
    select 4, 'Entregado al cliente antes que a la transportadora',
           count(*) filter (where entregado and fecha_entrega_cliente < fecha_entrega_transportadora),
           'Se dejan: son pocos y no cambian los promedios'
    from pedidos
    union all
    select 5, 'Entregado a la transportadora antes de la compra',
           count(*) filter (where fecha_entrega_transportadora < fecha_compra),
           'Se dejan: error de registro de la fuente'
    from pedidos
    union all
    select 6, 'Pedidos sin ningún producto',
           count(*) filter (where v.pedido_id is null), 'Casi todos cancelados o no disponibles'
    from pedidos p left join pedido_valor v using (pedido_id)
    union all
    select 7, 'Pedidos con más de una reseña',
           (select count(*) from (select order_id from resenas_crudas group by 1 having count(*) > 1)),
           'Me quedo con la más reciente'
    union all
    select 8, 'Pedidos con pago distinto a precio + flete (más de R$1)',
           count(*) filter (where abs(g.pagado - (v.precio + v.flete)) > 1),
           'Intereses de cuotas y vales: no afecta la logística'
    from pedido_valor v join pagos_por_pedido g using (pedido_id)
    union all
    select 9, 'Productos sin categoría',
           count(*) filter (where categoria = 'sin_categoria'), 'Quedan como sin_categoria'
    from productos
)
select orden, chequeo, cantidad, que_hago from chequeos order by orden;
