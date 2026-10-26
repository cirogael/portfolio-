"""Descarga los CSV anuales del SUACI / BA Colaborativa a data/raw/ e imprime un resumen.

Fuente: https://data.buenosaires.gob.ar/dataset/sistema-unico-atencion-ciudadana
Uso: python src/download.py
"""
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

YEARS = [2024, 2025, 2026]
BASE_URL = (
    "https://cdn.buenosaires.gob.ar/datosabiertos/datasets/atencion-ciudadana/"
    "sistema-unico-atencion-ciudadana/sistema-unico-de-atencion-ciudadana-{year}.csv"
)
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
HEADERS = {"User-Agent": "Mozilla/5.0 (analisis-reclamos-caba)"}


def download(year: int) -> Path:
    """Descarga el CSV del año. Si ya existe con el mismo tamaño que en el servidor, no lo baja de nuevo."""
    url = BASE_URL.format(year=year)
    dest = RAW_DIR / f"suaci_{year}.csv"
    with urlopen(Request(url, headers=HEADERS), timeout=120) as resp:
        size = int(resp.headers["Content-Length"])
        if dest.exists() and dest.stat().st_size == size:
            print(f"{dest.name}: ya descargado ({size / 1e6:.0f} MB)")
            return dest
        print(f"{dest.name}: descargando {size / 1e6:.0f} MB...")
        tmp = dest.with_suffix(".part")
        with open(tmp, "wb") as f:
            while chunk := resp.read(1 << 20):
                f.write(chunk)
    tmp.replace(dest)  # solo se reemplaza si la descarga terminó completa
    return dest


def detect_sep(path: Path) -> str:
    """Cada año viene con un separador distinto (';' o ',')."""
    header = path.open(encoding="utf-8").readline()
    return ";" if header.count(";") > header.count(",") else ","


def summarize(path: Path) -> None:
    """Imprime filas, columnas y rango de fechas."""
    sep = detect_sep(path)
    header = path.open(encoding="utf-8").readline()
    columns = [c.strip().strip('"') for c in header.split(sep)]
    fechas = pd.read_csv(path, sep=sep, usecols=["fecha_ingreso"], dtype=str)["fecha_ingreso"]
    fmt = "%d/%m/%Y" if "/" in fechas.dropna().iloc[0] else "%Y-%m-%d"
    fechas = pd.to_datetime(fechas, format=fmt, errors="coerce")
    print(
        f"  filas: {len(fechas):,} | columnas: {len(columns)} | separador: '{sep}'\n"
        f"  fechas: {fechas.min():%Y-%m-%d} a {fechas.max():%Y-%m-%d} "
        f"({fechas.isna().sum():,} sin fecha válida)\n"
        f"  {', '.join(columns)}"
    )


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for year in YEARS:
        summarize(download(year))


if __name__ == "__main__":
    main()
