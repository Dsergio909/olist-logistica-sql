"""Baja los 9 CSV de Olist desde Kaggle y los deja en datos_crudos/.

Uso:
    pip install kagglehub
    python scripts/descargar_datos.py

- Usa kagglehub, la librería oficial de Kaggle. Este dataset es público y en
  noviembre de 2026 bajaba sin cuenta. Si Kaggle pide credenciales, crea tu
  token en kaggle.com > Settings > API > «Create New Token» y guarda el archivo
  en %USERPROFILE%\\.kaggle\\kaggle.json (Windows) o ~/.kaggle/kaggle.json.
  Ese archivo es personal: nunca lo subas al repo (está en .gitignore).
- Comprueba que lleguen los 9 archivos y que tengan las filas esperadas.
- No hace falta para correr el SQL ni las pruebas: datos/ ya trae los Parquet.
  Sirve para rehacer datos/ desde cero con scripts/preparar_datos.py.
"""
from __future__ import annotations

import csv
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "datos_crudos"
DATASET = "olistbr/brazilian-ecommerce"

FILAS = {
    "olist_customers_dataset.csv": 99_441,
    "olist_geolocation_dataset.csv": 1_000_163,
    "olist_order_items_dataset.csv": 112_650,
    "olist_order_payments_dataset.csv": 103_886,
    "olist_order_reviews_dataset.csv": 99_224,
    "olist_orders_dataset.csv": 99_441,
    "olist_products_dataset.csv": 32_951,
    "olist_sellers_dataset.csv": 3_095,
    "product_category_name_translation.csv": 71,
}


def contar_filas(ruta: Path) -> int:
    """Filas de datos (sin encabezado). Usa el lector de CSV: las reseñas tienen saltos de línea dentro."""
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        return sum(1 for _ in csv.reader(f)) - 1


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        import kagglehub
    except ImportError:
        print("Falta kagglehub: pip install kagglehub")
        return 1

    print(f"Bajando {DATASET} desde Kaggle...")
    try:
        carpeta = Path(kagglehub.dataset_download(DATASET))
    except Exception as e:  # sin red, o Kaggle pidió credenciales
        print(f"No se pudo bajar: {e}")
        print("Si pide credenciales, mira las instrucciones al inicio de este archivo.")
        return 1

    DESTINO.mkdir(exist_ok=True)
    errores = 0
    for nombre, esperadas in FILAS.items():
        origen = carpeta / nombre
        if not origen.exists():
            print(f"FALTA  {nombre}")
            errores += 1
            continue
        shutil.copy2(origen, DESTINO / nombre)
        filas = contar_filas(DESTINO / nombre)
        ok = filas == esperadas
        errores += not ok
        print(f"{'OK   ' if ok else 'DISTINTO'} {nombre}: {filas:,} filas (esperadas {esperadas:,})")
    print(f"\n{len(FILAS) - errores} de {len(FILAS)} archivos bien, en datos_crudos/.")
    return 1 if errores else 0


if __name__ == "__main__":
    raise SystemExit(main())
