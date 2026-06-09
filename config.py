#!/usr/bin/python3
"""pi5-e-paper-hat 共通設定ローダ

同ディレクトリの .env を読み、定数として公開する。
.env が無いキーは .env.example のデフォルトにフォールバックせず、
ここのデフォルト値を使う (機密のみ .env 必須)。
"""
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_env(path):
    env = {}
    if not os.path.exists(path):
        return env
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


_ENV = _load_env(os.path.join(_HERE, ".env"))


def get(key, default=None):
    return _ENV.get(key, os.environ.get(key, default))


# --- Wi-Fi AP (オンボーディング QR 用) ---
WIFI_SSID = get("WIFI_SSID", "pi5-w-1")
WIFI_PSK = get("WIFI_PSK", "")
WELCOME_URL = get("WELCOME_URL", "https://yuiseki.dev/welcome")

# --- 地図 ---
MAP_URL = get("MAP_URL", "https://yuiseki.dev/static/epaper-map.html")
MAP_ZOOM = float(get("MAP_ZOOM", "15.5"))

# --- traccar (現在地追従) ---
TRACCAR_API = get("TRACCAR_API", "http://localhost:30082")
TRACCAR_USER = get("TRACCAR_USER", "")
TRACCAR_PASSWORD = get("TRACCAR_PASSWORD", "")
TRACCAR_DEVICE_ID = int(get("TRACCAR_DEVICE_ID", "1"))

# --- ハードウェア ---
EPAPER_LIB = get(
    "EPAPER_LIB",
    "/home/yuiseki/src/e-Paper/RaspberryPi_JetsonNano/python/lib",
)
