import os
import time
import cv2
import multiprocessing as mp
from datetime import datetime, timezone
from itertools import cycle

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
    "rtsp_transport;tcp"
    "|stimeout;5000000"
    "|max_delay;500000"
    "|buffer_size;102400"
    "|fflags;nobuffer"
    "|flags;low_delay"
)

def _open_cap(url, backend=cv2.CAP_FFMPEG):
    cap = cv2.VideoCapture(url, backend)
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass
    return cap

def _safe_crop(frame, crop_y, crop_x):
    h, w = frame.shape[:2]
    if not crop_y:
        y0, y1 = 0, h
    else:
        y0 = max(0, crop_y[0])
        y1 = min(h, crop_y[1])
    if not crop_x:
        x0, x1 = 0, w
    else:
        x0 = max(0, crop_x[0]) 
        x1 = min(w, crop_x[1])
    return frame[y0:y1, x0:x1]

def capture_process(url, queue: mp.Queue, stop_event: mp.Event, crop_y=None, crop_x=None, simulation = False, simulation_source = "", reconnect_delay=3):
    cap = None
    image_files_cycle = None
    if simulation:
        image_files = [os.path.join(simulation_source, f) for f in os.listdir(simulation_source) if f.endswith(('.png', '.jpg', '.jpeg'))]
        if not image_files:
            raise FileNotFoundError("No se encontraron imagenes en el folder.")
        image_files_cycle = cycle(image_files)

    while not stop_event.is_set():
        if simulation:
            try:
                image_path = next(image_files_cycle)
                if stop_event.is_set():
                    break
                frame = cv2.imread(image_path)
                if frame is not None:
                    ok, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                    if not ok:
                        continue
                    data = jpg.tobytes()
                    ts = datetime.now(timezone.utc).isoformat()
                try:
                    if queue.full():
                        try:
                            queue.get_nowait()
                        except Exception:
                            pass
                    queue.put_nowait((ts, data))
                except Exception:
                    pass
                time.sleep(0.001)
            except Exception as e:
                print(f"[SIMULATION {simulation_source}] ERROR: {e}")
                time.sleep(reconnect_delay)
        else:           
            try:
                if cap is None:
                    cap = _open_cap(url)
                    if not cap.isOpened():
                        time.sleep(reconnect_delay)
                        continue
                ret, frame = cap.read()
                if not ret or frame is None:
                    cap.release()
                    cap = None
                    time.sleep(reconnect_delay)
                    continue
                frame = _safe_crop(frame, crop_y or [], crop_x or [])
                ok, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if not ok:
                    continue
                data = jpg.tobytes()
                ts = datetime.now(timezone.utc).isoformat()
                try:
                    if queue.full():
                        try:
                            queue.get_nowait()
                        except Exception:
                            pass
                    queue.put_nowait((ts, data))
                except Exception:
                    pass
                time.sleep(0.001)
            except Exception as e:
                print(f"[CAPTURE {url}] ERROR: {e}, reintentando en {reconnect_delay}s")
                try:
                    if cap:
                        cap.release()
                except:
                    pass
                cap = None
                time.sleep(reconnect_delay)
    if cap:
        try:
            cap.release()
        except:
            pass
    print(f"[CAPTURE {url}] stop_event set - proceso detenido.")
