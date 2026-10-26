"""Carga el parquet limpio en una base DuckDB local y ejecuta las consultas de sql/kpis.sql.

Uso: python src/build_db.py  (antes correr src/clean.py)
"""
from pathlib import Path

import duckdb

from clean import PROCESSED_DIR

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "reclamos.duckdb"
SQL_PATH = ROOT / "sql" / "kpis.sql"


def load_queries(path: Path = SQL_PATH) -> dict[str, str]:
    """Separa el archivo SQL en consultas usando los marcadores '-- name: <nombre>'."""
    blocks = path.read_text(encoding="utf-8").split("\n-- name:")[1:]
    return {b.split("\n", 1)[0].strip(): b.split("\n", 1)[1].strip().rstrip(";") for b in blocks}


def build(con: duckdb.DuckDBPyConnection) -> None:
    parquet = (PROCESSED_DIR / "reclamos_clean.parquet").as_posix()
    con.execute(f"CREATE OR REPLACE TABLE reclamos AS SELECT * FROM read_parquet('{parquet}')")
    print(f"Tabla 'reclamos' cargada: {con.sql('SELECT count(*) FROM reclamos').fetchall()[0][0]:,} filas")


def main() -> None:
    with duckdb.connect(DB_PATH) as con:
        build(con)
        for name, query in load_queries().items():
            print(f"\n=== {name} ===")
            con.sql(query).show(max_rows=40, max_width=200)


if __name__ == "__main__":
    main()
