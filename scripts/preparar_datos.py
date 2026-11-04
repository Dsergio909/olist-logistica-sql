"""Convierte los 9 CSV de Olist (Kaggle) a Parquet en la carpeta datos/.

Uso:
    python scripts/preparar_datos.py            # lee datos_crudos/ y escribe datos/

Qué cambia frente a los CSV originales (y por qué):
- Mismo número de filas y mismas columnas, salvo dos cambios:
  1. Reseñas: se quitan el título y el texto del comentario (texto libre escrito
     por clientes) y se deja solo una marca `tiene_comentario`. El análisis no
     los usa y así el repo no redistribuye texto personal.
  2. Geolocalización: el CSV trae 1.000.163 filas, con muchos puntos repetidos
     por código postal. Se resume a una fila por prefijo de código postal
     (mediana de latitud y longitud). Solo se usa para el mapa.
- Al final escribe datos/MANIFIESTO.json con las filas de cada CSV original,
  para que las pruebas comprueben que no se perdió nada.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parent.parent
CRUDOS = RAIZ / "datos_crudos"
DATOS = RAIZ / "datos"

ARCHIVOS = [
    "olist_customers_dataset",
    "olist_geolocation_dataset",
    "olist_order_items_dataset",
    "olist_order_payments_dataset",
    "olist_order_reviews_dataset",
    "olist_orders_dataset",
    "olist_products_dataset",
    "olist_sellers_dataset",
    "product_category_name_translation",
]

# Tipos fijos: así el resultado no depende de lo que adivine el lector de CSV.
TIPOS = {
    "olist_customers_dataset": {"customer_zip_code_prefix": "VARCHAR"},
    "olist_sellers_dataset": {"seller_zip_code_prefix": "VARCHAR"},
    "olist_geolocation_dataset": {"geolocation_zip_code_prefix": "VARCHAR"},
}


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def leer(con: duckdb.DuckDBPyConnection, nombre: str) -> str:
    ruta = (CRUDOS / f"{nombre}.csv").as_posix()
    tipos = TIPOS.get(nombre)
    extra = f", types={tipos!r}" if tipos else ""
    return f"read_csv('{ruta}', header=true{extra})"


def main() -> None:
    faltan = [n for n in ARCHIVOS if not (CRUDOS / f"{n}.csv").exists()]
    if faltan:
        raise SystemExit(
            "Faltan CSV en datos_crudos/: " + ", ".join(faltan)
            + "\nDescárgalos de https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce"
        )
    DATOS.mkdir(exist_ok=True)
    con = duckdb.connect()
    manifiesto = {"fuente": "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce",
                  "licencia": "CC BY-NC-SA 4.0", "filas_csv_original": {}, "filas_parquet": {}}

    for nombre in ARCHIVOS:
        origen = leer(con, nombre)
        n = con.execute(f"select count(*) from {origen}").fetchone()[0]
        manifiesto["filas_csv_original"][nombre] = n

        if nombre == "olist_order_reviews_dataset":
            consulta = f"""
                select review_id, order_id, review_score,
                       coalesce(length(trim(review_comment_message)), 0) > 0 as tiene_comentario,
                       review_creation_date, review_answer_timestamp
                from {origen}"""
        elif nombre == "olist_geolocation_dataset":
            consulta = f"""
                select geolocation_zip_code_prefix,
                       round(median(geolocation_lat), 6) as geolocation_lat,
                       round(median(geolocation_lng), 6) as geolocation_lng,
                       mode(geolocation_state) as geolocation_state,
                       count(*) as puntos_originales
                from {origen}
                group by 1 order by 1"""
        else:
            consulta = f"select * from {origen}"

        destino = (DATOS / f"{nombre}.parquet").as_posix()
        con.execute(f"copy ({consulta}) to '{destino}' (format parquet, compression zstd)")
        m = con.execute(f"select count(*) from read_parquet('{destino}')").fetchone()[0]
        manifiesto["filas_parquet"][nombre] = m
        print(f"{nombre}: {n:,} filas en el CSV -> {m:,} en Parquet")

    zip_kaggle = CRUDOS / "brazilian-ecommerce.zip"
    if zip_kaggle.exists():
        manifiesto["sha256_zip_kaggle"] = sha256(zip_kaggle)
    (DATOS / "MANIFIESTO.json").write_text(json.dumps(manifiesto, indent=2, ensure_ascii=False) + "\n",
                                           encoding="utf-8")
    print("Listo: datos/MANIFIESTO.json")


if __name__ == "__main__":
    main()
