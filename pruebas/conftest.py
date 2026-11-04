"""Prepara una sola conexión de DuckDB con todas las consultas ya corridas."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import correr_sql  # noqa: E402


@pytest.fixture(scope="session")
def con():
    conexion = correr_sql.conectar()
    correr_sql.correr_todo(conexion)
    yield conexion
    conexion.close()


@pytest.fixture(scope="session")
def uno(con):
    """Devuelve el primer valor de una consulta."""
    def _uno(sql: str):
        return con.execute(sql).fetchone()[0]
    return _uno


@pytest.fixture(scope="session")
def hallazgos(con):
    return {clave: (valor, int(dec)) for clave, valor, dec in
            con.execute("select clave, valor, decimales from r_hallazgos").fetchall()}
