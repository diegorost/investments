# Investments

Conjunto de mini-aplicaciones web relacionadas con inversiones y mercados financieros. Cada proyecto es un sitio estático (`index.html`); los que necesitan datos en vivo incluyen su propio Worker de Cloudflare en la subcarpeta `worker/` (`index.js` + `wrangler.toml`), que actúa como proxy hacia la API de Yahoo Finance. Los Workers son independientes por proyecto (`miners-uplift`, `price-date`, `stock-exchanges` y `ticker-analysis`); `investing-calculator` no tiene Worker.

## Proyectos

### investing-calculator
Calculadora de interés compuesto. Permite simular el crecimiento de una inversión a lo largo del tiempo según aportes, tasa de interés y plazo, mostrando el resultado en un gráfico (Chart.js). Es un sitio puramente estático, sin Worker asociado. Incluye toggle de tema claro/oscuro.

### miners-uplift
Dashboard de ETFs de empresas mineras de metales preciosos (oro y plata), como RING, AUAU, GDX, GDXJ, SLVP, SIL y SILJ. El Worker expone dos endpoints sobre Yahoo Finance: `/api/etf-prices` (precio actual, ATH y % bajo el máximo de cada ETF) y `/api/stock-prices?tickers=...` (mismos datos en lote para los tickers individuales de cada holding, hasta 50 por llamada). El frontend fusiona los precios en `knownData` y re-renderiza las tablas. Incluye una barra de estado fija con botones para refrescar precios (todos, solo oro, solo plata o solo ETFs); "Refresh All" también actualiza las holdings. Al cargar la página se ejecuta un `refreshEtfs('all')` y, durante el horario de mercado de EE.UU. (9:30-20:00 hora de Nueva York), un auto-refresco unificado cada 15 minutos que actualiza tanto los ETFs como las holdings.

### price-date
Herramienta de consulta de precios históricos de un ticker en una fecha determinada. El Worker obtiene la serie de precios diarios desde Yahoo Finance para un rango de fechas y la devuelve en formato JSON para que el frontend la muestre.

### stock-exchanges
Visualización del estado de los principales mercados/índices bursátiles del mundo ("World Markets"): S&P 500, NASDAQ, Dow Jones, Russell 2000, VIX, forex, futuros/metales, mineras, una sección Tech (ETFs tecnológicos y apalancados) y acciones chilenas seleccionadas. El Worker trae las cotizaciones desde Yahoo Finance. El frontend organiza las secciones en un layout de 3 columnas con drag-and-drop, cuyo orden se persiste en `localStorage`, e incluye toggle de tema claro/oscuro.

### ticker-analysis
Análisis detallado de un ticker individual: precio, nombre del instrumento y métricas calculadas a partir de la serie histórica obtenida de Yahoo Finance.

## Otras carpetas

- **archive**: Versiones anteriores en Python de los proyectos anteriores (`investing-calculator-py`, `miners-uplift-py`, `price-date-py`, `stock-exchanges-py`, `ticker-analysis-py`), reemplazadas por las versiones actuales basadas en Cloudflare Workers.
