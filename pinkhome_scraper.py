from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
import pandas as pd
import time
import json
import re
import logging
from urllib.parse import urljoin
import urllib3

# SSL uyarılarını kapat
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Logging ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PinkHomeSeleniumScraper:
    def __init__(self, headless=True, wait_time=10):
        self.base_url = "https://www.pinkhometr.com.tr"
        self.wait_time = wait_time
        self.products = []
        self.driver = None
        self.setup_driver(headless)
        
    def setup_driver(self, headless=True):
        """Chrome WebDriver'ı ayarla"""
        try:
            chrome_options = Options()
            
            if headless:
                chrome_options.add_argument("--headless")
            
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--ignore-certificate-errors")
            chrome_options.add_argument("--ignore-ssl-errors")
            chrome_options.add_argument("--ignore-certificate-errors-spki-list")
            chrome_options.add_argument("--ignore-ssl-errors-types")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-images")  # Hızlandırmak için resimleri yükleme
            
            # User agent
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, self.wait_time)
            
            logger.info("Chrome WebDriver başarıyla başlatıldı")
            
        except Exception as e:
            logger.error(f"WebDriver başlatılamadı: {e}")
            logger.info("ChromeDriver'ın yüklü olduğundan emin olun: https://chromedriver.chromium.org/")
            raise
    
    def close_driver(self):
        """WebDriver'ı kapat"""
        if self.driver:
            self.driver.quit()
            logger.info("WebDriver kapatıldı")
    
    def scroll_page(self):
        """Sayfayı aşağı kaydır (lazy loading için)"""
        logger.info("Sayfa kaydırılıyor (lazy loading için)...")
        
        # Sayfayı yavaşça aşağı kaydır
        total_height = self.driver.execute_script("return document.body.scrollHeight")
        current_height = 0
        scroll_step = 500
        
        while current_height < total_height:
            current_height += scroll_step
            self.driver.execute_script(f"window.scrollTo(0, {current_height});")
            time.sleep(0.5)
            
            # Sayfanın boyutu değiştiyse (yeni içerik yüklendiyse) güncelle
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height > total_height:
                total_height = new_height
        
        # En üste geri dön
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)
        
    def get_page_source(self, url):
        """Sayfa kaynağını JavaScript ile birlikte al"""
        try:
            logger.info(f"Sayfa yükleniyor: {url}")
            self.driver.get(url)
            
            # Sayfanın yüklenmesini bekle
            time.sleep(3)
            
            # Sayfayı kaydır (lazy loading varsa)
            self.scroll_page()
            
            # Son bir bekleme
            time.sleep(2)
            
            return self.driver.page_source
            
        except Exception as e:
            logger.error(f"Sayfa yüklenirken hata: {url} - {e}")
            return None
    
    def extract_product_links_from_page(self, page_url):
        """Tek sayfa dari ürün linklerini çeker"""
        page_source = self.get_page_source(page_url)
        if not page_source:
            return []
            
        soup = BeautifulSoup(page_source, 'html.parser')
        product_links = []
        
        # Debug: Sayfa başlığını göster
        title = soup.find('title')
        logger.info(f"📄 Sayfa: {page_url} - Başlık: {title.get_text() if title else 'Bulunamadı'}")
        
        # Sayfadaki tüm linkleri listele
        all_links = soup.select('a[href]')
        logger.info(f"Sayfada toplam {len(all_links)} link bulundu")
        
        if len(all_links) == 0:
            logger.warning("Hiç link bulunamadı! Sayfa tam yüklenmemiş olabilir.")
            return []
        
        # Farklı ürün link pattern'ları dene
        link_patterns = [
            r'/urun/',
            r'/product/', 
            r'-p-\d+',
            r'/item/',
            r'/detay/',
            r'/detail/',
        ]
        
        for link in all_links:
            href = link.get('href', '')
            if href and href != '#' and 'javascript:' not in href:
                # Relative URL'leri absolute yap
                full_url = urljoin(self.base_url, href)
                
                # URL'de ürün pattern'ı var mı kontrol et
                is_product = any(re.search(pattern, full_url, re.IGNORECASE) for pattern in link_patterns)
                
                if is_product and full_url not in product_links:
                    product_links.append(full_url)
        
        logger.info(f"Bu sayfada {len(product_links)} ürün linki bulundu")
        return product_links
    
    def extract_product_links(self, base_category_url):
        """Tüm sayfalardan ürün linklerini çeker"""
        all_product_links = []
        page_number = 1
        max_pages = 50  # Güvenlik için maksimum sayfa sınırı
        
        logger.info("📚 Tüm sayfalar taranıyor...")
        
        while page_number <= max_pages:
            # Sayfa URL'sini oluştur
            if page_number == 1:
                page_url = base_category_url  # İlk sayfa için ?tp= yok
            else:
                page_url = f"{base_category_url}?tp={page_number}"
            
            logger.info(f"📄 Sayfa {page_number} taranıyor: {page_url}")
            
            # Bu sayfadaki ürünleri çek
            page_product_links = self.extract_product_links_from_page(page_url)
            
            # Eğer bu sayfada ürün yoksa, sonraki sayfalarda da olmayabilir
            if not page_product_links:
                logger.info(f"Sayfa {page_number}'da ürün bulunamadı.")
                
                # İlk sayfada ürün bulunamadıysa sorun var
                if page_number == 1:
                    logger.warning("❌ İlk sayfada bile ürün bulunamadı! CSS selector'ları kontrol edilmeli.")
                    break
                
                # Diğer sayfalarda ürün yoksa, sayfalama bitmiş olabilir
                # 2 boş sayfa üst üste gelirse dur
                if page_number > 1:
                    logger.info("Sayfalama tamamlandı (boş sayfa).")
                    break
            else:
                # Bu sayfadaki ürünleri genel listeye ekle
                all_product_links.extend(page_product_links)
                
                # İlk 3 ürün linkini göster
                logger.info(f"  İlk 3 ürün:")
                for i, link in enumerate(page_product_links[:3], 1):
                    logger.info(f"    {i}. {link}")
                
                if len(page_product_links) > 3:
                    logger.info(f"    ... ve {len(page_product_links) - 3} ürün daha")
            
            page_number += 1
            
            # Sayfalar arası kısa bekleme
            time.sleep(1)
        
        # Duplicate linkleri kaldır
        unique_links = list(set(all_product_links))
        logger.info(f"🎯 Toplam {len(all_product_links)} link bulundu, {len(unique_links)} benzersiz ürün")
        
        return unique_links
    
    def extract_product_details(self, product_url):
        """Tek ürün sayfasından sadece istenen detayları çeker"""
        page_source = self.get_page_source(product_url)
        if not page_source:
            return None
            
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Debug: İlk ürün için HTML yapısını incele
        if len(self.products) == 0:  # Sadece ilk ürün için
            logger.info("🔍 DEBUG: İlk ürün sayfasının HTML yapısı inceleniyor...")
            
            # H1 elementlerini bul
            h1_elements = soup.find_all('h1')
            logger.info(f"H1 elementleri bulundu: {len(h1_elements)}")
            for i, h1 in enumerate(h1_elements):
                logger.info(f"  H1-{i+1}: {h1.get_text().strip()[:100]}")
            
            # .product-detail class'ını bul
            detail_elements = soup.select('.product-detail')
            logger.info(f".product-detail elementleri: {len(detail_elements)}")
            for i, detail in enumerate(detail_elements):
                logger.info(f"  Detail-{i+1}: {detail.get_text().strip()[:100]}...")
            
            # .product-price-old class'ını bul
            old_price_elements = soup.select('.product-price-old')
            logger.info(f".product-price-old elementleri: {len(old_price_elements)}")
            for i, price in enumerate(old_price_elements):
                logger.info(f"  OldPrice-{i+1}: {price.get_text().strip()}")
            
            # Eğer bulamazsa, tüm class'ları listele
            if not detail_elements and not old_price_elements:
                logger.info("❌ Hedef class'lar bulunamadı! Sayfadaki tüm class'ları listeliyorum...")
                all_elements_with_class = soup.find_all(attrs={"class": True})[:20]  # İlk 20'si
                for elem in all_elements_with_class:
                    classes = ' '.join(elem.get('class', []))
                    text = elem.get_text().strip()[:50]
                    logger.info(f"  Class: '{classes}' - Text: '{text}'")
        
        # Sadece istenen 3 bilgiyi çek
        product_data = {
            'url': product_url,
            'urun_adi': self.extract_h1(soup),
            'aciklama': self.extract_product_detail(soup),
            'eski_fiyat': self.extract_old_price(soup)
        }
        
        return product_data
    
    def extract_h1(self, soup):
        """H1 etiketinden ürün adını çıkarır"""
        try:
            h1_element = soup.select_one('h1')
            if h1_element:
                return h1_element.get_text().strip()
        except:
            pass
        return None
    
    def extract_product_detail(self, soup):
        """'.product-detail' class'ından açıklamayı çıkarır"""
        try:
            detail_element = soup.select_one('.product-detail')
            if detail_element:
                text = detail_element.get_text().strip()
                # HTML etiketlerini temizle
                text = re.sub(r'<[^>]+>', '', text)
                text = re.sub(r'\s+', ' ', text)
                return text
        except:
            pass
        return None
    
    def extract_old_price(self, soup):
        """'.product-price-old' class'ından eski fiyatı çıkarır"""
        try:
            old_price_element = soup.select_one('.product-price-old')
            if old_price_element:
                price_text = old_price_element.get_text().strip()
                # Sayısal değeri çıkar
                price_match = re.search(r'[\d.,]+', price_text.replace('₺', '').replace('TL', '').replace(',', '.'))
                if price_match:
                    try:
                        return float(price_match.group())
                    except ValueError:
                        return price_text  # Sayısal değere çevrilemezse text olarak döndür
                return price_text
        except:
            pass
        return None
    
    def scrape_all_products(self):
        """Belirtilen kategori sayfasındaki ürünleri çeker"""
        logger.info("Pink Home Selenium ürün çekme işlemi başlatılıyor...")
        
        try:
            category_url = self.base_url + '/marka/pink-home'
            
            # Ürün linklerini çek
            product_links = self.extract_product_links(category_url)
            
            if not product_links:
                logger.error("Hiç ürün linki bulunamadı! Lütfen debug_page.html dosyasını kontrol edin.")
                return []
            
            logger.info(f"Toplam {len(product_links)} ürün bulundu")
            
            # Her ürünün detaylarını çek
            for i, product_url in enumerate(product_links, 1):
                logger.info(f"Ürün işleniyor ({i}/{len(product_links)}): {product_url}")
                
                product_data = self.extract_product_details(product_url)
                if product_data and (product_data.get('urun_adi') or product_data.get('aciklama') or product_data.get('eski_fiyat')):
                    self.products.append(product_data)
                    logger.info(f"✅ Ürün: {product_data.get('urun_adi', 'Ad yok')} | Açıklama: {'Var' if product_data.get('aciklama') else 'Yok'} | Eski Fiyat: {product_data.get('eski_fiyat', 'Yok')}")
                else:
                    logger.warning(f"❌ Ürün verisi bulunamadı: {product_url}")
                    # İlk başarısız ürün için debug
                    if len(self.products) == 0 and product_data:
                        logger.info(f"Debug - Çekilen veri: {product_data}")
                
                # Her 10 üründe bir ara ver
                if i % 10 == 0:
                    time.sleep(2)
            
            logger.info(f"Toplam {len(self.products)} ürün başarıyla çekildi")
            return self.products
            
        except Exception as e:
            logger.error(f"Scraping sırasında hata: {e}")
            return []
        finally:
            self.close_driver()
    
    def save_to_excel(self, filename='pink_home_selenium.xlsx'):
        """Verileri Excel dosyasına kaydeder"""
        if not self.products:
            logger.warning("Kaydedilecek ürün verisi bulunamadı")
            return
            
        df = pd.DataFrame(self.products)
        
        # Liste sütunlarını string'e çevir
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].apply(lambda x: '\n'.join(x) if isinstance(x, list) else str(x) if x else '')
        
        df.to_excel(filename, index=False, engine='openpyxl')
        logger.info(f"Veriler {filename} dosyasına kaydedildi")
    
    def save_to_csv(self, filename='pink_home_selenium.csv'):
        """Verileri CSV dosyasına kaydeder"""
        if not self.products:
            logger.warning("Kaydedilecek ürün verisi bulunamadı")
            return
            
        df = pd.DataFrame(self.products)
        
        # Liste sütunlarını string'e çevir
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].apply(lambda x: '\n'.join(x) if isinstance(x, list) else str(x) if x else '')
        
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        logger.info(f"Veriler {filename} dosyasına kaydedildi")

# Kullanım örneği
if __name__ == "__main__":
    print("🔧 Pink Home Selenium Scraper başlatılıyor...")
    print("Not: ChromeDriver'ın yüklü olduğundan emin olun!")
    print("İndirme: https://chromedriver.chromium.org/")
    print("-" * 50)
    
    try:
        # Scraper'ı başlat (headless=False yaparsan tarayıcı görünür)
        scraper = PinkHomeSeleniumScraper(headless=True)
        
        # Tüm ürünleri çek
        products = scraper.scrape_all_products()
        
        if products:
            # Excel'e kaydet
            scraper.save_to_excel('pink_home_selenium.xlsx')
            
            # CSV'ye kaydet  
            scraper.save_to_csv('pink_home_selenium.csv')
            
            # Özet bilgileri göster
            print(f"\n🎉 İşlem tamamlandı!")
            print(f"Toplam çekilen ürün sayısı: {len(products)}")
            
            print(f"\n📋 İlk ürün örneği:")
            first_product = products[0]
            for key, value in first_product.items():
                print(f"  {key}: {value}")
        else:
            print("❌ Hiç ürün çekilemedi!")
            
    except Exception as e:
        print(f"❌ Hata: {e}")
        print("ChromeDriver kurulumu için: pip install selenium")
        print("ChromeDriver indirme: https://chromedriver.chromium.org/")