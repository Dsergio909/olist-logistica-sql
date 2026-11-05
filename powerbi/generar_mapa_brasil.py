"""Dibuja el contorno de Brasil y sus 27 estados como imagen de fondo del mapa de burbujas.

Uso:
    python powerbi/generar_mapa_brasil.py                 # usa powerbi/brasil_estados.json
    python powerbi/generar_mapa_brasil.py --desde RUTA    # rehace brasil_estados.json desde el
                                                          # GeoJSON de Natural Earth (admin-1, 50m)

- Fuente del contorno: Natural Earth, «Admin 1 – States, Provinces» 1:50m, dominio público
  (https://www.naturalearthdata.com). Solo se guardan los 27 estados de Brasil, con 3 decimales.
- La imagen usa exactamente los mismos límites de longitud y latitud que los ejes del mapa de
  burbujas (LON y LAT abajo), así que cada burbuja cae sobre su estado.
- Se dibuja con Python puro (sin librerías): relleno por líneas de barrido, bordes y suavizado
  dibujando al doble de tamaño y reduciendo.
"""
from __future__ import annotations

import json
import math
import struct
import sys
import zlib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CONTORNO = RAIZ / "powerbi" / "brasil_estados.json"
SALIDA = RAIZ / "powerbi" / "mapa_brasil.png"

# Límites del mapa (los mismos que usa generar_pbip.py en los ejes del gráfico)
LON = (-75.0, -32.0)
LAT = (-36.0, 9.0)
COS = math.cos(math.radians(-15))          # corrección de escala a la latitud media de Brasil
ANCHO = 1040
ALTO = round(ANCHO * (LAT[1] - LAT[0]) / ((LON[1] - LON[0]) * COS))
ESCALA = 2                                  # se dibuja al doble y se reduce (suavizado)

FONDO = (255, 255, 255)
PAIS = (238, 242, 239)                      # relleno: gris verdoso muy claro
ESTADOS = (190, 199, 194)                   # líneas entre estados
BORDE = (120, 132, 126)                     # borde del país


def extraer(geojson: Path) -> None:
    """Guarda solo Brasil, redondeado, para que el repo no cargue el mundo entero."""
    datos = json.loads(geojson.read_text(encoding="utf-8"))
    estados = {}
    for f in datos["features"]:
        p = f["properties"]
        if p.get("adm0_a3") != "BRA":
            continue
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        estados[p["postal"]] = [[[[round(x, 3), round(y, 3)] for x, y in anillo] for anillo in poly]
                                for poly in polys]
    assert len(estados) == 27, f"Esperaba 27 estados y hay {len(estados)}"
    salida = {"fuente": "Natural Earth, Admin 1 States/Provinces 1:50m (dominio público)",
              "estados": dict(sorted(estados.items()))}
    CONTORNO.write_text(json.dumps(salida, separators=(",", ":")), encoding="utf-8", newline="\n")
    print(f"{CONTORNO.relative_to(RAIZ)}: 27 estados, {CONTORNO.stat().st_size // 1024} KB")


def a_pixel(lon: float, lat: float, w: int, h: int) -> tuple[float, float]:
    x = (lon - LON[0]) / (LON[1] - LON[0]) * w
    y = (LAT[1] - lat) / (LAT[1] - LAT[0]) * h
    return x, y


def rellenar(img: bytearray, w: int, h: int, anillos: list, color: tuple) -> None:
    """Relleno par-impar por líneas de barrido (sirve para polígonos con huecos)."""
    lados = []
    for anillo in anillos:
        pts = [a_pixel(x, y, w, h) for x, y in anillo]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
            if y1 != y2:
                lados.append((x1, y1, x2, y2))
    if not lados:
        return
    ymin = max(0, int(min(min(l[1], l[3]) for l in lados)))
    ymax = min(h - 1, int(max(max(l[1], l[3]) for l in lados)) + 1)
    for y in range(ymin, ymax + 1):
        yc = y + 0.5
        cortes = sorted(x1 + (yc - y1) * (x2 - x1) / (y2 - y1)
                        for x1, y1, x2, y2 in lados if (y1 <= yc < y2) or (y2 <= yc < y1))
        for a, b in zip(cortes[0::2], cortes[1::2]):
            for x in range(max(0, int(a + 0.5)), min(w, int(b + 0.5))):
                i = (y * w + x) * 3
                img[i:i + 3] = bytes(color)


def linea(img: bytearray, w: int, h: int, p1, p2, color: tuple, grosor: int) -> None:
    x1, y1 = p1
    x2, y2 = p2
    pasos = int(max(abs(x2 - x1), abs(y2 - y1))) + 1
    r = grosor // 2
    for k in range(pasos + 1):
        t = k / pasos
        cx, cy = int(x1 + (x2 - x1) * t), int(y1 + (y2 - y1) * t)
        for dy in range(-r, grosor - r):
            for dx in range(-r, grosor - r):
                x, y = cx + dx, cy + dy
                if 0 <= x < w and 0 <= y < h:
                    i = (y * w + x) * 3
                    img[i:i + 3] = bytes(color)


def guardar_png(img: bytes, w: int, h: int, ruta: Path) -> None:
    filas = b"".join(b"\x00" + img[y * w * 3:(y + 1) * w * 3] for y in range(h))

    def bloque(tipo: bytes, datos: bytes) -> bytes:
        return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF)

    ruta.write_bytes(bytes([0x89]) + b"PNG" + bytes([13, 10, 26, 10])
                     + bloque(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + bloque(b"IDAT", zlib.compress(filas, 9)) + bloque(b"IEND", b""))


def dibujar() -> None:
    estados = json.loads(CONTORNO.read_text(encoding="utf-8"))["estados"]
    w, h = ANCHO * ESCALA, ALTO * ESCALA
    img = bytearray(bytes(FONDO) * (w * h))
    for polys in estados.values():                       # 1. relleno del país
        for poly in polys:
            rellenar(img, w, h, poly, PAIS)
    for polys in estados.values():                       # 2. líneas entre estados
        for poly in polys:
            pts = [a_pixel(x, y, w, h) for x, y in poly[0]]
            for p1, p2 in zip(pts, pts[1:]):
                linea(img, w, h, p1, p2, ESTADOS, 2 * ESCALA - 1)
    # 3. borde del país: los lados que no comparte ningún otro estado
    conteo: dict = {}
    for polys in estados.values():
        for poly in polys:
            anillo = [tuple(p) for p in poly[0]]
            for a, b in zip(anillo, anillo[1:]):
                clave = (a, b) if a < b else (b, a)
                conteo[clave] = conteo.get(clave, 0) + 1
    for (a, b), n in conteo.items():
        if n == 1:
            linea(img, w, h, a_pixel(*a, w, h), a_pixel(*b, w, h), BORDE, 3 * ESCALA)
    # 4. reducir al tamaño final (promedio de cada bloque de ESCALA x ESCALA)
    final = bytearray(ANCHO * ALTO * 3)
    n = ESCALA * ESCALA
    for y in range(ALTO):
        for x in range(ANCHO):
            s = [0, 0, 0]
            for dy in range(ESCALA):
                base = ((y * ESCALA + dy) * w + x * ESCALA) * 3
                for dx in range(ESCALA):
                    i = base + dx * 3
                    s[0] += img[i]
                    s[1] += img[i + 1]
                    s[2] += img[i + 2]
            j = (y * ANCHO + x) * 3
            final[j:j + 3] = bytes((s[0] // n, s[1] // n, s[2] // n))
    guardar_png(bytes(final), ANCHO, ALTO, SALIDA)
    print(f"{SALIDA.relative_to(RAIZ)}: {ANCHO}x{ALTO}, longitud {LON}, latitud {LAT}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--desde" in sys.argv:
        extraer(Path(sys.argv[sys.argv.index("--desde") + 1]))
    dibujar()
