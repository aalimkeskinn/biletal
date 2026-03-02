import time
import requests
from bs4 import BeautifulSoup
import datetime
import os
from urllib.parse import quote_plus
from curl_cffi import requests as cf_requests

# ============================================================
#  🇹🇷 Türkiye - Romanya Maç Bileti Takip Botu
#  26 Mart 2026 | Beşiktaş Park
#  ☁️  Cloud Version (Strict Ticket Finder)
# ============================================================

# --- Telegram Bot Ayarları ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8608755861:AAFn25KiynNF7GRsnuczkD0TqHwhbg6XNg0")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "1723785769")

# --- Passo API Sorguları ---
PASSO_QUERIES = ["Romanya", "Turkiye Romanya", "Milli Takim"]

# --- Sadece Resmi Satış / Duyuru Kaynakları ---
OFFICIAL_SOURCES = [
    {"name": "TFF Bilet Duyuruları", "url": "https://www.tff.org/default.aspx?pageID=202"},
    {"name": "Passo Futbol Kategorisi", "url": "https://www.passo.com.tr/tr/kategori/futbol-mac-biletleri/4615"},
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


# ── PASSO API (DOĞRUDAN BİLET SATIŞ EKRANI) ──
def check_passo():
    """Passo ana sayfasını Playwright ile render edip anlık satışta olan etkinlikleri kontrol eder."""
    found_any = False
    print(f"[{now()}] 🎫 Passo UI (Direkt Satış) kontrol ediliyor...")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for query in PASSO_QUERIES:
            try:
                # Arama sayfasına git ve render olmasını bekle
                page.goto(f"https://www.passo.com.tr/tr/ara?searchQuery={quote_plus(query)}", timeout=45000)
                try:
                    # Passo'nun içindeki event kartları gelene kadar bekle (10 saniye max)
                    page.wait_for_load_state("networkidle", timeout=10000)
                except:
                    pass
                
                # Sayfadaki tüm yazıları çek
                text = page.inner_text("body").lower()
                
                # Sadece eğer aranılan kelime ("Romanya" vs) eşleşirse ve sayfada "detaylı i̇ncele" veya "satın al" varsa
                is_match = (
                    ("romanya" in text or "romania" in text or ("türkiye" in text and "milli" in text))
                )
                
                if is_match and ("bilet" in text or "satın al" in text or "incele" in text):
                    event_name = "Türkiye - Romanya Maçı (Passo Arama Sonucu)"
                    event_id = f"passo:{query}"
                    ticket_url = f"https://www.passo.com.tr/tr/ara?searchQuery={quote_plus(query)}"
                    
                    if event_id not in notified_items:
                        print(f"[{now()}] 🚨 PASSO'DA BİLET BULUNDU! 🚨")
                        notify(
                            "🚨 BİLET SATIŞINI BULDUM! 🚨", 
                            f"Passo'da bilet satışa çıktı. Hemen aşağıdaki linkten alabilirsin:\n\n"
                            f"📌 {event_name}\n"
                            f"🔗 {ticket_url}"
                        )
                        notified_items.add(event_id)
                        found_any = True
            except Exception as e:
                print(f"[{now()}] ❌ Passo UI hatası: {e}")

        browser.close()

    if not found_any:
        print(f"[{now()}]   Passo'da henüz bilet satışı yok.")
    return found_any


# ── RESMİ KAYNAKLAR (TFF DUYURULARI) ──
def check_official_sources():
    """Sadece resmi sitelerde (örneğin TFF) kesin satış haberlerini arar."""
    found_any = False
    print(f"[{now()}] 📡 TFF ve Passo Resmi sayfalar kontrol ediliyor...")
    
    # Sadece kesin haberler için zorunlu kelimeler
    REQUIRED_KEYWORDS = ["romanya", "bilet", "satışa çıktı", "satışta"]

    for site in OFFICIAL_SOURCES:
        try:
            # Passo'nun Cloudflare engelini aşması için cf_requests kullanıyoruz
            if "passo.com" in site["url"]:
                resp = cf_requests.get(site["url"], impersonate="chrome120", timeout=15)
            else:
                resp = requests.get(site["url"], headers=HEADERS, timeout=15)
                
            if resp.status_code != 200:
                continue
                
            if hasattr(resp, "apparent_encoding") and resp.apparent_encoding:
                resp.encoding = resp.apparent_encoding
                
            page_text = resp.text.lower()
            
            # Tüm kelimeler aynı sayfada/haberde var mı?
            # Passo arama sayfasında sadece "romanya" geçmesi yeterli (çünkü direkt bilet sayfası)
            if "passo.com" in site["url"]:
                has_match = ("romanya" in page_text) and ("cloudflare" not in page_text)
            else:
                has_match = ("romanya" in page_text) and ("bilet" in page_text) and (
                    "satışa çıktı" in page_text or "genel satış" in page_text or "satışa sunuldu" in page_text
                )

            if has_match:
                site_id = f"official:{site['name']}"
                if site_id not in notified_items:
                    print(f"[{now()}] 🚨 RESMİ DUYURU BULDUM! → {site['name']}")
                    notify(
                        "🚨 BİLET SATIŞ DUYURUSU! 🚨", 
                        f"{site['name']} üzerinde biletlerin satışa çıktığına dair resmi duyuru/link bulundu!\n\n"
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
    print(f"[{now()}] ⏰ Tarama başlıyor (Sadece Kesin Biletler)...")
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
    print("  🇹🇷 Katı Bilet Botu Başlatıldı (Cloud)")
    print("=" * 45)

    notify("Bilet Botu Güncellendi ✅", "Haber siteleri (Google/Bing) KALDIRILDI. Artık SADECE Passo'da bilet satışa çıktığında veya TFF remsi duyuru yaptığında direkt bilet linkini alacaksınız.")

    check_interval = 3 * 60

    while True:
        found = run_scan()
        if found:
            # Bulursa sürekli mesaj atmasın diye 5 dakika bekle
            time.sleep(300)
        else:
            time.sleep(check_interval)
