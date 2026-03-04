from __future__ import annotations
import re
from typing import Optional, Dict, Any, Tuple

AI_VERSION = "v0.2"

PREFIX_MAP: Dict[str, Tuple[str, str, Optional[str]]] = {
    # prefix : (category, subcategory, brand)
    "60AR": ("Sanitarios", "WC Suite / Repuestos", "Ares"),
    "60AU": ("Sanitarios", "Lavamanos / Pedestales", "Aura"),
    "60PB": ("Muebles", "Mueble Vanitorio", None),
    "60PZ": ("Muebles", "Cubierta Vanitorio", None),
    "66ES": ("Accesorios", "Espejo", None),
    "65PB": ("Ducha", "Mampara", None),
    "21BE": ("Accesorios", "Set / Barras / Perchas", "Benton"),
    "21ST": ("Ducha", "Columna de Ducha", "Venti"),
    "20AA": ("Grifería", "Monomando (Línea Arona)", "Arona"),
    "20VT": ("Grifería", "Monomando (Línea Vermont)", "Vermont"),
    "20PL": ("Grifería", "Llaves (Plumber)", "Plumber"),
    "20SX": ("Grifería", "Monomando (Sibel)", "Sibel"),
    "20ZZ": ("Grifería", "Monomando (Arezzo)", "Arezzo"),
    "22PB": ("Ducha", "Desagüe / Receptáculo", None),
}

KEYWORDS = [
    (r"\b(taza\s*wc|estanque\s*wc|asiento\s*y\s*tapa)\b", ("Sanitarios", "WC Suite / Repuestos")),
    (r"\b(lavamanos|lavatorio)\b", ("Sanitarios", "Lavamanos / Lavatorio")),
    (r"\b(mueble\s+\w+\s*60x46|mueble\s+vanitorio|vanitorio)\b", ("Muebles", "Mueble Vanitorio")),
    (r"\b(cubierta\s+vanitorio)\b", ("Muebles", "Cubierta Vanitorio")),
    (r"\b(mampara|corredera\s+\d+\s*x\s*\d+)\b", ("Ducha", "Mampara")),
    (r"\b(columna\s+de\s+ducha)\b", ("Ducha", "Columna de Ducha")),
    (r"\b(monomando)\b", ("Grifería", "Monomando")),
    (r"\b(llave\s+lavatorio|llave\s+lavaplato|combinacion\s+lavaplato)\b", ("Grifería", "Llaves")),
    (r"\b(espejo)\b", ("Accesorios", "Espejo")),
    (r"\b(daño\s+en\s+ruta|aver[ií]a|merma)\b", ("No Merch", "Ajuste/Incidencia")),
]

BRANDS = ["Ares","Aura","Arona","Vermont","Sibel","Arezzo","Benton","Plumber","Zoé","Amélie","Renèe","Óptima"]

DIM_RE = re.compile(r"(\d{2,3})\s*x\s*(\d{2,3})(?:\s*x\s*(\d{2,3}))?", re.I)
COLORS = ["Cromo","Gris Grafito","Ulmo","Acácia","Inox Satinado"]
MATERIALS = ["Inox","Urea","P.P.","Acrílico","Urea Soft Close","Soft Close"]

def _prefix(code: Optional[str]) -> Optional[str]:
    if not code: return None
    s = str(code).strip().upper()
    m = re.match(r"([A-Z0-9]{4})", s)
    return m.group(1) if m else None

def _extract_attrs(text: str) -> Dict[str, Any]:
    attrs: Dict[str, Any] = {}
    if not text:
        return attrs
    dm = DIM_RE.search(text)
    if dm:
        w, h, d = dm.group(1), dm.group(2), dm.group(3)
        attrs["dimension"] = {"w": int(w), "h": int(h), **({"d": int(d)} if d else {})}
    for c in COLORS:
        if c.lower() in text.lower():
            attrs["color"] = c; break
    for m in MATERIALS:
        if m.lower() in text.lower():
            attrs["material"] = m; break
    return attrs

def classify(code: Optional[str], name: str, desc: Optional[str]) -> Dict[str, Any]:
    t = " ".join([p for p in [name or "", desc or ""] if p]).strip()
    px = _prefix(code)
    base_cat = (None, None, None)
    conf = 0.40

    # 1) por prefijo
    if px and px in PREFIX_MAP:
        base_cat = PREFIX_MAP[px]
        conf += 0.40

    # 2) por keywords
    for rx, (cat, sub) in KEYWORDS:
        if re.search(rx, t, re.I):
            # si no había prefijo, setea; si había, refuerza subcat si está vacía
            if base_cat[0] is None:
                base_cat = (cat, sub, base_cat[2])
            else:
                # armoniza subcategoría si no definida
                if base_cat[1] is None:
                    base_cat = (base_cat[0], sub, base_cat[2])
            conf += 0.15
            break

    # 3) marca
    brand = None
    for b in BRANDS:
        if re.search(rf"\b{re.escape(b)}\b", t, re.I):
            brand = b
            conf += 0.05
            break

    # 4) atributos
    attrs = _extract_attrs(t)
    if "color" in attrs: conf += 0.02
    if "material" in attrs: conf += 0.02
    conf = round(min(conf, 0.99), 2)

    # Caída controlada si no clasificó
    cat, sub, pre_brand = base_cat
    if not cat:
        cat, sub = "Sin Clasificar", None

    # Excepción: “DAÑO EN RUTA” → No Merch
    if re.search(r"\bdaño\s+en\s+ruta\b", t, re.I) or code == ".":
        cat, sub, brand = "No Merch", "Ajuste/Incidencia", None
        conf = 0.95

    # Si el prefijo traía “brand” úsalo por defecto
    brand = brand or pre_brand

    return {
        "ai_category": cat,
        "ai_subcategory": sub,
        "ai_brand": brand,
        "ai_attrs": attrs or None,
        "ai_confidence": conf,
        "ai_version": AI_VERSION,
    }
