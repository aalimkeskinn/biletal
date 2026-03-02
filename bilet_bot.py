import time
import requests
from bs4 import BeautifulSoup
import datetime
import json
import os
from urllib.parse import urlparse, quote_plus
from curl_cffi import requests as cf_requests

# ============================================================
#  🇹🇷 Türkiye - Romanya Maç Bileti Takip Botu
#  26 Mart 2026 | Beşiktaş Park
#  ☁️  Cloud Version (Telegram Only)
# ============================================================

# --- Telegram Bot Ayarları ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8608755861:AAFn25KiynNF7GRsnuczkD0TqHwhbg6XNg0")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "1723785769")

# --- Passo API Sorguları ---
PASSO_QUERIES = ["Romanya", "Turkiye Romanya", "Milli Takim"]

# --- Google News RSS Sorguları ---
GOOGLE_NEWS_QUERIES = [
    "türkiye romanya bilet",
    "türkiye romanya maç bilet satış",
    "milli maç bilet passo",
]

# --- Bing'de Aranacak Sorgular ---
BING_QUERIES = [
    "türkiye romanya milli maç bilet satış 2026",
    "türkiye romanya bilet al passo",
    "turkey romania ticket sale beşiktaş park",
]

# --- Doğrudan Kontrol Edilecek Sabit Siteler ---
STATIC_SITES = [
    {"name": "TFF Milli Takımlar", "url": "https://www.tff.org/default.aspx?pageID=202"},
    {"name": "TFF Ana Sayfa", "url": "https://www.tff.org/default.aspx?pageID=285"},
    {"name": "NTV Spor Futbol", "url": "https://www.ntvspor.net/futbol"},
    {"name": "Fanatik Milli Takım", "url": "https://www.fanatik.com.tr/milli-takim"},
    {"name": "Sabah Spor", "url": "https://www.sabah.com.tr/spor/futbol"},
    {"name": "Hürriyet Spor", "url": "https://www.hurriyet.com.tr/sporarena/"},
]

TICKET_KEYWORDS = [
    "bilet", "satış", "satışa", "passo", "ticket",
    "biletleri", "biletler", "satın al",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}

notified_items = set()
last_check_time = None


def now():
    return datetime.datetime.now().strftime("%H:%M:%S")


def send_telegram(text):
    """Telegram üzerinden bildirim gönderir."""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
        }, timeout=10)
    except Exception as e:
        print(f"[{now()}] ⚠️ Telegram hatası: {e}")


def notify(title, text):
    """Telegram'a bildirim gönderir."""
    send_telegram(f"<b>{title}</b>\n{text}")
    print(f"[{now()}] 📩 Bildirim: {title} - {text[:60]}")


# ── PASSO ──
def check_passo():
    found_any = False
    print(f"[{now()}] 🎫 Passo kontrol ediliyor...")
    session = cf_requests.Session(impersonate="chrome120")

    for query in PASSO_QUERIES:
        try:
            resp = session.post(
                "https://ticketingweb.passo.com.tr/api/passoweb/allevents",
                json={"query": query, "etkinlikdetay": "true", "LanguageId": 118, "from": 0, "size": 50},
                headers={"Content-Type": "application/json", "Origin": "https://www.passo.com.tr", "Referer": "https://www.passo.com.tr/"},
                timeout=15,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            events = []
            if isinstance(data, dict):
                result = data.get("resultObject", data)
                if isinstance(result, list):
                    events = result
                elif isinstance(result, dict):
                    events = result.get("data", result.get("events", []))

            for event in events:
                name = event.get("name", "").lower()
                seo_url = event.get("seoUrl", "")
                is_match = "romanya" in name or "romania" in name
                if is_match:
                    event_name = event.get("name", "?")
                    event_id = f"passo:{event_name}"
                    ticket_url = f"https://www.passo.com.tr/tr/etkinlik/{seo_url}"
                    if event_id not in notified_items:
                        print(f"[{now()}] 🚨🚨🚨 PASSO'DA BİLET BULUNDU! 🚨🚨🚨")
                        notify("🎫 PASSO BİLET BULUNDU!", f"{event_name}\n🔗 {ticket_url}")
                        notified_items.add(event_id)
                        found_any = True
        except Exception as e:
            print(f"[{now()}] ❌ Passo hatası: {e}")

    if not found_any:
        print(f"[{now()}]   Passo'da henüz bilet yok.")
    return found_any


# ── GOOGLE NEWS ──
def check_google_news():
    found_any = False
    print(f"[{now()}] 📰 Google News RSS taranıyor...")
    for query in GOOGLE_NEWS_QUERIES:
        try:
            encoded = quote_plus(query)
            rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=tr&gl=TR&ceid=TR:tr"
            resp = requests.get(rss_url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "xml")
            for item in soup.find_all("item"):
                title = (item.find("title").text if item.find("title") else "").lower()
                has_romania = "romanya" in title or "romania" in title
                has_ticket = any(kw in title for kw in TICKET_KEYWORDS)
                if has_romania and has_ticket:
                    original_title = item.find("title").text
                    if original_title not in notified_items:
                        notify("🎫 Bilet Haberi!", original_title[:150])
                        notified_items.add(original_title)
                        found_any = True
        except Exception as e:
            print(f"[{now()}] ❌ Google News hatası: {e}")
        time.sleep(0.5)
    if not found_any:
        print(f"[{now()}]   Google News'te yeni bilet duyurusu yok.")
    return found_any


# ── BING ──
def check_bing():
    found_any = False
    all_urls = set()
    print(f"[{now()}] 🔍 Bing aramaları yapılıyor...")
    for query in BING_QUERIES:
        try:
            resp = requests.get("https://www.bing.com/search", params={"q": query}, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            for r in soup.find_all("li", class_="b_algo"):
                cite = r.find("cite")
                if cite:
                    raw = cite.get_text().strip()
                    if raw.startswith("http"):
                        all_urls.add(raw.split(" ")[0])
        except Exception:
            pass
        time.sleep(1)

    for url in all_urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
            if resp.status_code != 200:
                continue
            resp.encoding = resp.apparent_encoding
            page_text = resp.text.lower()
            has_romania = "romanya" in page_text or "romania" in page_text
            has_ticket = any(kw in page_text for kw in TICKET_KEYWORDS)
            if has_romania and has_ticket:
                domain = urlparse(url).netloc
                page_id = f"bing:{domain}"
                if page_id not in notified_items:
                    notify("🎫 Bilet Haberi!", f"Kaynak: {domain}")
                    notified_items.add(page_id)
                    found_any = True
        except Exception:
            pass
    if not found_any:
        print(f"[{now()}]   Bing'de bilet duyurusu yok.")
    return found_any


# ── SABİT SİTELER ──
def check_static_sites():
    found_any = False
    print(f"[{now()}] 📡 Sabit siteler kontrol ediliyor...")
    for site in STATIC_SITES:
        try:
            resp = requests.get(site["url"], headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue
            resp.encoding = resp.apparent_encoding
            page_text = resp.text.lower()
            has_romania = "romanya" in page_text or "romania" in page_text
            has_ticket = any(kw in page_text for kw in TICKET_KEYWORDS)
            if has_romania and has_ticket:
                site_id = f"static:{site['name']}"
                if site_id not in notified_items:
                    notify("🎫 Bilet Haberi!", f"{site['name']} - bilet haberi!")
                    notified_items.add(site_id)
                    found_any = True
        except Exception:
            pass
    if not found_any:
        print(f"[{now()}]   Sabit sitelerde bilet duyurusu yok.")
    return found_any


# ── ANA TARAMA ──
def run_scan():
    """Tek bir tarama döngüsü çalıştırır."""
    global last_check_time
    print(f"\n{'─' * 45}")
    print(f"[{now()}] ⏰ Tarama başlıyor...")
    print(f"{'─' * 45}")

    found_passo = check_passo()
    found_news = check_google_news()
    found_bing = check_bing()
    found_static = check_static_sites()

    last_check_time = datetime.datetime.now().strftime("%H:%M:%S")

    if found_passo or found_news or found_bing or found_static:
        print(f"[{now()}] ✅ Bilet haberi tespit edildi!")
    else:
        print(f"[{now()}] 😴 Bilet duyurusu bulunamadı.")

    return found_passo or found_news or found_bing or found_static


def bot_loop():
    """Sürekli çalışan bot döngüsü."""
    print("=" * 45)
    print("  🇹🇷 Bilet Botu Başlatıldı (Cloud)")
    print("=" * 45)

    notify("Bilet Botu Aktif ✅", "Bot bulutta çalışmaya başladı! 3 dk aralıkla tarama yapılacak.")

    check_interval = 3 * 60

    while True:
        found = run_scan()
        if found:
            time.sleep(60)
        else:
            time.sleep(check_interval)
