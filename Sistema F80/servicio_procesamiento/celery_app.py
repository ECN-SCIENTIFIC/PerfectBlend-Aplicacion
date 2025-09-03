from celery import Celery
import json
from pyinstaller_utils import resource_path 

frecuencia_camaras = 30.0 
try:
    config_path = resource_path("configs/config_general.json")
    with open(config_path, 'r') as f:
        config_data = json.load(f)
        frecuencia_camaras = config_data.get("frecuencia_camaras", 30.0)
        
except Exception as e:
    print(f"No se pudo cargar config_general.json, usando frecuencia por defecto. Error: {e}")

celery_app = Celery(
    'tasks', 
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0',
    include=[
        'tasks',
        'workers.inference',
        'workers.process',
        'workers.database'
    ]
)

celery_app.conf.task_routes = {
    'workers.inference.perform_inference': {'queue': 'inference_queue'},
    'workers.process.process_granulometry': {'queue': 'processing_queue'},
    'workers.database.save_to_db': {'queue': 'processing_queue'},
    'tasks.initialize_cameras': {'queue': 'camaras_queue'},
    'tasks.request_cameras': {'queue': 'camaras_queue'},
}

celery_app.conf.beat_schedule = {
    'poll-cameras-every-3-seconds': {
        'task': 'tasks.request_cameras',
        'schedule': frecuencia_camaras, 
    },
}