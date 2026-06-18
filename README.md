# @biglazyseals 每日 IG 數據追蹤器

每晚 22:30（台灣時間）自動拉 Instagram Reels 數據，寄到指定 Email。

---

## 設定步驟

### 1. 建立 GitHub Repo

1. 到 [github.com](https://github.com) 新增一個 **private** repo，名稱例如 `biglazyseals-tracker`
2. 把這個資料夾的所有檔案上傳進去（或用 git push）

### 2. 取得 Windsor.ai API Key

1. 登入 Windsor.ai → 右上角頭像 → **API Key**
2. 複製你的 API Key

### 3. 取得 Gmail App Password

> 注意：不是你的 Gmail 登入密碼，是 App 專用密碼

1. 登入 Google 帳號 → [myaccount.google.com/security](https://myaccount.google.com/security)
2. 確認已開啟「兩步驟驗證」
3. 搜尋「應用程式密碼」→ 新增一個，名稱隨便填（例如 `biglazyseals tracker`）
4. 複製產生的 16 碼密碼

### 4. 設定 GitHub Secrets

在你的 repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

新增以下四個 Secrets：

| 名稱 | 值 |
|------|----|
| `WINDSOR_API_KEY` | Windsor.ai 的 API Key |
| `ANTHROPIC_API_KEY` | Anthropic API Key（目前腳本備用，可先填任意值） |
| `GMAIL_USER` | `biglazyseals@gmail.com` |
| `GMAIL_APP_PASSWORD` | 剛才產生的 16 碼 App 密碼 |

### 5. 測試

設定完成後，到 repo → **Actions** → **Daily IG Tracker** → **Run workflow**

手動觸發一次，確認 email 有收到再等自動排程。

---

## 趨緩偵測邏輯

若某集 Reels 貼文超過 7 天且觀看次數低於 1,000，Email 中會出現橘色警告，建議停止追蹤該集。

---

## 檔案結構

```
biglazyseals-tracker/
├── .github/
│   └── workflows/
│       └── daily_tracker.yml   # GitHub Actions 排程設定
├── scripts/
│   └── tracker.py              # 主程式
└── README.md
```
