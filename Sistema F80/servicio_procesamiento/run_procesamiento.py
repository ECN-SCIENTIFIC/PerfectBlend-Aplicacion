import subprocess
import sys

if __name__ == "__main__":
    command = [
        "celery",
        "-A", "celery_app.celery_app",
        "worker",
        "--loglevel=info",
        "--pool=gevent",
        "-c", "2", 
        "-Q", "processing_queue" 
    ]
    subprocess.run(command)