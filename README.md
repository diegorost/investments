# Investments

Conjunto de mini-aplicaciones web relacionadas con inversiones y mercados financieros. Cada proyecto es un sitio estático (`index.html`) que consume datos en tiempo real desde un Worker de Cloudflare (`worker/`), el cual actúa como proxy hacia la API de Yahoo Finance.

## Proyectos

### investing-calculator
Calculadora de interés compuesto. Permite simular el crecimiento de una inversión a lo largo del tiempo según aportes, tasa de interés y plazo, mostrando el resultado en un gráfico (Chart.js). Es un sitio puramente estático, sin Worker asociado.

### miners-uplift
Dashboard de ETFs de empresas mineras de metales preciosos (oro y plata), como RING, AUAU, GDX, GDXJ, SLVP, SIL y SILJ. El Worker consulta a Yahoo Finance el precio actual y el máximo histórico (ATH) de cada ETF, calculando el potencial de suba ("uplift") respecto al máximo. Incluye una barra de estado fija con botones para refrescar precios (todos, solo oro, solo plata o solo ETFs) y auto-refresco cada 5 minutos durante el horario de mercado de EE.UU. (9:30-20:00 hora de Nueva York).

### price-date
Herramienta de consulta de precios históricos de un ticker en una fecha determinada. El Worker obtiene la serie de precios diarios desde Yahoo Finance para un rango de fechas y la devuelve en formato JSON para que el frontend la muestre.

### stock-exchanges
Visualización del estado de los principales mercados/índices bursátiles del mundo ("World Markets"): S&P 500, NASDAQ, Dow Jones, Russell 2000, VIX, índices de Latinoamérica (IPSA, IBOVESPA, MERVAL) y acciones individuales. El Worker trae las cotizaciones desde Yahoo Finance.

### ticker-analysis
Análisis detallado de un ticker individual: precio, nombre del instrumento y métricas calculadas a partir de la serie histórica obtenida de Yahoo Finance.

## Otras carpetas

- **archive**: Versiones anteriores en Python de los proyectos anteriores (`investing-calculator-py`, `miners-uplift-py`, `price-date-py`, `stock-exchanges-py`, `ticker-analysis-py`), reemplazadas por las versiones actuales basadas en Cloudflare Workers.
- **build**: Carpeta de salida generada automáticamente por procesos de build/empaquetado, no contiene código fuente propio.
