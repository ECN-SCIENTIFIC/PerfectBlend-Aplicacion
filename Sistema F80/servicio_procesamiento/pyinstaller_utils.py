import sys
from pathlib import Path

def resource_path(relative_path: str) -> str:
    """
    Genera la ruta absoluta a un recurso para que funcione tanto en
    desarrollo como en una aplicación empaquetada (ej. PyInstaller).
    """
    if getattr(sys, 'frozen', False):
        # Entorno empaquetado: la ruta base es el directorio del ejecutable.
        application_path = Path(sys.executable).parent
    else:
        # Entorno de desarrollo: la ruta base es el directorio del script.
        application_path = Path(__file__).resolve().parent

    # Se asume que la raíz del proyecto está un nivel por encima del script/ejecutable.
    base_path = application_path.parent

    # Construye y devuelve la ruta completa al recurso.
    return str(base_path / "shared_resources" / relative_path)