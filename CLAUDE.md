# olist-logistica-sql · instrucciones para Claude Code

Proyecto 2 del plan de portafolio de datos de Sergio: logística de la tienda Olist con SQL (DuckDB) y Power BI.

## Antes de empezar
- En el PC: lee en el cerebro de Obsidian `Proyectos/Plan datos y n8n.md` (sección «2. Tienda en línea, Olist» y las reglas de todos los repos), `Proyectos/Como trabajar con Sergio.md` y, si vas a escribir texto público, `Personal/Mi_voz_al_escribir.md`.
- En la nube: el cerebro solo se lee (repo privado `cerebro`); al terminar entrega un paquete en Markdown para que Sergio lo aplique desde el PC.

## Reglas de este repo
- Las cifras del README salen de `salidas/r_hallazgos.csv`. Si cambias el SQL, corre `python scripts/correr_sql.py` y actualiza los dos README: `pytest` falla si una cifra no coincide.
- `datos/` tiene los Parquet de Olist (licencia CC BY-NC-SA 4.0, con atribución). `datos_crudos/` (los CSV de Kaggle) no se sube.
- Para rehacer los datos: `python scripts/descargar_datos.py` (kagglehub, sin cuenta) y luego `python scripts/preparar_datos.py`.
- Para comprobar: `python scripts/auditoria_independiente.py` (Python puro contra el SQL) y `python scripts/comparar_tablero.py` (PDF del tablero contra el SQL).
- El tablero se genera con `python powerbi/generar_pbip.py` (modelo, Power Query, gráficos y `dax/medidas.md`). No edites a mano los archivos de `powerbi/OlistLogistica.*`: cambia el generador.
- Una sola tarea pesada a la vez en el PC: antes de abrir Power BI, revisa que no esté abierto por otro chat.
- Nada de rutas del PC con usuario, correos, claves ni teléfonos (`pruebas/test_privacidad.py` lo revisa).
- No publicar ni crear el repo en GitHub sin el «sí» de Sergio.
