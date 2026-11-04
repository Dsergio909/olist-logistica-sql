"""Los datos de datos/ son los de Kaggle, completos."""
from __future__ import annotations

import json

import pytest

from conftest import RAIZ

MANIFIESTO = json.loads((RAIZ / "datos" / "MANIFIESTO.json").read_text(encoding="utf-8"))

# Filas de cada CSV de Kaggle (contadas al descargar el 4-nov-2026).
FILAS_KAGGLE = {
    "olist_customers_dataset": 99_441,
    "olist_geolocation_dataset": 1_000_163,
    "olist_order_items_dataset": 112_650,
    "olist_order_payments_dataset": 103_886,
    "olist_order_reviews_dataset": 99_224,
    "olist_orders_dataset": 99_441,
    "olist_products_dataset": 32_951,
    "olist_sellers_dataset": 3_095,
    "product_category_name_translation": 71,
}


@pytest.mark.parametrize("nombre,filas", FILAS_KAGGLE.items())
def test_manifiesto_tiene_las_filas_de_kaggle(nombre, filas):
    assert MANIFIESTO["filas_csv_original"][nombre] == filas


@pytest.mark.parametrize("nombre", [n for n in FILAS_KAGGLE if n != "olist_geolocation_dataset"])
def test_parquet_no_pierde_filas(uno, nombre):
    n = uno(f"select count(*) from read_parquet('datos/{nombre}.parquet')")
    assert n == FILAS_KAGGLE[nombre]


def test_geolocalizacion_resumida_cubre_todos_los_puntos(uno):
    # Se resume a un punto por código postal, pero no se pierde ningún punto.
    assert uno("select sum(puntos_originales) from geo_cp") == 1_000_163
    assert uno("select count(*) from geo_cp") == MANIFIESTO["filas_parquet"]["olist_geolocation_dataset"]


def test_resenas_sin_texto_libre(con):
    columnas = [c[0] for c in con.execute("describe resenas_crudas").fetchall()]
    assert "review_comment_message" not in columnas
    assert "review_comment_title" not in columnas


def test_totales_conocidos(uno):
    assert uno("select count(distinct pedido_id) from pedidos") == 99_441
    assert uno("select count(distinct cliente_id) from clientes") == 96_096
    assert uno("select count(*) from vendedores") == 3_095
    assert uno("select round(sum(price), 2) from items_crudos") == pytest.approx(13_591_643.70)
    assert uno("select round(sum(freight_value), 2) from items_crudos") == pytest.approx(2_251_909.54)
    assert uno("select round(sum(payment_value), 2) from pagos_crudos") == pytest.approx(16_008_872.12)


def test_llaves_unicas_y_completas(uno):
    assert uno("select count(*) - count(distinct pedido_id) from pedidos") == 0
    assert uno("select count(*) - count(distinct pedido_id) from resenas") == 0
    # Todo producto vendido existe en la tabla de productos y todo ítem tiene pedido.
    assert uno("select count(*) from items_crudos i anti join productos p on p.producto_id = i.product_id") == 0
    assert uno("select count(*) from items_crudos i anti join pedidos p on p.pedido_id = i.order_id") == 0
    assert uno("select count(*) from productos where categoria is null") == 0
