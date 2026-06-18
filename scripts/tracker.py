import os
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta

WINDSOR_API_KEY    = os.environ["WINDSOR_API_KEY"]
GMAIL_USER         = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT_EMAIL    = os.environ["RECIPIENT_EMAIL"]

IG_ACCOUNT_ID = "17841414078573276"
YT_ACCOUNT_ID = "18192"
TW = timezone(timedelta(hours=8))
SLOWDOWN_DAYS  = 7
SLOWDOWN_VIEWS = 1000

IG_FIELDS = [
    "timestamp", "media_caption", "media_type",
    "media_views", "media_reach", "media_reel_total_interactions",
    "media_reel_avg_watch_time", "media_saved", "media_shares",
    "media_comments_count", "media_like_count", "media_permalink"
]

YT_FIELDS = [
    "published_at", "video_title", "video_description",
    "views", "likes", "comments", "shares",
    "average_view_duration", "average_view_percentage",
    "subscribers_gained", "subscribers_lost", "videourl"
]


def fetch_ig_data():
    r = requests.get(
        "https://connectors.windsor.ai/instagram",
        params={
            "api_key": WINDSOR_API_KEY,
            "accounts": IG_ACCOUNT_ID,
            "date_preset": "last_30dT",
            "fields": ",".join(IG_FIELDS),
        },
        timeout=30
    )
    r.raise_for_status()
    return r.json().get("data", [])


def fetch_yt_data():
    r = requests.get(
        "https://connectors.windsor.ai/youtube",
        params={
            "api_key": WINDSOR_API_KEY,
            "accounts": YT_ACCOUNT_ID,
            "date_preset": "last_30dT",
            "fields": ",".join(YT_FIELDS),
        },
        timeout=30
    )
    r.raise_for_status()
    return r.json().get("data", [])


def filter_reels(data):
    return [d for d in data if d.get("media_type") == "REELS"]


def get_latest_ig_episode(reels, keyword):
    matches = [r for r in reels if keyword in (r.get("media_caption") or "")]
    return max(matches, key=lambda x: x.get("timestamp", ""), default=None)


def get_latest_yt_video(data):
    videos = [d for d in data if d.get("video_title")]
    return max(videos, key=lambda x: x.get("published_at", ""), default=None)


def detect_ig_slowdown(ep):
    if not ep:
        return False, ""
    ts = ep.get("timestamp", "")
    try:
        post_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        days_old = (datetime.now(timezone.utc) - post_time).days
        views = int(ep.get("media_views") or 0)
        if days_old >= SLOWDOWN_DAYS and views < SLOWDOWN_VIEWS:
            return True, f"貼文已 {days_old} 天，觀看停滯在 {views:,}"
    except Exception:
        pass
    return False, ""


def ig_card(ep, series_name, emoji):
    if not ep:
        return f"<p style='color:#888;font-size:13px;'>（{series_name}：本月尚無資料）</p>"

    caption  = (ep.get("media_caption") or "")[:80].replace("\n", " ")
    views    = int(ep.get("media_views") or 0)
    reach    = int(ep.get("media_reach") or 0)
    likes    = int(ep.get("media_like_count") or 0)
    comments = int(ep.get("media_comments_count") or 0)
    saved    = int(ep.get("media_saved") or 0)
    shares   = int(ep.get("media_shares") or 0)
    interact = int(ep.get("media_reel_total_interactions") or 0)
    avg_w    = round((ep.get("media_reel_avg_watch_time") or 0) / 1000, 1)
    link     = ep.get("media_permalink", "#")
    ts       = ep.get("timestamp", "")
    try:
        dt_str = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(TW).strftime("%Y/%m/%d %H:%M")
    except Exception:
        dt_str = ts

    is_slow, slow_reason = detect_ig_slowdown(ep)
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


def yt_card(ep):
    if not ep:
        return "<p style='color:#888;font-size:13px;'>（YouTube：本月尚無資料）</p>"

    title    = (ep.get("video_title") or "")[:60]
    views    = int(ep.get("views") or 0)
    likes    = int(ep.get("likes") or 0)
    comments = int(ep.get("comments") or 0)
    shares   = int(ep.get("shares") or 0)
    avg_dur  = int(ep.get("average_view_duration") or 0)
    avg_pct  = round(float(ep.get("average_view_percentage") or 0), 1)
    subs_g   = int(ep.get("subscribers_gained") or 0)
    subs_l   = int(ep.get("subscribers_lost") or 0)
    link     = ep.get("videourl", "#")
    ts       = ep.get("published_at", "")
    try:
        dt_str = datetime.fromisoformat(str(ts)).astimezone(TW).strftime("%Y/%m/%d")
    except Exception:
        dt_str = str(ts)

    mins = avg_dur // 60
    secs = avg_dur % 60
    avg_dur_str = f"{mins}:{secs:02d}"

    def cell(label, val):
        return f"""<td style="padding:7px 8px;background:#F5F5F3;border-radius:6px;
            text-align:center;width:25%">
            <div style="font-size:11px;color:#666;">{label}</div>
            <div style="font-size:17px;font-weight:500;color:#333;">{val}</div></td>"""

    sp = '<td style="width:4px"></td>'
    return f"""
    <div style="background:#f9f8f6;border-radius:10px;padding:16px;margin-bottom:16px;">
        <div style="margin-bottom:8px;">
            <span style="background:#FFE8E8;color:#C00;font-size:11px;padding:2px 8px;border-radius:999px;">▶ YouTube 最新影片</span>
            <span style="font-size:11px;color:#888;margin-left:8px;">{dt_str} 發布</span>
        </div>
        <p style="font-size:13px;font-weight:500;color:#333;margin:0 0 12px;">{title}</p>
        <table style="width:100%;border-collapse:separate;border-spacing:4px 0;">
            <tr>
                <td style="padding:7px 8px;background:#FFE8E8;border-radius:6px;text-align:center;width:25%">
                    <div style="font-size:11px;color:#C00;">觀看次數</div>
                    <div style="font-size:20px;font-weight:500;color:#C00;">{views:,}</div>
                </td>
                {sp}{cell("按讚",f"{likes:,}")}{sp}{cell("留言",f"{comments:,}")}{sp}{cell("分享",f"{shares:,}")}
            </tr>
        </table>
        <table style="width:100%;border-collapse:separate;border-spacing:4px 0;margin-top:6px;">
            <tr>{cell("平均觀看時長",avg_dur_str)}{sp}{cell("平均觀看%",f"{avg_pct}%")}{sp}{cell("新訂閱",f"+{subs_g:,}")}{sp}{cell("取消訂閱",f"-{subs_l:,}")}</tr>
        </table>
        <p style="margin:10px 0 0;font-size:12px;"><a href="{link}" style="color:#C00;">在 YouTube 查看 →</a></p>
    </div>"""


def build_email(xl, sy, yt):
    now_tw = datetime.now(TW).strftime("%Y/%m/%d %H:%M")
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
             max-width:600px;margin:0 auto;padding:20px;background:#fff;">
  <span style="background:#E1F5EE;color:#0F6E56;font-size:11px;padding:3px 10px;border-radius:999px;">@biglazyseals · 每日追蹤</span>
  <p style="font-size:21px;font-weight:500;color:#2C2C2A;margin:8px 0 4px;">Instagram & YouTube 數據報告</p>
  <p style="font-size:12px;color:#888;margin:0 0 16px;">報告時間：{now_tw}（台灣時間）</p>
  <hr style="border:none;border-top:0.5px solid #D3D1C7;margin-bottom:16px;">
  <p style="font-size:13px;font-weight:500;color:#5F5E5A;margin:0 0 8px;">💘 心靈電影院（最新集數）</p>
  {xl}
  <p style="font-size:13px;font-weight:500;color:#5F5E5A;margin:16px 0 8px;">🌙 深夜選片指南（最新集數）</p>
  {sy}
  <hr style="border:none;border-top:0.5px solid #D3D1C7;margin:16px 0;">
  <p style="font-size:13px;font-weight:500;color:#5F5E5A;margin:0 0 8px;">YouTube 最新影片</p>
  {yt}
  <hr style="border:none;border-top:0.5px solid #D3D1C7;margin:20px 0 10px;">
  <p style="font-size:11px;color:#aaa;margin:0;">資料來源：Windsor.ai · 自動排程每晚 22:30（台灣時間）</p>
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
    ig_data = fetch_ig_data()
    reels   = filter_reels(ig_data)
    xl_ep   = get_latest_ig_episode(reels, "心靈電影院")
    sy_ep   = get_latest_ig_episode(reels, "深夜選片")

    print("Fetching YouTube data...")
    yt_data = fetch_yt_data()
    yt_ep   = get_latest_yt_video(yt_data)

    html = build_email(
        ig_card(xl_ep, "心靈電影院", "💘"),
        ig_card(sy_ep, "深夜選片指南", "🌙"),
        yt_card(yt_ep)
    )
    send_email(html)
    print("Done.")


if __name__ == "__main__":
    main()
