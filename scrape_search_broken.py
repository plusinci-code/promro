# -*- coding: utf-8 -*-
from typing import List, Dict, Any, Optional
import re
import time
import urllib.parse
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from fake_useragent import UserAgent
from python_anticaptcha import AnticaptchaClient, NoCaptchaTaskProxylessTask, ImageToTextTask
try:
    from .captcha_solver import _detect_and_solve_captcha
except ImportError:
    def _detect_and_solve_captcha(driver, captcha_client):
        return False
from collections import defaultdict

from .utils import ensure_dir, save_csv, uniq_list

SEARCH_ENGINES = {
    "Google": "https://www.google.com/search?q={q}&hl=en",
    "Bing": "https://www.bing.com/search?q={q}",
    "Yahoo": "https://search.yahoo.com/search?p={q}",
    "Yandex": "https://yandex.com/search/?text={q}",
}

# Filtrelenecek domainler ve URL pattern'leri
FILTERED_DOMAINS = [
    "wikipedia.org", "facebook.com", "instagram.com", "twitter.com", "x.com",
    "linkedin.com", "youtube.com", "tiktok.com", "pinterest.com", "reddit.com",
    "amazon.com", "ebay.com", "alibaba.com", "aliexpress.com",
    "google.com", "bing.com", "yahoo.com", "yandex.com", "duckduckgo.com",
    "news", "blog", "forum", ".gov", ".edu", ".mil", ".int"
]

def _is_filtered_domain(url: str) -> bool:
    """URL'nin filtrelenmiş domain listesinde olup olmadığını kontrol eder"""
    url_lower = url.lower()
    return any(domain in url_lower for domain in FILTERED_DOMAINS)

def _get_base_domain(url: str) -> str:
    """URL'den base domain çıkarır"""
    try:
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except:
        return url

def _driver(headless: bool=False):
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1366,900")
    ua = UserAgent().random
    options.add_argument(f"user-agent={ua}")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def _extract_emails_advanced(driver, base_url: str, soup: BeautifulSoup, html: str) -> set:
    """Gelişmiş email çıkarma - resim dosyalarını ve sahte emailleri filtreler"""
    emails = set()
    
    # Temel regex ile email çıkarma
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
    potential_emails = re.findall(email_pattern, html)
    
    # Filtreleme: resim dosyaları ve sahte emailler
    image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.ico', '.bmp', '.tiff'}
    invalid_domains = {'example.com', 'test.com', 'domain.com', 'yoursite.com', 'website.com'}
    
    for email in potential_emails:
        email = email.lower().strip()
        
        # Resim dosyası kontrolü
        if any(ext in email for ext in image_extensions):
            continue
            
        # Geçersiz domain kontrolü
        domain = email.split('@')[1] if '@' in email else ''
        if domain in invalid_domains:
            continue
            
        # Minimum uzunluk kontrolü
        if len(email) < 6:
            continue
            
        # Geçerli TLD kontrolü
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            continue
            
        emails.add(email)
    
    # HTML içinde mailto: linklerini ara
    mailto_links = soup.find_all('a', href=re.compile(r'^mailto:', re.I))
    for link in mailto_links:
        href = link.get('href', '')
        if href.startswith('mailto:'):
            email = href[7:].split('?')[0].strip()  # mailto: kısmını çıkar ve parametreleri temizle
            if email and '@' in email:
                emails.add(email.lower())
    
    return emails

def _extract_phones_advanced(html: str, soup: BeautifulSoup) -> set:
    """Gelişmiş telefon numarası çıkarma"""
    phones = set()
    
    # Çeşitli telefon formatları
    phone_patterns = [
        r'\+?\d{1,4}[\s\-\.]?\(?\d{1,4}\)?[\s\-\.]?\d{1,4}[\s\-\.]?\d{1,4}[\s\-\.]?\d{1,9}',
        r'\b\d{3}[\s\-\.]\d{3}[\s\-\.]\d{4}\b',  # US format
        r'\b\d{2}[\s\-\.]\d{4}[\s\-\.]\d{4}\b',  # TR format
        r'\+\d{1,3}[\s\-\.]\d{1,4}[\s\-\.]\d{1,4}[\s\-\.]\d{1,4}',
    ]
    
    for pattern in phone_patterns:
        matches = re.findall(pattern, html)
        for match in matches:
            # Temizleme ve doğrulama
            clean_phone = re.sub(r'[^\d+]', '', match)
            if len(clean_phone) >= 7 and len(clean_phone) <= 15:
                phones.add(match.strip())
    
    # tel: linklerini ara
    tel_links = soup.find_all('a', href=re.compile(r'^tel:', re.I))
    for link in tel_links:
        href = link.get('href', '')
        if href.startswith('tel:'):
            phone = href[4:].strip()  # tel: kısmını çıkar
            if phone:
                phones.add(phone)
    
    return phones

def _extract_contact_info(driver, base_url: str, soup: BeautifulSoup) -> Dict[str, any]:
    """İletişim sayfasından adres, ülke, email ve telefon bilgisi çıkarır"""
    contact_info = {"address": "", "country": "", "language": "", "emails": set(), "phones": set()}
    
    # İletişim sayfası linklerini ara
    contact_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        text = a.get_text().lower()
        if any(word in href or word in text for word in ["contact", "iletisim", "kontakt", "contacto", "contatto"]):
            full_url = urllib.parse.urljoin(base_url, a["href"])
            contact_links.append(full_url)
    
    # Hakkımızda sayfası linklerini ara
    about_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        text = a.get_text().lower()
        if any(word in href or word in text for word in ["about", "hakkimizda", "uber-uns", "acerca", "chi-siamo"]):
            full_url = urllib.parse.urljoin(base_url, a["href"])
            about_links.append(full_url)
    
    # İletişim ve hakkımızda sayfalarını ziyaret et
    for link in (contact_links + about_links)[:3]:  # Max 3 sayfa
        try:
            driver.get(link)
            time.sleep(2)
            page_html = driver.page_source
            page_soup = BeautifulSoup(page_html, "lxml")
            
            # Bu sayfadan email ve telefon çıkar
            page_emails = _extract_emails_advanced(driver, base_url, page_soup, page_html)
            page_phones = _extract_phones_advanced(page_html, page_soup)
            contact_info["emails"].update(page_emails)
            contact_info["phones"].update(page_phones)
            
            # Adres bilgisi ara
            address_patterns = [
                r'(?i)address[:\s]*([^<\n]{10,100})',
                r'(?i)adres[:\s]*([^<\n]{10,100})',
                r'(?i)adresse[:\s]*([^<\n]{10,100})',
                r'(?i)dirección[:\s]*([^<\n]{10,100})'
            ]
            
            page_text = page_soup.get_text()
            for pattern in address_patterns:
                matches = re.findall(pattern, page_text)
                if matches and not contact_info["address"]:
                    contact_info["address"] = matches[0].strip()[:200]
            
            # Ülke bilgisi ara
            country_patterns = [
                r'(?i)(Germany|Deutschland|Almanya)',
                r'(?i)(United States|USA|Amerika)',
                r'(?i)(United Kingdom|UK|İngiltere)',
                r'(?i)(France|Fransa|Francia)',
                r'(?i)(Italy|Italia|İtalya)',
                r'(?i)(Spain|España|İspanya)',
                r'(?i)(Turkey|Türkiye|Turkiye)',
                r'(?i)(Australia|Avustralya)',
                r'(?i)(Canada|Kanada)',
                r'(?i)(Netherlands|Hollanda)'
            ]
            
            for pattern in country_patterns:
                matches = re.findall(pattern, page_text)
                if matches and not contact_info["country"]:
                    contact_info["country"] = matches[0].strip()
            
        except Exception:
            continue
    
    # Ana sayfadan da header/footer email ve telefon çıkar
    main_emails = _extract_emails_advanced(driver, base_url, soup, driver.page_source)
    main_phones = _extract_phones_advanced(driver.page_source, soup)
    contact_info["emails"].update(main_emails)
    contact_info["phones"].update(main_phones)
    
    # Header ve footer özel tarama
    header_footer_selectors = ['header', 'footer', '.header', '.footer', '#header', '#footer', 'nav', '.navbar']
    for selector in header_footer_selectors:
        try:
            elements = soup.select(selector)
            for element in elements:
                element_html = str(element)
                hf_emails = _extract_emails_advanced(driver, base_url, element, element_html)
                hf_phones = _extract_phones_advanced(element_html, element)
                contact_info["emails"].update(hf_emails)
                contact_info["phones"].update(hf_phones)
        except Exception:
            continue
    
    # Dil tespiti (HTML lang attribute veya içerik analizi)
    try:
        html_lang = soup.find("html", {"lang": True})
        if html_lang:
            contact_info["language"] = html_lang.get("lang", "")[:10]
    except:
        pass
    
    return contact_info

def _get_google_results_with_pagination(driver, keyword: str, per_keyword_limit: int) -> List[str]:
    """Google'da çoklu sayfa sonuçları çıkarır"""
    all_links = []
    pages_needed = max(1, (per_keyword_limit + 9) // 10)  # Her sayfada ~10 sonuç
    
    base_url = f"https://www.google.com/search?q={urllib.parse.quote(keyword)}&hl=en"
    
    for page in range(min(pages_needed, 5)):  # Max 5 sayfa
        if page == 0:
            url = base_url
        else:
            url = f"{base_url}&start={page * 10}"
        
        try:
            driver.get(url)
            time.sleep(10)
            
            # Google sonuç linklerini çıkar
            result_links = driver.find_elements(By.CSS_SELECTOR, "div.g a[href^='http']")
            
            for link in result_links:
                href = link.get_attribute("href")
                if href and not _is_filtered_domain(href):
                    all_links.append(href)
                    if len(all_links) >= per_keyword_limit:
                        break
                        
            if len(all_links) >= per_keyword_limit:
                break
                
        except Exception as e:
            print(f"Google sayfa {page+1} hatası: {e}")
            break
    
    return all_links

def search_and_collect(
    keywords: List[str],
    engines: List[str],
    max_sites_total: int,
    per_keyword_limit: int,
    dwell_seconds: int,
    out_dir: Path,
    anticaptcha_api_key: str = None,
) -> pd.DataFrame:
    ensure_dir(out_dir)
    domain_data = defaultdict(lambda: {
        "Firma Adı": "",
        "Firma Websitesi": "",
        "Firma Adresi": "",
        "Firma Ülkesi/Dil": "",
        "Telefon Numaraları": set(),
        "Email Adresleri": set(),
        "Sosyal Medya": set(),
        "Sayfa Başlığı": "",
        "Özet Metin": ""
    })
    
    # Ziyaret edilmiş domainleri takip et (tekrar ziyaret önleme)
    visited_domains = set()
    
    # Anti-Captcha client başlat
    captcha_client = None
    if anticaptcha_api_key:
        try:
            captcha_client = AnticaptchaClient(anticaptcha_api_key)
            print("Anti-Captcha client baslatildi")
        except Exception as e:
            print(f"Anti-Captcha client baslatilamadi: {e}")
    
    print(f"Toplam {len(keywords)} anahtar kelime, {len(engines)} arama motoru")
    print(f"Maksimum {max_sites_total} site, her kelime icin {per_keyword_limit} sonuc")
    print(f"Site basina {dwell_seconds} saniye bekleme")
    if anticaptcha_api_key:
        print("CAPTCHA cozme aktif")

    driver = _driver(headless=False)
    try:
        for kw in keywords:
            for eng in engines:
                if eng not in SEARCH_ENGINES: 
                    continue
                
                print(f"Araniyor: {kw} - {eng}")
                
                # Google için gelişmiş sayfalama
                if eng == "Google":
                    links = _get_google_results_with_pagination(driver, kw, per_keyword_limit)
                else:
                    # Diğer arama motorları için mevcut yöntem
                    url = SEARCH_ENGINES[eng].format(q=urllib.parse.quote(kw))
                    driver.get(url)
                    time.sleep(5)
                    
                    links = []
                    a_elems = driver.find_elements(By.CSS_SELECTOR, "a")
                    for a in a_elems:
                        href = a.get_attribute("href") or ""
                        if href.startswith("http") and not _is_filtered_domain(href):
                            links.append(href)
                    
                    links = links[:per_keyword_limit]

                # Her linki ziyaret et
                for lnk in links:
                    if len(domain_data) >= max_sites_total:
                        break
                    
                    base_domain = _get_base_domain(lnk)
                    
                    # Domain tekrar kontrolü
                    if base_domain in visited_domains:
                        print(f"Atlaniyor (zaten ziyaret edildi): {base_domain}")
                        continue
                    
                    try:
                        print(f"Ziyaret ediliyor: {base_domain}")
                        driver.get(lnk)
                        visited_domains.add(base_domain)  # Domain'i ziyaret edildi olarak işaretle
                        
                        # CAPTCHA kontrolü ve çözümü
                        captcha_solved = _detect_and_solve_captcha(driver, captcha_client)
                        if captcha_solved:
                            print(f"CAPTCHA cozuldu: {base_domain}")
                            time.sleep(2)  # CAPTCHA çözümü sonrası ek bekleme
                        
                        time.sleep(max(2, dwell_seconds))

                        html = driver.page_source
                        soup = BeautifulSoup(html, "lxml")
                        title = (soup.title.string if soup.title else "") or ""
                        
                        # Gelişmiş email ve telefon çıkarımı
                        emails = _extract_emails_advanced(driver, base_domain, soup, html)
                        phones = _extract_phones_advanced(html, soup)
                        
                        # Sosyal medya linkleri
                        socials = set()
                        for dom in ["facebook.com","instagram.com","linkedin.com","x.com","twitter.com","youtube.com","t.me"]:
                            for a in soup.find_all("a", href=True):
                                if dom in a["href"]:
                                    socials.add(a["href"])
                        
                        # İletişim bilgilerini çıkar (email ve telefon da dahil)
                        contact_info = _extract_contact_info(driver, base_domain, soup)
                        
                        # İletişim sayfalarından ek email ve telefon bilgileri
                        contact_emails, contact_phones = contact_info.get('emails', set()), contact_info.get('phones', set())
                        emails.update(contact_emails)
                        phones.update(contact_phones)
                        
                        # Domain bazlı veri birleştirme
                        if base_domain not in domain_data:
                            domain_data[base_domain] = {
                                "Firma Adı": title[:200],
                                "Firma Websitesi": base_domain,
                                "Firma Adresi": contact_info["address"],
                                "Firma Ülkesi/Dil": f"{contact_info['country']} / {contact_info['language']}".strip(" /"),
                                "Telefon Numaraları": phones,
                                "Email Adresleri": emails,
                                "Sosyal Medya": socials,
                                "Sayfa Başlığı": title,
                                "Özet Metin": soup.get_text()[:500]
                            }
                        else:
                            # Mevcut verilerle birleştir
                            domain_data[base_domain]["Telefon Numaraları"].update(phones)
                            domain_data[base_domain]["Email Adresleri"].update(emails)
                            domain_data[base_domain]["Sosyal Medya"].update(socials)
                            
                            if not domain_data[base_domain]["Firma Adresi"] and contact_info["address"]:
                                domain_data[base_domain]["Firma Adresi"] = contact_info["address"]
                            
                            if not domain_data[base_domain]["Firma Ülkesi/Dil"] and (contact_info["country"] or contact_info["language"]):
                                domain_data[base_domain]["Firma Ülkesi/Dil"] = f"{contact_info['country']} / {contact_info['language']}".strip(" /")

                    except Exception as e:
                        print(f"Hata: {base_domain} - {str(e)}")
                        visited_domains.add(base_domain)  # Hatalı siteleri de işaretle
                        continue

                if len(domain_data) >= max_sites_total:
                    break
            if len(domain_data) >= max_sites_total:
                break
    finally:
        try: 
            driver.quit()
        except: 
            pass
    
    print(f"\nToplam {len(visited_domains)} benzersiz domain ziyaret edildi")
    print(f"{len(domain_data)} siteden veri toplandi")

    # Veriyi DataFrame'e dönüştür
    rows = []
    for domain, data in domain_data.items():
        rows.append({
            "Firma Adı": data["Firma Adı"],
            "Firma Websitesi": data["Firma Websitesi"],
            "Firma Adresi": data["Firma Adresi"],
            "Firma Ülkesi/Dil": data["Firma Ülkesi/Dil"],
            "Telefon Numaraları": "; ".join(data["Telefon Numaraları"]),
            "Email Adresleri": "; ".join(data["Email Adresleri"]),
            "Sosyal Medya": "; ".join(data["Sosyal Medya"]),
            "Sayfa Başlığı": data["Sayfa Başlığı"],
            "Özet Metin": data["Özet Metin"]
        })

    df = pd.DataFrame(rows)
    save_csv(rows, out_dir / "C_search_results.csv")
    return df
