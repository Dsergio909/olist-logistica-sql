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
