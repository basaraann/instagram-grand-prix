import os
import json
import time
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# =============================================================================
# --- AYARLAR ---
# =============================================================================
HTML_DOSYASI = "followers_1.html"  # Instagram'dan indirdiğin dosya
CIKTI_KLASORU = "racers"           # Resimlerin ineceği klasör
REACT_JSON = "racer_data.json"     # React'ın kullanacağı dosya
# =============================================================================

def get_users_from_html(filepath):
    """HTML dosyasından kullanıcı adlarını ayıklar."""
    if not os.path.exists(filepath):
        print(f"HATA: {filepath} bulunamadı!")
        return []

    print(f"📂 {filepath} okunuyor...")
    user_list = []
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
            # Instagram HTML çıktısında kullanıcı adları genelde <a> etiketindedir
            links = soup.find_all("a")
            
            for link in links:
                username = link.text.strip()
                # Basit doğrulama: Boş değilse ve link Instagram'a gidiyorsa
                if username and "instagram.com" in link.get('href', ''):
                    user_list.append(username)
                elif username and len(username.split()) == 1: # Alternatif kontrol
                    user_list.append(username)
                    
        # Tekrarlananları temizle
        user_list = list(set(user_list))
        print(f"✅ Toplam {len(user_list)} kullanıcı bulundu.")
        return user_list
        
    except Exception as e:
        print(f"HTML okuma hatası: {e}")
        return []

def main():
    print("=== Instagram Final Proje Scraper ===")

    # 1. KULLANICILARI BELİRLE
    kullanicilar = get_users_from_html(HTML_DOSYASI)
    
    if not kullanicilar:
        print("❌ Listelenecek kullanıcı yok. Çıkış yapılıyor.")
        print("İPUCU: Instagram Ayarlar > Bilgilerini İndir > HTML seçeneği ile verini al.")
        return

    if not os.path.exists(CIKTI_KLASORU):
        os.makedirs(CIKTI_KLASORU)

    # 2. TARAYICIYI AÇ
    print("\n🚀 Chrome başlatılıyor...")
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-notifications")
    # options.add_argument("--headless") # Kafasız mod (arka planda çalışma) için açabilirsin
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        # 3. GİRİŞ İŞLEMİ (MANUEL)
        # Profil resimlerini tam boy görmek için giriş yapmak şarttır.
        driver.get("https://www.instagram.com/")
        print("\n" + "="*60)
        print("⚠️  GİRİŞ YAPMA EKRANI BEKLENİYOR...")
        print("⚠️  Açılan Chrome penceresinden hesabına giriş yap.")
        print("⚠️  Giriş yaptıktan ve ana sayfayı gördükten sonra buraya gelip ENTER'a bas.")
        print("="*60 + "\n")
        input("Giriş yaptıysan ENTER'a bas ve arkanı yaslan... ")

        print("📸 Fotoğraflar toplanıyor...")

        for index, username in enumerate(kullanicilar):
            resim_yolu = os.path.join(CIKTI_KLASORU, f"{username}.jpg")

            # Zaten indirdiysek pas geç (Resume özelliği)
            if os.path.exists(resim_yolu):
                print(f"⏩ [{index+1}/{len(kullanicilar)}] {username} zaten var.")
                continue

            print(f"🔍 [{index+1}/{len(kullanicilar)}] {username} taranıyor...", end="")

            try:
                # Kullanıcı profiline git
                driver.get(f"https://www.instagram.com/{username}/")

                # Profil resmini Meta Tag'den çek (En garantisi)
                # <meta property="og:image" content="...">
                img_url = None
                try:
                    meta = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, '//meta[@property="og:image"]'))
                    )
                    img_url = meta.get_attribute("content")
                except:
                    # Meta yoksa Twitter kartına bak
                    try:
                        meta = driver.find_element(By.XPATH, '//meta[@property="twitter:image"]')
                        img_url = meta.get_attribute("content")
                    except:
                        img_url = None

                # Resmi İndir
                if img_url:
                    response = requests.get(img_url)
                    if response.status_code == 200:
                        with open(resim_yolu, "wb") as f:
                            f.write(response.content)
                        print(" İNDİRİLDİ ✅")
                    else:
                        print(" URL HATASI ❌")
                else:
                    # Varsayılan/Boş resim olabilir veya hesap gizlidir meta tag vermiyordur
                    print(" RESİM BULUNAMADI ❌")

                # Instagram'ın bizi engellememesi için insani bekleme süresi
                time.sleep(1.5)

            except Exception as e:
                print(f" HATA: {e}")

    except Exception as e:
        print(f"Genel Driver Hatası: {e}")
    
    finally:
        driver.quit()

    # 4. REACT İÇİN JSON OLUŞTUR
    print("\n📊 Veri tabanı (JSON) güncelleniyor...")
    final_data = []
    id_counter = 1
    
    if os.path.exists(CIKTI_KLASORU):
        dosyalar = sorted([f for f in os.listdir(CIKTI_KLASORU) if f.endswith(".jpg")])
        for dosya in dosyalar:
            final_data.append({
                "id": id_counter,
                "name": dosya.replace(".jpg", ""),
                "image": f"/{CIKTI_KLASORU}/{dosya}" # React public klasör yolu
            })
            id_counter += 1

    with open(REACT_JSON, "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)

    print(f"🎉 İŞLEM TAMAMLANDI! {len(final_data)} yarışmacı eklendi.")

if __name__ == "__main__":
    main()