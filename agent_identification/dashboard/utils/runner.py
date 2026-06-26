import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent.parent.parent


def run_pipeline(mode: str, **kwargs):
    cmd = [sys.executable, str(BASE / "run.py"), "--mode", mode]
    for k, v in kwargs.items():
        if v is not None:
            flag = f"--{k.replace('_', '-')}"
            if isinstance(v, bool):
                if v:
                    cmd.append(flag)
            else:
                cmd.extend([flag, str(v)])

    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

    (BASE / "data").mkdir(parents=True, exist_ok=True)

    log_path = BASE / "data" / f"run_{mode}_{datetime.now():%Y%m%d_%H%M%S}.log"
    with open(log_path, "w", encoding="utf-8") as log:
        log.write(f"COMMAND: {' '.join(cmd)}\n\n")
        log.flush()
        with subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            cwd=str(BASE),
            env=env,
        ) as proc:
            for line in iter(proc.stdout.readline, ""):
                log.write(line)
                log.flush()
                yield line.rstrip()
            proc.wait()
            log.write(f"\nEXIT CODE: {proc.returncode}\n")

    if proc.returncode != 0:
        yield f"ERREUR: code {proc.returncode} — voir {log_path}"
