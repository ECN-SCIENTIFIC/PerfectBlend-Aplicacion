# build.spec
import sys
sys.setrecursionlimit(5000)

a = Analysis(
    ['run.py'],
    pathex=['C:/Users/Miguel/Documents/GitHub/PerfectBlend-Aplicacion/Sistema F80'],
    binaries=[],
    datas=[
        ('C:/Users/Miguel/Documents/GitHub/PerfectBlend-Aplicacion/Sistema F80/shared_resources/*', 'shared_resources'),
        ('C:/Users/Miguel/Documents/GitHub/PerfectBlend-Aplicacion/Sistema F80/servicio_procesamiento/*', '.'),
        ('C:/Users/Miguel/Documents/GitHub/PerfectBlend-Aplicacion/Sistema F80/servicio_procesamiento/camera_service/*', 'camera_service')
    ],
    hiddenimports=[
       'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        # --- Psycopg2 (PostgreSQL) ---
        'psycopg2._psycopg',
        'sklearn.utils._cython_blas',
        'sklearn.neighbors._typedefs',
        'sklearn.neighbors._quad_tree',
        'sklearn.tree',
        'sklearn.tree._utils',
        'scipy._lib.messagestream',
        'cv2.ffmpeg main.spec',
        'gevent',
        'psycopg2',
        'redis',
        'celery', 'celery.app', 'celery.app.amqp', 'celery.app.control',
        'celery.app.events', 'celery.app.log', 'celery.app.result',
        'celery.apps', 'celery.apps.worker',
        'celery.backends', 'celery.backends.database', 'celery.backends.redis',
        'celery.bin',
        'celery.concurrency', 'celery.concurrency.prefork', 'celery.concurrency.gevent',
        'celery.contrib', 'celery.contrib.testing',
        'celery.events', 'celery.events.state',
        'celery.fixups', 'celery.fixups.django',
        'celery.loaders',
        'celery.security',
        'celery.utils', 'celery.utils.dispatch', 'celery.utils.static',
        'celery.worker', 'celery.worker.autoscale', 'celery.worker.components',
        'celery.worker.consumer', 'celery.worker.strategy', 'celery.worker.consumer.delayed_delivery', 'celery.apps.beat',
        # --- Broker y Concurrencia ---
        'kombu.transport.redis',
        'celery.concurrency.gevent',
        'gevent',
        'celery_app',
        'main',
        'camera_service.main',
        'cv2',
        'onnx',
        'onnxruntime',
        'ultralytics',
        'fastapi',
        # Módulos de tasks y workers de Celery
        'tasks',
        'workers.inference',
        'workers.process',
        'workers.database',
        'pyinstaller_utils',
        'pandas'
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None
)
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='F80_service', 
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='proyecto_output'
)
