-- Consultas de las preguntas de negocio sobre la tabla `reclamos` (DuckDB).
-- Cada consulta empieza con una línea "name" que la identifica; src/build_db.py las ejecuta en orden.
-- Datos: SUACI / BA Colaborativa, 01/01/2024 a 15/10/2026 (octubre 2026 es un mes parcial).


-- name: p1_evolucion_mensual
-- P1. ¿Cuántos reclamos entran por mes y cómo evoluciona el volumen?
-- Variación contra el mes anterior y contra el mismo mes del año anterior (funciones de ventana LAG).
-- Ojo: marzo-abril 2025 tiene un pico de ~237 mil consultas por demoras en expedientes de catastro
-- (DESARROLLO URBANO) y desde octubre 2025 aparecen los reportes automáticos de PLATAFORMA BA COLABORATIVA.
WITH mensual AS (
    SELECT
        date_trunc('month', fecha_ingreso) AS mes,
        count(*) AS reclamos
    FROM reclamos
    GROUP BY 1
)
SELECT
    strftime(mes, '%Y-%m') AS mes,
    reclamos,
    round(100.0 * (reclamos - lag(reclamos) OVER (ORDER BY mes))
          / lag(reclamos) OVER (ORDER BY mes), 1) AS var_mensual_pct,
    round(100.0 * (reclamos - lag(reclamos, 12) OVER (ORDER BY mes))
          / lag(reclamos, 12) OVER (ORDER BY mes), 1) AS var_interanual_pct,
    CASE WHEN mes = (SELECT max(mes) FROM mensual) THEN 'parcial' ELSE 'completo' END AS estado_mes
FROM mensual
ORDER BY mes;


-- name: p2a_top_categorias
-- P2a. ¿Qué categorías concentran más reclamos? Top 10 con su peso sobre el total.
SELECT
    categoria,
    count(*) AS reclamos,
    round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS pct_total,
    round(100.0 * sum(count(*)) OVER (ORDER BY count(*) DESC)
          / sum(count(*)) OVER (), 1) AS pct_acumulado
FROM reclamos
GROUP BY categoria
ORDER BY reclamos DESC
LIMIT 10;


-- name: p2b_reclamos_por_comuna
-- P2b. ¿Qué comunas concentran más reclamos? Solo reclamos con ubicación (~74 %).
SELECT
    comuna,
    count(*) AS reclamos,
    round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS pct_con_ubicacion,
    rank() OVER (ORDER BY count(*) DESC) AS ranking
FROM reclamos
WHERE comuna IS NOT NULL
GROUP BY comuna
ORDER BY ranking;


-- name: p3_tasa_cierre_categoria
-- P3. ¿Qué tasa de cierre (% cerrado) tiene cada categoría?
-- Los reclamos de 2026 son recientes y tienen más chance de seguir abiertos,
-- por eso se muestra también la tasa solo sobre 2024-2025.
-- Se consideran categorías con al menos 5.000 reclamos.
-- Se excluye PLATAFORMA BA COLABORATIVA: son reportes automáticos de Boti
-- ("Demanda insatisfecha - Mis profesionales") que nunca se cierran y no son reclamos a resolver.
SELECT
    categoria,
    count(*) AS reclamos,
    round(100.0 * avg(CASE WHEN cerrado THEN 1 ELSE 0 END), 1) AS tasa_cierre_pct,
    round(100.0 * avg(CASE WHEN cerrado THEN 1 ELSE 0 END) FILTER (WHERE anio < 2026), 1) AS tasa_cierre_2024_2025_pct,
    sum(CASE WHEN NOT cerrado THEN 1 ELSE 0 END) AS abiertos
FROM reclamos
WHERE categoria <> 'PLATAFORMA BA COLABORATIVA'
GROUP BY categoria
HAVING count(*) >= 5000
ORDER BY tasa_cierre_pct;


-- name: p4_tasa_cierre_comuna
-- P4. ¿Qué tasa de cierre (% cerrado) tiene cada comuna? Se compara con el promedio de la Ciudad.
WITH por_comuna AS (
    SELECT
        comuna,
        count(*) AS reclamos,
        avg(CASE WHEN cerrado THEN 1 ELSE 0 END) AS tasa
    FROM reclamos
    WHERE comuna IS NOT NULL
    GROUP BY comuna
)
SELECT
    comuna,
    reclamos,
    round(100 * tasa, 1) AS tasa_cierre_pct,
    round(100 * (tasa - avg(tasa) OVER ()), 1) AS dif_vs_promedio_pp,
    CASE
        WHEN tasa >= avg(tasa) OVER () + 0.02 THEN 'por encima'
        WHEN tasa <= avg(tasa) OVER () - 0.02 THEN 'por debajo'
        ELSE 'en el promedio'
    END AS comparacion
FROM por_comuna
ORDER BY tasa_cierre_pct;


-- name: p5a_estacionalidad_dia_semana
-- P5a. ¿Hay estacionalidad por día de la semana? Promedio de reclamos por día.
WITH por_dia AS (
    SELECT fecha_ingreso, dia_semana_num, dia_semana, count(*) AS reclamos
    FROM reclamos
    GROUP BY ALL
)
SELECT
    dia_semana,
    round(avg(reclamos)) AS promedio_diario,
    round(100.0 * avg(reclamos) / (SELECT avg(reclamos) FROM por_dia) - 100, 1) AS dif_vs_dia_promedio_pct
FROM por_dia
GROUP BY dia_semana_num, dia_semana
ORDER BY dia_semana_num;


-- name: p5b_estacionalidad_mes
-- P5b. ¿Hay estacionalidad por mes? Solo años completos (2024 y 2025).
SELECT
    mes,
    sum(CASE WHEN anio = 2024 THEN 1 ELSE 0 END) AS reclamos_2024,
    sum(CASE WHEN anio = 2025 THEN 1 ELSE 0 END) AS reclamos_2025,
    round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS pct_del_bienio
FROM reclamos
WHERE anio IN (2024, 2025)
GROUP BY mes
ORDER BY mes;
