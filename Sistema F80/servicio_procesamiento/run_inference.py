import subprocess
import sys

if __name__ == "__main__":
    command = [
        "celery",
        "-A", "celery_app.celery_app",
        "worker",
        "--loglevel=info",
        "--pool=gevent",
        "-c", "1",
        "-Q", "inference_queue" 
    ]
    subprocess.run(command)