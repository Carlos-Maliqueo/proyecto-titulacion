from lxml import etree
from app.core.config import settings
import os

def validate_with_xsd(xml_path: str, xsd_path: str) -> list[str]:
    schema_doc = etree.parse(xsd_path)
    schema = etree.XMLSchema(schema_doc)
    parser = etree.XMLParser(schema=schema)
    try:
        etree.parse(xml_path, parser)
        return []
    except etree.XMLSyntaxError as e:
        return [str(err) for err in e.error_log]

def pick_xsd_path_for_xml(xml_path: str) -> str | None:
    """Devuelve el XSD a usar según el schemaLocation del XML."""
    try:
        with open(xml_path, "rb") as f:
            head = f.read(4096).decode("utf-8", "ignore")
    except Exception:
        return None

    if "EnvioBOLETA_v11.xsd" in head:
        return os.path.join(settings.SII_XSD_DIR, settings.SII_XSD_BOLETA)
    if "EnvioDTE_v10.xsd" in head:
        return os.path.join(settings.SII_XSD_DIR, settings.SII_XSD_DTE)

    return None
