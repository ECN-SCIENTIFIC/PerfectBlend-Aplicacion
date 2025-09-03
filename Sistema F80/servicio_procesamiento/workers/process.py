import time
import json
import numpy as np
import pandas as pd
from celery_app import celery_app
from scipy.interpolate import interp1d
import redis 
from pyinstaller_utils import resource_path
CONFIG = None
REDIS_CLIENT = None

from .database import save_to_db

def load_resources():
    """
    Carga la configuración del proceso especifico
    """
    global CONFIG, REDIS_CLIENT
    
    # Load config only once
    if CONFIG is None:
        try:
            config_file = resource_path("configs/process_config.json")
            with open(config_file, 'r') as f:
                CONFIG = json.load(f)
            print("Se cargo el config del procesamiento correctamente")
        except Exception as e:
            print(f"Error cargando el config del procesamiento: {e}")
            CONFIG = {} # Prevent retrying on failure
    if REDIS_CLIENT is None:
        try:
            # Conexión a Redis para el historial
            REDIS_CLIENT = redis.Redis(host='localhost', port=6379, db=0)
            REDIS_CLIENT.ping()
            print("Conexión a Redis para historial establecida.")
        except Exception as e:
            print(f"Error conectando a Redis para historial: {e}")
            REDIS_CLIENT = None
    
@celery_app.task(name="workers.process.process_granulometry")
def process_granulometry(camera_id: str, inference_data: dict):
    
    """
        Recibe los datos de la inferencia y los procesa. Por ahora nada mas imprime los resultados. Los datos recibidos son:
        results = {
            "img_result": image_data_string,
            "area_ar": area_ar,
            "detections": detections
        }
    """
    load_resources()
    if not CONFIG or not REDIS_CLIENT:
        return {"status": "Fallo: No se cargaron los recursos (config/redis)."}

    try:
        history_key = f"history:{camera_id}"
        window_size = CONFIG.get("window_size", 1)

        new_data_json = json.dumps(inference_data["area_ar"])
        REDIS_CLIENT.lpush(history_key, new_data_json)
        
        

        current_size = REDIS_CLIENT.llen(history_key)
        
        if current_size < window_size:
            print(f"Historial para {camera_id} tiene {current_size}/{window_size} mediciones. Esperando más datos.")
            return {"status": f"Acumulando datos para {camera_id}"}
        
        REDIS_CLIENT.ltrim(history_key, 0, window_size - 1)
        print(f"Cola para {camera_id} llena ({current_size}/{window_size}). Calculando granulometría suavizada.")
        
        all_data_json = REDIS_CLIENT.lrange(history_key, 0, -1)
        
        combined_ellips_list = []
        for item_json in all_data_json:
            area_ar_list = json.loads(item_json)
            ellipses = [[
                max(ejes) * CONFIG["px_mm"], 
                min(ejes) * CONFIG["px_mm"]
            ] for ejes in area_ar_list]
            combined_ellips_list.extend(ellipses)
        
        rect_df = pd.DataFrame(combined_ellips_list, columns=["eje_M", "eje_m"])
        rect_df["ell_vol"] = (4/3 * np.pi * (rect_df["eje_M"] / 2) 
                            * np.power((rect_df["eje_m"] / 2), 2))
        ellips_df  = rect_df.sort_values("eje_m")
        histvalues_vol = ellips_df["ell_vol"] \
            / ellips_df["ell_vol"].sum()*100
        ellips_df["cumulative"] = np.cumsum(histvalues_vol)
        psd = interp1d(ellips_df["cumulative"].tolist(), ellips_df["eje_m"].tolist() 
                    )
        Fs = psd([10,20,30,40,50,60,70,80,90])

        Fs = np.append(Fs, max(ellips_df["eje_m"]))
    except Exception as e:
        print(f"Error calculando los Fs: {e}")
        return {"status": "Proceso fallido", "camara": camera_id}
    Fs_ajust = None
    
    if CONFIG["CALIBRAR"]:
        try:
            calibrations = CONFIG.get("calibrations", {})
            camera_cal = calibrations.get(camera_id)
            coeffs = camera_cal.get("coeffs", [1, 0])
            Fs_ajust = np.polyval(coeffs, Fs)
        except Exception as e:
            print(f"Error ejecutando la calibración {e}")
            return {"status": "Proceso fallido", "camara": camera_id}

    fs_list = Fs.tolist()
    fs_ajust_list = Fs_ajust.tolist() if Fs_ajust is not None else None

    results = {
        "Fs": fs_list,
        "Fs_ajust": fs_ajust_list,
        "cam_id": camera_id,
        "sim": inference_data["sim"],
        "capture_time": inference_data["capture_time"]
    }

    print(f"--- Procesado completo para camara: {camera_id} ---")
    print(f"{results}")

    save_to_db.delay(results)
    return {"status": "Procesado completo", "camara": camera_id}

