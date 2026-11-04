"""Nada privado en los archivos del repo: rutas del PC, correos, claves ni teléfonos."""
from __future__ import annotations

import re

import pytest

from conftest import RAIZ

IGNORAR = {".git", ".venv", "datos_crudos", "__pycache__", ".pytest_cache"}
EXTENSIONES = {".md", ".py", ".sql", ".yml", ".yaml", ".json", ".csv", ".txt", ".tmdl", ".pbir",
               ".pbism", ".pbip", ".m", ".gitignore", ".toml", ".ini"}

PATRONES = {
    "ruta de Windows con usuario": re.compile(r"[A-Za-z]:[\\/]+Users[\\/]", re.I),
    "ruta de Google Drive": re.compile(r"Mi\s+unidad", re.I),
    "correo": re.compile(r"[\w.+-]+@[\w-]+\.(com|co|org|net|io)\b", re.I),
    "token de GitHub": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    "clave de API": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "teléfono de Colombia": re.compile(r"(\+57\s?)?\b3\d{2}[\s.-]?\d{3}[\s.-]?\d{4}\b"),
}
# Excepciones conocidas y revisadas a mano.
PERMITIDO = {
    "correo": {"noreply@anthropic.com"},
}


def archivos_de_texto():
    for ruta in RAIZ.rglob("*"):
        if any(p in IGNORAR for p in ruta.relative_to(RAIZ).parts):
            continue
        if ruta.is_file() and (ruta.suffix.lower() in EXTENSIONES or ruta.name in EXTENSIONES):
            if ruta.parent.name == "salidas" and ruta.name == "r_vendedores.csv":
                continue  # solo ids anónimos de Olist; se revisa abajo aparte
            yield ruta


@pytest.mark.parametrize("nombre,patron", PATRONES.items())
def test_sin_datos_privados(nombre, patron):
    encontrados = []
    for ruta in archivos_de_texto():
        texto = ruta.read_text(encoding="utf-8", errors="ignore")
        for m in patron.finditer(texto):
            if m.group(0) not in PERMITIDO.get(nombre, set()):
                encontrados.append(f"{ruta.relative_to(RAIZ)}: {m.group(0)}")
    assert not encontrados, f"Encontré {nombre}: {encontrados[:5]}"


def test_vendedores_solo_ids_anonimos():
    lineas = (RAIZ / "salidas" / "r_vendedores.csv").read_text(encoding="utf-8").splitlines()[1:]
    assert all(re.fullmatch(r"[0-9a-f]{32}", l.split(",")[0]) for l in lineas)


def test_gitignore_protege_lo_local():
    texto = (RAIZ / ".gitignore").read_text(encoding="utf-8")
    for patron in ("datos_crudos/", ".venv/", ".env"):
        assert patron in texto
