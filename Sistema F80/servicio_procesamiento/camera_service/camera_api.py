import multiprocessing as mp
import threading
import pickle
import redis
import cv2
import numpy as np
from pydantic import BaseModel, Extra
from .proceso_captura import capture_process
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
import time
camaras = {}

class CameraConfig(BaseModel):
    camara_id: str
    url: str
    intervalo_captura: float = 1.0  
    simulation: bool = True
    simulation_source: str = ""
    crop_y: list = []
    crop_x: list = []
    enabled: bool = True
    class Config:
        extra = Extra.ignore

app = FastAPI(title="Servicio de la camara")
try:
    redis_client = redis.Redis(host='localhost', port=6379, db=1)
    redis_client.ping()
    print("Conexión a Redis para colas de cámara establecida.")
except Exception as e:
    print(f"Error conectando a Redis: {e}")
    redis_client = None

@app.post("/start_camera")
def start_camera(config: CameraConfig):
    cam_id = config.camara_id
    print(f"Procesando solicitud de inicio de cámara {cam_id}...")
    if cam_id in camaras:
        raise HTTPException(status_code=400, detail=f"Camara '{cam_id}' en ejecución.")
    if not redis_client:
        raise HTTPException(status_code=500, detail="Servicio de Redis no disponible.")
    
    q = mp.Queue(maxsize=1)
    stop_evt = mp.Event()
    p = mp.Process(target=capture_process, args=(config.url, q, stop_evt, config.crop_y, config.crop_x, config.simulation, config.simulation_source), daemon=True)
    p.start()


    def dispatch():
        r = redis.Redis(host="localhost", port=6379, db=1)
        redis_key = f"camera_queue:{config.camara_id}"
        while not stop_evt.is_set():
            try:
                ts, jpg_bytes = q.get(timeout=1)  
            except Exception:
                continue
            arr = np.frombuffer(jpg_bytes, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            payload = pickle.dumps((ts, frame))
            try:
                r.rpush(redis_key, payload)
                r.ltrim(redis_key, -5, -1)
                #print("Image pushed to Redis.")
            except Exception as e:
                print("Reconnecting to Redis...")
                r = redis.Redis(host="localhost", port=6379, db=1)
                print(f"[DISPATCHER {config.camara_id}] Redis push error: {e}")
                print(f"[DISPATCHER {config.camara_id}] stop.")


    dispatch_thread = threading.Thread(target=dispatch, daemon=True)
    dispatch_thread.start()

    camaras[config.camara_id] = {'proc': p, 'queue': q, 'stop': stop_evt, 'dispatch_thread': dispatch_thread}
    print(f"Camara {cam_id} iniciada correctamente.")
    return {"status": f"Camara {cam_id} iniciada correctamente."}


            

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
        time.sleep(1)
        payload = redis_client.lpop(redis_key)
        if payload is None:
            print("No hay frames en la cola")
            raise HTTPException(status_code=404, detail="No hay frames en la cola.")


    capture_time, frame = pickle.loads(payload)
    
    _, buffer = cv2.imencode(".jpg", frame)
    
    headers = {"capture-time": capture_time}
    
    return Response(content=buffer.tobytes(), media_type="image/jpeg", headers=headers)

@app.post("/stop_camera/{camera_id}")
def stop_camera_process(cam_id, timeout=5):
    info = camaras.get(cam_id)
    if not info:
        return
    info['stop'].set()
    info['dispatch_thread'].join(timeout)
    info['proc'].join(timeout)
    if info['proc'].is_alive():
        info['proc'].terminate()
    #Clear queue
    while not info["queue"].empty():
        info["queue"].get()
    del camaras[cam_id]

if __name__ == "__main__":
    mp.freeze_support() 
    uvicorn.run(app, host="0.0.0.0", port=8001, workers=1)
