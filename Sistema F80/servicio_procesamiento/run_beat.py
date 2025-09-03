import subprocess
import sys

if __name__ == "__main__":
    command = [
        "celery",
        "-A", "celery_app.celery_app",
        "beat",
        "--loglevel=info"
    ]
    subprocess.run(command)