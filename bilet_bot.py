import time
import requests
import datetime
import os
from urllib.parse import quote_plus
from curl_cffi import requests as cf_requests

# ============================================================
#  🇹🇷 Türkiye - Romanya Maç Bileti Takip Botu
#  26 Mart 2026 | Beşiktaş Park
#  ☁️  Cloud Version (curl_cffi Only - No Browser Needed)
# ============================================================

# --- Telegram Bot Ayarları ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8608755861:AAFn25KiynNF7GRsnuczkD0TqHwhbg6XNg0")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "1723785769")

# --- Passo API Sorguları ---
PASSO_QUERIES = ["romanya", "türkiye", "milli takım"]

# --- Sadece Resmi Satış / Duyuru Kaynakları ---
OFFICIAL_SOURCES = [
    {"name": "TFF Bilet Duyuruları", "url": "https://www.tff.org/default.aspx?pageID=202"},
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


# ── PASSO API (DOĞRUDAN BİLET KONTROLÜ - curl_cffi) ──
def check_passo():
    """Passo API üzerinden anlık satışta olan etkinlikleri kontrol eder."""
    found_any = False
    print(f"[{now()}] 🎫 Passo API kontrol ediliyor...")
    session = cf_requests.Session(impersonate="chrome120")

    for query in PASSO_QUERIES:
        try:
            resp = session.post(
                "https://ticketingweb.passo.com.tr/api/passoweb/allevents",
                json={"query": query, "LanguageId": 118, "from": 0, "size": 50},
                headers={
                    "Content-Type": "application/json",
                    "Origin": "https://www.passo.com.tr",
                    "Referer": "https://www.passo.com.tr/",
                },
                timeout=15,
            )
            if resp.status_code != 200:
                print(f"[{now()}]   Passo API status: {resp.status_code}")
                continue

            data = resp.json()
            
            # API sonuçları "valueList" anahtarında geliyor
            events = data.get("valueList", [])
            # Eski format desteği (resultObject)
            if not events:
                events = data.get("resultObject", [])
                if isinstance(events, dict):
                    events = events.get("data", events.get("events", []))

            total = data.get("totalItemCount", 0)
            print(f"[{now()}]   Sorgu: '{query}' → {total} sonuç bulundu")
            
            for event in events:
                if not isinstance(event, dict):
                    continue
                    
                name = event.get("name", "").lower()
                seo_url = event.get("seoUrl", "")
                event_id_num = event.get("id", "")
                
                # Üretim kodu: Romanya, Türkiye veya Milli Takım içerenleri yakala
                is_match = ("romanya" in name or "romania" in name or "türkiye" in name or "milli" in name)
                
                if is_match and ("bilet" in name or "satın" in name or "incele" in name or "i̇ncele" in name or "yakında" in name):
                    event_name = event.get("name", "Bilinmeyen Etkinlik")
                    venue = event.get("venueName", "")
                    event_id = f"passo:{event_id_num}:{event_name}"
                    ticket_url = f"https://www.passo.com.tr/tr/etkinlik/{seo_url}/{event_id_num}"
                    
                    if event_id not in notified_items:
                        print(f"[{now()}] 🚨 PASSO'DA BİLET BULUNDU! 🚨")
                        notify(
                            "🚨 BİLET SATIŞINI BULDUM! 🚨",
                            f"Passo'da bilet satışa çıktı. Hemen aşağıdaki linkten alabilirsin:\n\n"
                            f"📌 {event_name}\n"
                            f"📍 {venue}\n"
                            f"🔗 {ticket_url}"
                        )
                        notified_items.add(event_id)
                        found_any = True
        except Exception as e:
            print(f"[{now()}] ❌ Passo API hatası: {e}")
            # Hata bildirimini Telegram'a da gönder
            if "passo_error" not in notified_items:
                notify("🛠 BOT HATA", f"Passo API'de hata: {str(e)[:300]}")
                notified_items.add("passo_error")

    if not found_any:
        print(f"[{now()}]   Passo'da eşleşen bilet bulunamadı.")
    return found_any


# ── RESMİ KAYNAKLAR (TFF DUYURULARI) ──
def check_official_sources():
    """Sadece resmi sitelerde kesin satış haberlerini arar."""
    found_any = False
    print(f"[{now()}] 📡 TFF Resmi sayfalar kontrol ediliyor...")

    for site in OFFICIAL_SOURCES:
        try:
            resp = requests.get(site["url"], headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue

            if hasattr(resp, "apparent_encoding") and resp.apparent_encoding:
                resp.encoding = resp.apparent_encoding

            page_text = resp.text.lower()

            has_match = ("romanya" in page_text) and ("bilet" in page_text) and (
                "satışa çıktı" in page_text or "genel satış" in page_text or "satışa sunuldu" in page_text
            )

            if has_match:
                site_id = f"official:{site['name']}"
                if site_id not in notified_items:
                    print(f"[{now()}] 🚨 RESMİ DUYURU BULDUM! → {site['name']}")
                    notify(
                        "🚨 BİLET SATIŞ DUYURUSU! 🚨",
                        f"{site['name']} üzerinde biletlerin satışa çıktığına dair resmi duyuru bulundu!\n\n"
                        f"Hemen kontrol et:\n"
                        f"🔗 {site['url']}"
                    )
                    notified_items.add(site_id)
                    found_any = True
        except Exception as e:
            print(f"[{now()}] ❌ Hata ({site['name']}): {e}")

    if not found_any:
        print(f"[{now()}]   Resmi duyuru sitelerinde bilet satışı yok.")
    return found_any


# ── ANA TARAMA ──
def run_scan():
    """Tek bir tarama döngüsü çalıştırır."""
    global last_check_time
    print(f"\n{'─' * 45}")
    print(f"[{now()}] ⏰ Tarama başlıyor...")
    print(f"{'─' * 45}")

    found_passo = check_passo()
    found_official = check_official_sources()

    last_check_time = datetime.datetime.now().strftime("%H:%M:%S")

    if found_passo or found_official:
        print(f"[{now()}] ✅ BİLET SATIŞI TESPİT EDİLDİ!")
    else:
        print(f"[{now()}] 😴 Bilet duyurusu bulunamadı, bekleniyor...")

    return found_passo or found_official


def bot_loop():
    """Sürekli çalışan bot döngüsü."""
    print("=" * 45)
    print("  🇹🇷 Bilet Botu Başlatıldı (Cloud)")
    print("=" * 45)

    notify("Bilet Botu Aktif ✅", "Bot bulutta çalışmaya başladı! 3 dk aralıkla Passo API'den doğrudan bilet satışı kontrol edilecek.")

    check_interval = 3 * 60

    while True:
        found = run_scan()
        if found:
            time.sleep(300)
        else:
            time.sleep(check_interval)
