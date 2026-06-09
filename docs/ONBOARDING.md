# Pi Swarm 物理オンボーディング構成 (2026-06-03 構築)

e-Paper HAT を Pi Swarm / k3s クラスタの物理オンボーディング画面として使う構成。
ハードウェア基礎情報は NOTES.md を参照。

## 構成要素と変更ファイル一覧

| ファイル | 内容 |
|---|---|
| `/etc/NetworkManager/dnsmasq-shared.d/captive-portal.conf` | 新規。pi4 の DHCP 予約(clusterタグ) + Option 114 を tag:!cluster にのみ配布 |
| `/etc/NetworkManager/dnsmasq-shared.d/yuiseki-dev.conf` | 既存(変更なし)。address=/yuiseki.dev/192.168.100.1 + filter-rr=HTTPS |
| `/etc/caddy/Caddyfile` | handle /captive-portal/api を https/http 両ブロックに追加 (RFC 8908 JSON, application/captive+json) |
| `/etc/caddy/Caddyfile.bak-20260603` | 変更前バックアップ |
| `/opt/niroku/data/welcome/index.html` | 新規。welcome ページ (接続成功表示 + PWA インストールボタン) |
| `/opt/niroku/data/manifest.json` | 新規。PWA manifest (scope=/, start_url=/, standalone) |
| `/opt/niroku/data/sw.js` | 新規。最小 Service Worker (network-first + 簡易オフライン) |
| `/opt/niroku/data/icon-192.png`, `icon-512.png` | 新規。PWA アイコン (PIL 生成) |
| `/home/yuiseki/src/epd_onboarding.py` | 新規。e-Paper 表示デーモン |
| `/etc/systemd/system/epd-onboarding.service` | 新規。enabled |

## ネットワーク要約

- AP: NetworkManager hotspot `ap-wlan1` (wlan1, 192.168.100.1/24, SSID=pi5-w-1, WPA-PSK)
- DHCP/DNS: NM 内蔵 dnsmasq (conf-dir=/etc/NetworkManager/dnsmasq-shared.d)
- pi4-r-2 = d8:3a:dd:19:04:c3 = 192.168.100.174 (予約済み・clusterタグ)
- pi4-r-3 = d8:3a:dd:19:04:ce = 192.168.100.185 (予約済み・clusterタグ)
- **pi4-r-1 は AP 配下にいない** (192.168.0.176 で上流直結)。将来の AP 接続に備え hostname マッチで clusterタグ付与済み
- Option 114 (https://yuiseki.dev/captive-portal/api) は cluster タグのない端末にのみ配布
- yuiseki.dev とそのサブドメインは AP 配下では 192.168.100.1 に解決 → Caddy (*:443, Cloudflare DNS-01 証明書なので閉域でも証明書エラーなし)

## e-Paper 表示 (epd-onboarding.service)

- Page 1: Wi-Fi QR (WIFI:T:WPA;S:pi5-w-1;P:password;;)
- Page 2: https://yuiseki.dev/welcome の URL QR
- Page 3: k3s ノード状態 + 異常 Pod 数
- Page 4: hostname / uplink IP / AP IP / 温度 / uptime / リース数 / caddy / k3s
- ボタン: KEY1=Wi-Fi QR (再押下で URL QR とトグル, Captive Portal 不発時のバックアップ), KEY2=network/diag, KEY3=k3s status, KEY4=単押し: Wi-Fi QR に戻る (ESC) / 長押し1秒: 地図表示 (4Gray)
- 強制更新はページ選択ボタンの再押下でも発生する (dirty フラグ)。自動更新は300秒
- 自動更新: 300秒間隔 (e-Paper 劣化防止のため控えめ)
- ログ: journalctl -u epd-onboarding

## 検証済み (2026-06-03)

- dig yuiseki.dev @192.168.100.1 → 192.168.100.1
- curl https://yuiseki.dev/welcome/ → 200, ssl_verify:0
- curl https://yuiseki.dev/captive-portal/api → RFC 8908 JSON, application/captive+json
- k3s 4/4 Ready, 異常 Pod 0 (AP 再アクティベート後も自然復旧)
- DHCP 予約どおりのリース再取得を確認

## 既知の制約

- Option 114 が実際にスマホに配布されたかはサーバ側ログでは見えない (log-dhcp 無効のため)。実機のスマホで Wi-Fi 再接続して確認する
- Captive Portal は案内専用。captive: true を返し続けるため、OS によっては「インターネット未接続」表示が残る。気になる場合は captive: false 化や Enter 後の状態管理を将来検討
- AUTO_REFRESH_SEC=300 のため k3s 状態の反映は最大5分遅れる (KEY2 で即時更新可)

## Rollback 手順

```bash
# 1. Captive Portal API と Option 114 をやめる
sudo rm /etc/NetworkManager/dnsmasq-shared.d/captive-portal.conf
sudo nmcli con down ap-wlan1 && sudo nmcli con up ap-wlan1  # pi4 が数分 NotReady になるが自然復旧

# 2. Caddy を変更前に戻す
sudo cp /etc/caddy/Caddyfile.bak-20260603 /etc/caddy/Caddyfile
sudo systemctl reload caddy

# 3. e-Paper サービスを止める
sudo systemctl disable --now epd-onboarding.service
sudo rm /etc/systemd/system/epd-onboarding.service && sudo systemctl daemon-reload

# 4. welcome ページを消す (任意)
sudo rm -r /opt/niroku/data/welcome
```

## PWA インストール (2026-06-04 追加)

- Android Chrome 系: /welcome の beforeinstallprompt でインストールボタン表示
- iOS Safari: ボタン不可 (OS 制約)。共有→ホーム画面に追加の手順を案内表示
- キャプティブポータル簡易ブラウザ (CNA) では beforeinstallprompt が来ないため、
  3秒待って来なければ「フルブラウザで開き直して」の案内を表示
- manifest/sw/icon は yuiseki.dev ルート直下 (file_server browse の一覧に出る点は許容)

## 地図表示 (2026-06-04 追加, KEY4 長押し)

- スタイル: /static/styles/toner-epaper-4gray.json (4値固定 #fff/#d0d0d0/#707070/#000)
  - osm-toner.json 派生。building は薄灰塗り+濃灰点線外枠 (minzoom14)、fill-pattern/POI/sprite なし
  - overlay source: kind=current(黒丸)/pi5(白丸黒縁)/track(濃灰線), name でラベル
- レンダリング: headless Chromium + Selenium (~/src/epd_map_capture.py)
  - /static/epaper-map.html (176x264, fadeDuration:0) を map idle まで待って撮影
  - 4値量子化 (閾値 232/160/56) -> epd.Init_4Gray() + display_4Gray()
  - 所要 約6秒。撮影中は "Rendering map..." を先に表示
- 表示位置: MAP_HASH 定数 (epd_onboarding.py 内, 現在 #17.5/35.726048/139.790577)
- 地図ページは自動更新対象外 (静的なため)
- ブラウザ確認: https://yuiseki.dev/static/test.html (4gray ラジオボタン)

## pi-z2-wh 現在地追従 (2026-06-04 追加)

- 地図ページ (KEY4 長押し) は traccar の pi-z2-wh 最新座標を中心に表示・追従
- traccar は k3s 上 (namespace traccar, NodePort 30082=8082, 30055=5055)。H2 組み込みDBで起動中は排他ロック→DB直読み不可、API 経由が正道
- 認証: /home/yuiseki/pi-z2-driving-logger/.traccar.env (TRACCAR_USER/PASSWORD)。device id=1 = pi-z2-wh
- **重要**: traccar の Basic 認証はプリエンプティブに Authorization ヘッダを付けること。urllib の HTTPBasicAuthHandler (チャレンジ応答式) は 401 を取りこぼす
- epd_map_capture.py が Python 側で座標取得→URL クエリ (?lat&lon&course&name) で epaper-map.html に渡す。認証情報はブラウザに晒さない
- 取得失敗時は座標 None → HTML 側で pi5 設置場所中心にフォールバック (地図機能は壊れない)

- pi5-w-1 マーカーは廃止 (ハードコード値で誤った位置を示すため)。GPS 実測の pi-z2-wh (USB GPS マウス) のみ表示
