"""Vista previa del dashboard (2 páginas) hecha con matplotlib a partir del CSV para Power BI.

No es una captura de Power BI: replica el diseño y las medidas de dashboard/README.md
para mostrar el resultado esperado hasta tener el dashboard real.
Uso: python src/dashboard_preview.py  (antes correr src/clean.py)
"""
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from clean import PROCESSED_DIR

FIG_DIR = PROCESSED_DIR.parent.parent / "reports" / "figures"
AUTOMATICOS = "PLATAFORMA BA COLABORATIVA"  # reportes de Boti que nunca se cierran

AZUL, NARANJA, GRIS, FONDO_TARJETA = "#2a78d6", "#eb6834", "#c3c2b7", "#f3f2ef"
TEXTO, TEXTO_2 = "#0b0b0b", "#52514e"
NOTA = "Vista previa generada con Python (matplotlib) a partir de reclamos_powerbi.csv — no es una captura de Power BI."

plt.rcParams.update({
    "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.edgecolor": GRIS, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "axes.axisbelow": True, "grid.color": "#e8e7e3", "grid.linewidth": 0.6,
    "xtick.color": TEXTO_2, "ytick.color": TEXTO_2, "text.color": TEXTO,
})


def miles(x, _=None):
    return f"{x:,.0f}".replace(",", ".")


def pct(x, decimales=1):
    return f"{x:.{decimales}f} %".replace(".", ",")


def tasa(df):
    """Equivale a la medida DAX '% cerrado'."""
    return 100 * df["cerrados"].sum() / df["reclamos"].sum()


def encabezado(fig, subtitulo):
    fig.text(0.03, 0.955, "Reclamos ciudadanos CABA 2024–2026", fontsize=20, fontweight="bold")
    fig.text(0.03, 0.915, subtitulo, fontsize=11, color=TEXTO_2)
    fig.text(0.03, 0.015, f"{NOTA}  Fuente: Buenos Aires Data (CC-BY-2.5-AR). Octubre 2026 es un mes parcial.",
             fontsize=8, color=TEXTO_2)


def tarjeta(ax, titulo, valor, detalle=""):
    ax.set_facecolor(FONDO_TARJETA)
    ax.grid(False)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.text(0.06, 0.72, titulo, fontsize=10, color=TEXTO_2, transform=ax.transAxes)
    ax.text(0.06, 0.32, valor, fontsize=24, fontweight="bold", transform=ax.transAxes)
    ax.text(0.06, 0.1, detalle, fontsize=8.5, color=TEXTO_2, transform=ax.transAxes)


def pagina_resumen(df):
    mensual = df.groupby(df["fecha_ingreso"].dt.to_period("M"))["reclamos"].sum()
    ultimo_dia = df["fecha_ingreso"].max()
    parcial = ultimo_dia != ultimo_dia + pd.offsets.MonthEnd(0)
    completos = mensual.iloc[:-1] if parcial else mensual
    var = 100 * (completos.iloc[-1] / completos.iloc[-2] - 1)

    total, cerrados = df["reclamos"].sum(), df["cerrados"].sum()
    fig = plt.figure(figsize=(16, 9))
    encabezado(fig, "Página 1 · Resumen   |   Filtros: Año = todos · Categoría = todas · Comuna = todas")

    cards = [
        ("Total reclamos", miles(total), "01/01/2024 al 15/10/2026"),
        ("% cerrado", pct(tasa(df[df["categoria"] != AUTOMATICOS])), "sin reportes automáticos de Boti"),
        ("Reclamos abiertos", miles(total - cerrados), "estado actual en el dataset"),
        ("Variación mensual", ("+" if var > 0 else "") + pct(var),
         f"{completos.index[-1].strftime('%m/%Y')} vs. {completos.index[-2].strftime('%m/%Y')}"),
    ]
    for i, (titulo, valor, detalle) in enumerate(cards):
        tarjeta(fig.add_axes([0.03 + i * 0.24, 0.7, 0.22, 0.17]), titulo, valor, detalle)

    ax = fig.add_axes([0.06, 0.1, 0.91, 0.52])
    x = completos.index.to_timestamp()
    ax.plot(x, completos.values, color=AZUL, linewidth=2, marker="o", markersize=4)
    if parcial:
        ax.plot(mensual.index[-1:].to_timestamp(), mensual.values[-1:], color=NARANJA, marker="o",
                markersize=7, linestyle="none", label="mes parcial")
        ax.legend(frameon=False, loc="upper left")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(miles))
    ax.set_ylim(0, None)
    ax.set_title("Evolución mensual de reclamos")
    fig.savefig(FIG_DIR / "dashboard_preview_pagina1.png", dpi=120)
    plt.close(fig)


def pagina_detalle(df):
    por_cat = df.groupby("categoria").agg(reclamos=("reclamos", "sum"), cerrados=("cerrados", "sum"))
    por_cat["tasa"] = 100 * por_cat["cerrados"] / por_cat["reclamos"]
    con_ubic = df.dropna(subset=["comuna"])
    por_com = con_ubic.groupby("comuna").agg(reclamos=("reclamos", "sum"), cerrados=("cerrados", "sum"))
    por_com.index = por_com.index.astype(int).astype(str)
    por_com["tasa"] = 100 * por_com["cerrados"] / por_com["reclamos"]

    fig = plt.figure(figsize=(16, 9))
    encabezado(fig, "Página 2 · Categorías, comunas y cierre   |   Filtros: Año = todos · Categoría = todas · Comuna = todas")
    ax1 = fig.add_axes([0.17, 0.5, 0.31, 0.36])
    ax2 = fig.add_axes([0.56, 0.5, 0.41, 0.36])
    ax3 = fig.add_axes([0.17, 0.08, 0.31, 0.34])
    ax4 = fig.add_axes([0.56, 0.08, 0.41, 0.34])

    top = por_cat.nlargest(10, "reclamos").sort_values("reclamos")
    ax1.barh(top.index, top["reclamos"], color=AZUL, height=0.65)
    ax1.xaxis.set_major_formatter(mtick.FuncFormatter(miles))
    ax1.grid(axis="y", visible=False)
    ax1.tick_params(axis="y", labelsize=8)
    ax1.set_title("Top 10 categorías")

    com = por_com.sort_values("reclamos", ascending=False)
    ax2.bar(com.index, com["reclamos"], color=AZUL, width=0.7)
    ax2.yaxis.set_major_formatter(mtick.FuncFormatter(miles))
    ax2.grid(axis="x", visible=False)
    ax2.set_title("Reclamos por comuna (con ubicación)")

    bajas = (por_cat[(por_cat["reclamos"] >= 5000) & (por_cat.index != AUTOMATICOS)]
             .nsmallest(10, "tasa").sort_values("tasa", ascending=False))
    ax3.barh(bajas.index, bajas["tasa"], color=NARANJA, height=0.65)
    for y, t in enumerate(bajas["tasa"]):
        ax3.text(t, y, " " + pct(t), va="center", fontsize=8, color=TEXTO_2)
    ax3.set_xlim(0, 100)
    ax3.xaxis.set_major_formatter(mtick.PercentFormatter())
    ax3.grid(axis="y", visible=False)
    ax3.tick_params(axis="y", labelsize=8)
    ax3.set_title("% cerrado: 10 categorías más bajas (≥ 5.000 reclamos)")

    com_t = por_com.sort_values("tasa")
    promedio = com_t["tasa"].mean()  # igual que la línea de promedio de Power BI
    ax4.bar(com_t.index, com_t["tasa"], color=AZUL, width=0.7)
    ax4.axhline(promedio, color=TEXTO_2, linewidth=1, linestyle="--")
    ax4.text(-0.4, promedio + 0.3, "promedio " + pct(promedio), fontsize=9, color=TEXTO_2)
    ax4.set_ylim(80, 100)
    ax4.set_yticks(range(80, 101, 5))
    ax4.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax4.grid(axis="x", visible=False)
    ax4.set_title("% cerrado por comuna (eje desde 80 %)")
    fig.savefig(FIG_DIR / "dashboard_preview_pagina2.png", dpi=120)
    plt.close(fig)


def main() -> None:
    df = pd.read_csv(PROCESSED_DIR / "reclamos_powerbi.csv", parse_dates=["fecha_ingreso"])
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    pagina_resumen(df)
    pagina_detalle(df)
    print(f"Guardado en {FIG_DIR}")


if __name__ == "__main__":
    main()
