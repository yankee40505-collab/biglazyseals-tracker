import os
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta

META_ACCESS_TOKEN  = os.environ["META_ACCESS_TOKEN"]
GMAIL_USER         = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT_EMAIL    = os.environ["RECIPIENT_EMAIL"]

IG_USER_ID = "17841414078573276"
TW = timezone(timedelta(hours=8))
SLOWDOWN_DAYS  = 7
SLOWDOWN_VIEWS = 1000

def fetch_ig_reels():
    url = f"https://graph.facebook.com/v25.0/{IG_USER_ID}/media"
    params = {
        "fields": "id,caption,media_type,timestamp,permalink",
        "access_token": META_ACCESS_TOKEN,
        "limit": 20,
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    items = r.json().get("data", [])
    print(f"Raw items: {[(i.get('id'), i.get('media_type')) for i in items]}")
    reels = [i for i in items if i.get("media_type") in ("VIDEO", "REELS")]
    print(f"Filtered reels: {len(reels)}")

    results = []
    for reel in reels[:10]:
        mid = reel["id"]
        ins_url = f"https://graph.facebook.com/v25.0/{mid}/insights"
        ins_params = {
            "metric": "views,reach,saved,shares,comments,likes,total_interactions,ig_reels_avg_watch_time",
            "access_token": META_ACCESS_TOKEN,
        }
        ins_r = requests.get(ins_url, params=ins_params, timeout=30)
        if ins_r.status_code != 200:
            print(f"Insights error for {mid}: {ins_r.status_code} {ins_r.text[:200]}")
            continue
        ins_data = {m["name"]: m["values"][0]["value"] for m in ins_r.json().get("data", [])}
        reel.update(ins_data)
        results.append(reel)
    return results

def get_latest_episode(reels, keyword):
    matches = [r for r in reels if keyword in (r.get("caption") or "")]
    return max(matches, key=lambda x: x.get("timestamp", ""), default=None)

def detect_slowdown(ep):
    if not ep:
        return False, ""
    ts = ep.get("timestamp", "")
    try:
        post_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        days_old = (datetime.now(timezone.utc) - post_time).days
        views = int(ep.get("views") or 0)
        if days_old >= SLOWDOWN_DAYS and views < SLOWDOWN_VIEWS:
            return True, f"貼文已 {days_old} 天，觀看停滯在 {views:,}"
    except Exception:
        pass
    return False, ""

def ig_card(ep, series_name, emoji):
    if not ep:
        return f"<p style='color:#888;font-size:13px;'>（{series_name}：本月尚無資料）</p>"

    caption  = (ep.get("caption") or "")[:80].replace("\n", " ")
    views    = int(ep.get("views") or 0)
    reach    = int(ep.get("reach") or 0)
    likes    = int(ep.get("likes") or 0)
    comments = int(ep.get("comments") or 0)
    saved    = int(ep.get("saved") or 0)
    shares   = int(ep.get("shares") or 0)
    interact = int(ep.get("total_interactions") or 0)
    avg_w    = round((ep.get("ig_reels_avg_watch_time") or 0) / 1000, 1)
    link     = ep.get("permalink", "#")
    ts       = ep.get("timestamp", "")
    try:
        dt_str = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(TW).strftime("%Y/%m/%d %H:%M")
    except Exception:
        dt_str = ts

    is_slow, slow_reason = detect_slowdown(ep)
    slow_html = f"""<div style="background:#FAEEDA;border-radius:8px;padding:8px 12px;
        margin-bottom:10px;font-size:12px;color:#854F0B;">
        ⚠️ 趨緩偵測：{slow_reason}。建議停止每日追蹤此集。</div>""" if is_slow else ""

    def cell(label, val, hi=False):
        bg = "#E1F5EE" if hi else "#F5F5F3"
        lc = "#0F6E56" if hi else "#666"
        vc = "#0F6E56" if hi else "#333"
        sz = "20px" if hi else "17px"
        return f"""<td style="padding:7px 8px;background:{bg};border-radius:6px;
            text-align:center;width:25%">
            <div style="font-size:11px;color:{lc};">{label}</div>
            <div style="font-size:{sz};font-weight:500;color:{vc};">{val}</div></td>"""

    sp = '<td style="width:4px"></td>'
    return f"""
    <div style="background:#f9f8f6;border-radius:10px;padding:16px;margin-bottom:16px;">
        <div style="margin-bottom:8px;">
            <span style="background:#E1F5EE;color:#0F6E56;font-size:11px;padding:2px 8px;border-radius:999px;">{emoji} {series_name}</span>
            <span style="font-size:11px;color:#888;margin-left:8px;">{dt_str} 發布</span>
        </div>
        <p style="font-size:12px;color:#555;margin:0 0 12px;">{caption}…</p>
        {slow_html}
        <table style="width:100%;border-collapse:separate;border-spacing:4px 0;">
            <tr>{cell("觀看次數",f"{views:,}",hi=True)}{sp}{cell("觸及人數",f"{reach:,}")}{sp}{cell("儲存",f"{saved:,}")}{sp}{cell("分享",f"{shares:,}")}</tr>
        </table>
        <table style="width:100%;border-collapse:separate;border-spacing:4px 0;margin-top:6px;">
            <tr>{cell("按讚",f"{likes:,}")}{sp}{cell("留言",f"{comments:,}")}{sp}{cell("總互動",f"{interact:,}")}{sp}{cell("平均觀看",f"{avg_w} 秒")}</tr>
        </table>
        <p style="margin:10px 0 0;font-size:12px;"><a href="{link}" style="color:#0F6E56;">在 Instagram 查看 →</a></p>
    </div>"""

def build_email(xl, sy):
    now_tw = datetime.now(TW).strftime("%Y/%m/%d %H:%M")
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
             max-width:600px;margin:0 auto;padding:20px;background:#fff;">
  <span style="background:#E1F5EE;color:#0F6E56;font-size:11px;padding:3px 10px;border-radius:999px;">@biglazyseals · 每日追蹤</span>
  <p style="font-size:21px;font-weight:500;color:#2C2C2A;margin:8px 0 4px;">Instagram Reels 數據報告</p>
  <p style="font-size:12px;color:#888;margin:0 0 16px;">報告時間：{now_tw}（台灣時間）</p>
  <hr style="border:none;border-top:0.5px solid #D3D1C7;margin-bottom:16px;">
  <p style="font-size:13px;font-weight:500;color:#5F5E5A;margin:0 0 8px;">💘 心靈電影院（最新集數）</p>
  {xl}
  <p style="font-size:13px;font-weight:500;color:#5F5E5A;margin:16px 0 8px;">🌙 深夜選片指南（最新集數）</p>
  {sy}
  <hr style="border:none;border-top:0.5px solid #D3D1C7;margin:20px 0 10px;">
  <p style="font-size:11px;color:#aaa;margin:0;">資料來源：Instagram Graph API · 自動排程每晚 21:00（台灣時間）</p>
</body></html>"""

def send_email(html):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 @biglazyseals 每日數據 {datetime.now(TW).strftime('%m/%d')}"
    msg["From"]    = GMAIL_USER
    msg["To"]      = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_string())
    print("Email sent.")

def main():
    print("Fetching Instagram data...")
    reels = fetch_ig_reels()
    print(f"Found {len(reels)} reels.")

    xl_ep = get_latest_episode(reels, "大懶豹心靈電影院")
    sy_ep = get_latest_episode(reels, "大懶豹深夜選片")

    html = build_email(
        ig_card(xl_ep, "心靈電影院", "💘"),
        ig_card(sy_ep, "深夜選片指南", "🌙"),
    )
    send_email(html)
    print("Done.")

if __name__ == "__main__":
    main()
