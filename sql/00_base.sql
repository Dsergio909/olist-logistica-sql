-- =============================================================================
-- 00_base.sql · Tablas base limpias
-- Lee los Parquet de datos/ y deja vistas con nombres en español y las columnas
-- de tiempo ya calculadas. Todas las demás consultas parten de aquí.
--
-- Definiciones que usa todo el proyecto:
--   entregado     = estado 'delivered' y con fecha de entrega al cliente.
--   dias_entrega  = días (con decimales) entre la compra y la entrega.
--   dias_retraso  = días de calendario entre la fecha prometida y la real.
--                   Positivo = llegó tarde; 0 o negativo = a tiempo.
--   tarde         = dias_retraso > 0.
-- =============================================================================

create or replace view pedidos_crudos  as select * from read_parquet('datos/olist_orders_dataset.parquet');
create or replace view items_crudos    as select * from read_parquet('datos/olist_order_items_dataset.parquet');
create or replace view pagos_crudos    as select * from read_parquet('datos/olist_order_payments_dataset.parquet');
create or replace view resenas_crudas  as select * from read_parquet('datos/olist_order_reviews_dataset.parquet');
create or replace view clientes_crudos as select * from read_parquet('datos/olist_customers_dataset.parquet');
create or replace view vendedores      as
    select seller_id as vendedor_id, seller_zip_code_prefix as vendedor_cp,
           seller_city as vendedor_ciudad, seller_state as vendedor_estado
    from read_parquet('datos/olist_sellers_dataset.parquet');
create or replace view geo_cp as select * from read_parquet('datos/olist_geolocation_dataset.parquet');

-- Clientes: customer_id cambia en cada pedido; customer_unique_id es la persona.
create or replace view clientes as
select customer_id        as cliente_pedido_id,
       customer_unique_id as cliente_id,
       customer_zip_code_prefix as cliente_cp,
       customer_city      as cliente_ciudad,
       customer_state     as cliente_estado
from clientes_crudos;

-- Productos con la categoría en inglés (la tabla de traducción no cubre 2
-- categorías: se deja el nombre en portugués) y 'sin_categoria' si viene vacía.
create or replace view productos as
select p.product_id as producto_id,
       coalesce(t.product_category_name_english, p.product_category_name, 'sin_categoria') as categoria,
       p.product_weight_g as peso_g,
       p.product_length_cm * p.product_height_cm * p.product_width_cm as volumen_cm3
from read_parquet('datos/olist_products_dataset.parquet') p
left join read_parquet('datos/product_category_name_translation.parquet') t
       using (product_category_name);

-- Pedidos con sus tiempos.
create or replace table pedidos as
select o.order_id                      as pedido_id,
       c.cliente_id,
       c.cliente_estado,
       o.order_status                  as estado_pedido,
       o.order_purchase_timestamp      as fecha_compra,
       o.order_approved_at             as fecha_aprobacion,
       o.order_delivered_carrier_date  as fecha_entrega_transportadora,
       o.order_delivered_customer_date as fecha_entrega_cliente,
       o.order_estimated_delivery_date as fecha_prometida,
       date_trunc('month', o.order_purchase_timestamp)::date as mes_compra,
       (o.order_status = 'delivered' and o.order_delivered_customer_date is not null) as entregado,
       date_diff('second', o.order_purchase_timestamp, o.order_delivered_customer_date) / 86400.0 as dias_entrega,
       date_diff('second', o.order_purchase_timestamp, o.order_estimated_delivery_date) / 86400.0 as dias_prometidos,
       date_diff('day', o.order_estimated_delivery_date::date, o.order_delivered_customer_date::date) as dias_retraso
from pedidos_crudos o
join clientes c on c.cliente_pedido_id = o.customer_id;

-- Una sola reseña por pedido: hay pedidos con 2 o 3 reseñas; se queda la más
-- reciente (la última respuesta del cliente).
create or replace table resenas as
select pedido_id, nota, tiene_comentario, fecha_resena
from (
    select order_id as pedido_id, review_score as nota, tiene_comentario,
           review_creation_date as fecha_resena,
           row_number() over (partition by order_id
                              order by review_answer_timestamp desc, review_creation_date desc, review_id) as orden
    from resenas_crudas
)
where orden = 1;

-- Totales de dinero por pedido (precio de los productos y flete).
create or replace table pedido_valor as
select order_id as pedido_id,
       count(*)              as items,
       count(distinct seller_id) as vendedores,
       sum(price)            as precio,
       sum(freight_value)    as flete
from items_crudos
group by 1;

-- Pedido por vendedor: un pedido puede tener varios vendedores (cada uno despacha
-- lo suyo). shipping_limit_date es la fecha límite para entregar a la transportadora.
create or replace table pedido_vendedor as
select i.order_id as pedido_id,
       i.seller_id as vendedor_id,
       count(*) as items,
       sum(i.price) as precio,
       sum(i.freight_value) as flete,
       max(i.shipping_limit_date) as fecha_limite_despacho
from items_crudos i
group by 1, 2;
