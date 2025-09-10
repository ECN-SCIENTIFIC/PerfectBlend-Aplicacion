from celery_app import celery_app
from .process import process_granulometry
import cv2
import numpy as np
import onnx
import onnxruntime
from ultralytics import YOLO
import json
import pickle
import traceback
import base64
import time
from pyinstaller_utils import resource_path
from ..logger import setup_worker_logging
logger = setup_worker_logging("inference_worker", "logs/inference_worker.log")
CONFIG = None
MODEL = None


def load_resources():
    """
    This function loads the model and config, but only if they haven't been loaded yet.
    It will be called by the task.
    """
    global MODEL, CONFIG
    
    # Load config only once
    if CONFIG is None:
        try:
            config_file = resource_path("configs/inference_config.json")
            with open(config_file, 'r') as f:
                CONFIG = json.load(f)
            logger.info("Se cargo el config de la inferencia correctamente")
        except Exception as e:
            logger.error(f"Error cargando el config de inferencia: {e}")
            CONFIG = {} # Prevent retrying on failure

    if MODEL is None and CONFIG:
        logger.info("--- Cargando modelo ---")
        try:
            MODEL = YOLO(CONFIG["MODEL_PATH"], task="segment")
            logger.info("Modelo cargado exitosamente.")
        except Exception as e:
            logger.info(f"Error cargando el modelo: {e}")
            MODEL = None
    if CONFIG["CALIBRATION_PATH"]:
        with open(CONFIG["CALIBRATION_PATH"], "rb") as f:
            cal = pickle.load(f)

        CONFIG["mtx"] = cal["mtx"]
        CONFIG["dist"] = cal["dist"]
        CONFIG["newcameramtx"] = cal["newcameramtx"]


### Funciones auxiliares
def pre_process_image(img, config):
    frame = cv2.imdecode(np.frombuffer(img, np.uint8), cv2.IMREAD_COLOR)
    ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
    y, cr, cb = cv2.split(ycrcb)

    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    y_clahe = clahe.apply(y)

    merged = cv2.merge((y_clahe, cr, cb))
    img = cv2.cvtColor(merged, cv2.COLOR_YCrCb2BGR)
    #gaussian_3 = cv2.GaussianBlur(img, (0, 0), 0.2)
    dst = cv2.undistort(img, config["mtx"], config["dist"], None, config["newcameramtx"])
    return dst

def non_max_suppression(boxes, scores, threshold):
    indices = cv2.dnn.NMSBoxes(boxes, scores, threshold, CONFIG["NMS_THRESHOLD"])
    return indices.flatten() if len(indices) > 0 else []



### Task del worker
@celery_app.task(name='workers.inference.perform_inference')
def perform_inference(camera_id: str, image_data: str, sim, capture_time):
    load_resources()
    if MODEL is None:
        return {"error": "Modelo no cargado"}

    logger.info(f"[{camera_id}] Inferencia por lotes comenzada para camara {camera_id}")
    start_time = time.time()

    image_bytes = base64.b64decode(image_data)
    frame = pre_process_image(image_bytes, CONFIG)

    img_h, img_w, _ = frame.shape
    total_image_area = float(img_h * img_w)
    slice_h = CONFIG["SLICE"]
    slice_w = CONFIG["SLICE"]
    overlap = CONFIG["OVERLAP"]

    slices = []
    slice_coords = []
    step_y = int(slice_h * (1 - overlap))
    step_x = int(slice_w * (1 - overlap))

    for y in range(0, img_h, step_y):
        for x in range(0, img_w, step_x):
            y1, y2 = y, min(y + slice_h, img_h)
            x1, x2 = x, min(x + slice_w, img_w)
            slices.append(frame[y1:y2, x1:x2])
            slice_coords.append((x1, y1))

    if not slices:
        return {"status": "Inferencia completa sin detecciones.", "camera_id": camera_id}

    batch_results = MODEL.predict(slices, conf=CONFIG["CONF"], verbose=False, task='segment')

    all_boxes = []
    all_scores = []
    all_masks = []

    for result, (x1, y1) in zip(batch_results, slice_coords):
        if result.masks is not None:
            for box, mask in zip(result.boxes, result.masks.xy):
                global_box = [box.xyxy[0][0] + x1, box.xyxy[0][1] + y1, box.xyxy[0][2] + x1, box.xyxy[0][3] + y1]
                global_mask = mask + [x1, y1]
                all_boxes.append([int(b) for b in global_box])
                all_scores.append(float(box.conf))
                all_masks.append(global_mask.astype(int).tolist())

    if not all_boxes:
        logger.info(f"[{camera_id}] No se encontraron detecciones para la camara: {camera_id}")
        return {"status": "Inferencia completa sin detecciones.", "camera_id": camera_id}

    boxes_for_nms = [[box[0], box[1], box[2] - box[0], box[3] - box[1]] for box in all_boxes]
    indices = non_max_suppression(boxes_for_nms, all_scores, CONFIG["CONF"])
    final_masks = [all_masks[i] for i in indices]

    area_ar = []
    for mask_points in final_masks:
        if len(mask_points) >= 5:
            ellipse = cv2.fitEllipse(np.array(mask_points))
            area_ar.append(ellipse[1])

    res_img = frame.copy()
    overlay = frame.copy()
    alpha = 0.4 
    color_fill = (0, 255, 0) 

    pts_for_poly = [np.array(mask, dtype=np.int32) for mask in final_masks]

    cv2.fillPoly(overlay, pts_for_poly, color_fill)

    cv2.addWeighted(overlay, alpha, res_img, 1 - alpha, 0, res_img)
    
    _, buffer = cv2.imencode(".jpg", res_img)
    _, buffer_og = cv2.imencode(".jpg", frame)
    img_result_encoded = base64.b64encode(buffer).decode('utf-8')
    frame_encoded = base64.b64encode(buffer_og).decode('utf-8')
    total_mask_area = 0.0
    for mask_points in final_masks:
        contour = np.array(mask_points)
        total_mask_area += cv2.contourArea(contour)

    detection_percentage = 0.0
    if total_image_area > 0:
        detection_percentage = (total_mask_area / total_image_area) * 100

    results = {
        "img_result": img_result_encoded,
        "img_original": frame_encoded,
        "area_ar": area_ar,
        "detections": detection_percentage,
        "sim": sim,
        "capture_time": capture_time
    }

    process_granulometry.delay(camera_id, results)

    end_time = time.time()
    logger.info(f"INFERENCE [COMPLETED] for camera: {camera_id} in {end_time - start_time:.2f} seconds.")

    return {"status": "Inference complete, passed to processing worker.", "camera_id": camera_id}


