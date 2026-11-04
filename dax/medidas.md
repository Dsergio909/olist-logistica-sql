# Medidas DAX del tablero

Este archivo lo genera `powerbi/generar_pbip.py` con las mismas fórmulas que van en el modelo, así se pueden leer sin abrir Power BI. Todas viven en la tabla `Medidas`.

Reglas que seguí:
- Toda división con `DIVIDE`, para que no salga error cuando el denominador es cero.
- Los filtros de verdadero o falso se escriben completos (`= TRUE ()`).
- Para contar notas de 1 o 2 uso `IN { 1, 2 }`: en DAX una nota vacía cuenta como menor que 2.

## Logística

### Pedidos (todos)
Todos los pedidos, en cualquier estado.

```dax
Pedidos (todos) =
COUNTROWS ( Pedidos )
```
Formato: `#,0`

### Pedidos entregados
Pedidos con estado delivered y fecha de entrega. Es la base de los tiempos.

```dax
Pedidos entregados =
CALCULATE ( COUNTROWS ( Pedidos ), Pedidos[entregado] = TRUE () )
```
Formato: `#,0`

### Pedidos tarde
Entregados después del día prometido.

```dax
Pedidos tarde =
CALCULATE ( COUNTROWS ( Pedidos ), Pedidos[tarde] = TRUE () )
```
Formato: `#,0`

### % tarde
Parte de las entregas que llegó tarde.

```dax
% tarde =
DIVIDE ( [Pedidos tarde], [Pedidos entregados] )
```
Formato: `0.0%`

### % tarde (meses completos)
Igual, pero solo de ene-2017 a ago-2018 (los meses con datos completos), para la línea de tiempo.

```dax
% tarde (meses completos) =
CALCULATE ( [% tarde], Pedidos[mes_completo] = TRUE () )
```
Formato: `0.0%`

### Días de entrega
Días promedio de la compra a la entrega.

```dax
Días de entrega =
CALCULATE ( AVERAGE ( Pedidos[dias_entrega] ), Pedidos[entregado] = TRUE () )
```
Formato: `0.0`

### Días prometidos
Días promedio que la tienda prometió al comprar.

```dax
Días prometidos =
CALCULATE ( AVERAGE ( Pedidos[dias_prometidos] ), Pedidos[entregado] = TRUE () )
```
Formato: `0.0`

### Colchón (días)
Cuántos días antes de lo prometido llega, en promedio.

```dax
Colchón (días) =
[Días prometidos] - [Días de entrega]
```
Formato: `0.0`

### Aprobar el pago (días)
De la compra a la aprobación del pago.

```dax
Aprobar el pago (días) =
AVERAGE ( Pedidos[dias_aprobacion] )
```
Formato: `0.0`

### Vendedor despacha (días)
De la aprobación a la entrega a la transportadora.

```dax
Vendedor despacha (días) =
AVERAGE ( Pedidos[dias_vendedor] )
```
Formato: `0.0`

### Transportadora (días)
De la transportadora a la puerta del cliente.

```dax
Transportadora (días) =
AVERAGE ( Pedidos[dias_transportadora] )
```
Formato: `0.0`

### Latitud
Para el mapa de burbujas (eje Y).

```dax
Latitud =
AVERAGE ( Estados[lat] )
```
Formato: `0.00`

### Longitud
Para el mapa de burbujas (eje X).

```dax
Longitud =
AVERAGE ( Estados[lng] )
```
Formato: `0.00`

## Vendedores

### Vendedores con ventas
Vendedores con al menos un pedido.

```dax
Vendedores con ventas =
DISTINCTCOUNT ( PedidoVendedor[vendedor_id] )
```
Formato: `#,0`

### Pedidos de vendedor entregados
Unidad: lo que despachó un vendedor en un pedido.

```dax
Pedidos de vendedor entregados =
CALCULATE ( COUNTROWS ( PedidoVendedor ), PedidoVendedor[entregado] = TRUE () )
```
Formato: `#,0`

### Pedidos de vendedor tarde

```dax
Pedidos de vendedor tarde =
CALCULATE ( COUNTROWS ( PedidoVendedor ), PedidoVendedor[tarde] = TRUE () )
```
Formato: `#,0`

### % tarde (vendedor)

```dax
% tarde (vendedor) =
DIVIDE ( [Pedidos de vendedor tarde], [Pedidos de vendedor entregados] )
```
Formato: `0.0%`

### % despacho tarde
El vendedor entregó a la transportadora después de su fecha límite.

```dax
% despacho tarde =
DIVIDE (
    CALCULATE ( [Pedidos de vendedor entregados], PedidoVendedor[despacho] = "Tarde" ),
    [Pedidos de vendedor entregados]
)
```
Formato: `0.0%`

### % de los retrasos con despacho a tiempo
De los pedidos que llegaron tarde (de un solo vendedor), en cuántos el vendedor sí despachó a tiempo.

```dax
% de los retrasos con despacho a tiempo =
VAR TardeConDato =
    CALCULATE ( [Pedidos de vendedor tarde], PedidoVendedor[vendedores_del_pedido] = 1, PedidoVendedor[despacho] <> "Sin dato" )
VAR TardeDespachoATiempo =
    CALCULATE ( [Pedidos de vendedor tarde], PedidoVendedor[vendedores_del_pedido] = 1, PedidoVendedor[despacho] = "A tiempo" )
RETURN
    DIVIDE ( TardeDespachoATiempo, TardeConDato )
```
Formato: `0.0%`

### Nota (vendedor)

```dax
Nota (vendedor) =
CALCULATE ( AVERAGE ( PedidoVendedor[nota] ), PedidoVendedor[entregado] = TRUE () )
```
Formato: `0.00`

## Clientes

### Clientes
Personas distintas (customer_unique_id) con compras válidas.

```dax
Clientes =
COUNTROWS ( RFM )
```
Formato: `#,0`

### % clientes

```dax
% clientes =
DIVIDE ( [Clientes], CALCULATE ( [Clientes], ALL ( RFM ) ) )
```
Formato: `0.0%`

### Monto
Total pagado, en reales.

```dax
Monto =
SUM ( RFM[monto] )
```
Formato: `#,0`

### % del dinero

```dax
% del dinero =
DIVIDE ( [Monto], CALCULATE ( [Monto], ALL ( RFM ) ) )
```
Formato: `0.0%`

### % que vuelve a comprar
Clientes con más de un pedido.

```dax
% que vuelve a comprar =
DIVIDE ( CALCULATE ( [Clientes], RFM[frecuencia] > 1 ), [Clientes] )
```
Formato: `0.0%`

### Gasto por pedido (R$)

```dax
Gasto por pedido (R$) =
DIVIDE ( [Monto], SUM ( RFM[frecuencia] ) )
```
Formato: `#,0.00`

### Flete % del precio
Suma de fletes sobre suma de precios.

```dax
Flete % del precio =
DIVIDE ( SUM ( Pedidos[flete] ), SUM ( Pedidos[precio] ) )
```
Formato: `0.0%`

### % volvió a comprar
Del resultado SQL: clientes que volvieron después de su primera compra.

```dax
% volvió a comprar =
DIVIDE ( SUM ( RecompraSQL[volvieron] ), SUM ( RecompraSQL[clientes] ) )
```
Formato: `0.00%`

## Reseñas

### Nota promedio
Nota de 1 a 5 de los pedidos entregados.

```dax
Nota promedio =
CALCULATE ( AVERAGE ( Pedidos[nota] ), Pedidos[entregado] = TRUE () )
```
Formato: `0.00`

### Nota promedio (meses completos)

```dax
Nota promedio (meses completos) =
CALCULATE ( [Nota promedio], Pedidos[mes_completo] = TRUE () )
```
Formato: `0.00`

### % notas de 1 o 2
Se usa IN { 1, 2 } y no <= 2, porque en DAX una nota vacía cuenta como menor que 2.

```dax
% notas de 1 o 2 =
DIVIDE (
    CALCULATE ( COUNTROWS ( Pedidos ), Pedidos[nota] IN { 1, 2 }, Pedidos[entregado] = TRUE () ),
    CALCULATE ( COUNT ( Pedidos[nota] ), Pedidos[entregado] = TRUE () )
)
```
Formato: `0.0%`

### Nota si llega a tiempo

```dax
Nota si llega a tiempo =
CALCULATE ( [Nota promedio], Pedidos[tarde] = FALSE () )
```
Formato: `0.00`

### Nota 1 a 6 días tarde

```dax
Nota 1 a 6 días tarde =
CALCULATE ( [Nota promedio], Pedidos[dias_retraso] >= 1, Pedidos[dias_retraso] <= 6 )
```
Formato: `0.00`

### Nota 7 o más días tarde

```dax
Nota 7 o más días tarde =
CALCULATE ( [Nota promedio], Pedidos[dias_retraso] >= 7 )
```
Formato: `0.00`
