import os
import json
import asyncio
import aiohttp
import instaloader
from bs4 import BeautifulSoup
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
import time
import sys

# =============================================================================
# --- AYARLAR ---
# =============================================================================
HTML_DOSYASI = "followers_1.html"
CIKTI_KLASORU = "racers"
REACT_JSON = "racer_data.json"

# Performans ayarları
MAX_CONCURRENT = 80          # Aynı anda kaç istek atılsın
BATCH_SIZE = 500             # Kaçarlı gruplarla işlensin
BATCH_DELAY = 1.0            # Gruplar arası bekleme (saniye)
TIMEOUT = 10                 # Tek istek timeout (saniye)
RETRY_COUNT = 2              # Başarısızsa kaç kere denesin
# =============================================================================


def get_users_from_html(filepath: str) -> list[str]:
    """HTML dosyasından kullanıcı adlarını ayıklar."""
    if not os.path.exists(filepath):
        print(f"HATA: {filepath} bulunamadı!")
        return []

    print(f"📂 {filepath} okunuyor...")
    with open(filepath, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
        links = soup.find_all("a")

    user_set = set()
    for link in links:
        username = link.text.strip()
        if username and "instagram.com" in link.get("href", ""):
            user_set.add(username)

    users = sorted(user_set)
    print(f"✅ Toplam {len(users)} kullanıcı bulundu.")
    return users


def create_dummy_image(path: str):
    """200x200 beyaz placeholder resim."""
    img = Image.new("RGB", (200, 200), color="white")
    img.save(path, quality=85)


# ─────────────────────────────────────────────────────────────
#  YÖNTEM 1: Instaloader ile profil URL'lerini toplu çek
#  (API rate limit'e daha az takılır çünkü sadece URL alıyoruz,
#   indirmeyi ayrı yapıyoruz)
# ─────────────────────────────────────────────────────────────

def fetch_profile_urls_instaloader(usernames: list[str], login: bool = False) -> dict[str, str]:
    """
    Instaloader ile profil fotoğrafı URL'lerini topla.
    Thread pool ile paralel çalıştırıyoruz.
    """
    L = instaloader.Instaloader()

    if login:
        my_user = input("Kullanıcı Adınız: ")
        try:
            L.interactive_login(my_user)
            print("✅ Giriş başarılı!")
        except Exception as e:
            print(f"❌ Giriş hatası: {e} — Anonim devam ediliyor...")

    url_map: dict[str, str] = {}
    lock = asyncio.Lock() if False else None  # placeholder
    total = len(usernames)

    def _fetch_one(idx_user):
        idx, username = idx_user
        try:
            profile = instaloader.Profile.from_username(L.context, username)
            url = profile.profile_pic_url
            if url:
                return (username, url)
        except Exception:
            pass
        return (username, None)

    print(f"\n🔗 {total} kullanıcının profil URL'leri toplanıyor (paralel)...")

    # Instaloader thread-safe değil tam olarak, ama context paylaşımı
    # çoğu durumda çalışıyor. Sorun olursa birden fazla context açarız.
    # Burada 5 thread kullanıyoruz — Instagram rate limit'e takılmamak için.
    completed = 0
    failed = 0

    # Instaloader için çok fazla paralel yapamayız (rate limit),
    # ama 5-10 thread bile büyük fark yaratır.
    NUM_IL_THREADS = 8

    with ThreadPoolExecutor(max_workers=NUM_IL_THREADS) as pool:
        futures = list(pool.map(_fetch_one, enumerate(usernames)))

    for username, url in futures:
        if url:
            url_map[username] = url
            completed += 1
        else:
            failed += 1

    print(f"✅ URL toplama bitti: {completed} başarılı, {failed} başarısız")
    return url_map


# ─────────────────────────────────────────────────────────────
#  YÖNTEM 2: Asenkron paralel indirme (çok hızlı)
# ─────────────────────────────────────────────────────────────

async def download_image(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    username: str,
    url: str,
    output_path: str,
    retry: int = RETRY_COUNT,
) -> bool:
    """Tek bir resmi asenkron indir."""
    async with semaphore:
        for attempt in range(retry + 1):
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        # Dosyaya yaz (I/O blocking ama küçük dosya, sorun değil)
                        with open(output_path, "wb") as f:
                            f.write(data)
                        return True
            except Exception:
                if attempt < retry:
                    await asyncio.sleep(0.5)
        return False


async def download_all(url_map: dict[str, str], output_dir: str) -> tuple[int, int]:
    """Tüm resimleri paralel indir."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT, limit_per_host=MAX_CONCURRENT)

    downloaded = 0
    failed_users = []

    async with aiohttp.ClientSession(connector=connector) as session:
        items = list(url_map.items())
        total = len(items)

        # Batch'ler halinde işle — bellek ve rate limit kontrolü
        for batch_start in range(0, total, BATCH_SIZE):
            batch = items[batch_start : batch_start + BATCH_SIZE]
            batch_num = batch_start // BATCH_SIZE + 1
            total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

            tasks = []
            for username, url in batch:
                path = os.path.join(output_dir, f"{username}.jpg")
                tasks.append(download_image(session, semaphore, username, url, path))

            results = await asyncio.gather(*tasks)

            batch_ok = sum(1 for r in results if r)
            batch_fail = sum(1 for r in results if not r)
            downloaded += batch_ok

            # Başarısız olanları kaydet
            for (username, _), success in zip(batch, results):
                if not success:
                    failed_users.append(username)

            print(
                f"  📦 Batch {batch_num}/{total_batches}: "
                f"{batch_ok} indirildi, {batch_fail} başarısız"
            )

            if batch_start + BATCH_SIZE < total:
                await asyncio.sleep(BATCH_DELAY)

    return downloaded, failed_users


def generate_json(output_dir: str, json_path: str):
    """React için JSON oluştur."""
    final_data = []
    if os.path.exists(output_dir):
        dosyalar = sorted(f for f in os.listdir(output_dir) if f.endswith(".jpg"))
        for i, dosya in enumerate(dosyalar, 1):
            final_data.append({
                "id": i,
                "name": dosya.replace(".jpg", ""),
                "image": f"/racers/{dosya}",
            })

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)

    return len(final_data)


# ─────────────────────────────────────────────────────────────
#  ANA FONKSİYON
# ─────────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("  ⚡ HIZLI Instagram Profil Fotoğrafı Toplayıcı ⚡")
    print("  (Paralel mod — 10.000 kişi ~5-10 dakika)")
    print("=" * 60)

    # 1) Kullanıcıları HTML'den çek
    kullanicilar = get_users_from_html(HTML_DOSYASI)
    if not kullanicilar:
        print("❌ Kullanıcı bulunamadı.")
        return

    os.makedirs(CIKTI_KLASORU, exist_ok=True)

    # Zaten indirilmiş olanları atla (resume desteği)
    mevcut = set()
    if os.path.exists(CIKTI_KLASORU):
        mevcut = {f.replace(".jpg", "") for f in os.listdir(CIKTI_KLASORU) if f.endswith(".jpg")}

    eksik = [u for u in kullanicilar if u not in mevcut]
    print(f"⏩ {len(mevcut)} zaten indirilmiş, {len(eksik)} kaldı.")

    if not eksik:
        print("✅ Tüm fotoğraflar zaten mevcut!")
    else:
        # 2) Giriş tercihi
        print("\n⚠️  Giriş yapmak daha fazla profil fotoğrafı çekmenizi sağlar.")
        giris = input("Giriş yapmak ister misiniz? (e/h): ").strip().lower()
        login = giris == "e"

        start = time.time()

        # 3) Instaloader ile URL'leri topla (paralel thread)
        url_map = fetch_profile_urls_instaloader(eksik, login=login)

        url_time = time.time() - start
        print(f"⏱️  URL toplama süresi: {url_time:.1f}s")

        # 4) Asenkron paralel indirme
        print(f"\n📥 {len(url_map)} resim paralel indiriliyor (max {MAX_CONCURRENT} eşzamanlı)...")
        download_start = time.time()

        downloaded, failed_users = await download_all(url_map, CIKTI_KLASORU)

        dl_time = time.time() - download_start
        print(f"⏱️  İndirme süresi: {dl_time:.1f}s")

        # 5) Başarısız olanlar + URL'si hiç bulunamayanlar → beyaz resim
        no_url_users = [u for u in eksik if u not in url_map]
        all_failed = set(failed_users) | set(no_url_users)

        if all_failed:
            print(f"\n⚪ {len(all_failed)} kullanıcı için beyaz resim oluşturuluyor...")
            for username in all_failed:
                path = os.path.join(CIKTI_KLASORU, f"{username}.jpg")
                if not os.path.exists(path):
                    create_dummy_image(path)

        total_time = time.time() - start
        print(f"\n⏱️  TOPLAM SÜRE: {total_time:.1f}s ({total_time/60:.1f} dakika)")

    # 6) JSON oluştur
    count = generate_json(CIKTI_KLASORU, REACT_JSON)
    print(f"\n🎉 TAMAMLANDI! {count} yarışmacı {REACT_JSON} dosyasına yazıldı.")


if __name__ == "__main__":
    asyncio.run(main())