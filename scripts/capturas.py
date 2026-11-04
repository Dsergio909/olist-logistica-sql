"""Saca una captura PNG de cada página de tablero.pdf (el PDF que exporta Power BI).

Uso:
    pip install pypdfium2      (no necesita Pillow: el PNG se escribe con zlib)
    python scripts/capturas.py

Escribe capturas/01_logistica.png ... 04_resenas.png.
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

try:
    import pypdfium2 as pdfium
except ImportError as e:  # solo hace falta para regenerar las capturas
    raise SystemExit("Falta pypdfium2: pip install pypdfium2") from e

RAIZ = Path(__file__).resolve().parent.parent
NOMBRES = ["01_logistica", "02_vendedores", "03_clientes", "04_resenas"]


def guardar_png(bitmap, ruta: Path) -> tuple[int, int]:
    """Escribe un PNG RGB desde el bitmap BGR de pdfium, sin librerías extra."""
    ancho, alto, paso = bitmap.width, bitmap.height, bitmap.stride
    datos = bytes(bitmap.buffer)
    filas = bytearray()
    for y in range(alto):
        fila = datos[y * paso: y * paso + ancho * 3]
        rgb = bytearray(fila)
        rgb[0::3], rgb[2::3] = fila[2::3], fila[0::3]      # BGR -> RGB
        filas += bytes(1) + rgb                              # filtro 0 por fila

    def bloque(tipo: bytes, contenido: bytes) -> bytes:
        return (struct.pack(">I", len(contenido)) + tipo + contenido
                + struct.pack(">I", zlib.crc32(tipo + contenido) & 0xFFFFFFFF))

    firma = bytes([0x89]) + b"PNG" + bytes([0x0D, 0x0A, 0x1A, 0x0A])
    ruta.write_bytes(firma
                     + bloque(b"IHDR", struct.pack(">IIBBBBB", ancho, alto, 8, 2, 0, 0, 0))
                     + bloque(b"IDAT", zlib.compress(bytes(filas), 9))
                     + bloque(b"IEND", b""))
    return ancho, alto


def main() -> None:
    pdf = pdfium.PdfDocument(RAIZ / "tablero.pdf")
    if len(pdf) != len(NOMBRES):
        raise SystemExit(f"El PDF tiene {len(pdf)} páginas y esperaba {len(NOMBRES)}")
    destino = RAIZ / "capturas"
    destino.mkdir(exist_ok=True)
    for pagina, nombre in zip(pdf, NOMBRES):
        ancho = pagina.get_width()
        bitmap = pagina.render(scale=1600 / ancho, rev_byteorder=False)   # 1600 px de ancho, BGR
        w, h = guardar_png(bitmap, destino / f"{nombre}.png")
        print(f"capturas/{nombre}.png {w}x{h}")


if __name__ == "__main__":
    main()
