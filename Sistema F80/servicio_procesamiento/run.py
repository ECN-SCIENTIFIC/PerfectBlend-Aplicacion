from gevent import monkey
monkey.patch_all()
import sys
import os
import subprocess


def apply_gevent_patch():
    """Aplica el monkey-patch de gevent. Debe ser la primera acción."""
    from gevent import monkey
    monkey.patch_all()


def fix_paths():
    """Modifica el path de Python para encontrar los módulos."""
    base_path = '.'
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    
    sys.path.insert(0, os.path.join(base_path, 'servicio_procesamiento'))
    sys.path.insert(0, os.path.join(base_path, 'camera_service'))
    sys.path.insert(0, os.path.join(base_path, 'servicio_procesamiento', 'workers'))

def run_api_service():
    """Inicia la API principal."""
    import uvicorn
    from main import app
    print("Iniciando API de procesamiento en el puerto 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)

def run_camera_service():
    """Inicia la API del servicio de cámaras."""
    import uvicorn
    from camera_service.camera_api import app
    print("Iniciando servicio de camara en el puerto 8001...")
    uvicorn.run("camera_service.camera_api:app", host="0.0.0.0", port=8001)

def run_celery_worker_entrypoint():
    """Punto de entrada REAL para el worker de Celery."""
    from celery_app import celery_app
    queue_name = sys.argv[2]
    concurrency = int(sys.argv[3])
    argv = [
        'worker', f'--hostname={queue_name}@%h', f'--queues={queue_name}',
        '--loglevel=INFO', f'--concurrency={concurrency}', '--pool=gevent'
    ]
    celery_app.worker_main(argv)

def run_celery_beat_entrypoint():
    """Punto de entrada REAL para Celery Beat."""
    from celery_app import celery_app
    argv = ['beat', '--loglevel=INFO']
    celery_app.start(argv)

if __name__ == '__main__':
    import multiprocessing as mp
    mp.freeze_support()
    service = sys.argv[1] if len(sys.argv) > 1 else None

    if service and '_entry' in service:
        fix_paths()
        
        if service == 'worker_entry':
            run_celery_worker_entrypoint()
        elif service == 'beat_entry':
            run_celery_beat_entrypoint()
    
    else:
        if not service:
            print("Error: Especifique el servicio a ejecutar.")
            print("Opciones: api, camera, worker, beat")
            sys.exit(1)

        command = [sys.executable]
        
        if service == 'api':
            fix_paths()
            run_api_service()
        elif service == 'camera':
            fix_paths()
            run_camera_service()
        elif service == 'worker':
            if len(sys.argv) < 4:
                print("Uso: python run.py worker <nombre_cola> <concurrencia>")
                sys.exit(1)

            if getattr(sys, 'frozen', False):
                command = [sys.executable, 'worker_entry', sys.argv[2], sys.argv[3]]
            else:
                command = [sys.executable, __file__, 'worker_entry', sys.argv[2], sys.argv[3]]

            subprocess.run(command)

        elif service == 'beat':
            if getattr(sys, 'frozen', False):
                command = [sys.executable, 'beat_entry']
            else:
                command = [sys.executable, __file__, 'beat_entry']
            subprocess.run(command)
        else:
            print(f"Error: Servicio '{service}' desconocido.")
            sys.exit(1)