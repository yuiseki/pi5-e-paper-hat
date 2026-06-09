#!/usr/bin/python3
"""e-Paper 用地図キャプチャ: headless Chromium で epaper-map.html を撮影し4値量子化する

usage: epd_map_capture.py [出力PNG] [#hash]
  例: epd_map_capture.py /run/epd-map.png

設定は同ディレクトリの .env (config.py 経由) から読む。
"""
import base64
import json
import sys
import time
import urllib.parse
import urllib.request

from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

import config

W, H = 176, 264
# 4値パレット: スタイル側の色 -> e-Paper 4階調 (waveshare lib の期待値)
LEVELS = [0x00, 0x80, 0xC0, 0xFF]


def get_pi_z2_position():
    """traccar API から pi-z2-wh の最新座標を取得。失敗時 None"""
    try:
        if not config.TRACCAR_USER or not config.TRACCAR_PASSWORD:
            return None
        # traccar はチャレンジ応答式だと取りこぼすため Authorization を先付けする
        token = base64.b64encode(
            f"{config.TRACCAR_USER}:{config.TRACCAR_PASSWORD}".encode()
        ).decode()
        url = f"{config.TRACCAR_API}/api/positions?deviceId={config.TRACCAR_DEVICE_ID}"
        req = urllib.request.Request(url, headers={"Authorization": f"Basic {token}"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.load(r)
        if not data:
            return None
        p = data[0]
        return {"lat": p["latitude"], "lon": p["longitude"],
                "course": p.get("course", 0), "time": p.get("deviceTime")}
    except Exception as e:
        print(f"traccar position fetch failed: {e}", file=sys.stderr)
        return None


def quantize(img):
    """グレースケール画像を4値 {0x00, 0x80, 0xC0, 0xFF} に量子化 (ディザなし)"""
    g = img.convert("L")
    lut = []
    for v in range(256):
        # 閾値: アンチエイリアスの中間色を最寄りの4値へ
        if v >= 232:
            lut.append(0xFF)  # #ffffff
        elif v >= 160:
            lut.append(0xC0)  # #d0d0d0
        elif v >= 56:
            lut.append(0x80)  # #707070
        else:
            lut.append(0x00)  # #000000
    return g.point(lut)


def capture(out_path, url_hash="", timeout=60, follow_pi_z2=True, zoom=None):
    if zoom is None:
        zoom = config.MAP_ZOOM
    # pi-z2-wh の現在地を取得して URL に渡す (認証情報はブラウザに晒さない)
    query = ""
    if follow_pi_z2:
        pos = get_pi_z2_position()
        if pos:
            query = "?" + urllib.parse.urlencode(
                {"lat": pos["lat"], "lon": pos["lon"],
                 "course": pos["course"], "name": "pi-z2-wh"}
            )
            # hash 未指定なら現在地を中心に
            if not url_hash:
                url_hash = f"#{zoom}/{pos['lat']}/{pos['lon']}"
            print(f"pi-z2-wh: {pos['lat']:.5f},{pos['lon']:.5f} @ {pos['time']}",
                  flush=True)

    opts = Options()
    opts.binary_location = "/usr/bin/chromium"
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--use-gl=angle")
    opts.add_argument("--use-angle=swiftshader")
    opts.add_argument("--hide-scrollbars")
    opts.add_argument("--window-size=400,500")
    driver = webdriver.Chrome(
        service=Service("/usr/bin/chromedriver"), options=opts
    )
    try:
        driver.set_page_load_timeout(timeout)
        driver.get(config.MAP_URL + query + url_hash)
        # map.on("idle") が document.title を ready にするのを待つ
        deadline = time.time() + timeout
        while time.time() < deadline:
            if driver.title == "ready":
                break
            time.sleep(0.5)
        else:
            raise TimeoutError("map idle timeout")
        time.sleep(1)  # 最終描画の安定待ち
        el = driver.find_element("id", "map")
        raw_path = out_path + ".raw.png"  # /tmp 直下の固定名は protected_regular で他ユーザーと衝突するため出力先に揃える
        el.screenshot(raw_path)
    finally:
        driver.quit()

    img = Image.open(raw_path)
    if img.size != (W, H):
        img = img.resize((W, H), Image.LANCZOS)
    quantize(img).save(out_path)
    return out_path


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/run/epd-map.png"
    h = sys.argv[2] if len(sys.argv) > 2 else ""
    print(capture(out, h))
