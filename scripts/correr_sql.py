"""Corre las consultas de sql/ en orden y guarda los resultados en salidas/.

Uso (desde la carpeta del repo):
    python scripts/correr_sql.py

- Cada archivo sql/NN_*.sql se corre completo, en orden de número.
- Toda tabla que empiece por r_ se guarda como salidas/r_<nombre>.csv.
- rfm_clientes se guarda como salidas/rfm_clientes.parquet (la usa Power BI).
- Los CSV salen siempre iguales (mismo orden, punto decimal, UTF-8), para que
  GitHub Actions pueda revisar que nadie los cambió a mano.
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parent.parent
SQL = RAIZ / "sql"
SALIDAS = RAIZ / "salidas"


def conectar() -> duckdb.DuckDBPyConnection:
    """Abre DuckDB en memoria con la carpeta del repo como base de las rutas."""
    os.chdir(RAIZ)
    con = duckdb.connect()
    con.execute("set threads = 4")
    return con


def correr_todo(con: duckdb.DuckDBPyConnection) -> list[str]:
    archivos = sorted(SQL.glob("[0-9][0-9]_*.sql"))
    for archivo in archivos:
        try:
            con.execute(archivo.read_text(encoding="utf-8"))
        except duckdb.Error as e:
            raise SystemExit(f"Falló {archivo.name}: {e}") from e
    return [a.name for a in archivos]


def guardar(con: duckdb.DuckDBPyConnection, carpeta: Path = SALIDAS) -> list[str]:
    carpeta.mkdir(exist_ok=True)
    tablas = [t for (t,) in con.execute(
        "select table_name from information_schema.tables "
        "where table_name like 'r\\_%' escape '\\' order by 1").fetchall()]
    for tabla in tablas:
        res = con.execute(f"select * from {tabla}")
        columnas = [d[0] for d in res.description]
        filas = res.fetchall()
        with (carpeta / f"{tabla}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(columnas)
            for fila in filas:
                w.writerow(["" if v is None else v for v in fila])
    destino = (carpeta / "rfm_clientes.parquet").as_posix()
    con.execute(f"copy (select * from rfm_clientes order by cliente_id) to '{destino}' "
                "(format parquet, compression zstd)")
    return tablas


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    con = conectar()
    archivos = correr_todo(con)
    tablas = guardar(con)
    print(f"Corrí {len(archivos)} archivos SQL y guardé {len(tablas)} resultados en salidas/:")
    for t in tablas:
        n = con.execute(f"select count(*) from {t}").fetchone()[0]
        print(f"  {t}.csv ({n} filas)")


if __name__ == "__main__":
    main()
