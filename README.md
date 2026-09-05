# 金太郎 中秋甜品禮盒（代購網站）

日本甜品中秋禮盒代購展示站，主題「金太郎」。含商品照片牆、購物車、運費試算（第 1 地帶）、訂單 Email 送出。

## 架構

- 純靜態網站（`index.html`），Render 以 Static Site 部署。
- 商品資料放在 `products.json`，圖片放在 `images/`。
- 訂單透過 [FormSubmit](https://formsubmit.co) 寄到店家信箱（在 `index.html` 最上方的 `KINTARO_ORDER_EMAIL` 設定）。
- 商品資料由背景自動化每小時從 Google 雲端相簿辨識後更新（更新 `products.json` 與 `images/` 後推到本 repo，Render 會自動重新部署）。

## 本機預覽

```bash
python3 -m http.server 8080
# 開 http://localhost:8080
```

## 更新商品

覆寫 `products.json`（與對應的 `images/`）後 commit、push，Render 會自動重新部署。

`products.json` 每個商品欄位：

| 欄位 | 說明 |
|------|------|
| `title` | 品名 |
| `desc` | 介紹（可留空） |
| `price` | 顯示用價格字串（如「日本售價 JP¥1,998（含稅）」） |
| `qty` | 數量／入數（如「20 支入」） |
| `priceJPY` | 純數字日圓價（購物車計算用） |
| `weight_g` | 每盒重量（0＝用購物車預設值估算） |
| `images` | 圖片路徑陣列（`images/xxx.jpg`） |
| `labelImg` | 選用：該商品價目標籤照片路徑（辨識用，前台不顯示） |

## 持續新增商品（進貨管線）

店家會在 Google 雲端硬碟按日期開新資料夾放商品照片（每組 4 張：1 張價目標籤 + 3 張商品照）。
把新資料夾丟進來後，跑：

```bash
python3 tools/ingest.py --src "/新的照片資料夾路徑"            # 實際寫入
python3 tools/ingest.py --src "/新的照片資料夾路徑" --dry-run   # 先預覽不寫入
```

腳本會自動：轉檔壓縮 → OCR 讀價目標籤 → 依拍攝時間與標籤分組 → 擷取品名／稅込價格／入數 → 編號接續併入 `products.json` 與 `images/`。
辨識規則與品牌官網對應放在 `tools/title-fixes.json`、`tools/brands.json`，遇到新品名或新品牌就往這兩個檔加規則。
OCR 使用 macOS 內建 Vision（`tools/ocr.swift`，首次執行會自動編譯），需在 Mac 上執行。

## 購物車送出 LINE@ 估價

購物車面板新增「📱 用 LINE 發送估價」：點擊後自動**複製商品明細**（品名 × 數量、JPY 小計、運費估算、收件人資料），
並直接開啟店家 LINE 官方帳號（`KINTARO_LINE_URL`，短連結 <https://lin.ee/xtBgE5B>），顧客貼上後送出即可估價。
金額僅供參考，以最終報價為主。

## 訂單信箱啟用

第一次有人送出訂單時，FormSubmit 會寄一封啟用信到店家信箱，點信中連結啟用一次後即可正常收單。
