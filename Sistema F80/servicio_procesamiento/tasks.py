import requests
import base64
import json
import sys
from celery import signals
from celery_app import celery_app
from pyinstaller_utils import resource_path
from workers.inference import perform_inference

config_file = resource_path("configs/camera_config.json")
config = None

@signals.beat_init.connect
def on_beat_init(sender, **kwargs):
    print("--- (Beat Process Detected) Inicializando camaras ---")
    initialize_cameras.delay()


try:
    with open(config_file, 'r') as config:
        data_info = config.read()
        data_dir = json.loads(data_info)
        print("Se cargo el config de las camaras correctamente")
    config = data_dir

except FileNotFoundError:
    print(f"Error: No se encontro el config '{config_file}'.")
    sys.exit(0)
except json.JSONDecodeError:
    print(f"Error: Formato JSON invalido '{config_file}'.")
    sys.exit(0)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(0)




@celery_app.task
def initialize_cameras():
    """
    Task para inicializar todas las camaras.
    """
    
    print("Inicializando camaras")
    try:
        
        enabled_cameras = [cam for cam in config["camera_list"] if cam.get("enabled", False)]
        camera_service_url = config["url"]

        for camera_config in enabled_cameras:
            cam_id = camera_config["camara_id"]
            try:
                response = requests.post(f"{camera_service_url}/start_camera", json=camera_config, timeout=5)
                response.raise_for_status()
                print(f"Enviada señal de start para camara: {cam_id}")
            except requests.exceptions.HTTPError as e:
                print(f"HTTP Error starting camera {cam_id}: Status Code {e.response.status_code}")
                print(f"Validation Details: {e.response.json()}")
            except requests.exceptions.RequestException as e:
                print(f"Network Error starting camera {cam_id}: {e}")

    except Exception as e:
        print(f"Ocurrio un error inicializando camaras: {e}")

@celery_app.task
def request_cameras():

    CAMERA_SERVICE_URL = config["url"]
    CAMERAS_dict = config["camera_list"]

    print("Haciendo request de las camaras")
    for camera in CAMERAS_dict:
        #print(camera)
        cam_id = camera["camara_id"]
        sim = camera["simulation"]
        try:
            frame_response = requests.get(f"{CAMERA_SERVICE_URL}/get_frame/{cam_id}", timeout=2)
            if frame_response.status_code == 200:
                image_bytes = frame_response.content
                base64_image = base64.b64encode(image_bytes).decode("utf-8")
                capture_time = frame_response.headers.get("capture-time")
                perform_inference.delay(cam_id, base64_image, sim, capture_time)
        except requests.exceptions.RequestException as e:
            print(f"Error polling camera {cam_id}: {e}")



