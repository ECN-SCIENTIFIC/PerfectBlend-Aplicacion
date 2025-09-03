import json
import psycopg2
from celery_app import celery_app
from pyinstaller_utils import resource_path
CONFIG = None

def load_resources():
    """Carga la configuración desde el JSON."""
    global CONFIG
    if CONFIG is None:
        try:
            config_path = resource_path("configs/db_config.json")
            with open(config_path, 'r') as f:
                CONFIG = json.load(f)
            print("Se cargo el config de la base de datos correctamente")
        except Exception as e:
            print(f"Error cargando el config de la base de datos: {e}")
            CONFIG = {}

@celery_app.task(name="workers.database.save_to_db")
def save_to_db(results):
    """
        Se conecta a la DB y guarda los resultados que recibe como argumento
    """

    load_resources()
    if not CONFIG:
        return {"error": "Modulo de base de datos no configurado."}
    
    fs_values = results.get("Fs", [])
    Fs_formateado = {
        "f10": fs_values[0] if len(fs_values) > 0 else None,
        "f20": fs_values[1] if len(fs_values) > 1 else None,
        "f30": fs_values[2] if len(fs_values) > 2 else None,
        "f40": fs_values[3] if len(fs_values) > 3 else None,
        "f50": fs_values[4] if len(fs_values) > 4 else None,
        "f60": fs_values[5] if len(fs_values) > 5 else None,
        "f70": fs_values[6] if len(fs_values) > 6 else None,
        "f80": fs_values[7] if len(fs_values) > 7 else None,
        "f90": fs_values[8] if len(fs_values) > 8 else None,
        "f100": fs_values[9] if len(fs_values) > 9 else None,
    }

    fs_ajst_values = results.get("Fs_ajust", [])
    Fs_ajst_formateado = {
        "f10": fs_ajst_values[0] if len(fs_ajst_values) > 0 else None,
        "f20": fs_ajst_values[1] if len(fs_ajst_values) > 1 else None,
        "f30": fs_ajst_values[2] if len(fs_ajst_values) > 2 else None,
        "f40": fs_ajst_values[3] if len(fs_ajst_values) > 3 else None,
        "f50": fs_ajst_values[4] if len(fs_ajst_values) > 4 else None,
        "f60": fs_ajst_values[5] if len(fs_ajst_values) > 5 else None,
        "f70": fs_ajst_values[6] if len(fs_ajst_values) > 6 else None,
        "f80": fs_ajst_values[7] if len(fs_ajst_values) > 7 else None,
        "f90": fs_ajst_values[8] if len(fs_ajst_values) > 8 else None,
        "f100": fs_ajst_values[9] if len(fs_ajst_values) > 9 else None,
    }
    conn = None
    try:
        conn = psycopg2.connect(**CONFIG)
        cur = conn.cursor()
        sql = """
            INSERT INTO results (
                timestamp, camera_id, f10, f20, f30, f40, f50, f60, f70, f80, f90, f100, f10_ajst, f20_ajst, f30_ajst, f40_ajst,
                f50_ajst, f60_ajst, f70_ajst, f80_ajst, f90_ajst, f100_ajst, simulation
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        data_to_insert = (
            results.get("capture_time"),
            results.get("cam_id"),
            *list(Fs_formateado.values()),
            *list(Fs_ajst_formateado.values()),
            results["sim"]
        )
        print(data_to_insert)
        cur.execute(sql, data_to_insert)
        conn.commit()
        cur.close()
        print(f"Resultado guardado en la base de datos para la camara: {results.get('cam_id')}")

    except Exception as error:
        print(f"Error conectando o guardando en PostgreSQL: {error}")
        if conn is not None:
            conn.close()
        return {"status": "Database save attempt failed."}
    finally:
        if conn is not None:
            conn.close()

    return {"status": "Database save attempt complete."}

