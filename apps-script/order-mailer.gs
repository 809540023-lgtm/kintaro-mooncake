/**
 * 林博 中秋禮盒 — 訂單寄信後端（Google Apps Script）
 *
 * 功能：網站「送出訂單」時直接用你的 Gmail 把訂單寄到店家信箱，
 *       顧客手機／電腦都不需要開郵件 App。
 *
 * 設定步驟（約 5 分鐘）：
 *   1. 開 https://script.google.com → 左上「新增專案」
 *   2. 把這個檔案的全部內容貼進編輯器，覆蓋原本的程式碼
 *   3. 按「儲存」，然後按上方「部署」→「新增部署作業」
 *   4. 類型選「網頁應用程式」：
 *        - 說明：任意
 *        - 執行身分：我（你的帳號）
 *        - 具有存取權的使用者：所有人
 *   5. 按「部署」→ 授權（選你的帳號 → 進階 → 允許）
 *   6. 複製產生的「網頁應用程式」網址（結尾是 /exec）
 *   7. 把網址貼到 index.html 裡的 window.KINTARO_ORDER_API = "這裡"
 *   8. commit + push 即生效
 *
 * 注意：第一次部署會要求授權 Gmail 寄信權限（MailApp），照畫面點下去即可。
 *       免費 Gmail 每天可寄約 100 封，足夠訂單使用。
 */

// 店家收單信箱（也可以用 e.parameter 覆寫，這裡固定即可）
var ORDER_TO = 'cia8885@gmail.com';

function doPost(e) {
  try {
    var d = JSON.parse(e.postData.contents);
    var subject = d._subject || '【林博】新訂單';
    var body = [
      '姓名：' + (d['姓名'] || ''),
      '電話：' + (d['電話'] || ''),
      '地址：' + (d['地址'] || ''),
      '',
      d.text || ''
    ].join('\n');
    MailApp.sendEmail({ to: ORDER_TO, subject: subject, body: body });
    return ContentService
      .createTextOutput(JSON.stringify({ status: 'ok' }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ status: 'error', message: String(err) }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

// 瀏覽器打開網址測試用：看到 {"status":"ok"} 代表部署成功
function doGet(e) {
  return ContentService
    .createTextOutput(JSON.stringify({ status: 'ok', service: 'order-mailer' }))
    .setMimeType(ContentService.MimeType.JSON);
}