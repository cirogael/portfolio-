"""Limpia y une los CSV del SUACI (2024-2026) y guarda el resultado en data/processed/.

Uso: python src/clean.py  (antes correr src/download.py)
"""
import json

import pandas as pd

from download import RAW_DIR, YEARS, detect_sep

PROCESSED_DIR = RAW_DIR.parent / "processed"

# Columnas que se usan del crudo. Se descartan coordenadas y esquina (no se usan en el análisis).
RAW_COLUMNS = [
    "nro_solicitud", "categoria", "prestacion", "tipo", "fecha_ingreso", "hora_ingreso",
    "comuna", "barrio", "calle", "altura", "canal", "genero", "estado_general",
]
TEXT_COLUMNS = ["categoria", "prestacion", "tipo", "barrio", "canal", "genero", "estado_general"]

# El mismo valor aparece escrito distinto según el año
BARRIO_MAP = {"BOCA": "LA BOCA"}
CANAL_MAP = {"APP BA 147": "APP", "OPERADOR GCBA": "OPERADOR"}

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

# Mismo trámite, en la misma dirección y en el mismo momento: se considera carga duplicada
DUPLICATE_KEY = ["fecha_ingreso", "hora_ingreso", "prestacion", "tipo", "calle", "altura"]

# El CSV para Power BI va agregado por estas columnas (una fila por combinación, no por reclamo)
POWERBI_KEYS = ["fecha_ingreso", "categoria", "tipo", "canal", "comuna", "barrio"]


def load_year(year: int) -> pd.DataFrame:
    """Lee un año y convierte la fecha según el formato de ese archivo."""
    path = RAW_DIR / f"suaci_{year}.csv"
    df = pd.read_csv(path, sep=detect_sep(path), usecols=RAW_COLUMNS, dtype=str)
    fmt = "%d/%m/%Y" if "/" in df["fecha_ingreso"].iloc[0] else "%Y-%m-%d"
    df["fecha_ingreso"] = pd.to_datetime(df["fecha_ingreso"], format=fmt, errors="coerce")
    df["anio_archivo"] = year
    return df


def normalize_text(s: pd.Series) -> pd.Series:
    """Mayúsculas, sin espacios sobrantes y tildes en forma única (NFC)."""
    return s.str.normalize("NFC").str.strip().str.replace(r"\s+", " ", regex=True).str.upper()


def parse_hour(s: pd.Series) -> pd.Series:
    """Hora 0-23 desde '13:12:33' o '05:03:21 pm'.

    Solo se usa la hora: en 2024 y 2025 el campo de minutos trae el mes (error de origen).
    """
    h = s.str[:2].astype(int)
    suffix = s.str[-2:].str.lower()
    return h.where(~suffix.isin(["am", "pm"]), h % 12 + 12 * (suffix == "pm"))


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Normaliza, descarta registros inválidos/duplicados y agrega columnas derivadas."""
    log = {"filas_crudas": len(df)}

    for col in TEXT_COLUMNS:
        df[col] = normalize_text(df[col])
    df["barrio"] = df["barrio"].replace(BARRIO_MAP)
    df["canal"] = df["canal"].replace(CANAL_MAP)

    # Registros imposibles: sin fecha válida, fecha fuera del año del archivo o de prueba
    invalid = (
        df["fecha_ingreso"].isna()
        | (df["fecha_ingreso"].dt.year != df["anio_archivo"])
        | df["canal"].str.contains("PRUEBA", na=False)
    )
    log["descartados_invalidos"] = int(invalid.sum())
    df = df[~invalid]

    n = len(df)
    df = df.drop_duplicates("nro_solicitud")
    log["duplicados_nro_solicitud"] = n - len(df)

    # Solo se buscan cargas repetidas entre registros con dirección
    dup = df["calle"].notna() & df.duplicated(DUPLICATE_KEY)
    log["duplicados_misma_carga"] = int(dup.sum())
    df = df[~dup].copy()

    comuna = pd.to_numeric(df["comuna"], errors="coerce").astype("Int64")
    out_of_range = comuna.notna() & ~comuna.between(1, 15)
    log["comunas_fuera_de_rango"] = int(out_of_range.sum())
    df["comuna"] = comuna.mask(out_of_range)

    df["hora"] = parse_hour(df["hora_ingreso"])
    df["anio"] = df["fecha_ingreso"].dt.year
    df["mes"] = df["fecha_ingreso"].dt.month
    df["dia_semana_num"] = df["fecha_ingreso"].dt.day_of_week + 1
    df["dia_semana"] = df["dia_semana_num"].map(lambda d: DIAS[d - 1])
    # Reemplaza a cerrado_en_plazo: el dataset no publica fecha de cierre, solo el estado
    df["cerrado"] = df["estado_general"] == "CERRADO"

    df = df.drop(columns=["hora_ingreso", "calle", "altura", "anio_archivo"])
    log["filas_finales"] = len(df)
    return df.reset_index(drop=True), log


def quality_report(df: pd.DataFrame, log: dict) -> None:
    """Imprime el reporte de calidad de datos."""
    print("\n=== Reporte de calidad de datos ===")
    print(f"Filas crudas ({YEARS[0]}-{YEARS[-1]}):            {log['filas_crudas']:>10,}")
    print(f"Descartadas (fecha inválida/prueba): {log['descartados_invalidos']:>10,}")
    print(f"Duplicados por nro_solicitud:        {log['duplicados_nro_solicitud']:>10,}")
    print(f"Duplicados de carga (misma dirección, trámite y momento): {log['duplicados_misma_carga']:,}")
    print(f"Comunas fuera de rango (-> nulo):    {log['comunas_fuera_de_rango']:>10,}")
    print(f"Filas finales:                       {log['filas_finales']:>10,}")

    print("\nNulos por columna (% del total):")
    nulls = (df.isna().mean() * 100).round(1)
    print(nulls[nulls > 0].sort_values(ascending=False).to_string())

    print("\nNulos de comuna por año (%):")
    print((df["comuna"].isna().groupby(df["anio"]).mean() * 100).round(1).to_string())

    print(f"\nRango de fechas: {df['fecha_ingreso'].min():%Y-%m-%d} a {df['fecha_ingreso'].max():%Y-%m-%d}")
    print(f"Categorías: {df['categoria'].nunique()} | Barrios: {df['barrio'].nunique()} | Canales: {df['canal'].nunique()}")


def main() -> None:
    assert parse_hour(pd.Series(["13:01:02", "12:00:00 am", "12:30:00 PM", "05:03:21 pm"])).tolist() == [13, 0, 12, 17]

    # Se limpia año por año para no tener los ~3,4 M de filas crudas en memoria a la vez.
    # Los duplicados no cruzan años (nro_solicitud lleva el año y la clave incluye la fecha).
    parts, logs = zip(*(clean(load_year(y)) for y in YEARS))
    df = pd.concat(parts, ignore_index=True)
    del parts
    df[TEXT_COLUMNS] = df[TEXT_COLUMNS].astype("category")
    log = {k: sum(l[k] for l in logs) for k in logs[0]}

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PROCESSED_DIR / "reclamos_clean.parquet", index=False)
    powerbi = (
        df.groupby(POWERBI_KEYS, observed=True, dropna=False)
        .agg(reclamos=("cerrado", "size"), cerrados=("cerrado", "sum"))
        .reset_index()
    )
    assert powerbi["reclamos"].sum() == len(df)
    powerbi["comuna"] = powerbi["comuna"].astype("Int64")  # el groupby con nulos la pasa a float
    powerbi.to_csv(
        PROCESSED_DIR / "reclamos_powerbi.csv", index=False, encoding="utf-8-sig", date_format="%Y-%m-%d"
    )
    (PROCESSED_DIR / "calidad.json").write_text(json.dumps(log, indent=2), encoding="utf-8")  # lo lee el notebook
    quality_report(df, log)
    print(f"\nGuardado en {PROCESSED_DIR}")


if __name__ == "__main__":
    main()
