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
    reels = [i for i in items if i.get("media_type") == "VIDEO"]

    results = []
    for reel in reels[:10]:
        mid = reel["id"]
        ins_url = f"https://graph.facebook.com/v25.0/{mid}/insights"
        ins_params = {
            "metric": "plays,reach,saved,shares,comments,likes,total_interactions,avg_watch_time",
            "access_token": META_ACCESS_TOKEN,
        }
        ins_r = requests.get(ins_url, params=ins_params, timeout=30)
        if ins_r.status_code != 200:
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
        views = int(ep.get("plays") or 0)
        if days_old >= SLOWDOWN_DAYS and views < SLOWDOWN_VIEWS:
            return True, f"貼文已 {days_old} 天，觀看停滯在 {views:,}"
    except Exception:
        pass
    return False, ""

def ig_card(ep, series_name, emoji):
    if not ep:
        return f"<p style='color:#888;font-size:13px;'>（{series_name}：本月尚無資料）</p>"

    caption  = (ep.get("caption") or "")[:80].replace("\n", " ")
    views    = int(ep.get("plays") or 0)
    reach    = int(ep.get("reach") or 0)
    likes    = int(ep.get("likes") or 0)
    comments = int(ep.get("comments") or 0)
    saved    = int(ep.get("saved") or 0)
    shares   = int(ep.get("shares") or 0)
    interact = int(ep.get("total_interactions") or 0)
    avg_w    = round((ep.get("avg_watch_time") or 0) / 1000, 1)
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
    return
