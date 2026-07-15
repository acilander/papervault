import os
import subprocess
import sys
from fastapi import HTTPException

from utils import log

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.normpath(os.path.join(_HERE, ".."))

ARCHIVER_STDOUT = os.path.normpath(os.path.join(_BACKEND_DIR, "archiver_stdout.log"))
_ARCHIVER_PID_FILE = os.path.normpath(os.path.join(_BACKEND_DIR, "archiver.pid"))
_archiver_proc = None

def _pid_is_alive(pid: int) -> bool:
    """Check if a process with given PID is still running (Windows-compatible)."""
    try:
        import psutil
        return psutil.pid_exists(pid)
    except ImportError:
        pass
    # Fallback: Windows tasklist
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"], text=True, stderr=subprocess.DEVNULL
        )
        return str(pid) in out
    except Exception:
        return False

def _proc_running() -> bool:
    global _archiver_proc
    # Fast path: in-memory handle
    if _archiver_proc is not None:
        if _archiver_proc.poll() is None:
            return True
        _archiver_proc = None
    # Fallback: check PID file (survives backend restart)
    if os.path.exists(_ARCHIVER_PID_FILE):
        try:
            pid = int(open(_ARCHIVER_PID_FILE).read().strip())
            if _pid_is_alive(pid):
                return True
        except (ValueError, OSError):
            pass
        # Stale PID file — clean up
        try:
            os.remove(_ARCHIVER_PID_FILE)
        except OSError:
            pass
    return False

def archiver_status():
    running = _proc_running()
    pid = None
    if running:
        if _archiver_proc is not None:
            pid = _archiver_proc.pid
        elif os.path.exists(_ARCHIVER_PID_FILE):
            try:
                pid = int(open(_ARCHIVER_PID_FILE).read().strip())
            except (ValueError, OSError):
                pass
    return {"running": running, "pid": pid}

def archiver_start():
    global _archiver_proc
    if _proc_running():
        raise HTTPException(status_code=409, detail="Archiver läuft bereits")
    python = sys.executable
    project_root = os.path.join(os.path.dirname(__file__), "..")
    log_out = open(ARCHIVER_STDOUT, "a", encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    _archiver_proc = subprocess.Popen(
        [python, "-u", "archiver.py"],
        cwd=os.path.abspath(project_root),
        stdout=log_out,
        stderr=log_out,
        text=True,
        env=env,
    )
    with open(_ARCHIVER_PID_FILE, "w") as f:
        f.write(str(_archiver_proc.pid))
    return {"started": True, "pid": _archiver_proc.pid}

def archiver_stop():
    global _archiver_proc
    if not _proc_running():
        raise HTTPException(status_code=409, detail="Archiver läuft nicht")

    if _archiver_proc is not None:
        _archiver_proc.terminate()
        try:
            _archiver_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _archiver_proc.kill()
        _archiver_proc = None
    elif os.path.exists(_ARCHIVER_PID_FILE):
        try:
            pid = int(open(_ARCHIVER_PID_FILE).read().strip())
            try:
                import psutil
                proc = psutil.Process(pid)
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                # Windows fallback: taskkill
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        except Exception as e:
            log(f"Fehler beim Stoppen des Archivers via PID: {e}")

    try:
        os.remove(_ARCHIVER_PID_FILE)
    except OSError:
        pass
    return {"stopped": True}