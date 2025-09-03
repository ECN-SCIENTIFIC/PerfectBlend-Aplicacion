from fastapi import FastAPI, HTTPException, Depends
from celery.result import AsyncResult
import psycopg2
import psycopg2.extras
from celery_app import celery_app
import uvicorn
import json
from pyinstaller_utils import resource_path

app = FastAPI(title="F80 - Perfect Blend API")

def get_db_connection_details():
    config_path = resource_path("configs/db_config.json")
    with open(config_path, 'r') as f:
        return json.load(f)

def get_db():
    conn = None
    try:
        db_config = get_db_connection_details()
        conn = psycopg2.connect(**db_config)
        yield conn
    finally:
        if conn:
            conn.close()

@app.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """
    Regresa el status de un task de Celery
    """
    task_result = AsyncResult(task_id, app=celery_app)
    return {"task_id": task_id, "status": task_result.status}

@app.get("/result/{task_id}")
async def get_task_result(task_id: str):
    """
    Obtiene el resultado de un task de Celery
    """
    task_result = AsyncResult(task_id, app=celery_app)
    
    if not task_result.ready():
        raise HTTPException(status_code=202, detail="El task se esta procesando...")
    
    if task_result.failed():
        return {"task_id": task_id, "status": "FAILURE", "result": str(task_result.result)}

    return {"task_id": task_id, "status": "SUCCESS", "result": task_result.result}

@app.get("/results/{camera_id}")
async def get_results_for_camera(camera_id: str, limit: int = 10, db=Depends(get_db)):
    try:
        with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM results 
                WHERE camera_id = %s 
                ORDER BY timestamp DESC 
                LIMIT %s;
                """,
                (camera_id, limit)
            )
            results = cur.fetchall()
            if not results:
                raise HTTPException(status_code=404, detail=f"No hay resultados para '{camera_id}'")
            return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@app.get("/results/latest/all")
async def get_latest_results_for_all_cameras(db=Depends(get_db)):
    try:
        with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT DISTINCT ON (camera_id) *
                FROM results
                ORDER BY camera_id, timestamp DESC;
                """
            )
            results = cur.fetchall()
            if not results:
                raise HTTPException(status_code=404, detail="No hay resultados en la base de datos.")
            return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)