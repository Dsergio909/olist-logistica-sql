-- =============================================================================
-- 04_flete.sql · ¿Cuánto pesa el flete frente al precio?
-- flete_pct = flete / precio de los productos del pedido.
-- Doy dos cifras porque cuentan cosas distintas:
--   pct_ponderado  = suma de fletes / suma de precios (lo que pesa en la plata total).
--   pct_mediana    = el pedido típico (la mitad paga más, la mitad menos).
-- Solo pedidos entregados, como el resto del análisis (con todos da lo mismo
-- en el primer decimal, salvo 10,2 % contra 10,1 %).
-- Resultados: r_flete_por_rango_precio y r_flete_por_categoria.
-- =============================================================================

create or replace table r_flete_por_rango_precio as
with rangos as (
    select *,
           case when precio < 50  then 1
                when precio < 100 then 2
                when precio < 200 then 3
                when precio < 500 then 4
                else 5 end as orden_rango
    from pedido_valor
    join pedidos using (pedido_id)
    where entregado            -- mismo universo que el resto del análisis
)
select orden_rango,
       case orden_rango when 1 then 'Menos de R$50'  when 2 then 'R$50 a R$99'
                        when 3 then 'R$100 a R$199'  when 4 then 'R$200 a R$499'
                        else 'R$500 o más' end                   as rango_precio,
       count(*)                                                    as pedidos,
       round(100.0 * count(*) / sum(count(*)) over (), 1)          as pct_pedidos,
       round(median(flete), 2)                                     as flete_mediana,
       round(100.0 * sum(flete) / sum(precio), 1)                  as pct_ponderado,
       round(100.0 * median(flete / precio), 1)                    as pct_mediana,
       round(100.0 * count(*) filter (where flete >= precio) / count(*), 1) as pct_flete_mayor_que_precio
from rangos
group by 1
order by 1;

-- Por categoría (las 15 con más pedidos). Un pedido con varias categorías
-- cuenta en cada una con sus propios productos.
create or replace table r_flete_por_categoria as
with por_categoria as (
    select pr.categoria,
           count(distinct i.order_id)                    as pedidos,
           sum(i.price)                                  as precio,
           sum(i.freight_value)                          as flete,
           median(pr.peso_g)                             as peso_mediana_g   -- por ítem vendido
    from items_crudos i
    join productos pr on pr.producto_id = i.product_id
    join pedidos p on p.pedido_id = i.order_id
    where p.entregado and pr.categoria <> 'sin_categoria'
    group by 1
)
select categoria,
       pedidos,
       round(100.0 * flete / precio, 1) as pct_ponderado,
       round(peso_mediana_g)            as peso_mediana_g,
       -- Puesto entre todas las categorías con nombre (se calcula antes de quedarme
       -- con las 15 con más pedidos).
       rank() over (order by flete / precio desc) as puesto_entre_todas
from por_categoria
qualify row_number() over (order by pedidos desc, categoria) <= 15
order by pct_ponderado desc, categoria;
