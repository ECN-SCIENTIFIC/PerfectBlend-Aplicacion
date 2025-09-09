import threading
import queue
import time
import cv2
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Extra
import io
import os
from itertools import cycle
import pickle
import redis
from datetime import datetime, timezone

camaras = {}

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
    "rtsp_transport;tcp"
    "|stimeout;5000000"      
    "|max_delay;500000"      
    "|buffer_size;102400"   
)

app = FastAPI(title="Servicio de la camara")
try:
    redis_client = redis.Redis(host='localhost', port=6379, db=1)
    redis_client.ping()
    print("Conexión a Redis para colas de cámara establecida.")
except Exception as e:
    print(f"Error conectando a Redis: {e}")
    redis_client = None


class CameraConfig(BaseModel):
    camara_id: str
    url: str
    intervalo_captura: float = 1.0  
    simulation: bool = True
    simulation_source: str = ""
    crop_y: list = []
    crop_x: list = []
    class Config:
        extra = Extra.ignore

def _open_cap(url):
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass
    return cap


def capture_frames(config: CameraConfig, stop_event: threading.Event):
    """
    Define un hilo para capturar imagenes
    """
    cam_id = config.camara_id
    redis_key = f"camera_queue:{cam_id}"
    
    RECONNECT_DELAY = 3

    FRAME_TIMEOUT = max(5.0, config.intervalo_captura + 10.0)
    last_frame_time = time.time()


    if config.simulation:
        print(f"[{cam_id}] Iniciando camara en modo simulación desde: {config.simulation_source}")
        try:
            image_files = [os.path.join(config.simulation_source, f) for f in os.listdir(config.simulation_source) if f.endswith(('.png', '.jpg', '.jpeg'))]
            if not image_files:
                raise FileNotFoundError("No se encontraron imagenes en el folder.")
            
            for image_path in cycle(image_files):
                if stop_event.is_set():
                    break
                frame = cv2.imread(image_path)
                if frame is not None:
                    frame = frame[config.crop_y[0]:config.crop_y[1], config.crop_x[0]:config.crop_x[1]]
                    capture_time = datetime.now(timezone.utc).isoformat()
                    payload = pickle.dumps((capture_time, frame))
                    redis_client.rpush(redis_key, payload)
                    redis_client.ltrim(redis_key, -5, -1)
                time.sleep(config.intervalo_captura)
                        
        except Exception as e:
            print(f"[{cam_id}] Error en el loop de simulación: {e}")

    else:
        print(f"[{cam_id}] Iniciando camara en feed real desde: {config.url}")
        cap = None
        next_publish = 0.0
        while not stop_event.is_set():
            try:
                if cap is None or not cap.isOpened:
                    print(f"[{cam_id}] Conectando a la camara en {config.url}...")
                    if cap is not None:
                        cap.release()
                    cap = _open_cap(config.url)
                    if not cap.isOpened():
                        raise IOError("No se puede abrir el stream de video.")
                    print(f"[{cam_id}] Conexión establecida exitosamente.")
                    last_frame_ts = time.time()
                    next_publish = last_frame_ts
                
                ret, frame = cap.read()
                if not ret or frame is None:
                    raise IOError("Lectura falló / frame nulo.")
                
                last_frame_ts = time.time()

                if last_frame_ts >= next_publish:
                    frame = frame[config.crop_y[0]:config.crop_y[1], config.crop_x[0]:config.crop_x[1]]
                    capture_time = datetime.now(timezone.utc).isoformat()
                    payload = pickle.dumps((capture_time, frame))
                    redis_client.rpush(redis_key, payload)
                    redis_client.ltrim(redis_key, -5, -1)
                    next_publish = last_frame_ts + config.intervalo_captura

                if time.time() - last_frame_ts > FRAME_TIMEOUT:
                    raise TimeoutError("Timeout de frame - reconexión.")
                
                time.sleep(0.001)
            except Exception as e:
                print(f"[{cam_id}] Error en el bucle de captura: {e}. Esperando {RECONNECT_DELAY}s.")
                if cap:
                    cap.release()
                cap = None
                time.sleep(RECONNECT_DELAY)
            
    if cap:
        cap.release()
    redis_client.delete(redis_key)
    print(f"[{config.camara_id}] Se paró el hilo de captura y se limpió la cola.")


            
@app.post("/start_camera")
async def start_camera(config: CameraConfig):
    """
    Comienza la captura de las camaras usando hilos.
    """
    cam_id = config.camara_id
    if cam_id in camaras:
        raise HTTPException(status_code=400, detail=f"Camara '{cam_id}' en ejecución.")
    if not redis_client:
        raise HTTPException(status_code=500, detail="Servicio de Redis no disponible.")
    
    stop_event = threading.Event()
    camaras[cam_id] = {
        "stop_event": stop_event,
        "thread": threading.Thread(
            target=capture_frames, args=(config, stop_event), daemon=True
        )
    }
    camaras[cam_id]["thread"].start()
    print(f"Se comenzó el hilo para: {cam_id}")
    return {"message": f"Camara '{cam_id}' inició captura."}

@app.get("/get_frame/{camera_id}")
async def get_frame(camera_id: str):
    """
    Regresa el ultimo frame en la cola
    """
    if camera_id not in camaras:
        raise HTTPException(status_code=404, detail=f"Camara '{camera_id}' no se encontró.")
    
    redis_key = f"camera_queue:{camera_id}"
    payload = redis_client.lpop(redis_key)
    
    if payload is None:
        raise HTTPException(status_code=404, detail="No hay frames en la cola.")


    capture_time, frame = pickle.loads(payload)
    
    _, buffer = cv2.imencode(".jpg", frame)
    
    headers = {"capture-time": capture_time}
    
    return Response(content=buffer.tobytes(), media_type="image/jpeg", headers=headers)

@app.post("/stop_camera/{camera_id}")
async def stop_camera(camera_id: str):
    """
    Detiene la captura para una camara específica.
    """
    if camera_id not in camaras:
        raise HTTPException(status_code=404, detail=f"Camara '{camera_id}' no encontrada.")
    
    camaras[camera_id]["stop_event"].set()
    camaras[camera_id]["thread"].join(timeout=5)
    del camaras[camera_id]
    
    print(f"Se paró la captura para la camara: {camera_id}")
    return {"message": f"Camara '{camera_id}' detenida."}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, workers=1)






