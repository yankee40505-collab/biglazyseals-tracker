import os
import smtplib
import sys
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

WINDSOR_API_KEY    = os.environ["WINDSOR_API_KEY"]
GMAIL_USER         = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT_EMAIL    = "biglazyseals@gmail.com"

IG_ACCOUNT_ID  = "17841414078573276"
YT_ACCOUNT_ID  = "18192"
TW             = timezone(timedelta(hours=8))
SLOWDOWN_DAYS  = 7
SLOWDOWN_VIEWS = 1000

IG_FIELDS = [
    "timestamp", "media_caption", "media_type",
    "media_views", "media_reach", "media_reel_total_interactions",
    "media_reel_avg_watch_time", "media_saved", "media_shares",
    "media_comments_count", "media_like_count", "media_permalink",
]

YT_FIELDS = [
    "published_at", "video_title", "views", "likes", "comments", "shares",
    "average_view_duration", "average_view_percentage",
    "subscribers_gained", "subscribers_lost", "videourl", "creator_content_type",
]


def fetch_ig_data():
    try:
        r = requests.get(
            "https://connectors.windsor.ai/instagram",
            params={
                "api_key": WINDSOR_API_KEY,
                "account_id": IG_ACCOUNT_ID,
                "date_preset": "last_90dT",
                "fields": ",".join(IG_FIELDS),
            },
            timeout=90,
        )
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception as e:
        print(f"Instagram API error: {e}")
        return []


def fetch_yt_data():
    try:
        r = requests.get(
            "https://connectors.windsor.ai/youtube",
            params={
                "api_key": WINDSOR_API_KEY,
                "account_id": YT_ACCOUNT_ID,
                "date_preset": "last_90dT",
                "fields": ",".join(YT_FIELDS),
            },
            timeout=30,
        )
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception as e:
        print(f"YouTube API error: {e}")
        return []


def filter_reels(data):
    return [d for d in data if str(d.get("media_type") or "").upper() == "REELS"]


def get_latest_ig_episode(reels, keyword):
    matches = [r for r in reels if keyword in (r.get("media_caption") or "")]
    return max(matches, key=lambda x: str(x.get("timestamp") or ""), default=None)


def get_latest_yt(data):
    shorts = [d for d in data if str(d.get("creator_content_type") or "").lower() == "shorts"]
    if shorts:
        return max(shorts, key=lambda x: str(x.get("published_at") or ""), default=None), True
    videos = [d for d in data if d.get("video_title")]
    return max(videos, key=lambda x: str(x.get("published_at") or ""), default=None), False


def detect_slowdown(ep):
    if not ep:
        return False, ""
    try:
        ts = str(ep.get("timestamp") or "").replace("Z", "+00:00")
        post_time = datetime.fromisoformat(ts)
        days_old = (datetime.now(timezone.utc) - post_time).days
        views = int(ep.get("media_views") or 0)
        if days_old >= SLOWDOWN_DAYS and views < SLOWDOWN_VIEWS:
            return True, f"貼文已 {days_old} 天，觀看停滯在 {views:,}"
    except Exception:
        pass
    return False, ""


def fmt_ts_tw(ts, date_only=False):
    if not ts:
        return "—"
    try:
        s = str(ts).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s).astimezone(TW)
        return dt.strftime("%Y/%m/%d") if date_only else dt.strftime("%Y/%m/%d %H:%M")
    except Exception:
        return str(ts)


def metric_cell(label, val, bg="#F5F5F3", color="#333", hi_color=None):
    vc = hi_color or color
    sz = "20px" if hi_color else "17px"
    return f"""<td style="padding:7px 8px;background:{bg};border-radius:6px;
        text-align:center;width:25%">
        <div style="font-size:11px;color:#666;">{label}</div>
        <div style="font-size:{sz};font-weight:500;color:{vc};">{val}</div></td>"""

SP = '<td style="width:4px"></td>'


def ig_card(ep, series_name, emoji):
    if not ep:
        return f"""<div style="background:#f9f8f6;border-radius:10px;padding:16px;margin-bottom:16px;">
            <span style="background:#E1F5EE;color:#0F6E56;font-size:11px;padding:2px 8px;border-radius:999px;">{emoji} {series_name}</span>
            <p style="color:#999;font-size:13px;margin:12px 0 0;">本月尚無資料</p></div>"""

    caption  = (ep.get("media_caption") or "")[:80].replace("\n", " ")
    views    = int(ep.get("media_views") or 0)
    reach    = int(ep.get("media_reach") or 0)
    likes    = int(ep.get("media_like_count") or 0)
    comments = int(ep.get("media_comments_count") or 0)
    saved    = int(ep.get("media_saved") or 0)
    shares   = int(ep.get("media_shares") or 0)
    interact = int(ep.get("media_reel_total_interactions") or 0)
    avg_w    = round(float(ep.get("media_reel_avg_watch_time") or 0) / 1000, 1)
    link     = ep.get("media_permalink") or "#"
    dt_str   = fmt_ts_tw(ep.get("timestamp"))

    is_slow, slow_reason = detect_slowdown(ep)
    slow_html = f"""<div style="background:#FAEEDA;border-radius:8px;padding:8px 12px;
        margin-bottom:10px;font-size:12px;color:#854F0B;">
        ⚠️ 趨緩偵測：{slow_reason}。建議停止每日追蹤此集。</div>""" if is_slow else ""

    return f"""
    <div style="background:#f9f8f6;border-radius:10px;padding:16px;margin-bottom:16px;">
        <div style="margin-bottom:8px;">
            <span style="background:#E1F5EE;color:#0F6E56;font-size:11px;padding:2px 8px;border-radius:999px;">{emoji} {series_name}</span>
            <span style="font-size:11px;color:#888;margin-left:8px;">{dt_str} 發布</span>
        </div>
        <p style="font-size:12px;color:#555;margin:0 0 12px;">{caption}…</p>
        {slow_html}
        <table style="width:100%;border-collapse:separate;border-spacing:4px 0;">
            <tr>
                {metric_cell("觀看次數", f"{views:,}", "#E1F5EE", hi_color="#0F6E56")}
                {SP}{metric_cell("觸及人數", f"{reach:,}")}
                {SP}{metric_cell("儲存", f"{saved:,}")}
                {SP}{metric_cell("分享", f"{shares:,}")}
            </tr>
        </table>
        <table style="width:100%;border-collapse:separate;border-spacing:4px 0;margin-top:6px;">
            <tr>
                {metric_cell("按讚", f"{likes:,}")}
                {SP}{metric_cell("留言", f"{comments:,}")}
                {SP}{metric_cell("總互動", f"{interact:,}")}
                {SP}{metric_cell("平均觀看", f"{avg_w} 秒")}
            </tr>
        </table>
        <p style="margin:10px 0 0;font-size:12px;"><a href="{link}" style="color:#0F6E56;">在 Instagram 查看 →</a></p>
    </div>"""


def yt_card(ep, is_shorts):
    if not ep:
        return """<div style="background:#f9f8f6;border-radius:10px;padding:16px;margin-bottom:16px;">
            <span style="background:#FFE8E8;color:#C00;font-size:11px;padding:2px 8px;border-radius:999px;">YouTube</span>
            <p style="color:#999;font-size:13px;margin:12px 0 0;">本月尚無資料</p></div>"""

    type_label = "YouTube Shorts 最新" if is_shorts else "YouTube 最新影片"
    title    = (ep.get("video_title") or "")[:60]
    views    = int(ep.get("views") or 0)
    likes    = int(ep.get("likes") or 0)
    comments = int(ep.get("comments") or 0)
    shares   = int(ep.get("shares") or 0)
    avg_dur  = int(float(ep.get("average_view_duration") or 0))
    avg_pct  = round(float(ep.get("average_view_percentage") or 0), 1)
    subs_g   = int(ep.get("subscribers_gained") or 0)
    subs_l   = int(ep.get("subscribers_lost") or 0)
    link     = ep.get("videourl") or "#"
    dt_str   = fmt_ts_tw(ep.get("published_at"), date_only=True)
    mmss     = f"{avg_dur // 60}:{avg_dur % 60:02d}"

    return f"""
    <div style="background:#f9f8f6;border-radius:10px;padding:16px;margin-bottom:16px;">
        <div style="margin-bottom:8px;">
            <span style="background:#FFE8E8;color:#C00;font-size:11px;padding:2px 8px;border-radius:999px;">▶ {type_label}</span>
            <span style="font-size:11px;color:#888;margin-left:8px;">{dt_str} 發布</span>
        </div>
        <p style="font-size:13px;font-weight:500;color:#333;margin:0 0 12px;">{title}</p>
        <table style="width:100%;border-collapse:separate;border-spacing:4px 0;">
            <tr>
                {metric_cell("觀看次數", f"{views:,}", "#FFE8E8", hi_color="#C00")}
                {SP}{metric_cell("按讚", f"{likes:,}")}
                {SP}{metric_cell("留言", f"{comments:,}")}
                {SP}{metric_cell("分享", f"{shares:,}")}
            </tr>
        </table>
        <table style="width:100%;border-collapse:separate;border-spacing:4px 0;margin-top:6px;">
            <tr>
                {metric_cell("平均觀看時長", mmss)}
                {SP}{metric_cell("平均觀看%", f"{avg_pct}%")}
                {SP}{metric_cell("新增訂閱", f"+{subs_g:,}")}
                {SP}{metric_cell("取消訂閱", f"-{subs_l:,}")}
            </tr>
        </table>
        <p style="margin:10px 0 0;font-size:12px;"><a href="{link}" style="color:#C00;">在 YouTube 查看 →</a></p>
    </div>"""


def build_email(card_xl, card_sy, card_yt):
    now_tw = datetime.now(TW).strftime("%Y/%m/%d %H:%M")
    return f"""<!DOCTYPE html>
<html lang="zh-TW"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#fff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<div style="max-width:600px;margin:0 auto;padding:24px 16px;">
  <div style="text-align:center;margin-bottom:20px;">
    <span style="background:#f0f0f0;color:#666;padding:4px 14px;border-radius:20px;font-size:12px;">@biglazyseals · 每日追蹤</span>
    <h1 style="font-size:22px;font-weight:700;color:#1a1a1a;margin:14px 0 4px;">Instagram & YouTube 數據報告</h1>
    <p style="font-size:13px;color:#999;margin:0;">{now_tw}（台灣時間）</p>
  </div>
  <hr style="border:none;border-top:1px solid #ebebeb;margin:20px 0;">
  {card_xl}
  {card_sy}
  <hr style="border:none;border-top:1px solid #ebebeb;margin:20px 0;">
  {card_yt}
  <hr style="border:none;border-top:1px solid #ebebeb;margin:20px 0;">
  <p style="font-size:11px;color:#bbb;text-align:center;margin:0;line-height:1.6;">
    資料來源：Windsor.ai &nbsp;·&nbsp; 每日台灣時間 21:00 自動執行
  </p>
</div>
</body></html>"""


def send_email(html):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 @biglazyseals 每日數據 {datetime.now(TW).strftime('%m/%d')}"
    msg["From"]    = GMAIL_USER
    msg["To"]      = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_string())
        print("Email sent successfully.")
    except Exception as e:
        print(f"Email send failed: {e}")
        sys.exit(1)


def main():
    print("Fetching Instagram data...")
    ig_data = fetch_ig_data()
    reels   = filter_reels(ig_data)
    print(f"  Got {len(reels)} reels")

    xl_ep = get_latest_ig_episode(reels, "心靈電影院")
    sy_ep = get_latest_ig_episode(reels, "深夜選片")

    print("Fetching YouTube data...")
    yt_data         = fetch_yt_data()
    yt_ep, is_short = get_latest_yt(yt_data)
    print(f"  Got {len(yt_data)} videos, is_shorts={is_short}")

    html = build_email(
        ig_card(xl_ep, "心靈電影院", "💘"),
        ig_card(sy_ep, "深夜選片指南", "🌙"),
        yt_card(yt_ep, is_short),
    )

    print("Sending email...")
    send_email(html)
    print("Done.")


if __name__ == "__main__":
    main()
