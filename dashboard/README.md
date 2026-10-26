# Guía para armar el dashboard en Power BI

Paso a paso para construir el dashboard de reclamos en **Power BI Desktop** a partir del CSV que genera
`src/clean.py`. El resultado son dos páginas: un resumen con KPIs y evolución, y un detalle de categorías,
comunas y tasa de cierre.

> **Resultado esperado:** `python src/dashboard_preview.py` genera una vista previa de las dos páginas con matplotlib
> (`reports/figures/dashboard_preview_pagina1.png` y `..._pagina2.png`). No es Power BI: sirve como referencia
> del diseño y para comparar los números de las tarjetas.

> El dataset no trae fecha de cierre, así que en lugar de "mediana de días de resolución" y "% en plazo"
> el dashboard usa **% cerrado** y **reclamos abiertos**.

## 1. Importar los datos

1. Correr `python src/download.py` y `python src/clean.py` (genera `data/processed/reclamos_powerbi.csv`).
2. En Power BI: **Inicio → Obtener datos → Texto/CSV** y elegir `reclamos_powerbi.csv`.
3. En la vista previa revisar: **Origen del archivo: 65001 Unicode (UTF-8)**, **Delimitador: Coma**.
   Hacer clic en **Transformar datos**.
4. En Power Query, renombrar la consulta a `Reclamos` y revisar los tipos de columna:

   | Columna | Tipo | Descripción |
   |---|---|---|
   | `fecha_ingreso` | Fecha | Día en que entró el reclamo |
   | `categoria` | Texto | Área temática (HIGIENE, VEREDAS, …) |
   | `tipo` | Texto | Solicitud, denuncia, queja, reporte o servicio |
   | `canal` | Texto | Por dónde entró (Boti, web, app, 147, …) |
   | `comuna` | Número entero | 1 a 15 (vacío si el reclamo no tiene ubicación) |
   | `barrio` | Texto | Barrio (vacío si no tiene ubicación) |
   | `reclamos` | Número entero | Cantidad de reclamos de esa combinación |
   | `cerrados` | Número entero | Cuántos de esos reclamos están cerrados |

   > Si `fecha_ingreso` aparece como texto, usar **Cambiar tipo → Usar configuración regional → Fecha → Inglés (Estados Unidos)**:
   > el formato del archivo es `aaaa-mm-dd`.

5. **Cerrar y aplicar.**

El CSV ya viene agregado (una fila por día × categoría × tipo × canal × comuna × barrio), por eso todas las medidas
**suman** las columnas `reclamos` y `cerrados` en lugar de contar filas.

## 2. Tabla calendario

**Modelado → Nueva tabla** y pegar:

```dax
Calendario =
ADDCOLUMNS (
    CALENDAR ( MIN ( Reclamos[fecha_ingreso] ), MAX ( Reclamos[fecha_ingreso] ) ),
    "Año", YEAR ( [Date] ),
    "Mes", MONTH ( [Date] ),
    "Mes nombre", FORMAT ( [Date], "mmm" ),
    "Año-Mes", FORMAT ( [Date], "yyyy-mm" ),
    "Inicio de mes", DATE ( YEAR ( [Date] ), MONTH ( [Date] ), 1 ),
    "Día semana", FORMAT ( [Date], "dddd" ),
    "Día semana nro", WEEKDAY ( [Date], 2 )
)
```

Después:

1. Seleccionar la tabla `Calendario` → **Herramientas de tabla → Marcar como tabla de fechas** → columna `Date`.
2. En la vista de modelo, crear la relación `Calendario[Date]` → `Reclamos[fecha_ingreso]` (uno a varios).
3. Ordenar `Mes nombre` por `Mes` y `Día semana` por `Día semana nro` (**Herramientas de columna → Ordenar por columna**).

## 3. Medidas DAX

Crear una tabla vacía para agrupar las medidas (**Inicio → Especificar datos** → nombre `Medidas` → Cargar) y
agregar cada medida con **Nueva medida**:

```dax
Total reclamos = SUM ( Reclamos[reclamos] )
```

```dax
Reclamos cerrados = SUM ( Reclamos[cerrados] )
```

```dax
Reclamos abiertos = [Total reclamos] - [Reclamos cerrados]
```

```dax
% cerrado = DIVIDE ( [Reclamos cerrados], [Total reclamos] )
```

```dax
-- Excluye los reportes automáticos de Boti (nunca se cierran y no son reclamos de vecinos)
% cerrado sin reportes automáticos =
CALCULATE (
    [% cerrado],
    Reclamos[categoria] <> "PLATAFORMA BA COLABORATIVA"
)
```

```dax
Reclamos mes anterior =
CALCULATE ( [Total reclamos], DATEADD ( Calendario[Date], -1, MONTH ) )
```

```dax
Variación mensual % =
DIVIDE ( [Total reclamos] - [Reclamos mes anterior], [Reclamos mes anterior] )
```

```dax
Promedio diario =
AVERAGEX ( VALUES ( Calendario[Date] ), [Total reclamos] )
```

Formatos: `% cerrado`, `% cerrado sin reportes automáticos` y `Variación mensual %` como **Porcentaje con 1 decimal**;
el resto como **Número entero** con separador de miles.

> `Variación mensual %` tiene sentido cuando el contexto es un mes (eje de un gráfico por `Año-Mes` o un
> segmentador de mes). En una tarjeta sin filtro de mes compara todo el período contra sí mismo desplazado y
> no es interpretable. Para la tarjeta, filtrarla al último mes completo (ver página 1).

## 4. Página 1 — Resumen

| Visual | Configuración |
|---|---|
| **Segmentadores** (fila superior) | `Calendario[Año]`, `Reclamos[categoria]`, `Reclamos[comuna]`. Estilo: lista desplegable |
| **Tarjeta** Total reclamos | Medida `Total reclamos` |
| **Tarjeta** % cerrado | Medida `% cerrado sin reportes automáticos` |
| **Tarjeta** Reclamos abiertos | Medida `Reclamos abiertos` |
| **Tarjeta** Variación mensual % | Medida `Variación mensual %` con filtro de objeto visual `Calendario[Año-Mes]` = último mes completo (ej. `2026-09`) |
| **Gráfico de líneas** Evolución mensual | Eje X: `Calendario[Inicio de mes]` (jerarquía desactivada). Eje Y: `Total reclamos`. Información sobre herramientas: `Variación mensual %` |

Sugerencia: título de la página "Reclamos ciudadanos CABA 2024–2026" y un cuadro de texto con la fuente
(Buenos Aires Data, CC-BY-2.5-AR) y la aclaración "octubre 2026 es un mes parcial".

## 5. Página 2 — Categorías, comunas y cierre

| Visual | Configuración |
|---|---|
| **Segmentadores** | Los mismos de la página 1 (**Ver → Sincronizar segmentaciones** para que filtren ambas páginas) |
| **Barras horizontales** Top categorías | Eje Y: `Reclamos[categoria]`. Eje X: `Total reclamos`. Filtro de objeto visual: **N superior = 10** por `Total reclamos` |
| **Columnas** Reclamos por comuna | Eje X: `Reclamos[comuna]` (ordenar por `Total reclamos` descendente). Filtro: `comuna` no está en blanco |
| **Barras horizontales** % cerrado por categoría | Eje Y: `Reclamos[categoria]`. Eje X: `% cerrado`. Ordenar ascendente. Filtro: `Total reclamos` ≥ 5000 y `categoria` ≠ PLATAFORMA BA COLABORATIVA |
| **Columnas** % cerrado por comuna | Eje X: `Reclamos[comuna]`. Eje Y: `% cerrado`. Agregar **línea de promedio** desde el panel Analítica. Eje Y desde 0,8 |
| **Matriz** (opcional) | Filas: `Calendario[Día semana]`. Columnas: `Calendario[Mes nombre]`. Valores: `Promedio diario`. Formato condicional: escala de colores de fondo (un solo color) |

## 6. Publicar las capturas

1. Exportar cada página: **Archivo → Exportar → Exportar a PDF**, o tomar una captura de pantalla.
2. Guardar las imágenes como `reports/figures/dashboard_pagina1.png` y `reports/figures/dashboard_pagina2.png`.
3. En el `README.md` principal (sección *Dashboard*) reemplazar las imágenes de la vista previa por estas capturas
   (el bloque comentado ya tiene las líneas listas) y borrar la aclaración de "vista previa hecha con Python".
