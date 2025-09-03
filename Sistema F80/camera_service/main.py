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
from datetime import datetime, timezone

camaras = {}

app = FastAPI(title="Servicio de la camara")

class CameraConfig(BaseModel):
    camara_id: str
    url: str
    intervalo_captura: float = 1.0
    simulation: bool = True
    simulation_source: str = ""
    class Config:
        extra = Extra.ignore

def capture_frames(config: CameraConfig, stop_event: threading.Event):
    """
    Define un hilo para capturar imagenes
    """
    cam_id = config.camara_id
    frame_queue = camaras[cam_id]["queue"]
    
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
                    capture_time = datetime.now(timezone.utc).isoformat()
                    frame_queue.put((capture_time, frame))
                time.sleep(config.intervalo_captura)
                        
        except Exception as e:
            print(f"[{cam_id}] Error en el loop de simulación: {e}")

    else:
        print(f"[{cam_id}] Iniciando camara en feed real desde: {config.url}")
        cap = None
        while not stop_event.is_set():
            try:
                if cap is None or not cap.isOpened:
                    print(f"[{cam_id}] Conectando a la camara en {config.url}...")
                    cap = cv2.VideoCapture(config.url)
                    if not cap.isOpened():
                        raise IOError("No se puede abrir el stream de video.")
                
                ret, frame = cap.read()
                if ret:
                    capture_time = datetime.now(timezone.utc).isoformat()
                    frame_queue.put((capture_time, frame))
                else:
                    print(f"[{cam_id}] No se pudo capturar el frame. Reintentando...")
                    cap.release()
                
                time.sleep(config.intervalo_captura)
            except Exception as e:
                print(f"[{config.camara_id}] Error en la captura: {e}")
                if cap:
                    cap.release()
                time.sleep(5) 
            
    if 'cap' in locals() and cap:
        cap.release()
        print(f"[{config.camara_id}] Se paró el hilo de captura.")

            
@app.post("/start_camera")
async def start_camera(config: CameraConfig):
    """
    Comienza la captura de las camaras usando hilos.
    """
    cam_id = config.camara_id
    if cam_id in camaras:
        raise HTTPException(status_code=400, detail=f"Camara '{cam_id}' en ejecución.")

    stop_event = threading.Event()
    camaras[cam_id] = {
        "queue": queue.Queue(maxsize=5),
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
    
    frame_queue = camaras[camera_id]["queue"]
    if frame_queue.empty():
        raise HTTPException(status_code=404, detail="No hay frames en la cola.")

    capture_time ,frame  = frame_queue.get()
    
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
    uvicorn.run(app, host="0.0.0.0", port=8001)






