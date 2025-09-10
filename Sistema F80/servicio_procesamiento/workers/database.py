import json
import psycopg2
import base64
from celery_app import celery_app
from pathlib import Path
import cv2
import numpy as np
from pyinstaller_utils import resource_path
from ..logger import setup_worker_logging
logger = setup_worker_logging("database_tasks", "logs/db.log")
CONFIG = None

def load_resources():
    """Carga la configuración desde el JSON."""
    global CONFIG
    if CONFIG is None:
        try:
            config_path = resource_path("configs/db_config.json")
            with open(config_path, 'r') as f:
                CONFIG = json.load(f)
            logger.info("Se cargo el config de la base de datos correctamente")
        except Exception as e:
            logger.error(f"Error cargando el config de la base de datos: {e}")
            CONFIG = {}

@celery_app.task(name="workers.database.save_to_db")
def save_to_db(results):
    """
        Se conecta a la DB y guarda los resultados que recibe como argumento
    """

    load_resources()
    if not CONFIG:
        return {"error": "Modulo de base de datos no configurado."}
    
    og_image_bytes = base64.b64decode(results["img_original"])
    inference_bytes = base64.b64decode(results["img_result"])
    frame = cv2.imdecode(np.frombuffer(og_image_bytes, np.uint8), cv2.IMREAD_COLOR)
    frame_segmented = cv2.imdecode(np.frombuffer(inference_bytes, np.uint8), cv2.IMREAD_COLOR)
    capture_time_safe = results.get("capture_time", "unknown_time").replace(":", "-").replace("+", "_")
    filename_seg = f"img_{capture_time_safe}_camera_{results.get('cam_id')}_segmented.jpeg"
    filename_og = f"img_{capture_time_safe}_camera_{results.get('cam_id')}_original.jpeg"
    directorio = Path(CONFIG.get("imgs_route"))
    s_seg = cv2.imwrite(directorio / filename_seg, frame_segmented)
    s_og = cv2.imwrite(directorio / filename_og, frame)
    if s_seg and s_og:
        logger.info(f"[{results.get["cam_id"]}] Se guardaron las imagenes correctamente.")

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
        db_keys = ["host", "port", "database", "user", "password"]
        db_connection_params = {key: CONFIG[key] for key in db_keys if key in CONFIG}
        conn = psycopg2.connect(**db_connection_params)
        cur = conn.cursor()
        sql = """
            INSERT INTO results (
                timestamp, camera_id, f10, f20, f30, f40, f50, f60, f70, f80, f90, f100, f10_ajst, f20_ajst, f30_ajst, f40_ajst,
                f50_ajst, f60_ajst, f70_ajst, f80_ajst, f90_ajst, f100_ajst, simulation, og_img_path, seg_img_path
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        data_to_insert = (
            results.get("capture_time"),
            results.get("cam_id"),
            *list(Fs_formateado.values()),
            *list(Fs_ajst_formateado.values()),
            results["sim"],
            str(directorio / filename_og),
            str(directorio / filename_seg)
        )
        #print(data_to_insert)
        cur.execute(sql, data_to_insert)
        conn.commit()
        cur.close()
        logger.info(f"[{results.get("cam_id")}] Resultado guardado en la base de datos para la camara: {results.get('cam_id')}")

    except Exception as error:
        logger.error(f"[{results.get("cam_id")}] Error conectando o guardando en PostgreSQL: {error}")
        if conn is not None:
            conn.close()
        return {"status": "Database save attempt failed."}
    finally:
        if conn is not None:
            conn.close()

    return {"status": "Database save attempt complete."}

