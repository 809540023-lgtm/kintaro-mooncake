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

## 訂單信箱啟用

第一次有人送出訂單時，FormSubmit 會寄一封啟用信到店家信箱，點信中連結啟用一次後即可正常收單。
