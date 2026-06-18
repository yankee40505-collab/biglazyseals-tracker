import os
import json
import requests
import smtplib
import anthropic
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta

# ── 設定 ──────────────────────────────────────────────
WINDSOR_API_KEY   = os.environ["WINDSOR_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GMAIL_USER        = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD= os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT_EMAIL   = os.environ["RECIPIENT_EMAIL"]

IG_ACCOUNT_ID = "17841414078573276"
FIELDS = [
    "timestamp", "media_caption", "media_type",
    "media_views", "media_reach", "media_reel_total_interactions",
    "media_reel_avg_watch_time", "media_saved", "media_shares",
    "media_comments_count", "media_like_count", "media_permalink"
]

# 台灣時間
TW = timezone(timedelta(hours=8))

# ── 趨緩偵測門檻 ──────────────────────────────────────
# 若觀看增量 < 這個數字，視為趨緩（可自行調整）
SLOWDOWN_THRESHOLD = 500


def fetch_windsor_data():
    url = "https://api.windsor.ai/all"
    params = {
        "api_key": WINDSOR_API_KEY,
        "connector": "instagram",
        "accounts": IG_ACCOUNT_ID,
        "date_preset": "last_30dT",
        "fields": ",".join(FIELDS),
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("data", [])


def filter_reels(data):
    return [d for d in data if d.get("media_type") == "REELS"]


def get_series_episodes(reels):
    """
    心靈電影院：caption 含 '心靈電影院'
    深夜選片指南：caption 含 '深夜選片'
    各取最新一集（timestamp 最大）
    """
    xingling = [r for r in reels if "心靈電影院" in (r.get("media_caption") or "")]
    shenyie  = [r for r in reels if "深夜選片" in (r.get("media_caption") or "")]

    latest_xl = max(xingling, key=lambda x: x.get("timestamp", ""), default=None)
    latest_sy  = max(shenyie,  key=lambda x: x.get("timestamp", ""), default=None)
    return latest_xl, latest_sy


def detect_slowdown(ep):
    """
    簡易趨緩判斷：
    若貼文已超過 7 天且觀看 < 100（幾乎停止），或
    若貼文超過 3 天且每日平均增量估算 < SLOWDOWN_THRESHOLD
    這裡只用靜態快照，真正的趨緩追蹤需要歷史數據對比。
    回傳 (is_slowing_down: bool, reason: str)
    """
    if not ep:
        return False, ""
    ts = ep.get("timestamp", "")
    if not ts:
        return False, ""
    try:
        post_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        days_old = (datetime.now(timezone.utc) - post_time).days
        views = ep.get("media_views") or 0
        if days_old >= 7 and views < 1000:
            return True, f"貼文已 {days_old} 天，觀看停滯在 {int(views):,}"
    except Exception:
        pass
    return False, ""


def format_ep_data(ep, series_name):
    if not ep:
        return f"<p style='color:#888'>（{series_name}：本月尚無資料）</p>"

    caption   = (ep.get("media_caption") or "")[:80].replace("\n", " ")
    views     = int(ep.get("media_views") or 0)
    reach     = int(ep.get("media_reach") or 0)
    likes     = int(ep.get("media_like_count") or 0)
    comments  = int(ep.get("media_comments_count") or 0)
    saved     = int(ep.get("media_saved") or 0)
    shares    = int(ep.get("media_shares") or 0)
    interact  = int(ep.get("media_reel_total_interactions") or 0)
    avg_watch = round((ep.get("media_reel_avg_watch_time") or 0) / 1000, 1)
    permalink = ep.get("media_permalink", "#")
    ts        = ep.get("timestamp", "")
    try:
        post_dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(TW)
        post_str = post_dt.strftime("%Y/%m/%d %H:%M")
    except Exception:
        post_str = ts

    is_slow, slow_reason = detect_slowdown(ep)
    slow_banner = ""
    if is_slow:
        slow_banner = f"""
        <div style="background:#FAEEDA;border-radius:8px;padding:8px 12px;margin-bottom:10px;font-size:13px;color:#854F0B;">
            ⚠️ 趨緩偵測：{slow_reason}。建議停止每日追蹤此集。
        </div>"""

    return f"""
    <div style="background:#f9f8f6;border-radius:10px;padding:16px;margin-bottom:16px;">
        <div style="margin-bottom:8px;">
            <span style="background:#E1F5EE;color:#0F6E56;font-size:11px;padding:2px 8px;border-radius:999px;">{series_name}</span>
            <span style="font-size:11px;color:#888;margin-left:8px;">{post_str} 發布</span>
        </div>
        <p style="font-size:13px;color:#444;margin:0 0 12px;">{caption}…</p>
        {slow_banner}
        <table style="width:100%;border-collapse:collapse;">
            <tr>
                <td style="padding:6px 8px;background:#E1F5EE;border-radius:6px;text-align:center;width:25%">
                    <div style="font-size:11px;color:#0F6E56;">觀看次數</div>
                    <div style="font-size:20px;font-weight:500;color:#0F6E56;">{views:,}</div>
                </td>
                <td style="width:4px"></td>
                <td style="padding:6px 8px;background:#F5F5F3;border-radius:6px;text-align:center;width:25%">
                    <div style="font-size:11px;color:#666;">觸及人數</div>
                    <div style="font-size:20px;font-weight:500;color:#333;">{reach:,}</div>
                </td>
                <td style="width:4px"></td>
                <td style="padding:6px 8px;background:#F5F5F3;border-radius:6px;text-align:center;width:25%">
                    <div style="font-size:11px;color:#666;">儲存</div>
                    <div style="font-size:20px;font-weight:500;color:#333;">{saved:,}</div>
                </td>
                <td style="width:4px"></td>
                <td style="padding:6px 8px;background:#F5F5F3;border-radius:6px;text-align:center;width:25%">
                    <div style="font-size:11px;color:#666;">分享</div>
                    <div style="font-size:20px;font-weight:500;color:#333;">{shares:,}</div>
                </td>
            </tr>
        </table>
        <table style="width:100%;border-collapse:collapse;margin-top:6px;">
            <tr>
                <td style="padding:6px 8px;background:#F5F5F3;border-radius:6px;text-align:center;width:25%">
                    <div style="font-size:11px;color:#666;">按讚</div>
                    <div style="font-size:16px;font-weight:500;color:#333;">{likes:,}</div>
                </td>
                <td style="width:4px"></td>
                <td style="padding:6px 8px;background:#F5F5F3;border-radius:6px;text-align:center;width:25%">
                    <div style="font-size:11px;color:#666;">留言</div>
                    <div style="font-size:16px;font-weight:500;color:#333;">{comments:,}</div>
                </td>
                <td style="width:4px"></td>
                <td style="padding:6px 8px;background:#F5F5F3;border-radius:6px;text-align:center;width:25%">
                    <div style="font-size:11px;color:#666;">總互動</div>
                    <div style="font-size:16px;font-weight:500;color:#333;">{interact:,}</div>
                </td>
                <td style="width:4px"></td>
                <td style="padding:6px 8px;background:#F5F5F3;border-radius:6px;text-align:center;width:25%">
                    <div style="font-size:11px;color:#666;">平均觀看</div>
                    <div style="font-size:16px;font-weight:500;color:#333;">{avg_watch} 秒</div>
                </td>
            </tr>
        </table>
        <p style="margin:10px 0 0;font-size:12px;">
            <a href="{permalink}" style="color:#0F6E56;">在 Instagram 查看 →</a>
        </p>
    </div>
    """


def build_email_html(xl_html, sy_html):
    now_tw = datetime.now(TW).strftime("%Y/%m/%d %H:%M")
    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:600px;margin:0 auto;padding:20px;background:#fff;">

  <div style="margin-bottom:20px;">
    <span style="background:#E1F5EE;color:#0F6E56;font-size:11px;padding:3px 10px;border-radius:999px;">@biglazyseals · 每日追蹤</span>
    <p style="font-size:22px;font-weight:500;color:#2C2C2A;margin:8px 0 4px;">Instagram Reels 數據報告</p>
    <p style="font-size:12px;color:#888;margin:0;">報告時間：{now_tw}（台灣時間）</p>
  </div>

  <hr style="border:none;border-top:0.5px solid #D3D1C7;margin:16px 0;">

  <p style="font-size:13px;font-weight:500;color:#5F5E5A;margin:0 0 10px;">💘 心靈電影院（最新集數）</p>
  {xl_html}

  <p style="font-size:13px;font-weight:500;color:#5F5E5A;margin:16px 0 10px;">🌙 深夜選片指南（最新集數）</p>
  {sy_html}

  <hr style="border:none;border-top:0.5px solid #D3D1C7;margin:20px 0 12px;">
  <p style="font-size:11px;color:#aaa;margin:0;">資料來源：Windsor.ai · Instagram Insights · 自動排程於每晚 22:30（台灣時間）</p>
</body>
</html>
    """


def send_email(html_content):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 @biglazyseals 每日數據 {datetime.now(TW).strftime('%m/%d')}"
    msg["From"]    = GMAIL_USER
    msg["To"]      = RECIPIENT_EMAIL
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_string())
    print("Email sent.")


def main():
    print("Fetching Windsor.ai data...")
    data  = fetch_windsor_data()
    reels = filter_reels(data)
    print(f"Found {len(reels)} Reels.")

    xl_ep, sy_ep = get_series_episodes(reels)

    xl_html = format_ep_data(xl_ep, "心靈電影院")
    sy_html = format_ep_data(sy_ep, "深夜選片指南")

    html = build_email_html(xl_html, sy_html)
    send_email(html)
    print("Done.")


if __name__ == "__main__":
    main()
