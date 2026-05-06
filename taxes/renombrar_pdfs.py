import os
import re
import pdfplumber

meses = {
    "1": "Enero", "2": "Febrero", "3": "Marzo", "4": "Abril",
    "5": "Mayo", "6": "Junio", "7": "Julio", "8": "Agosto",
    "9": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre"
}

tipo = input("Tipo de documento (1=Racional, 2=Vector): ").strip().lower()

if tipo in ("2", "vector"):
    carpeta = r"C:\Users\diego\OneDrive\Inversiones\Racional\Boletas Vector"
    etiqueta_fecha = "Fecha Pago"
    patron_fecha = r"Fecha\s+(?:de\s+)?Pago\b.{0,80}?(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})"
    orden_fecha = "dmy"
elif tipo in ("1", "racional"):
    carpeta = r"C:\Users\diego\OneDrive\Inversiones\Racional\Detalle Acciones Diario"
    sufijo = "Transacciones_Racional_Stocks"
    etiqueta_fecha = "Confirmation Date"
    patron_fecha = r"Confirmation Date\s*:?\s*(\d{1,2})/(\d{1,2})/(\d{4})"
    orden_fecha = "mdy"
else:
    raise ValueError("Tipo invalido. Escribe '1', '2', 'Racional' o 'Vector'.")

if not os.path.isdir(carpeta):
    raise NotADirectoryError(f"La carpeta no existe: {carpeta}")

print(f"Leyendo PDFs desde: {carpeta}")

pendientes_vector = []

for archivo in os.listdir(carpeta):
    if not archivo.lower().endswith(".pdf"):
        continue

    ruta = os.path.join(carpeta, archivo)

    try:
        with pdfplumber.open(ruta) as pdf:
            texto = ""
            for pagina in pdf.pages[:3]:
                texto += pagina.extract_text() or ""

        print(f"\n--- {archivo} ---")
        # busca cualquier linea con fecha para debug
        for linea in texto.split("\n"):
            if re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", linea):
                print(f"  fecha encontrada: {linea.strip()}")

        match = re.search(patron_fecha, texto, re.IGNORECASE | re.DOTALL)

        if match:
            if orden_fecha == "dmy":
                dia      = match.group(1).zfill(2)
                mes_num  = match.group(2)
            else:
                mes_num  = match.group(1)
                dia      = match.group(2).zfill(2)
            año      = match.group(3)
            if len(año) == 2:
                año = "20" + año
            mes_key = str(int(mes_num))
            mes_num = mes_key.zfill(2)
            mes_name = meses.get(mes_key, mes_key)

            if tipo in ("2", "vector"):
                match_operacion = re.search(r"\b(Compra|Venta)\b", texto, re.IGNORECASE)
                if not match_operacion:
                    print("  ✗ No encontré Compra/Venta — mostrando primeras 300 chars:")
                    print(texto[:300])
                    continue

                operacion = match_operacion.group(1).capitalize()
                nombre_base = f"{año}-{mes_num}-{mes_name}-{dia}-{operacion}_USD"
                pendientes_vector.append((ruta, nombre_base))
                continue
            else:
                nuevo_nombre = f"{año}-{mes_num}-{mes_name}-{dia}_{sufijo}.pdf"
            nueva_ruta   = os.path.join(carpeta, nuevo_nombre)

            if os.path.exists(nueva_ruta) and nueva_ruta != ruta:
                print(f"  ⚠ Ya existe: {nuevo_nombre}")
            else:
                os.rename(ruta, nueva_ruta)
                print(f"  ✓ → {nuevo_nombre}")
        else:
            print(f"  ✗ No encontré {etiqueta_fecha} — mostrando primeras 300 chars:")
            print(texto[:300])

    except Exception as e:
        print(f"✗ Error en {archivo}: {e}")

if pendientes_vector:
    totales = {}
    usados = {}

    for _, nombre_base in pendientes_vector:
        totales[nombre_base] = totales.get(nombre_base, 0) + 1

    for ruta, nombre_base in pendientes_vector:
        usados[nombre_base] = usados.get(nombre_base, 0) + 1

        if totales[nombre_base] > 1:
            nuevo_nombre = f"{nombre_base}-{usados[nombre_base]}.pdf"
        else:
            nuevo_nombre = f"{nombre_base}.pdf"

        nueva_ruta = os.path.join(carpeta, nuevo_nombre)

        if os.path.exists(nueva_ruta) and nueva_ruta != ruta:
            print(f"  ⚠ Ya existe: {nuevo_nombre}")
        else:
            os.rename(ruta, nueva_ruta)
            print(f"  ✓ → {nuevo_nombre}")
