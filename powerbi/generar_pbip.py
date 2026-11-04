"""Genera el tablero de Power BI como proyecto de texto (PBIP) y dax/medidas.md.

Uso (desde la carpeta del repo):
    python powerbi/generar_pbip.py

Por qué así: un .pbix es un archivo binario y en GitHub no se puede leer. El
formato PBIP guarda el modelo (TMDL), las consultas de Power Query (M) y cada
gráfico (JSON) como texto. Este script los escribe desde una sola fuente, así
las medidas del tablero y las de dax/medidas.md nunca quedan distintas.

Después: abrir powerbi/OlistLogistica.pbip en Power BI Desktop, cambiar el
parámetro CarpetaRepo si el repo está en otra carpeta, y pulsar Actualizar.
"""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PBI = RAIZ / "powerbi"
NOMBRE = "OlistLogistica"
MODELO = PBI / f"{NOMBRE}.SemanticModel"
INFORME = PBI / f"{NOMBRE}.Report"

# Carpeta del repo en el PC donde se arma el tablero. Quien lo descargue la
# cambia en Power BI: Transformar datos > Parámetros > CarpetaRepo.
CARPETA_REPO = "C:\\Trabajo\\olist-logistica-sql\\"

ACENTO = "#1d4a35"      # verde oscuro del portafolio: único color de acento
GRIS = "#8c959f"
TEXTO = "#1f2328"
TEXTO_SUAVE = "#57606a"
ROJO = "#b42318"        # solo para "tarde"

ESQUEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"


def guid(texto: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"olist-logistica/{texto}"))


# --------------------------------------------------------------------------
# 1. Power Query (M): de los Parquet del repo a tablas limpias
# --------------------------------------------------------------------------
def parquet(nombre: str) -> str:
    return f'Parquet.Document(File.Contents(CarpetaRepo & "datos\\{nombre}.parquet"))'


M = {}

M["Pedidos"] = f"""
let
    // Pedidos + cliente (customer_id cambia en cada pedido; customer_unique_id es la persona)
    Pedidos0 = {parquet("olist_orders_dataset")},
    Clientes = {parquet("olist_customers_dataset")},
    ConCliente = Table.NestedJoin(Pedidos0, {{"customer_id"}}, Clientes, {{"customer_id"}}, "c", JoinKind.LeftOuter),
    Cliente = Table.ExpandTableColumn(ConCliente, "c", {{"customer_unique_id", "customer_state"}}, {{"cliente_id", "estado_cliente"}}),
    Nombres = Table.RenameColumns(Cliente, {{
        {{"order_id", "pedido_id"}}, {{"order_status", "estado_pedido"}},
        {{"order_purchase_timestamp", "fecha_compra"}}, {{"order_approved_at", "fecha_aprobacion"}},
        {{"order_delivered_carrier_date", "fecha_transportadora"}},
        {{"order_delivered_customer_date", "fecha_entrega"}},
        {{"order_estimated_delivery_date", "fecha_prometida"}}}}),
    Tipos = Table.TransformColumnTypes(Nombres, {{
        {{"fecha_compra", type datetime}}, {{"fecha_aprobacion", type datetime}},
        {{"fecha_transportadora", type datetime}}, {{"fecha_entrega", type datetime}},
        {{"fecha_prometida", type datetime}}}}),
    // Entregado = estado delivered y con fecha de entrega (8 pedidos no la tienen)
    Entregado = Table.AddColumn(Tipos, "entregado", each [estado_pedido] = "delivered" and [fecha_entrega] <> null, type logical),
    DiasEntrega = Table.AddColumn(Entregado, "dias_entrega", each if [entregado] then Duration.TotalDays([fecha_entrega] - [fecha_compra]) else null, type number),
    DiasPrometidos = Table.AddColumn(DiasEntrega, "dias_prometidos", each if [entregado] then Duration.TotalDays([fecha_prometida] - [fecha_compra]) else null, type number),
    // Días de calendario entre lo prometido y lo real: positivo = tarde
    DiasRetraso = Table.AddColumn(DiasPrometidos, "dias_retraso", each if [entregado] then Duration.Days(DateTime.Date([fecha_entrega]) - DateTime.Date([fecha_prometida])) else null, Int64.Type),
    Tarde = Table.AddColumn(DiasRetraso, "tarde", each [dias_retraso] <> null and [dias_retraso] > 0, type logical),
    Resultado = Table.AddColumn(Tarde, "resultado", each if not [entregado] then null else if [tarde] then "Llegó tarde" else "A tiempo", type text),
    Tramo = Table.AddColumn(Resultado, "tramo_retraso", each if [dias_retraso] = null then null else List.Max({{-10, List.Min({{20, [dias_retraso]}})}}), Int64.Type),
    // Etapas: solo con las dos fechas de cada tramo
    ConEtapas = Table.AddColumn(Tramo, "con_etapas", each [entregado] and [fecha_aprobacion] <> null and [fecha_transportadora] <> null, type logical),
    Aprobar = Table.AddColumn(ConEtapas, "dias_aprobacion", each if [con_etapas] then Duration.TotalDays([fecha_aprobacion] - [fecha_compra]) else null, type number),
    Vendedor = Table.AddColumn(Aprobar, "dias_vendedor", each if [con_etapas] then Duration.TotalDays([fecha_transportadora] - [fecha_aprobacion]) else null, type number),
    Transporte = Table.AddColumn(Vendedor, "dias_transportadora", each if [con_etapas] then Duration.TotalDays([fecha_entrega] - [fecha_transportadora]) else null, type number),
    Dia = Table.AddColumn(Transporte, "fecha_compra_dia", each DateTime.Date([fecha_compra]), type date),
    MesCompleto = Table.AddColumn(Dia, "mes_completo", each [fecha_compra_dia] >= #date(2017, 1, 1) and [fecha_compra_dia] < #date(2018, 9, 1), type logical),
    // Reseñas: algunos pedidos tienen 2 o 3; me quedo con la más reciente
    Resenas0 = {parquet("olist_order_reviews_dataset")},
    ResenasOrden = Table.Buffer(Table.Sort(Resenas0, {{{{"order_id", Order.Ascending}}, {{"review_answer_timestamp", Order.Descending}}, {{"review_creation_date", Order.Descending}}, {{"review_id", Order.Ascending}}}})),
    ResenaUnica = Table.Distinct(ResenasOrden, {{"order_id"}}),
    ConResena = Table.NestedJoin(MesCompleto, {{"pedido_id"}}, ResenaUnica, {{"order_id"}}, "r", JoinKind.LeftOuter),
    Nota = Table.ExpandTableColumn(ConResena, "r", {{"review_score"}}, {{"nota"}}),
    // Precio y flete del pedido (suma de sus productos)
    Items0 = {parquet("olist_order_items_dataset")},
    PorPedido = Table.Group(Items0, {{"order_id"}}, {{
        {{"precio", each List.Sum([price]), type number}},
        {{"flete", each List.Sum([freight_value]), type number}},
        {{"vendedores", each List.Count(List.Distinct([seller_id])), Int64.Type}}}}),
    ConValor = Table.NestedJoin(Nota, {{"pedido_id"}}, PorPedido, {{"order_id"}}, "v", JoinKind.LeftOuter),
    Valor = Table.ExpandTableColumn(ConValor, "v", {{"precio", "flete", "vendedores"}}),
    Rango = Table.AddColumn(Valor, "orden_rango", each if [precio] = null then null else if [precio] < 50 then 1 else if [precio] < 100 then 2 else if [precio] < 200 then 3 else if [precio] < 500 then 4 else 5, Int64.Type),
    RangoTexto = Table.AddColumn(Rango, "rango_precio", each {{null, "Menos de R$50", "R$50 a R$99", "R$100 a R$199", "R$200 a R$499", "R$500 o más"}}{{if [orden_rango] = null then 0 else [orden_rango]}}, type text),
    Final = Table.SelectColumns(RangoTexto, {{"pedido_id", "cliente_id", "estado_cliente", "estado_pedido", "fecha_compra", "fecha_compra_dia",
        "entregado", "tarde", "resultado", "dias_entrega", "dias_prometidos", "dias_retraso", "tramo_retraso",
        "dias_aprobacion", "dias_vendedor", "dias_transportadora", "nota", "precio", "flete", "vendedores",
        "rango_precio", "orden_rango", "mes_completo"}}),
    TiposFinales = Table.TransformColumnTypes(Final, {{{{"nota", Int64.Type}}, {{"vendedores", Int64.Type}}}})
in
    TiposFinales
"""

M["PedidoVendedor"] = f"""
let
    // Unidad: lo que despachó un vendedor en un pedido
    Items0 = {parquet("olist_order_items_dataset")},
    Tipos0 = Table.TransformColumnTypes(Items0, {{{{"shipping_limit_date", type datetime}}}}),
    Grupo = Table.Group(Tipos0, {{"order_id", "seller_id"}}, {{
        {{"precio", each List.Sum([price]), type number}},
        {{"flete", each List.Sum([freight_value]), type number}},
        {{"fecha_limite", each List.Max([shipping_limit_date]), type datetime}}}}),
    Nombres = Table.RenameColumns(Grupo, {{{{"order_id", "pedido_id"}}, {{"seller_id", "vendedor_id"}}}}),
    // Datos del pedido (se recalculan aquí para no depender de otra consulta)
    Pedidos0 = {parquet("olist_orders_dataset")},
    Clientes = {parquet("olist_customers_dataset")},
    ConCliente = Table.NestedJoin(Pedidos0, {{"customer_id"}}, Clientes, {{"customer_id"}}, "c", JoinKind.LeftOuter),
    Cliente = Table.ExpandTableColumn(ConCliente, "c", {{"customer_state"}}, {{"estado_cliente"}}),
    TiposP = Table.TransformColumnTypes(Cliente, {{{{"order_purchase_timestamp", type datetime}}, {{"order_delivered_carrier_date", type datetime}},
        {{"order_delivered_customer_date", type datetime}}, {{"order_estimated_delivery_date", type datetime}}}}),
    ConPedido = Table.NestedJoin(Nombres, {{"pedido_id"}}, TiposP, {{"order_id"}}, "p", JoinKind.Inner),
    Pedido = Table.ExpandTableColumn(ConPedido, "p", {{"order_status", "order_purchase_timestamp", "order_delivered_carrier_date",
        "order_delivered_customer_date", "order_estimated_delivery_date", "estado_cliente"}},
        {{"estado_pedido", "fecha_compra", "fecha_transportadora", "fecha_entrega", "fecha_prometida", "estado_cliente"}}),
    Entregado = Table.AddColumn(Pedido, "entregado", each [estado_pedido] = "delivered" and [fecha_entrega] <> null, type logical),
    Tarde = Table.AddColumn(Entregado, "tarde", each [entregado] and Duration.Days(DateTime.Date([fecha_entrega]) - DateTime.Date([fecha_prometida])) > 0, type logical),
    DiasEntrega = Table.AddColumn(Tarde, "dias_entrega", each if [entregado] then Duration.TotalDays([fecha_entrega] - [fecha_compra]) else null, type number),
    Despacho = Table.AddColumn(DiasEntrega, "despacho", each if [fecha_transportadora] = null then "Sin dato" else if [fecha_transportadora] > [fecha_limite] then "Tarde" else "A tiempo", type text),
    // Cuántos vendedores tiene el pedido (para medir el despacho solo en pedidos de uno)
    Cuenta = Table.Group(Despacho, {{"pedido_id"}}, {{{{"vendedores_del_pedido", each Table.RowCount(_), Int64.Type}}}}),
    ConCuenta = Table.NestedJoin(Despacho, {{"pedido_id"}}, Cuenta, {{"pedido_id"}}, "n", JoinKind.LeftOuter),
    NVend = Table.ExpandTableColumn(ConCuenta, "n", {{"vendedores_del_pedido"}}),
    // Ruta: estado del vendedor -> estado del cliente
    Vendedores0 = {parquet("olist_sellers_dataset")},
    ConVendedor = Table.NestedJoin(NVend, {{"vendedor_id"}}, Vendedores0, {{"seller_id"}}, "s", JoinKind.LeftOuter),
    EstadoV = Table.ExpandTableColumn(ConVendedor, "s", {{"seller_state"}}, {{"estado_vendedor"}}),
    Ruta = Table.AddColumn(EstadoV, "ruta", each [estado_vendedor] & " → " & [estado_cliente], type text),
    // Nota del pedido (la reseña más reciente)
    Resenas0 = {parquet("olist_order_reviews_dataset")},
    ResenasOrden = Table.Buffer(Table.Sort(Resenas0, {{{{"order_id", Order.Ascending}}, {{"review_answer_timestamp", Order.Descending}}, {{"review_creation_date", Order.Descending}}, {{"review_id", Order.Ascending}}}})),
    ResenaUnica = Table.Distinct(ResenasOrden, {{"order_id"}}),
    ConResena = Table.NestedJoin(Ruta, {{"pedido_id"}}, ResenaUnica, {{"order_id"}}, "r", JoinKind.LeftOuter),
    Nota = Table.ExpandTableColumn(ConResena, "r", {{"review_score"}}, {{"nota"}}),
    Dia = Table.AddColumn(Nota, "fecha_compra_dia", each DateTime.Date([fecha_compra]), type date),
    Final = Table.SelectColumns(Dia, {{"pedido_id", "vendedor_id", "ruta", "estado_vendedor", "estado_cliente", "precio", "flete",
        "entregado", "tarde", "despacho", "vendedores_del_pedido", "nota", "dias_entrega", "fecha_compra_dia"}}),
    TiposFinales = Table.TransformColumnTypes(Final, {{{{"nota", Int64.Type}}, {{"vendedores_del_pedido", Int64.Type}}}})
in
    TiposFinales
"""

M["Vendedores"] = f"""
let
    Origen = {parquet("olist_sellers_dataset")},
    Nombres = Table.RenameColumns(Origen, {{{{"seller_id", "vendedor_id"}}, {{"seller_city", "ciudad_vendedor"}}, {{"seller_state", "estado_vendedor"}}}}),
    // Los id de Olist son anónimos y largos: muestro los 8 primeros caracteres
    Corto = Table.AddColumn(Nombres, "vendedor_corto", each Text.Start([vendedor_id], 8), type text),
    Ciudad = Table.TransformColumns(Corto, {{{{"ciudad_vendedor", Text.Proper, type text}}}}),
    Final = Table.SelectColumns(Ciudad, {{"vendedor_id", "vendedor_corto", "estado_vendedor", "ciudad_vendedor"}})
in
    Final
"""

ESTADOS_BR = [
    ("AC", "Acre", "Norte"), ("AL", "Alagoas", "Nordeste"), ("AM", "Amazonas", "Norte"),
    ("AP", "Amapá", "Norte"), ("BA", "Bahia", "Nordeste"), ("CE", "Ceará", "Nordeste"),
    ("DF", "Distrito Federal", "Centro-Oeste"), ("ES", "Espírito Santo", "Sudeste"),
    ("GO", "Goiás", "Centro-Oeste"), ("MA", "Maranhão", "Nordeste"), ("MG", "Minas Gerais", "Sudeste"),
    ("MS", "Mato Grosso do Sul", "Centro-Oeste"), ("MT", "Mato Grosso", "Centro-Oeste"),
    ("PA", "Pará", "Norte"), ("PB", "Paraíba", "Nordeste"), ("PE", "Pernambuco", "Nordeste"),
    ("PI", "Piauí", "Nordeste"), ("PR", "Paraná", "Sul"), ("RJ", "Rio de Janeiro", "Sudeste"),
    ("RN", "Rio Grande do Norte", "Nordeste"), ("RO", "Rondônia", "Norte"), ("RR", "Roraima", "Norte"),
    ("RS", "Rio Grande do Sul", "Sul"), ("SC", "Santa Catarina", "Sul"), ("SE", "Sergipe", "Nordeste"),
    ("SP", "São Paulo", "Sudeste"), ("TO", "Tocantins", "Norte"),
]
_filas = ",\n        ".join(f'{{"{c}", "{n}", "{r}"}}' for c, n, r in ESTADOS_BR)
M["Estados"] = f"""
let
    Lista = #table(type table [codigo = text, nombre = text, region = text], {{
        {_filas}}}),
    // Punto del mapa: mediana de las coordenadas de los códigos postales del estado
    Geo = {parquet("olist_geolocation_dataset")},
    Centro = Table.Group(Geo, {{"geolocation_state"}}, {{
        {{"lat", each List.Median([geolocation_lat]), type number}},
        {{"lng", each List.Median([geolocation_lng]), type number}}}}),
    ConCentro = Table.NestedJoin(Lista, {{"codigo"}}, Centro, {{"geolocation_state"}}, "g", JoinKind.LeftOuter),
    Final = Table.ExpandTableColumn(ConCentro, "g", {{"lat", "lng"}})
in
    Final
"""

M["Calendario"] = """
let
    Dias = List.Dates(#date(2016, 9, 1), Duration.Days(#date(2018, 12, 31) - #date(2016, 9, 1)) + 1, #duration(1, 0, 0, 0)),
    Tabla = Table.FromList(Dias, Splitter.SplitByNothing(), type table [Fecha = date]),
    Anio = Table.AddColumn(Tabla, "anio", each Date.Year([Fecha]), Int64.Type),
    InicioMes = Table.AddColumn(Anio, "inicio_mes", each Date.StartOfMonth([Fecha]), type date),
    NombresMes = {"ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"},
    Mes = Table.AddColumn(InicioMes, "mes", each NombresMes{Date.Month([Fecha]) - 1} & " " & Text.From(Date.Year([Fecha])), type text)
in
    Mes
"""

M["RFM"] = """
let
    // Sale del SQL (sql/07_rfm.sql): el mismo cálculo, sin repetirlo en Power Query
    Origen = Parquet.Document(File.Contents(CarpetaRepo & "salidas\\rfm_clientes.parquet")),
    Tipos = Table.TransformColumnTypes(Origen, {{"recencia_dias", Int64.Type}, {"frecuencia", Int64.Type}, {"monto", type number},
        {"r", Int64.Type}, {"f", Int64.Type}, {"m", Int64.Type}, {"segmento", type text}})
in
    Tipos
"""

M["RecompraSQL"] = """
let
    // Resultado de sql/06_cohortes_recompra.sql (la prueba z está en el CSV)
    Origen = Csv.Document(File.Contents(CarpetaRepo & "salidas\\r_recompra_primera_entrega.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars = true]),
    Tipos = Table.TransformColumnTypes(Encabezados, {{"grupo", type text}, {"clientes", Int64.Type}, {"volvieron", Int64.Type},
        {"pct_volvio", type number}, {"z_diferencia", type number}}, "en-US")
in
    Tipos
"""

M["Medidas"] = """
let
    Vacia = #table(type table [columna = text], {})
in
    Vacia
"""

# Columnas de cada tabla: (nombre, tipo, formato, oculta)
COLUMNAS = {
    "Pedidos": [
        ("pedido_id", "string", None, True), ("cliente_id", "string", None, True),
        ("estado_cliente", "string", None, False), ("estado_pedido", "string", None, False),
        ("fecha_compra", "dateTime", "dd/mm/yyyy hh:nn", False), ("fecha_compra_dia", "dateTime", "dd/mm/yyyy", True),
        ("entregado", "boolean", None, False), ("tarde", "boolean", None, False), ("resultado", "string", None, False),
        ("dias_entrega", "double", "0.0", False), ("dias_prometidos", "double", "0.0", False),
        ("dias_retraso", "int64", "0", False), ("tramo_retraso", "int64", "0", False),
        ("dias_aprobacion", "double", "0.0", False), ("dias_vendedor", "double", "0.0", False),
        ("dias_transportadora", "double", "0.0", False), ("nota", "int64", "0", False),
        ("precio", "double", "#,0.00", False), ("flete", "double", "#,0.00", False),
        ("vendedores", "int64", "0", False), ("rango_precio", "string", None, False),
        ("orden_rango", "int64", "0", True), ("mes_completo", "boolean", None, True),
    ],
    "PedidoVendedor": [
        ("pedido_id", "string", None, True), ("vendedor_id", "string", None, True), ("ruta", "string", None, False),
        ("estado_vendedor", "string", None, False), ("estado_cliente", "string", None, False),
        ("precio", "double", "#,0.00", False), ("flete", "double", "#,0.00", False),
        ("entregado", "boolean", None, False), ("tarde", "boolean", None, False), ("despacho", "string", None, False),
        ("vendedores_del_pedido", "int64", "0", False), ("nota", "int64", "0", False),
        ("dias_entrega", "double", "0.0", False), ("fecha_compra_dia", "dateTime", "dd/mm/yyyy", True),
    ],
    "Vendedores": [
        ("vendedor_id", "string", None, False), ("vendedor_corto", "string", None, False),
        ("estado_vendedor", "string", None, False), ("ciudad_vendedor", "string", None, False),
    ],
    "Estados": [
        ("codigo", "string", None, False), ("nombre", "string", None, False), ("region", "string", None, False),
        ("lat", "double", "0.0000", True), ("lng", "double", "0.0000", True),
    ],
    "Calendario": [
        ("Fecha", "dateTime", "dd/mm/yyyy", False), ("anio", "int64", "0", False),
        ("inicio_mes", "dateTime", "mmm yyyy", False), ("mes", "string", None, False),
    ],
    "RFM": [
        ("cliente_id", "string", None, True), ("recencia_dias", "int64", "0", False),
        ("frecuencia", "int64", "0", False), ("monto", "double", "#,0.00", False),
        ("r", "int64", "0", False), ("f", "int64", "0", False), ("m", "int64", "0", False),
        ("segmento", "string", None, False),
    ],
    "RecompraSQL": [
        ("grupo", "string", None, False), ("clientes", "int64", "#,0", False), ("volvieron", "int64", "#,0", False),
        ("pct_volvio", "double", "0.00", False), ("z_diferencia", "double", "0.00", False),
    ],
    "Medidas": [("columna", "string", None, True)],
}
ORDENAR_POR = {("Pedidos", "rango_precio"): "orden_rango", ("Calendario", "mes"): "inicio_mes"}
DESCRIPCION_TABLA = {
    "Pedidos": "Un pedido por fila, con sus tiempos, su nota y su valor. Limpieza en Power Query.",
    "PedidoVendedor": "Lo que despachó cada vendedor en cada pedido.",
    "Vendedores": "Vendedores de Olist (id anónimo).",
    "Estados": "Los 27 estados de Brasil con su región y el punto del mapa.",
    "Calendario": "Un día por fila, de sep-2016 a dic-2018.",
    "RFM": "Puntaje RFM por cliente, calculado en sql/07_rfm.sql.",
    "RecompraSQL": "Recompra según la primera entrega, calculada en sql/06_cohortes_recompra.sql.",
    "Medidas": "Todas las medidas DAX del tablero.",
}

RELACIONES = [
    ("Pedidos", "estado_cliente", "Estados", "codigo"),
    ("Pedidos", "fecha_compra_dia", "Calendario", "Fecha"),
    ("PedidoVendedor", "vendedor_id", "Vendedores", "vendedor_id"),
    ("PedidoVendedor", "fecha_compra_dia", "Calendario", "Fecha"),
]

# --------------------------------------------------------------------------
# 2. Medidas DAX: (carpeta, nombre, fórmula, formato, explicación)
# --------------------------------------------------------------------------
MEDIDAS = [
    # Logística
    ("Logística", "Pedidos (todos)", "COUNTROWS ( Pedidos )", "#,0", "Todos los pedidos, en cualquier estado."),
    ("Logística", "Pedidos entregados", "CALCULATE ( COUNTROWS ( Pedidos ), Pedidos[entregado] = TRUE () )", "#,0",
     "Pedidos con estado delivered y fecha de entrega. Es la base de los tiempos."),
    ("Logística", "Pedidos tarde", "CALCULATE ( COUNTROWS ( Pedidos ), Pedidos[tarde] = TRUE () )", "#,0",
     "Entregados después del día prometido."),
    ("Logística", "% tarde", "DIVIDE ( [Pedidos tarde], [Pedidos entregados] )", "0.0%",
     "Parte de las entregas que llegó tarde."),
    ("Logística", "% tarde (meses completos)", "CALCULATE ( [% tarde], Pedidos[mes_completo] = TRUE () )", "0.0%",
     "Igual, pero solo de ene-2017 a ago-2018 (los meses con datos completos), para la línea de tiempo."),
    ("Logística", "Días de entrega", "CALCULATE ( AVERAGE ( Pedidos[dias_entrega] ), Pedidos[entregado] = TRUE () )", "0.0",
     "Días promedio de la compra a la entrega."),
    ("Logística", "Días prometidos", "CALCULATE ( AVERAGE ( Pedidos[dias_prometidos] ), Pedidos[entregado] = TRUE () )", "0.0",
     "Días promedio que la tienda prometió al comprar."),
    ("Logística", "Colchón (días)", "[Días prometidos] - [Días de entrega]", "0.0",
     "Cuántos días antes de lo prometido llega, en promedio."),
    ("Logística", "Aprobar el pago (días)", "AVERAGE ( Pedidos[dias_aprobacion] )", "0.0",
     "De la compra a la aprobación del pago."),
    ("Logística", "Vendedor despacha (días)", "AVERAGE ( Pedidos[dias_vendedor] )", "0.0",
     "De la aprobación a la entrega a la transportadora."),
    ("Logística", "Transportadora (días)", "AVERAGE ( Pedidos[dias_transportadora] )", "0.0",
     "De la transportadora a la puerta del cliente."),
    ("Logística", "Latitud", "AVERAGE ( Estados[lat] )", "0.00", "Para el mapa de burbujas (eje Y)."),
    ("Logística", "Longitud", "AVERAGE ( Estados[lng] )", "0.00", "Para el mapa de burbujas (eje X)."),
    # Vendedores
    ("Vendedores", "Vendedores con ventas", "DISTINCTCOUNT ( PedidoVendedor[vendedor_id] )", "#,0",
     "Vendedores con al menos un pedido."),
    ("Vendedores", "Pedidos de vendedor entregados",
     "CALCULATE ( COUNTROWS ( PedidoVendedor ), PedidoVendedor[entregado] = TRUE () )", "#,0",
     "Unidad: lo que despachó un vendedor en un pedido."),
    ("Vendedores", "Pedidos de vendedor tarde",
     "CALCULATE ( COUNTROWS ( PedidoVendedor ), PedidoVendedor[tarde] = TRUE () )", "#,0", ""),
    ("Vendedores", "% tarde (vendedor)", "DIVIDE ( [Pedidos de vendedor tarde], [Pedidos de vendedor entregados] )",
     "0.0%", ""),
    ("Vendedores", "% despacho tarde",
     "DIVIDE (\n    CALCULATE ( [Pedidos de vendedor entregados], PedidoVendedor[despacho] = \"Tarde\" ),\n"
     "    [Pedidos de vendedor entregados]\n)", "0.0%",
     "El vendedor entregó a la transportadora después de su fecha límite."),
    ("Vendedores", "% de los retrasos con despacho a tiempo",
     "VAR UnVendedor = PedidoVendedor[vendedores_del_pedido] = 1\n"
     "VAR TardeConDato =\n    CALCULATE ( [Pedidos de vendedor tarde], PedidoVendedor[vendedores_del_pedido] = 1, PedidoVendedor[despacho] <> \"Sin dato\" )\n"
     "VAR TardeDespachoATiempo =\n    CALCULATE ( [Pedidos de vendedor tarde], PedidoVendedor[vendedores_del_pedido] = 1, PedidoVendedor[despacho] = \"A tiempo\" )\n"
     "RETURN\n    DIVIDE ( TardeDespachoATiempo, TardeConDato )", "0.0%",
     "De los pedidos que llegaron tarde (de un solo vendedor), en cuántos el vendedor sí despachó a tiempo."),
    ("Vendedores", "Nota (vendedor)",
     "CALCULATE ( AVERAGE ( PedidoVendedor[nota] ), PedidoVendedor[entregado] = TRUE () )", "0.00", ""),
    # Clientes
    ("Clientes", "Clientes", "COUNTROWS ( RFM )", "#,0", "Personas distintas (customer_unique_id) con compras válidas."),
    ("Clientes", "% clientes", "DIVIDE ( [Clientes], CALCULATE ( [Clientes], ALL ( RFM ) ) )", "0.0%", ""),
    ("Clientes", "Monto", "SUM ( RFM[monto] )", "#,0", "Total pagado, en reales."),
    ("Clientes", "% del dinero", "DIVIDE ( [Monto], CALCULATE ( [Monto], ALL ( RFM ) ) )", "0.0%", ""),
    ("Clientes", "% que vuelve a comprar", "DIVIDE ( CALCULATE ( [Clientes], RFM[frecuencia] > 1 ), [Clientes] )", "0.0%",
     "Clientes con más de un pedido."),
    ("Clientes", "Gasto por pedido (R$)", "DIVIDE ( [Monto], SUM ( RFM[frecuencia] ) )", "#,0.00", ""),
    ("Clientes", "Flete % del precio", "DIVIDE ( SUM ( Pedidos[flete] ), SUM ( Pedidos[precio] ) )", "0.0%",
     "Suma de fletes sobre suma de precios."),
    ("Clientes", "% volvió a comprar", "DIVIDE ( SUM ( RecompraSQL[volvieron] ), SUM ( RecompraSQL[clientes] ) )", "0.00%",
     "Del resultado SQL: clientes que volvieron después de su primera compra."),
    # Reseñas
    ("Reseñas", "Nota promedio", "CALCULATE ( AVERAGE ( Pedidos[nota] ), Pedidos[entregado] = TRUE () )", "0.00",
     "Nota de 1 a 5 de los pedidos entregados."),
    ("Reseñas", "Nota promedio (meses completos)", "CALCULATE ( [Nota promedio], Pedidos[mes_completo] = TRUE () )", "0.00", ""),
    ("Reseñas", "% notas de 1 o 2",
     "DIVIDE (\n    CALCULATE ( COUNTROWS ( Pedidos ), Pedidos[nota] IN { 1, 2 }, Pedidos[entregado] = TRUE () ),\n"
     "    CALCULATE ( COUNT ( Pedidos[nota] ), Pedidos[entregado] = TRUE () )\n)", "0.0%",
     "Se usa IN { 1, 2 } y no <= 2, porque en DAX una nota vacía cuenta como menor que 2."),
    ("Reseñas", "Nota si llega a tiempo", "CALCULATE ( [Nota promedio], Pedidos[tarde] = FALSE () )", "0.00", ""),
    ("Reseñas", "Nota 1 a 6 días tarde",
     "CALCULATE ( [Nota promedio], Pedidos[dias_retraso] >= 1, Pedidos[dias_retraso] <= 6 )", "0.00", ""),
    ("Reseñas", "Nota 7 o más días tarde", "CALCULATE ( [Nota promedio], Pedidos[dias_retraso] >= 7 )", "0.00", ""),
]
# La VAR UnVendedor no se usa: la quito para que la fórmula quede limpia.
MEDIDAS = [(c, n, f.replace("VAR UnVendedor = PedidoVendedor[vendedores_del_pedido] = 1\n", ""), fo, e)
           for c, n, f, fo, e in MEDIDAS]


# --------------------------------------------------------------------------
# 3. Escribir el modelo (TMDL)
# --------------------------------------------------------------------------
def nombre_tmdl(n: str) -> str:
    return n if n.replace("_", "").isalnum() and n.isascii() else "'" + n.replace("'", "''") + "'"


def sangrar(texto: str, tabs: int) -> str:
    pre = "\t" * tabs
    return "\n".join(pre + linea if linea.strip() else "" for linea in texto.strip("\n").splitlines())


def escribir_modelo() -> None:
    if MODELO.exists():
        shutil.rmtree(MODELO)
    (MODELO / "definition" / "tables").mkdir(parents=True)
    (MODELO / "definition.pbism").write_text(json.dumps(
        {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
         "version": "4.2", "settings": {}}, indent=2) + "\n", encoding="utf-8")
    d = MODELO / "definition"
    (d / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1600\n", encoding="utf-8")
    tablas = list(COLUMNAS)
    modelo = ["model Model", "\tculture: es-CO", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
              "\tsourceQueryCulture: es-CO", "\tdataAccessOptions", "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull", "",
              "annotation PBI_QueryOrder = " + json.dumps(["CarpetaRepo"] + tablas), "",
              "annotation __PBI_TimeIntelligenceEnabled = 0", ""]
    modelo += [f"ref table {nombre_tmdl(t)}" for t in tablas]
    (d / "model.tmdl").write_text("\n".join(modelo) + "\n", encoding="utf-8")
    (d / "expressions.tmdl").write_text(
        f'expression CarpetaRepo = "{CARPETA_REPO}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
        f"\tlineageTag: {guid('param')}\n\n\tannotation PBI_ResultType = Text\n", encoding="utf-8")
    rel = []
    for desde_t, desde_c, hacia_t, hacia_c in RELACIONES:
        rel += [f"relationship {guid(desde_t + desde_c + hacia_t)}",
                f"\tfromColumn: {nombre_tmdl(desde_t)}.{nombre_tmdl(desde_c)}",
                f"\ttoColumn: {nombre_tmdl(hacia_t)}.{nombre_tmdl(hacia_c)}", ""]
    (d / "relationships.tmdl").write_text("\n".join(rel), encoding="utf-8")

    for tabla, columnas in COLUMNAS.items():
        out = [f"/// {DESCRIPCION_TABLA[tabla]}", f"table {nombre_tmdl(tabla)}", f"\tlineageTag: {guid(tabla)}", ""]
        if tabla == "Medidas":
            for carpeta, nombre, formula, formato, explicacion in MEDIDAS:
                if explicacion:
                    out.append(f"\t/// {explicacion}")
                if "\n" in formula:
                    out.append(f"\tmeasure {nombre_tmdl(nombre)} =")
                    out.append(sangrar(formula, 3))
                else:
                    out.append(f"\tmeasure {nombre_tmdl(nombre)} = {formula}")
                out += [f"\t\tformatString: {formato}", f"\t\tdisplayFolder: {carpeta}",
                        f"\t\tlineageTag: {guid('m' + nombre)}", ""]
        for col, tipo, formato, oculta in columnas:
            out.append(f"\tcolumn {nombre_tmdl(col)}")
            out.append(f"\t\tdataType: {tipo}")
            if formato:
                out.append(f"\t\tformatString: {formato}")
            if oculta:
                out.append("\t\tisHidden")
            out.append(f"\t\tlineageTag: {guid(tabla + col)}")
            out.append("\t\tsummarizeBy: none")
            out.append(f"\t\tsourceColumn: {col}")
            orden = ORDENAR_POR.get((tabla, col))
            if orden:
                out.append(f"\t\tsortByColumn: {orden}")
            out += ["", "\t\tannotation SummarizationSetBy = Automatic", ""]
        out += [f"\tpartition {nombre_tmdl(tabla)} = m", "\t\tmode: import", "\t\tsource =", sangrar(M[tabla], 4), ""]
        (d / "tables" / f"{tabla}.tmdl").write_text("\n".join(out) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# 4. Escribir el informe (PBIR): páginas y gráficos
# --------------------------------------------------------------------------
def lit(valor) -> dict:
    if isinstance(valor, bool):
        v = "true" if valor else "false"
    elif isinstance(valor, (int, float)):
        v = f"{valor}D"
    else:
        v = "'" + str(valor).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": v}}}


def color(hexa: str) -> dict:
    return {"solid": {"color": lit(hexa)}}


def C(tabla: str, col: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": tabla}}, "Property": col}}


def Me(nombre: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": "Medidas"}}, "Property": nombre}}


def proy(campo) -> dict:
    """Campo del gráfico. Se puede pasar (campo, "Nombre visible") para renombrarlo."""
    nombre = None
    if isinstance(campo, tuple):
        campo, nombre = campo
    tipo = "Column" if "Column" in campo else "Measure"
    ent = campo[tipo]["Expression"]["SourceRef"]["Entity"]
    prop = campo[tipo]["Property"]
    salida = {"field": campo, "queryRef": f"{ent}.{prop}", "nativeQueryRef": prop}
    if nombre:
        salida["displayName"] = nombre
    return salida


def unir(base: dict, extra: dict) -> dict:
    """Une objetos de formato: si los dos tienen la misma clave, junta sus propiedades."""
    salida = {k: [dict(v[0], properties=dict(v[0]["properties"]))] + v[1:] for k, v in base.items()}
    for clave, valor in extra.items():
        if clave in salida and len(valor) == 1 and "selector" not in valor[0] and "selector" not in salida[clave][0]:
            salida[clave][0]["properties"].update(valor[0]["properties"])
        else:
            salida[clave] = valor
    return salida


class Pagina:
    def __init__(self, nombre: str, titulo: str, subtitulo: str):
        self.nombre, self.titulo, self.subtitulo = nombre, titulo, subtitulo
        self.visuales: list[dict] = []
        self.texto(titulo, subtitulo, 24, 12, 1232, 64)
        self.texto_pie()

    def _base(self, x, y, w, h) -> tuple[str, dict]:
        n = f"v{len(self.visuales):02d}{guid(self.nombre + str(len(self.visuales)))[:8]}"
        return n, {"x": x, "y": y, "z": len(self.visuales) * 1000, "width": w, "height": h,
                   "tabOrder": len(self.visuales) * 1000}

    def texto(self, titulo, subtitulo, x, y, w, h):
        n, pos = self._base(x, y, w, h)
        parrafos = [{"textRuns": [{"value": titulo, "textStyle": {"fontFamily": "Segoe UI Semibold", "fontSize": "18pt",
                                                                     "color": TEXTO}}]}]
        if subtitulo:
            parrafos.append({"textRuns": [{"value": subtitulo, "textStyle": {"fontFamily": "Segoe UI", "fontSize": "10pt",
                                                                             "color": TEXTO_SUAVE}}]})
        self.visuales.append({"name": n, "position": pos, "visual": {
            "visualType": "textbox",
            "objects": {"general": [{"properties": {"paragraphs": parrafos}}]},
            "drillFilterOtherVisuals": True}})

    def texto_pie(self):
        n, pos = self._base(24, 694, 1232, 22)
        self.visuales.append({"name": n, "position": pos, "visual": {
            "visualType": "textbox",
            "objects": {"general": [{"properties": {"paragraphs": [{"textRuns": [{
                "value": "Fuente: Olist, Brazilian E-Commerce Public Dataset (Kaggle), licencia CC BY-NC-SA 4.0. "
                         "Pedidos de sep-2016 a oct-2018. Tarde = llegó después del día prometido.",
                "textStyle": {"fontFamily": "Segoe UI", "fontSize": "8pt", "color": TEXTO_SUAVE}}]}]}}]},
            "drillFilterOtherVisuals": True}})

    def tarjetas(self, medidas: list[str], y=84, h=92):
        ancho = (1232 - 16 * (len(medidas) - 1)) / len(medidas)
        for i, m in enumerate(medidas):
            n, pos = self._base(round(24 + i * (ancho + 16)), y, round(ancho), h)
            self.visuales.append({"name": n, "position": pos, "visual": {
                "visualType": "card",
                "query": {"queryState": {"Values": {"projections": [proy(Me(m))]}}},
                "objects": {"labels": [{"properties": {"color": color(TEXTO), "fontSize": lit(26), "labelDisplayUnits": lit(1)}}],
                            "categoryLabels": [{"properties": {"color": color(TEXTO_SUAVE), "fontSize": lit(10)}}]},
                "visualContainerObjects": {
                    "background": [{"properties": {"show": lit(True), "color": color("#f6f8fa")}}],
                    "border": [{"properties": {"show": lit(True), "color": color("#d0d7de"), "radius": lit(4)}}]},
                "drillFilterOtherVisuals": True}})

    def grafico(self, tipo, x, y, w, h, titulo, roles: dict, orden=None, objetos=None, filtros=None):
        n, pos = self._base(x, y, w, h)
        query = {"queryState": {rol: {"projections": [proy(c) for c in campos]} for rol, campos in roles.items()}}
        if orden:
            campo, direccion = orden
            query["sortDefinition"] = {"sort": [{"field": campo, "direction": direccion}], "isDefaultSort": False}
        obj = {"labels": [{"properties": {"show": lit(True), "color": color(TEXTO_SUAVE), "fontSize": lit(8),
                                          "labelDisplayUnits": lit(1)}}]}
        if tipo != "tableEx":
            obj["categoryAxis"] = [{"properties": {"showAxisTitle": lit(False), "labelColor": color(TEXTO_SUAVE)}}]
            obj["valueAxis"] = [{"properties": {"showAxisTitle": lit(False), "labelColor": color(TEXTO_SUAVE)}}]
        if tipo not in ("tableEx", "scatterChart"):
            obj["dataPoint"] = [{"properties": {"fill": color(ACENTO)}}]
        obj = unir(obj, objetos or {})
        visual = {"visualType": tipo, "query": query, "objects": obj,
                  "visualContainerObjects": {"title": [{"properties": {
                      "show": lit(True), "text": lit(titulo), "fontColor": color(TEXTO), "fontSize": lit(11),
                      "fontFamily": lit("Segoe UI Semibold")}}]},
                  "drillFilterOtherVisuals": True}
        contenedor = {"name": n, "position": pos, "visual": visual}
        if filtros:
            contenedor["filterConfig"] = {"filters": filtros}
        self.visuales.append(contenedor)


def filtro_excluir(tabla: str, col: str, valor: str) -> dict:
    return {"name": guid(f"f{tabla}{col}{valor}")[:20].replace("-", ""), "field": C(tabla, col), "type": "Categorical",
            "filter": {"Version": 2, "From": [{"Name": "t", "Entity": tabla, "Type": 0}],
                       "Where": [{"Condition": {"Not": {"Expression": {"In": {
                           "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": col}}],
                           "Values": [[{"Literal": {"Value": f"'{valor}'"}}]]}}}}}]}}


SIN_EJES = {"categoryAxis": [{"properties": {"show": lit(False)}}],
            "valueAxis": [{"properties": {"show": lit(False), "gridlineShow": lit(False)}}]}
EJE_VALOR_OCULTO = {"valueAxis": [{"properties": {"show": lit(False), "gridlineShow": lit(False)}}]}


def paginas() -> list[Pagina]:
    p1 = Pagina("logistica", "¿Dónde se demoran las entregas?",
                "Entrega real contra la fecha que promete la tienda. Pedidos entregados de Olist (Brasil), 2016 a 2018.")
    p1.tarjetas(["Pedidos entregados", "% tarde", "Días de entrega", "Días prometidos"])
    p1.grafico("scatterChart", 24, 192, 392, 494, "Mapa: % de entregas tarde (burbuja = % tarde)",
               {"Category": [C("Estados", "codigo")], "X": [Me("Longitud")], "Y": [Me("Latitud")], "Size": [Me("% tarde")]},
               objetos={**SIN_EJES, "categoryLabels": [{"properties": {"show": lit(True), "color": color(TEXTO), "fontSize": lit(8)}}],
                        "dataPoint": [{"properties": {"fill": color(ACENTO)}}],
                        "bubbles": [{"properties": {"bubbleSize": lit(-20)}}]})
    p1.grafico("clusteredBarChart", 432, 192, 392, 494, "% de entregas tarde por estado del cliente",
               {"Category": [C("Estados", "codigo")], "Y": [Me("% tarde")]},
               orden=(Me("% tarde"), "Descending"), objetos=EJE_VALOR_OCULTO)
    p1.grafico("lineChart", 840, 192, 416, 239, "% de entregas tarde por mes de compra",
               {"Category": [C("Calendario", "inicio_mes")], "Y": [Me("% tarde (meses completos)")]},
               orden=(C("Calendario", "inicio_mes"), "Ascending"),
               objetos={"dataPoint": [{"properties": {"fill": color(ACENTO)}}],
                        "labels": [{"properties": {"show": lit(False)}}],
                        "categoryAxis": [{"properties": {"axisType": lit("Scalar")}}]})
    p1.grafico("barChart", 840, 447, 416, 239, "¿En qué etapa se va el tiempo? (días promedio)",
               {"Category": [C("Pedidos", "resultado")],
                "Y": [(Me("Aprobar el pago (días)"), "Aprobar pago"), (Me("Vendedor despacha (días)"), "Vendedor despacha"),
                      (Me("Transportadora (días)"), "Transportadora")]},
               objetos={**EJE_VALOR_OCULTO, "dataPoint": [
                   {"properties": {"fill": color("#c9d1d9")}, "selector": {"metadata": "Medidas.Aprobar el pago (días)"}},
                   {"properties": {"fill": color(GRIS)}, "selector": {"metadata": "Medidas.Vendedor despacha (días)"}},
                   {"properties": {"fill": color(ACENTO)}, "selector": {"metadata": "Medidas.Transportadora (días)"}}],
                   "legend": [{"properties": {"show": lit(True), "position": lit("Top")}}]})

    p2 = Pagina("vendedores", "¿Qué vendedores cumplen?",
                "Cada fila es lo que despachó un vendedor en un pedido. Despacho tarde = entregó a la transportadora después de su fecha límite.")
    p2.tarjetas(["Vendedores con ventas", "% despacho tarde", "% tarde (vendedor)", "% de los retrasos con despacho a tiempo"])
    p2.grafico("clusteredColumnChart", 24, 192, 360, 494, "% tarde según el despacho del vendedor",
               {"Category": [C("PedidoVendedor", "despacho")], "Y": [Me("% tarde (vendedor)")]},
               objetos=EJE_VALOR_OCULTO, filtros=[filtro_excluir("PedidoVendedor", "despacho", "Sin dato")])
    p2.grafico("tableEx", 400, 192, 480, 494, "Vendedores con más entregas tarde",
               {"Values": [(C("Vendedores", "vendedor_corto"), "Vendedor"), (C("Vendedores", "estado_vendedor"), "Estado"),
                           (Me("Pedidos de vendedor entregados"), "Entregados"), (Me("Pedidos de vendedor tarde"), "Tarde"),
                           (Me("% tarde (vendedor)"), "% tarde"), (Me("% despacho tarde"), "% despacho tarde"),
                           (Me("Nota (vendedor)"), "Nota")]},
               orden=(Me("Pedidos de vendedor tarde"), "Descending"))
    p2.grafico("clusteredBarChart", 896, 192, 360, 494, "Rutas con más entregas tarde (vendedor → cliente)",
               {"Category": [C("PedidoVendedor", "ruta")], "Y": [Me("Pedidos de vendedor tarde")]},
               orden=(Me("Pedidos de vendedor tarde"), "Descending"), objetos=EJE_VALOR_OCULTO)

    p3 = Pagina("clientes", "¿Los clientes vuelven? ¿Cuánto pesa el flete?",
                "Segmentos RFM (recencia, frecuencia y monto) calculados en SQL. Flete como % del precio de los productos del pedido.")
    p3.tarjetas(["Clientes", "% que vuelve a comprar", "Gasto por pedido (R$)", "Flete % del precio"])
    p3.grafico("clusteredBarChart", 24, 192, 600, 300, "Segmentos RFM: % de clientes y % del dinero",
               {"Category": [C("RFM", "segmento")], "Y": [Me("% clientes"), Me("% del dinero")]},
               orden=(C("RFM", "segmento"), "Ascending"),
               objetos={**EJE_VALOR_OCULTO, "dataPoint": [
                   {"properties": {"fill": color(GRIS)}, "selector": {"metadata": "Medidas.% clientes"}},
                   {"properties": {"fill": color(ACENTO)}, "selector": {"metadata": "Medidas.% del dinero"}}],
                   "legend": [{"properties": {"show": lit(True), "position": lit("Top")}}]})
    p3.grafico("clusteredColumnChart", 24, 508, 600, 178, "¿Vuelve a comprar? Según cómo llegó su primer pedido",
               {"Category": [C("RecompraSQL", "grupo")], "Y": [Me("% volvió a comprar")]}, objetos=EJE_VALOR_OCULTO)
    p3.grafico("clusteredColumnChart", 640, 192, 616, 494, "Flete como % del precio, según el valor del pedido",
               {"Category": [C("Pedidos", "rango_precio")], "Y": [Me("Flete % del precio")]},
               orden=(C("Pedidos", "rango_precio"), "Ascending"), objetos=EJE_VALOR_OCULTO)
    # Los 775 pedidos sin productos no tienen rango: la medida da vacío y no salen.

    p4 = Pagina("resenas", "¿Cuánto cuesta cada día de retraso en la nota?",
                "Nota de 1 a 5 que deja el cliente. Una reseña por pedido (la más reciente). Solo pedidos entregados.")
    p4.tarjetas(["Nota si llega a tiempo", "Nota 1 a 6 días tarde", "Nota 7 o más días tarde", "% notas de 1 o 2"])
    p4.grafico("clusteredColumnChart", 24, 192, 1232, 290,
               "Nota promedio según los días de retraso (negativo = llegó antes; -10 y 20 agrupan las puntas)",
               {"Category": [C("Pedidos", "tramo_retraso")], "Y": [Me("Nota promedio")]},
               orden=(C("Pedidos", "tramo_retraso"), "Ascending"),
               objetos={**EJE_VALOR_OCULTO, "categoryAxis": [{"properties": {"axisType": lit("Categorical")}}]})
    p4.grafico("lineChart", 24, 498, 608, 188, "Nota promedio por mes de compra",
               {"Category": [C("Calendario", "inicio_mes")], "Y": [Me("Nota promedio (meses completos)")]},
               orden=(C("Calendario", "inicio_mes"), "Ascending"),
               objetos={"labels": [{"properties": {"show": lit(False)}}],
                        "categoryAxis": [{"properties": {"axisType": lit("Scalar")}}]})
    p4.grafico("lineChart", 648, 498, 608, 188, "% de notas de 1 o 2 estrellas según los días de retraso",
               {"Category": [C("Pedidos", "tramo_retraso")], "Y": [Me("% notas de 1 o 2")]},
               orden=(C("Pedidos", "tramo_retraso"), "Ascending"),
               objetos={"labels": [{"properties": {"show": lit(False)}}],
                        "categoryAxis": [{"properties": {"axisType": lit("Scalar")}}]})
    return [p1, p2, p3, p4]


TEMA = {
    "name": "Olist sobrio",
    "dataColors": [ACENTO, GRIS, "#c9d1d9", "#4f6f5f", "#a5b5ac", ROJO, "#6e7781", "#2f5d47"],
    "background": "#FFFFFF", "foreground": TEXTO, "tableAccent": ACENTO,
    "good": ACENTO, "bad": ROJO, "neutral": GRIS,
    "textClasses": {
        "callout": {"fontSize": 26, "fontFace": "Segoe UI Semibold", "color": TEXTO},
        "title": {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": TEXTO},
        "header": {"fontSize": 10, "fontFace": "Segoe UI Semibold", "color": TEXTO},
        "label": {"fontSize": 9, "fontFace": "Segoe UI", "color": TEXTO_SUAVE},
    },
    "visualStyles": {"*": {"*": {
        "border": [{"show": False}],
        "dropShadow": [{"show": False}],
        "background": [{"show": True, "color": {"solid": {"color": "#FFFFFF"}}, "transparency": 0}],
    }}},
}


def escribir_informe() -> None:
    if INFORME.exists():
        shutil.rmtree(INFORME)
    d = INFORME / "definition"
    (d / "pages").mkdir(parents=True)
    base = INFORME / "StaticResources" / "SharedResources" / "BaseThemes"
    propio = INFORME / "StaticResources" / "RegisteredResources"
    base.mkdir(parents=True)
    propio.mkdir(parents=True)
    tema_base = PBI / "tema_base_CY24SU10.json"
    shutil.copy(tema_base, base / "CY24SU10.json")
    (propio / "TemaOlist.json").write_text(json.dumps(TEMA, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    (INFORME / "definition.pbir").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{NOMBRE}.SemanticModel"}}}, indent=2) + "\n",
        encoding="utf-8")
    (d / "version.json").write_text(json.dumps({
        "$schema": f"{ESQUEMA}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"}, indent=2) + "\n", encoding="utf-8")
    version_tema = {"visual": "1.8.0", "report": "2.0.0", "page": "1.3.0"}
    (d / "report.json").write_text(json.dumps({
        "$schema": f"{ESQUEMA}/report/3.0.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": "CY24SU10", "reportVersionAtImport": version_tema, "type": "SharedResources"},
            "customTheme": {"name": "TemaOlist.json", "reportVersionAtImport": version_tema, "type": "RegisteredResources"}},
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": "CY24SU10", "path": "BaseThemes/CY24SU10.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": "TemaOlist.json", "path": "TemaOlist.json", "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True,
                     "allowChangeFilterTypes": True, "useEnhancedTooltips": True}}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")

    lista = paginas()
    (d / "pages" / "pages.json").write_text(json.dumps({
        "$schema": f"{ESQUEMA}/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [p.nombre for p in lista], "activePageName": lista[0].nombre}, indent=2) + "\n", encoding="utf-8")
    nombres_pagina = {"logistica": "Logística", "vendedores": "Vendedores", "clientes": "Clientes", "resenas": "Reseñas"}
    for p in lista:
        carpeta = d / "pages" / p.nombre
        (carpeta / "visuals").mkdir(parents=True)
        (carpeta / "page.json").write_text(json.dumps({
            "$schema": f"{ESQUEMA}/page/2.0.0/schema.json", "name": p.nombre,
            "displayName": nombres_pagina[p.nombre], "displayOption": "FitToPage", "height": 720, "width": 1280},
            indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        for v in p.visuales:
            (carpeta / "visuals" / v["name"]).mkdir()
            contenido = {"$schema": f"{ESQUEMA}/visualContainer/2.4.0/schema.json", **v}
            (carpeta / "visuals" / v["name"] / "visual.json").write_text(
                json.dumps(contenido, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    (PBI / f"{NOMBRE}.pbip").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": f"{NOMBRE}.Report"}}],
        "settings": {"enableAutoRecovery": True}}, indent=2) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# 5. dax/medidas.md
# --------------------------------------------------------------------------
def escribir_medidas_md() -> None:
    (RAIZ / "dax").mkdir(exist_ok=True)
    lineas = ["# Medidas DAX del tablero", "",
              "Este archivo lo genera `powerbi/generar_pbip.py` con las mismas fórmulas que van en el modelo, "
              "así se pueden leer sin abrir Power BI. Todas viven en la tabla `Medidas`.", "",
              "Reglas que seguí:",
              "- Toda división con `DIVIDE`, para que no salga error cuando el denominador es cero.",
              "- Los filtros de verdadero o falso se escriben completos (`= TRUE ()`).",
              "- Para contar notas de 1 o 2 uso `IN { 1, 2 }`: en DAX una nota vacía cuenta como menor que 2.", ""]
    carpeta_actual = None
    for carpeta, nombre, formula, formato, explicacion in MEDIDAS:
        if carpeta != carpeta_actual:
            lineas += [f"## {carpeta}", ""]
            carpeta_actual = carpeta
        lineas.append(f"### {nombre}")
        if explicacion:
            lineas.append(explicacion)
        lineas += ["", "```dax", f"{nombre} =", formula, "```", f"Formato: `{formato}`", ""]
    (RAIZ / "dax" / "medidas.md").write_text("\n".join(lineas), encoding="utf-8")


def main() -> None:
    escribir_modelo()
    escribir_informe()
    escribir_medidas_md()
    print(f"Listo: powerbi/{NOMBRE}.pbip, {len(MEDIDAS)} medidas y dax/medidas.md")


if __name__ == "__main__":
    main()
