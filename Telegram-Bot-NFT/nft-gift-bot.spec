# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for NFT Gift Bot (Frontend)
#
# Build: pyinstaller nft-gift-bot.spec
# Output: dist/nft-gift-bot

import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

# Telethon needs special handling — TL layer classes are generated dynamically
telethon_datas, telethon_binaries, telethon_hiddenimports = collect_all("telethon")

# aiogram submodules
aiogram_hiddenimports = collect_submodules("aiogram")

# aiohttp submodules
aiohttp_hiddenimports = collect_submodules("aiohttp")

hidden_imports = [
    # Project modules
    "config",
    "Message_Bot",
    "Message_Bot.distribution",
    "Message_Bot.gift_buyer",
    "Message_Bot.protocol",
    "Message_Bot.telegram_api",
    "Message_Bot.udp_listener",
    # Core deps
    "dotenv",
    "cryptography",
    "cryptography.hazmat.primitives.hashes",
    "cryptography.hazmat.primitives.kdf",
    "cryptography.hazmat.backends",
    # Async
    "asyncio",
    "asyncio.events",
    "asyncio.selector_events",
    # Encoding
    "encodings",
    "encodings.idna",
    "encodings.utf_8",
    # SSL
    "ssl",
    "certifi",
    # aiosignal, frozenlist — aiohttp deps
    "aiosignal",
    "frozenlist",
    "multidict",
    "yarl",
    "attr",
    "attrs",
    "charset_normalizer",
    "idna",
    # Telethon internals
    "telethon.tl",
    "telethon.tl.types",
    "telethon.tl.functions",
    "telethon.tl.functions.payments",
    "telethon.tl.alltlobjects",
    "telethon.crypto",
    "telethon.sessions",
    # magic-filter (aiogram dep)
    "magic_filter",
] + telethon_hiddenimports + aiogram_hiddenimports + aiohttp_hiddenimports

a = Analysis(
    ["Message_Bot/talkbot.py"],
    pathex=["."],
    binaries=telethon_binaries,
    datas=[
        ("config.py", "."),
    ] + telethon_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
        "test",
        "xmlrpc",
        "pydoc",
        "doctest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="nft-gift-bot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
