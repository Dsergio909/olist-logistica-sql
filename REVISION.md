# Revisión por vueltas

Así revisé el proyecto antes de mostrarlo. Cada vuelta repasa todo de nuevo: cifras contra los datos, pruebas, privacidad y que corra en limpio «como un desconocido». Fechas de 2026.

## Punto de partida (4-nov)

- Datos: zip oficial de Kaggle (44,7 MB, 9 CSV). Filas contadas al bajarlo: 99.441 pedidos, 112.650 ítems, 103.886 pagos, 99.224 reseñas, 99.441 clientes (96.096 personas distintas), 3.095 vendedores, 32.951 productos, 71 categorías y 1.000.163 puntos de geolocalización.
- Construido de punta a punta: 11 consultas SQL, 17 resultados en `salidas/`, 47 pruebas, README en español e inglés y el generador del tablero (8 tablas, 34 medidas, 4 páginas).

## Vuelta 1 de errores (4-nov)

| Qué revisé | Cómo | Resultado |
|---|---|---|
| Cifras del README contra los datos | `scripts/auditoria_independiente.py`: recalculé 19 cifras con Python puro, leyendo los CSV originales de Kaggle, sin DuckDB ni Parquet | 19 de 19 iguales |
| Lógica del SQL, archivo por archivo | Lectura completa de las 11 consultas | 2 errores (abajo) |
| Pruebas que no prueban | Lectura de las 47 pruebas | 1 prueba floja (abajo) |
| Privacidad | Pruebas de privacidad + revisión del historial de git | 1 problema (abajo) |
| Correr en limpio | Clon nuevo en una carpeta vacía, entorno de Python nuevo, pasos del README tal cual | 47 de 47 en verde; `salidas/` idéntico byte a byte |

Lo que encontré y arreglé:
1. **La nota por mes contaba pedidos no entregados** (`09_mes_a_mes.sql`). El resto del análisis y el tablero usan solo entregados. Ahora también este. Cambian las notas mensuales en el segundo decimal; ninguna cifra del README cambia.
2. **Una columna se prestaba a confusión** (`04_flete.sql`): `puesto_por_flete` era el puesto entre las 73 categorías, pero la tabla muestra 15. Ahora se llama `puesto_entre_todas` y tiene su comentario.
3. **Una prueba no comprobaba nada**: comparaba los retrasos de `r_despacho` con un número sumándole 10.000. Ahora exige que sean exactamente los pedidos tarde de un solo vendedor con fecha de transportadora.
4. **Privacidad: los commits llevaban el Gmail de Sergio.** Al subir el repo habría quedado público. Ahora el repo usa el correo privado de GitHub (`…@users.noreply.github.com`), igual que sus otros repos, y rehíce los commits locales. Quedan 0 commits con Gmail.

## Vuelta 2 de errores (4-nov)

| Qué revisé | Cómo | Resultado |
|---|---|---|
| Por qué mi % tarde (6,8 %) no es el 8,1 % que dan otros análisis de Olist | Miré la hora de la fecha prometida en los 99.441 pedidos | Siempre es 00:00. Comparando horas, lo que llega el mismo día prometido sale tarde: 7.826 pedidos (8,1 %). Comparando días: 6.534 (6,8 %). Las dos son válidas; ahora el README explica la diferencia y la cifra 8,1 % sale del SQL |
| Que la prueba del README no se deje engañar | Antes buscaba el texto suelto: «8,0» pasaba aunque solo estuviera dentro de «48,0» | Ahora el número tiene que aparecer entero |
| Cifras del README que no salen del SQL | Prueba nueva al revés: toda cifra con decimales o miles de «Qué encontré» tiene que estar en `r_hallazgos` | 0 cifras sueltas |
| Que las pruebas sí fallen | Sabotaje a propósito: cambié 48,4 por 48,5 en el README y agregué una fila falsa a un CSV de `salidas/` | Fallaron las 3 pruebas que debían fallar; al restaurar, 49 de 49 en verde |
| Que el README diga lo que mide el dato | Lectura de cada conclusión contra su consulta | 2 precisiones: el 72,2 % es sobre pedidos de un solo vendedor (casi todos), y «valor alto» es el 40 % que más gasta |
| Power Query y DAX contra el SQL | Lectura de las 8 consultas M y las 34 medidas contra las definiciones de `00_base.sql` | Iguales: misma definición de entregado y tarde, misma reseña por pedido, mismo despacho tarde |

El tablero no se pudo abrir en esta vuelta: Power BI estaba ocupado por otros chats (4 ventanas y menos de 0,5 GB de RAM libre). Esperé mi turno.

## Vuelta 3 de errores (4-nov), ya con el tablero abierto

| Qué revisé | Cómo | Resultado |
|---|---|---|
| Que el proyecto de texto (PBIP) abra | Abrí `powerbi/OlistLogistica.pbip` en Power BI Desktop 2.159 y actualicé los datos | Abrió sin errores: 8 tablas, 34 medidas, 4 páginas, 40 gráficos. Cargó en unos 75 segundos |
| Cifras del tablero contra el SQL | `scripts/comparar_tablero.py` lee el texto del PDF exportado y busca en cada página las cifras de `salidas/` | 76 de 76 iguales. Son dos caminos distintos (Power Query + DAX contra DuckDB) |
| Que se lea bien | Revisé cada página en pantalla | 4 problemas (abajo) |
| Privacidad del `.pbix` | Lo abrí como zip y busqué rutas con usuario, correos y el nombre de Sergio | Nada. `SecurityBindings` es la configuración de privacidad de las fuentes, cifrada por Windows, sin claves (los datos son archivos locales) |

Lo que encontré y arreglé (en el generador, no a mano):
1. Las tarjetas decían «96 mil» y «95 mil» en vez de la cifra exacta: ahora muestran 96.470 y 94.990 completos.
2. Los gráficos mostraban títulos de ejes técnicos («codigo», «tramo_retraso», «Latitud»): quitados.
3. La tabla de vendedores tenía encabezados como «vendedor_corto» y «Pedidos de vendedor entregados» y no cabía: ahora dice Vendedor, Estado, Entregados, Tarde, % tarde, % despacho tarde y Nota.
4. Las dos líneas por mes tenían barra de desplazamiento y no se veía 2018 completo: ahora usan un eje de fechas continuo.

Quedan para la vuelta de mejora: el mapa corta algunas burbujas en los bordes, la barra de estados no muestra los 27 en el PDF y los números dentro de las barras oscuras casi no se leen.


## Vuelta 1 de mejora (4-nov): el tablero

| Antes | Después |
|---|---|
| El mapa cortaba burbujas en los bordes (RS, RN, PB) | Ejes con márgenes fijos (longitud -75 a -32, latitud -35 a 6): ninguna burbuja cortada |
| La barra de estados tenía barra de desplazamiento y el PDF mostraba 22 de 27 estados | La página de Logística pasó de 720 a 830 px de alto: se ven los 27 |
| Los números dentro de las barras oscuras de las etapas casi no se leían | Etiquetas en blanco |
| La comparación del PDF contra el SQL revisaba 15 estados | Revisa los 27: 88 de 88 cifras iguales |
| El generador borraba la caché de Power BI cada vez | Solo rehace `definition/`; Power BI aplica los cambios sin volver a cargar los datos |

El `.pbix` final pesa 19,9 MB (límite del plan: 50 MB), así que va en el repo.

## Vuelta 2 de mejora (4-nov): que un desconocido lo entienda y lo corra

| Antes | Después |
|---|---|
| Para rehacer los datos había que bajar el zip de Kaggle a mano | `scripts/descargar_datos.py` los baja con `kagglehub` (pedido de Sergio) y cuenta las filas. Probado: bajó sin cuenta en 9 segundos, 9 de 9 archivos con las filas esperadas e idénticos byte a byte a la primera descarga |
| El README no mostraba cómo se conecta todo | Diagrama (Kaggle → Parquet → SQL → salidas → Power BI → README) y tabla de qué consulta responde cada pregunta |
| No decía cómo se comprobaron las cifras | Sección «Cómo comprobé las cifras»: pruebas, auditoría con Python puro y comparación del PDF del tablero |
| `kaggle.json` (el token personal de Kaggle) no estaba en `.gitignore` | Agregado, y la prueba de privacidad lo exige |

## Vuelta 3 de mejora (4-nov): pruebas para el tablero

Antes, si alguien cambiaba una medida o un gráfico, solo se notaba abriendo Power BI. Ahora `pruebas/test_tablero.py` (9 pruebas) revisa sin Power BI:
- que las 4 páginas estén y que todos los JSON se lean;
- que cada gráfico use columnas y medidas que existen en el modelo;
- que cada fórmula DAX cite columnas y medidas que existen;
- que `dax/medidas.md` y el modelo estén al día con el generador;
- que Power Query devuelva exactamente las columnas del modelo;
- que el `.pbix` pese menos de 50 MB y que el tablero use un solo color de acento.

Sabotaje para comprobarlo: cambié el nombre de una medida en un gráfico y la prueba falló; al restaurar, 58 de 58 en verde (antes 49).

## Facilidad y diseño (4-nov)

- README: un resumen de una frase arriba («En 30 segundos») con las 4 cifras que importan. La prueba de cifras ahora cubre desde el título hasta las conclusiones.
- Tablero: fondo blanco, un solo acento verde oscuro (#1d4a35, el del portafolio), grises para lo secundario y letra Segoe UI. Sin neón, sin fondo oscuro, sin adornos. Cada página abre con su pregunta como título.

## IA local y Antigravity

Por la regla nueva de Sergio (4-nov) intenté pasar la revisión de gramática del README en inglés a la IA local o a Antigravity. No se pudo en ese momento: Ollama no, porque otro chat tenía Power BI abierto y quedaban 1,2 GB de RAM libres (la regla dice no cargar un modelo así); Antigravity no, porque `agy.exe` estaba corriendo para otro chat. La revisión la hice yo.

## Auditoría de cálculos, pedida por Sergio (4-nov, noche)

Sergio pidió revisar otra vez todos los cálculos, «porque es lo que más puede fallar», con agentes de Antigravity como revisores, y no parar hasta una vuelta sin fallas ni mejoras. Método de cada vuelta:
1. Antigravity (Gemini 4 Argon, el modelo más fuerte de su plan) recibe las consultas SQL, las medidas DAX y las cifras del README, y busca errores de cálculo y de lógica. Va por fila: un pedido a la vez, con candado en `C:\Trabajo\_temporal\antigravity_en_uso.txt`.
2. Yo compruebo cada hallazgo contra los datos antes de aceptarlo.
3. Cada cifra del README se recalcula por un segundo camino (`scripts/auditoria_independiente.py`, Python puro sobre los CSV de Kaggle, sin DuckDB).

### Auditoría, vuelta A

**Lo que encontré yo antes de leer a Antigravity:**

| Hallazgo | Comprobación | Veredicto |
|---|---|---|
| La recompra «primera entrega tarde» se medía hasta el final de los datos, y esos clientes compraron más tarde (tuvieron 297 días para volver contra 347) | Con la misma ventana de 180 días para todos: 2,86 % contra 2,45 % | **Cierto, grave.** La conclusión 5 decía «no es casualidad» (z 2,91) y no se sostiene |
| 281 clientes tienen «dos pedidos» en el mismo segundo: es una sola compra partida | Volver a comprar = comprar otro día | **Cierto.** Clientes que vuelven: de 3,0 % a 2,2 %. Recompra según la primera entrega: 2,02 % contra 1,61 %, z = 1,71 (no alcanza 1,96) |
| El promedio móvil de 3 meses promediaba porcentajes | Ponderado por pedidos | **Cierto, bajo.** Hasta 1 punto de diferencia (nov-2017: 7,0 % → 8,0 %). No está en el README |
| Empates en los cortes de NTILE del RFM | Máximo 15 clientes empatados en un corte, de 94.990 | Sin efecto |
| ¿Cambia la nota si se promedian las reseñas de un pedido en vez de tomar la más reciente? | Mismas cifras: 4,29, 1,73 y 0,38 | Sin efecto |
| Flete con pedidos cancelados | Solo entregados: 16,6 % y 48,4 %, iguales | Sin efecto |

**Lo que encontró Antigravity (parte 1: consultas 00 a 05), comprobado:**

| # | Hallazgo de Antigravity | Comprobación con los datos | Veredicto |
|---|---|---|---|
| 1 | La fecha prometida viene a las 00:00: contando horas, la promesa sale ~0,6 días más corta y el colchón no cuadra con «tarde» | Promesa en días de calendario: 24,4 (antes 23,7). Entrega: 12,5 (antes 12,6) | **Cierto.** Entrega y promesa ahora en días de calendario, en el SQL y en Power Query |
| 2 | Los pedidos con varios vendedores se suman más de una vez en la concentración, y el retraso se le carga a todos | 97.811 filas pedido-vendedor contra 96.470 pedidos | **Cierto en parte** (la unidad estaba documentada). Ahora solo pedidos de un vendedor (98,7 %): 58,7 % de los retrasos con 49,9 % de los pedidos. La conclusión no cambia |
| 3 | NTILE(4) parte vendedores empatados entre cuartiles | 20 vendedores con el mismo % en dos cuartiles | **Cierto, bajo.** Ahora el cuartil sale de PERCENT_RANK y los empates quedan juntos |
| 4 | Los extremos (-147 y +188 días) aplanan las pendientes de los tramos abiertos | Con tope de ±20 días: 7+ días pasa de +0,008 a -0,004 puntos por día | **Cierto, bajo.** Tope aplicado. La conclusión («desde el día 7 ya no baja») se mantiene |
| 4b | En los retrasos largos, la reseña se escribe antes de recibir el paquete | 99,7 % de las reseñas con 7+ días de retraso; 48,2 % entre 1 y 6 días; 0,3 % a tiempo | **Cierto y nuevo:** explica por qué la nota toca piso. Agregado a la conclusión 3 |
| 5 | Un chequeo de calidad usaba INNER JOIN y dejaba fuera un pedido sin pago; el flete incluye cancelados; la mediana de peso es por ítem vendido | 1 pedido sin pago. Flete igual con solo entregados | Pago: **cierto**, arreglado. Flete: **descartado** (no cambia nada). Peso: aclarado en el comentario |

Antigravity también confirmó como correctos: la separación de `customer_id` y `customer_unique_id`, el filtro de entregados, la reseña única por pedido, sumar precio y flete por pedido antes de dividir, y el orden de ventanas con `QUALIFY`.

Cifras del README que cambiaron: promesa 23,7 → 24,4 días; entrega 12,6 → 12,5; concentración 58,9/50,1 → 58,7/49,9; vuelven 3,0 % → 2,2 %; recompra 3,77/2,83 → 2,02/1,61; z 2,91 → 1,71; RFM 22,2/40,1 → 22,7/41,1. Dato nuevo: 99,7 %. El segundo camino (Python puro) da 28 de 28 iguales.

**Lo que encontró Antigravity (parte 2: consultas 06 a 10), comprobado.** Antigravity revisó la versión anterior de estas consultas, y eso sirvió de control: encontró solo, sin que se lo dijera, el mismo sesgo de recompra que encontré yo.

| # | Hallazgo de Antigravity | Comprobación con los datos | Veredicto |
|---|---|---|---|
| 1 | Recompra sesgada por el tiempo de observación | El mismo que encontré yo | Ya corregido |
| 1b | Hay quien vuelve a comprar antes de recibir el primer pedido: eso no puede ser una reacción al retraso | 257 de 2.260 recompras (11 %) pasan antes de recibir | **Cierto.** Ahora: recompra después de recibir, en los 180 días siguientes a la entrega. A tiempo 1,85 %, tarde 1,37 %, z = 1,82: sigue por debajo de 1,96 |
| 2 | «Ticket alto» era m = 5 (20 % que más gasta) en «Nuevos de ticket alto» y m ≥ 4 (40 %) en «Ticket alto que no volvió» | «Nuevos de ticket alto»: 7,5 % con m = 5, 15,5 % con m ≥ 4 | **Cierto.** La misma regla (m ≥ 4) en los dos. La cifra del README (22,7 % y 41,1 %) no cambia |
| 3 | Las cohortes contaban la primera compra en el mes 0 (siempre 100 %) y escondían las recompras del mismo mes | 360 de los 2.065 clientes que vuelven lo hacen el mismo mes (17 %) | **Cierto.** Ahora solo cuentan compras de otro día, hasta ago-2018 |
| 4 | Las rutas y «mismo estado contra otro estado» cuentan dos veces los pedidos de varios vendedores | 97.811 filas contra 96.470 pedidos | **Cierto.** Solo pedidos de un vendedor. SP → RJ: 8.048 pedidos, 14,3 % tarde. No está en el README |
| 5 | Promedio móvil sin ponderar | El mismo que encontré yo | Ya corregido |
| 6 | El 3,0 % general y las tasas por grupo se miden sobre poblaciones distintas y parecen contradecirse | Cierto: una es todo el período y la otra, 180 días desde la entrega | **Cierto, de claridad.** El README ahora dice «en todo el período» y «180 días desde que recibieron» |
| 7 | Días prometidos medidos hasta las 00:00 | El mismo hallazgo de la parte 1 | Ya corregido |
| 8 | NTILE(5) del RFM parte empates por `cliente_id` | Máximo 15 clientes empatados en un corte, de 94.990 | **Descartado:** sin efecto en ninguna cifra |

Cifras del README que cambiaron por la parte 2: recompra 2,02/1,61 → 1,85/1,37; z 1,71 → 1,82. Segundo camino (Python puro): 28 de 28 iguales. Pruebas: 58 de 58.

### Auditoría, vuelta B (sobre la versión ya corregida)

Antigravity revisó de nuevo las 3 partes, ya con el código corregido. La parte 3 (Power Query, DAX y conclusiones del README) se revisó por primera vez: en la vuelta A la respuesta se perdió porque la consola de Windows no imprimía un carácter («−»). Desde aquí todas las llamadas van en UTF-8.

Las 3 partes encontraron, cada una por su lado, el error más importante de esta vuelta: el «99,7 %» usaba `review_creation_date`, que es cuándo Olist **envió** la encuesta, no cuándo el cliente la **respondió** (`review_answer_timestamp`).

| # | Hallazgo de Antigravity | Comprobación con los datos | Veredicto |
|---|---|---|---|
| 1 | Reseña: fecha de envío de la encuesta en vez de la respuesta del cliente | Con la respuesta: 96,2 % de los clientes con 7+ días de retraso respondió antes de recibir (no 99,7 %) | **Cierto, alto.** Corregido. Y salió un dato nuevo: con 1 a 6 días de retraso, quien responde antes de recibir pone 1,65 y quien espera pone 3,73 |
| 2 | «Lo que pesa es pasarse, no cuánto» contradice los 0,38 puntos por día de la primera semana | Cierto: en la primera semana cada día sí cuenta | **Cierto.** Reescrito: «en la primera semana cada día cuenta; después, la nota ya está puesta» |
| 3 | «El retraso sigue al volumen» sale de ordenar por cantidad de retrasos, y eso siempre pone arriba a los grandes; ese 5 % tiene 8,1 % de tasa contra 5,7 % del resto | Por tamaño del vendedor, la tasa es casi igual: 6,9 %, 6,8 %, 6,4 %, 7,3 % y 7,2 %. El 10 % con peor tasa (30+ pedidos) llega tarde el 16,9 % de las veces y tiene el 12,7 % de los retrasos | **Cierto en el método.** Ahora se mide por tasa (`r_retraso_por_tamano` y `r_peores_vendedores`). La conclusión se mantiene, pero bien medida |
| 4 | El desempate de la concentración ponía primero al vendedor con más pedidos | Cierto | **Cierto, bajo.** A igual número de retrasos, primero el de peor tasa |
| 5 | Despacho tarde comparaba horas: entregar el último día por la tarde contaba como tarde | Por hora: 8.659 despachos tarde; por día: 5.538 | **Cierto, alto.** En días de calendario, como «tarde». El vendedor despachó a tiempo en el 77,6 % de los pedidos tarde (antes 72,2 %), en el SQL y en Power Query |
| 6 | La medida `% despacho tarde` no filtraba pedidos de un vendedor ni «Sin dato» | Cierto | **Cierto.** Corregido |
| 7 | La tarjeta «Vendedores con ventas» contaba vendedores sin ninguna entrega | 3.095 contra 2.970 | **Cierto.** Ahora «Vendedores con entregas» |
| 8 | `% que vuelve a comprar` sin `KEEPFILTERS` da mal al cruzarla por frecuencia | Cierto (no afecta la tarjeta) | **Cierto, bajo.** Con `KEEPFILTERS` |
| 9 | Flete con pedidos no entregados | 16,6 % y 48,4 % iguales; 10,2 % → 10,1 % | **Cierto, bajo.** Solo entregados, como el resto, en el SQL y en DAX |
| 10 | Las pendientes con tope en ±20 apilan la cola en el borde (el punto de más peso en la regresión) | Filtrando: -0,013, -0,376 y -0,017 | **Cierto, bajo.** Se filtra en vez de poner tope |
| 11 | Cohortes sin las celdas con 0 clientes de vuelta | Cierto | **Cierto.** Grilla completa de los meses observados |
| 12 | El comentario atribuía todo el cambio de recompra a los 281 pedidos del mismo segundo | 281 en el mismo segundo y 573 el mismo día, otra hora | **Cierto, de claridad.** Comentario corregido. Decisión: el mismo día cuenta como la misma visita (si no, 2,8 %) |
| 13 | El segmento «ticket alto que no volvió» exige además más de 6 meses sin comprar, y el README no lo decía | Cierto | **Cierto, de claridad.** README y descripción corregidos |
| 14 | La prueba debería ser de una cola (z 1,82 alcanzaría) | La hipótesis no se fijó de antemano; la prueba estándar es de dos colas | **Descartado como error.** El README ahora dice «hay una señal, pero no alcanza al 95 %, porque son pocos clientes con entrega tarde» |
| 15 | Promedio móvil con 1 y 2 meses al inicio | Cierto | **Cierto, bajo.** Vacío hasta tener 3 meses |
| 16 | 1.350 pedidos con la etapa del vendedor negativa (despachado antes de aprobar el pago) | 1.350 y 23 | **Cierto.** Agregado al chequeo de calidad (se dejan; son error de registro) |
| 17 | Las etapas (en horas) no suman la tarjeta de días de entrega (en días de calendario) | 12,1 contra 12,5 | **Cierto, de claridad.** El título del gráfico dice «días con horas» |
| 18 | `sin_categoria` entraba en el ranking de categorías | Cierto | **Cierto, bajo.** Excluida |
| 19 | El centro de cada estado del mapa no es por código postal | `geo_cp` ya tiene 1 fila por código (19.015 de 19.015) | **Descartado:** falso |
| 20 | La columna `tiene_comentario` no existe en el Parquet | Existe (40.968 reseñas con comentario) | **Descartado:** falso |
| 21 | La recencia del RFM se mide hasta el 2018-09-04 por un solo pedido de septiembre | Cierto, pero no cambia ningún segmento | **Descartado:** el corte «día después del último pedido» está documentado |
| 22 | Empates en NTILE y en el puesto con el % redondeado | Máximo 15 clientes; cosmético | **Descartado** (comentario aclarado) |

Cifras del README que cambiaron en la vuelta B: vendedor a tiempo 72,2 % → 77,6 %; concentración (58,7/49,9) reemplazada por la tasa por tamaño (6,4 % a 7,3 %) y el 10 % peor (16,9 % de tasa, 12,7 % de los retrasos); reseñas antes de recibir 99,7 % → 96,2 %, con las notas 1,65 y 3,73; flete mayor que el producto 10,2 % → 10,1 %. Segundo camino (Python puro): 32 de 32 iguales. Pruebas: 58 de 58.
