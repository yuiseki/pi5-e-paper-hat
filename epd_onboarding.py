#!/usr/bin/python3
"""Pi Swarm 物理オンボーディング画面 (Waveshare 2.7inch e-Paper HAT V2)

Page 1: Wi-Fi 接続 QR (SSID/パスフレーズ併記)
Page 2: welcome URL QR
Page 3: k3s cluster status
Page 4: network / diagnostics
(地図ページは KEY4 長押しで遷移)

KEY1(GPIO5):  Wi-Fi QR 表示。再押下で URL QR とトグル (Captive Portal 不発時のバックアップ)
KEY2(GPIO6):  network / diagnostics
KEY3(GPIO13): k3s cluster status
KEY4(GPIO19): 単押し = Wi-Fi QR に戻る (ESC) / 長押し(1秒) = 地図表示 (4Gray, pi-z2-wh 追従)

設定は同ディレクトリの .env (config.py 経由) から読む。
"""
import os
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime

import config

sys.path.append(config.EPAPER_LIB)

import qrcode
from gpiozero import Button
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd2in7_V2

import epd_map_capture
from k3s_status import (
    count_abnormal_pods,
    ksvc_reachable,
    parse_deployment_ready,
    parse_ksvc_ready,
    parse_node_status,
    parse_pod_ready,
)

# --- 設定 (.env 由来) ---
SSID = config.WIFI_SSID
PSK = config.WIFI_PSK
WELCOME_URL = config.WELCOME_URL
WIFI_QR_PAYLOAD = f"WIFI:T:WPA;S:{SSID};P:{PSK};;"
AUTO_REFRESH_SEC = 300  # 表示中ページの自動更新間隔 (e-Paper 劣化防止のため控えめに)
FONT_DIR = "/usr/share/fonts/truetype/dejavu"

font_title = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans-Bold.ttf", 16)
font_body = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans.ttf", 13)
font_mono = ImageFont.truetype(f"{FONT_DIR}/DejaVuSansMono.ttf", 12)
font_small = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans.ttf", 10)

# k3s ページ専用: 一回り小さいフォント
font_k3s_title = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans-Bold.ttf", 13)
font_k3s_mono = ImageFont.truetype(f"{FONT_DIR}/DejaVuSansMono.ttf", 10)
font_k3s_body = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans.ttf", 11)

W, H = 176, 264  # 縦向きネイティブ


def sh(cmd, timeout=10):
    try:
        return subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        ).stdout.strip()
    except Exception:
        return ""


def make_qr(payload, size=148):
    qr = qrcode.QRCode(border=1, box_size=10)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("1")
    return img.resize((size, size), Image.NEAREST)


def footer(draw):
    ts = datetime.now().strftime("%m/%d %H:%M")
    draw.text((4, H - 26), "1:QR 2:net 3:k3s 4:esc|map", font=font_small, fill=0)
    draw.text((4, H - 14), f"updated {ts}", font=font_small, fill=0)


def page_wifi_qr():
    img = Image.new("1", (W, H), 255)
    d = ImageDraw.Draw(img)
    d.text((4, 2), "Wi-Fi join", font=font_title, fill=0)
    img.paste(make_qr(WIFI_QR_PAYLOAD), ((W - 148) // 2, 24))
    d.text((4, 180), f"SSID: {SSID}", font=font_body, fill=0)
    d.text((4, 198), f"PASS: {PSK}", font=font_body, fill=0)
    d.text((4, 220), "Scan to join Pi Swarm AP", font=font_small, fill=0)
    footer(d)
    return img


def page_url_qr():
    img = Image.new("1", (W, H), 255)
    d = ImageDraw.Draw(img)
    d.text((4, 2), "Welcome URL", font=font_title, fill=0)
    img.paste(make_qr(WELCOME_URL), ((W - 148) // 2, 24))
    d.text((4, 180), "yuiseki.dev/welcome", font=font_body, fill=0)
    d.text((4, 198), "(closed LAN, no internet)", font=font_small, fill=0)
    d.text((4, 220), "Open after joining Wi-Fi", font=font_small, fill=0)
    footer(d)
    return img


def page_k3s():
    img = Image.new("1", (W, H), 255)
    d = ImageDraw.Draw(img)
    d.text((4, 2), "k3s status", font=font_k3s_title, fill=0)

    # ノード一覧（control-plane 先頭）
    out = sh("kubectl get nodes --no-headers", timeout=15)
    y = 22
    if not out:
        d.text((4, y), "k3s: unavailable", font=font_k3s_body, fill=0)
        y += 16
    else:
        nodes = parse_node_status(out)
        ready = sum(node.ready for node in nodes)
        for node in nodes:
            mark = "OK" if node.ready else "NG"
            d.text((4, y), f"[{mark}] {node.name}", font=font_k3s_mono, fill=0)
            y += 14
        d.text((4, y + 2), f"nodes {ready}/{len(nodes)} ready", font=font_k3s_body, fill=0)
        y += 16

    # サービス単位のステータス（ksvc READY + 独立 deployment）
    # ksvc: ksvc名 -> 表示ラベル のマッピング
    KSVC_LABELS = {
        "hotosm-imagery-tile": "imagery",
        "poc-cesg-route-search": "route",
        "poc-cesg-poi-search": "poi",
    }
    # 独立 deployment: namespace/deployment -> 表示ラベル
    DEPLOY_LABELS = {
        "cng-storage/cng-storage-rustfs": "storage",
        "traccar/traccar": "traccar",
    }

    y += 2
    d.line((4, y, W - 4, y), fill=0)
    y += 4

    # ksvc ステータス取得
    ksvc_out = sh("kubectl get ksvc -A --no-headers 2>/dev/null", timeout=15)
    deploy_out = sh(
        "kubectl get deployment -A --no-headers 2>/dev/null", timeout=15
    )
    pods_out = sh("kubectl get pods -A --no-headers 2>/dev/null", timeout=15)

    ksvc_ready = parse_ksvc_ready(ksvc_out)
    deploy_ready = parse_deployment_ready(deploy_out)
    pod_ready_raw = parse_pod_ready(pods_out)
    pod_ready = {
        "kourier-system/3scale-kourier-gateway": any(
            key.startswith("kourier-system/3scale-kourier-gateway") and value
            for key, value in pod_ready_raw.items()
        ),
        "knative-serving/activator": any(
            key.startswith("knative-serving/activator") and value
            for key, value in pod_ready_raw.items()
        ),
    }
    abnormal_pods = count_abnormal_pods(pods_out)

    for ksvc_name, label in KSVC_LABELS.items():
        if ksvc_name in ksvc_ready:
            mark = "OK" if ksvc_reachable(ksvc_ready[ksvc_name], pod_ready) else "NG"
        else:
            mark = "??"
        d.text((4, y), f"[{mark}] {label}", font=font_k3s_mono, fill=0)
        y += 14

    for key, label in DEPLOY_LABELS.items():
        if key in deploy_ready:
            mark = "OK" if deploy_ready[key] else "NG"
        else:
            mark = "??"
        d.text((4, y), f"[{mark}] {label}", font=font_k3s_mono, fill=0)
        y += 14

    d.text((4, y + 2), f"abnormal pods {abnormal_pods}", font=font_k3s_body, fill=0)

    footer(d)
    return img


def page_diag():
    img = Image.new("1", (W, H), 255)
    d = ImageDraw.Draw(img)
    d.text((4, 2), "network", font=font_k3s_title, fill=0)
    host = socket.gethostname()
    temp = sh("cat /sys/class/thermal/thermal_zone0/temp")
    temp_c = f"{int(temp) / 1000:.1f}C" if temp.isdigit() else "n/a"
    try:
        secs = int(float(open("/proc/uptime").read().split()[0]))
        days, r = divmod(secs, 86400)
        h, r = divmod(r, 3600)
        m, s = divmod(r, 60)
        up = f"{days} days, {h:02d}:{m:02d}:{s:02d}" if days else f"{h:02d}:{m:02d}:{s:02d}"
    except Exception:
        up = "n/a"
    wlan0 = sh("ip -4 -br addr show wlan0 | awk '{print $3}'").split("/")[0]
    wlan1 = sh("ip -4 -br addr show wlan1 | awk '{print $3}'").split("/")[0]
    clients = sh(
        "cat /var/lib/NetworkManager/dnsmasq-wlan1.leases 2>/dev/null | wc -l"
    )
    rows = [
        ("host", host),
        ("uplink", wlan0 or "n/a"),
        ("ap", wlan1 or "n/a"),
        ("temp", temp_c),
        ("uptime", up),
        ("leases", clients),
        ("caddy", sh("systemctl is-active caddy")),
        ("k3s", sh("systemctl is-active k3s")),
    ]
    y = 22
    for k, v in rows:
        d.text((4, y), f"{k:>7}: {v}", font=font_k3s_mono, fill=0)
        y += 14
    footer(d)
    return img


PAGES = [page_wifi_qr, page_url_qr, page_k3s, page_diag]

# --- 地図ページ (4Gray) ---
MAP_PAGE = 4


def page_map_loading():
    img = Image.new("1", (W, H), 255)
    d = ImageDraw.Draw(img)
    d.text((4, 2), "map", font=font_title, fill=0)
    d.text((4, H // 2 - 10), "Rendering map...", font=font_body, fill=0)
    footer(d)
    return img


class Onboarding:
    def __init__(self):
        self.epd = epd2in7_V2.EPD()
        self.page = 0
        self.dirty = True
        self.last_render = 0.0

    def render(self):
        if self.page == MAP_PAGE:
            self.render_map()
        else:
            img = PAGES[self.page]()
            img = img.rotate(180)  # 設置向きの都合 (NOTES.md 参照)
            self.epd.init()
            self.epd.display(self.epd.getbuffer(img))
            self.epd.sleep()  # 描画のたびに省電力へ
        self.last_render = time.time()
        self.dirty = False
        print(f"rendered page {self.page + 1}", flush=True)

    def render_map(self):
        # 1. すぐに Loading 表示 (B/W) -> 2. キャプチャ -> 3. 4Gray 表示
        self.epd.init()
        self.epd.display(self.epd.getbuffer(page_map_loading().rotate(180)))
        try:
            # /tmp は他ユーザーの残骸と protected_regular で衝突しうるため /run を使う
            # hash 空 = pi-z2-wh の現在地を中心に追従 (取得失敗時は HTML 側でフォールバック)
            epd_map_capture.capture("/run/epd-map.png", "")
            img = Image.open("/run/epd-map.png").rotate(180)
            self.epd.Init_4Gray()
            self.epd.display_4Gray(self.epd.getbuffer_4Gray(img))
        except Exception as e:
            print(f"map capture failed: {e}", flush=True)
            img = Image.new("1", (W, H), 255)
            d = ImageDraw.Draw(img)
            d.text((4, H // 2 - 10), "map render failed", font=font_body, fill=0)
            self.epd.init()
            self.epd.display(self.epd.getbuffer(img.rotate(180)))
        finally:
            self.epd.sleep()

    def goto(self, page):
        self.page = page
        self.dirty = True

    def on_key1(self):
        # Wi-Fi QR を表示。すでに Wi-Fi QR なら URL QR とトグル
        # (Captive Portal が自動表示されない端末向けのバックアップ導線)
        self.goto(1 if self.page == 0 else 0)

    def on_key4_held(self):
        self._key4_held = True
        self.goto(MAP_PAGE)  # 長押し = 地図表示 (4Gray)

    def on_key4_released(self):
        if not self._key4_held:
            self.goto(0)  # 単押し = Wi-Fi QR に戻る (ESC)
        self._key4_held = False

    def run(self):
        # Button オブジェクトは参照を保持しないと GC されてコールバックが死ぬ
        self.buttons = {
            "KEY1": Button(5),   # Wi-Fi QR <-> URL QR
            "KEY2": Button(6),   # network / diagnostics
            "KEY3": Button(13),  # k3s status
            "KEY4": Button(19, hold_time=1.0),  # 単押し=ESC / 長押し=地図
        }
        self.buttons["KEY1"].when_pressed = self.on_key1
        self.buttons["KEY2"].when_pressed = lambda: self.goto(3)
        self.buttons["KEY3"].when_pressed = lambda: self.goto(2)
        self._key4_held = False
        self.buttons["KEY4"].when_held = self.on_key4_held
        self.buttons["KEY4"].when_released = self.on_key4_released
        while True:
            # 地図ページは静的なので自動更新しない (ボタン操作時のみ)
            auto = self.page != MAP_PAGE and (
                time.time() - self.last_render > AUTO_REFRESH_SEC
            )
            if self.dirty or auto:
                try:
                    self.render()
                except Exception as e:
                    print(f"render failed: {e}", flush=True)
                    time.sleep(10)  # 失敗時は少し待って再試行
                    self.dirty = True
            time.sleep(0.2)


def main():
    ob = Onboarding()

    def cleanup(*_):
        print("cleanup: epd sleep", flush=True)
        try:
            ob.epd.sleep()
        finally:
            sys.exit(0)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)
    ob.run()


if __name__ == "__main__":
    main()
