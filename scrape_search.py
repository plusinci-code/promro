# -*- coding: utf-8 -*-
"""
scrape_search.py
----------------
Gelişmiş arama motorları ve site ziyaret sistemi.

Özellikler:
- Tüm arama motorlarında tutarlı çalışma
- Tarayıcı kapatılması durumunda veri kaydetme
- CAPTCHA sistemi tamamen kaldırıldı
- Gelişmiş session management
- Performans optimizasyonu
"""
from __future__ import annotations

import sys
from typing import List, Dict, Any, Optional, Set
import re
import time
import random
import urllib.parse
from pathlib import Path
from collections import defaultdict

# Windows console encoding düzeltmesi
if sys.platform.startswith('win'):
    try:
        import codecs
        if hasattr(sys.stdout, 'detach'):
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
        if hasattr(sys.stderr, 'detach'):
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())
    except Exception:
        # Streamlit ile uyumluluk için encoding düzeltmesi atlanır
        pass

import pandas as pd
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# Alternatif arama motorları kaldırıldı - sadece DuckDuckGo kullanılıyor

# ---- Opsiyonel user-agent ----
try:
    from fake_useragent import UserAgent  # opsiyonel
    _UA = UserAgent().random
except Exception:
    UserAgent = None  # type: ignore
    _UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


# ---- Yardımcılar (utils.py yoksa fallback) ----
try:
    from .utils import ensure_dir, save_csv, uniq_list  # type: ignore
except Exception:
    def ensure_dir(p: Path) -> None:
        p.mkdir(parents=True, exist_ok=True)

    def save_csv(records: List[Dict[str, Any]], out_path: Path) -> None:
        """Basit CSV kaydı (pandas üzerinden)."""
        df = pd.DataFrame(records)
        df.to_csv(out_path, index=False, encoding="utf-8-sig")

    def uniq_list(items: List[Any]) -> List[Any]:
        seen, res = set(), []
        for x in items:
            if x not in seen:
                seen.add(x)
                res.append(x)
        return res


# ---- Basit sınıflandırma ----
def _classify_company_type(page_text: str, title: str) -> str:
    text = (page_text + " " + title).lower()

    ecommerce_keywords = [
        'shop', 'store', 'cart', 'buy', 'purchase', 'online store', 'e-commerce', 'ecommerce',
        'mağaza', 'satın al', 'sepet', 'alışveriş', 'e-ticaret', 'online mağaza'
    ]
    manufacturer_keywords = [
        'manufacturer', 'factory', 'production', 'produce', 'made', 'manufacturing',
        'üretici', 'fabrika', 'üretim', 'imalat', 'üretiyoruz', 'imal'
    ]
    wholesale_keywords = [
        'wholesale', 'bulk', 'distributor', 'supplier', 'b2b',
        'toptan', 'toptancı', 'tedarikçi', 'distribütör'
    ]
    importer_keywords = [
        'import', 'importer', 'international trade', 'global supplier',
        'ithalat', 'ithalatçı', 'dış ticaret'
    ]
    exporter_keywords = [
        'export', 'exporter', 'international sales', 'global market',
        'ihracat', 'ihracatçı', 'uluslararası satış'
    ]
    service_keywords = [
        'service', 'repair', 'maintenance', 'support', 'technical',
        'servis', 'tamir', 'bakım', 'destek', 'teknik servis'
    ]
    dealer_keywords = [
        'dealer', 'authorized', 'reseller', 'partner', 'representative',
        'bayi', 'yetkili', 'temsilci', 'distribütör'
    ]
    institution_keywords = [
        'government', 'ministry', 'department', 'agency', 'public',
        'devlet', 'bakanlık', 'müdürlük', 'kamu', 'belediye'
    ]

    scores = {
        'E-ticaret Firması': sum(1 for kw in ecommerce_keywords if kw in text),
        'Üretici': sum(1 for kw in manufacturer_keywords if kw in text),
        'Toptancı': sum(1 for kw in wholesale_keywords if kw in text),
        'İthalatçı': sum(1 for kw in importer_keywords if kw in text),
        'İhracatçı': sum(1 for kw in exporter_keywords if kw in text),
        'Servis + Yedek Parça': sum(1 for kw in service_keywords if kw in text),
        'Bayi / Yetkili Satıcı': sum(1 for kw in dealer_keywords if kw in text),
        'Kurum/Devlet': sum(1 for kw in institution_keywords if kw in text),
    }
    return max(scores, key=scores.get) if max(scores.values()) > 0 else 'Mağaza'


SEARCH_ENGINES = {
    # Sadece DuckDuckGo arama motoru
    "DuckDuckGo": "https://html.duckduckgo.com/html/?q={q}",
}


# ---- Domain filtreleme ----
FILTERED_DOMAINS = {
    'wikipedia.org', 'facebook.com', 'youtube.com', 'instagram.com',
    'twitter.com', 'x.com', 'linkedin.com', 'amazon.com', 'ebay.com',
    'reddit.com', 'quora.com', 'pinterest.com', 'tiktok.com',
    'alibaba.com', 'aliexpress.com', 'booking.com', 'tripadvisor.com',
    'yelp.com', 'glassdoor.com', 'indeed.com', 'stackoverflow.com',
    'github.com', 'microsoft.com', 'apple.com', 'google.com',
    'gov.', '.edu', '.org', 'news.', 'blog.', 'medium.com',
    'wordpress.com', 'blogspot.com', 'tumblr.com', 'wix.com',
    'shopify.com', 'etsy.com', 'paypal.com', 'stripe.com',
}


def _is_filtered_domain(url: str) -> bool:
    try:
        domain = urllib.parse.urlparse(url).netloc.lower()
        return any(filtered in domain for filtered in FILTERED_DOMAINS)
    except Exception:
        return True


def _get_base_domain(url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        return url


def _get_clean_domain(url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc.lower()
        return domain[4:] if domain.startswith('www.') else domain
    except Exception:
        return url


def _driver(headless: bool = False) -> webdriver.Chrome:
    """Normal driver - görünür mod"""
    return _create_driver(headless=headless, stealth_mode=False)

def _stealth_driver(headless: bool = True) -> webdriver.Chrome:
    """Gelişmiş stealth driver - CAPTCHA bypass için optimize edilmiş"""
    return _create_driver(headless=headless, stealth_mode=True)

def _create_driver(headless: bool = False, stealth_mode: bool = False) -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    
    # Gelişmiş stealth ayarları
    if headless:
        options.add_argument("--headless=new")
    
    # Temel ayarlar - hızlandırıldı
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--disable-images")  # Resimleri yükleme - hız için
    
    # İnsan benzeri pencere boyutu ve görünüm
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    # Automation detection bypass
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-translate")
    options.add_argument("--hide-scrollbars")
    options.add_argument("--mute-audio")
    
    # Gelişmiş user agent ve fingerprinting bypass
    options.add_argument(f"user-agent={_UA}")
    options.add_argument("--accept-lang=en-US,en;q=0.9")
    options.add_argument("--accept-encoding=gzip, deflate, br")
    
    # Memory ve performance optimizasyonları - kararlılık için iyileştirildi
    options.add_argument("--memory-pressure-off")
    options.add_argument("--max_old_space_size=4096")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-crash-reporter")
    options.add_argument("--disable-logging")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-prompt-on-repost")
    options.add_argument("--disable-hang-monitor")
    options.add_argument("--disable-client-side-phishing-detection")
    options.add_argument("--disable-component-extensions-with-background-pages")
    
    # Network ve security ayarları
    options.add_argument("--disable-features=TranslateUI")
    options.add_argument("--disable-ipc-flooding-protection")
    options.add_argument("--disable-hang-monitor")
    options.add_argument("--disable-prompt-on-repost")
    options.add_argument("--disable-domain-reliability")
    
    # Stealth mode için ek ayarlar
    if stealth_mode:
        # Ek stealth argümanları
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-features=VizDisplayCompositor")
        options.add_argument("--disable-ipc-flooding-protection")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-client-side-phishing-detection")
        options.add_argument("--disable-component-extensions-with-background-pages")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-features=TranslateUI")
        options.add_argument("--disable-hang-monitor")
        options.add_argument("--disable-ipc-flooding-protection")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-prompt-on-repost")
        options.add_argument("--disable-sync")
        options.add_argument("--disable-translate")
        options.add_argument("--disable-windows10-custom-titlebar")
        options.add_argument("--metrics-recording-only")
        options.add_argument("--no-first-run")
        options.add_argument("--safebrowsing-disable-auto-update")
        options.add_argument("--enable-automation")
        options.add_argument("--password-store=basic")
        options.add_argument("--use-mock-keychain")
        
        # Ek stealth prefs
        stealth_prefs = {
            "profile.default_content_setting_values": {
                "notifications": 2,
                "geolocation": 2,
                "media_stream": 2,
                "plugins": 1,
                "popups": 2,
                "automatic_downloads": 2,
            },
            "profile.default_content_settings.popups": 0,
            "profile.managed_default_content_settings.images": 1,
            "profile.content_settings.exceptions.automatic_downloads.*.setting": 1,
            "profile.default_content_setting_values.automatic_downloads": 1,
            "profile.password_manager_enabled": False,
            "credentials_enable_service": False,
            "webrtc.ip_handling_policy": "disable_non_proxied_udp",
            "webrtc.multiple_routes_enabled": False,
            "webrtc.nonproxied_udp_enabled": False,
            "profile.default_content_settings": {
                "plugins": 1,
                "popups": 2,
                "geolocation": 2,
                "notifications": 2,
                "media_stream": 2,
            }
        }
        options.add_experimental_option("prefs", stealth_prefs)
    else:
        # Normal prefs
        prefs = {
            "profile.default_content_setting_values": {
                "notifications": 2,
                "geolocation": 2,
                "media_stream": 2,
            },
            "profile.default_content_settings.popups": 0,
            "profile.managed_default_content_settings.images": 1,
            "profile.content_settings.exceptions.automatic_downloads.*.setting": 1,
            "profile.default_content_setting_values.automatic_downloads": 1,
            "profile.password_manager_enabled": False,
            "credentials_enable_service": False,
            "webrtc.ip_handling_policy": "disable_non_proxied_udp",
            "webrtc.multiple_routes_enabled": False,
            "webrtc.nonproxied_udp_enabled": False
        }
        options.add_experimental_option("prefs", prefs)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    # Session timeout ayarları - kararlılık için
    driver.set_page_load_timeout(30)  # Sayfa yükleme timeout
    driver.implicitly_wait(10)  # Element bekleme timeout
    driver.set_script_timeout(30)  # JavaScript timeout
    
    # Session ayarları
    driver.maximize_window()
    driver.delete_all_cookies()  # Temiz başlangıç
    
    # Gelişmiş JavaScript stealth injection
    try:
        if stealth_mode:
            # Gelişmiş stealth script
            stealth_script = """
            // WebDriver detection bypass
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            
            // Plugin simulation
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer'},
                    {name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'},
                    {name: 'Native Client', filename: 'internal-nacl-plugin'}
                ]
            });
            
            // Language settings
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            
            // Permissions API
            Object.defineProperty(navigator, 'permissions', {
                get: () => ({
                    query: () => Promise.resolve({state: 'granted'})
                })
            });
            
            // Chrome runtime
            window.chrome = {
                runtime: {
                    onConnect: undefined,
                    onMessage: undefined
                }
            };
            
            // Platform info
            Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
            Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 4});
            Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
            
            // Screen properties
            Object.defineProperty(screen, 'colorDepth', {get: () => 24});
            Object.defineProperty(screen, 'pixelDepth', {get: () => 24});
            
            // Connection info
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    effectiveType: '4g',
                    rtt: 50,
                    downlink: 10
                })
            });
            
            // Battery API
            Object.defineProperty(navigator, 'getBattery', {
                get: () => () => Promise.resolve({
                    charging: true,
                    chargingTime: 0,
                    dischargingTime: Infinity,
                    level: 1
                })
            });
            
            // Timezone
            Object.defineProperty(Intl.DateTimeFormat.prototype, 'resolvedOptions', {
                value: function() {
                    return {
                        locale: 'en-US',
                        timeZone: 'America/New_York'
                    };
                }
            });
            """
        else:
            # Normal stealth script
            stealth_script = """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            Object.defineProperty(navigator, 'permissions', {get: () => ({query: () => Promise.resolve({state: 'granted'})})});
            window.chrome = {runtime: {}};
            Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
            Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 4});
            Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
            Object.defineProperty(screen, 'colorDepth', {get: () => 24});
            Object.defineProperty(screen, 'pixelDepth', {get: () => 24});
            """
        
        driver.execute_script(stealth_script)
        
        # Stealth mode için ek JavaScript injection
        if stealth_mode:
            additional_stealth = """
            // Mouse movement simulation
            document.addEventListener('DOMContentLoaded', function() {
                const event = new MouseEvent('mousemove', {
                    view: window,
                    bubbles: true,
                    cancelable: true,
                    clientX: Math.random() * window.innerWidth,
                    clientY: Math.random() * window.innerHeight
                });
                document.dispatchEvent(event);
            });
            
            // Random scroll simulation
            setTimeout(() => {
                window.scrollTo(0, Math.random() * 100);
            }, Math.random() * 2000 + 1000);
            """
            driver.execute_script(additional_stealth)
            
    except Exception:
        pass
    
    return driver


# ---- E-posta / Telefon çıkarma ----
def _extract_emails_advanced(base_url: str, soup: BeautifulSoup, html: str) -> Set[str]:
    """Gelişmiş email çıkarma - DuckDuckGo için optimize edildi"""
    emails: Set[str] = set()
    try:
        from urllib.parse import urlparse
        parsed_url = urlparse(base_url)
        site_domain = parsed_url.netloc.lower()
        site_domain = site_domain[4:] if site_domain.startswith('www.') else site_domain
    except Exception:
        site_domain = ""

    valid_email_domains = {
        'gmail.com', 'hotmail.com', 'outlook.com', 'yahoo.com', 'aol.com', 'icloud.com',
        'protonmail.com', 'yandex.com', 'mail.ru', 'zoho.com', 'fastmail.com'
    }

    # DuckDuckGo için genişletilmiş arama alanları
    contact_areas: List[str] = []
    contact_selectors = ['footer', 'header', '.contact', '#contact']  # Hızlı çıkarma için minimal selectors
    
    for selector in contact_selectors:
        for element in soup.select(selector):
            contact_areas.append(str(element))
    contact_areas.append(html)

    image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.ico', '.bmp', '.tiff', '.avif', '.jfif', '.pjpeg', '.pjp'}
    invalid_domains = {'example.com', 'test.com', 'domain.com', 'yoursite.com', 'website.com', 'localhost', '127.0.0.1'}
    invalid_prefixes = {'noreply', 'no-reply', 'donotreply', 'admin', 'webmaster', 'postmaster', 'test', 'demo', 'sample'}

    # Hızlı email pattern'leri - sadece temel
    email_patterns = [
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
        r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
    ]

    for pattern in email_patterns:
        for area_html in contact_areas:
            potential_emails = re.findall(pattern, area_html, re.IGNORECASE)
            for email in potential_emails:
                if isinstance(email, tuple):
                    email = f"{email[0]}@{email[1]}"
                
                email = email.lower().strip()
                if any(ext in email for ext in image_extensions):
                    continue
                if '@' not in email:
                    continue
                
                try:
                    local, domain = email.split('@', 1)
                    if domain in invalid_domains or local in invalid_prefixes:
                        continue
                    if len(email) < 6 or not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                        continue
                    if domain == site_domain or domain in valid_email_domains:
                        emails.add(email)
                except ValueError:
                    continue

    # Mailto linklerini çıkar
    for link in soup.find_all('a', href=re.compile(r'^mailto:', re.I)):
        href = link.get('href', '')
        if href.startswith('mailto:'):
            email = href[7:].split('?')[0].strip().lower()
            if '@' in email:
                try:
                    domain = email.split('@', 1)[1]
                    if domain == site_domain or domain in valid_email_domains:
                        emails.add(email)
                except ValueError:
                    continue

    return set(list(emails)[:2])  # Hızlı çıkarma için azaltıldı


def _extract_phones_advanced(html: str, soup: BeautifulSoup) -> Set[str]:
    """Gelişmiş telefon çıkarma - DuckDuckGo için optimize edildi"""
    phones: Set[str] = set()
    valid_country_codes = {
        '+1', '+52', '+54', '+55', '+56', '+57', '+58', '+51', '+591', '+593', '+595', '+598', '+597', '+592', '+594',
        '+30', '+31', '+32', '+33', '+34', '+351', '+352', '+353', '+354', '+355', '+356', '+357', '+358', '+359', '+36',
        '+370', '+371', '+372', '+373', '+374', '+375', '+376', '+377', '+378', '+380', '+381', '+382', '+383', '+385',
        '+386', '+387', '+389', '+39', '+40', '+41', '+420', '+421', '+423', '+43', '+44', '+45', '+46', '+47', '+48', '+49',
        '+20', '+212', '+213', '+216', '+218', '+220', '+221', '+222', '+223', '+224', '+225', '+226', '+227', '+228', '+229',
        '+230', '+231', '+232', '+233', '+234', '+235', '+236', '+237', '+238', '+239', '+240', '+241', '+242', '+243', '+244',
        '+245', '+246', '+248', '+249', '+250', '+251', '+252', '+253', '+254', '+255', '+256', '+257', '+258', '+260', '+261',
        '+262', '+263', '+264', '+265', '+266', '+267', '+268', '+269', '+27', '+290', '+291', '+297', '+298', '+299',
        '+60', '+61', '+62', '+63', '+64', '+65', '+66', '+81', '+82', '+84', '+86', '+91', '+92', '+93', '+94', '+95', '+98',
        '+850', '+852', '+853', '+855', '+856', '+880', '+886', '+960', '+961', '+962', '+963', '+964', '+965', '+966', '+967',
        '+968', '+970', '+971', '+972', '+973', '+974', '+975', '+976', '+977', '+992', '+993', '+994', '+995', '+996', '+998',
        '+672', '+673', '+674', '+675', '+676', '+677', '+678', '+679', '+680', '+681', '+682', '+683', '+684', '+685', '+686',
        '+687', '+688', '+689', '+690', '+691', '+692', '+7', '+500', '+501', '+502', '+503', '+504', '+505', '+506', '+507',
        '+508', '+509', '+590', '+591', '+592', '+593', '+594', '+595', '+596', '+597', '+598', '+599',
    }

    # DuckDuckGo için genişletilmiş arama alanları
    contact_areas: List[str] = []
    contact_selectors = ['footer', 'header', '.contact', '#contact']  # Hızlı çıkarma için minimal selectors
    
    for selector in contact_selectors:
        for element in soup.select(selector):
            contact_areas.append(str(element))
    contact_areas.append(html)

    # Hızlı telefon pattern'leri - sadece temel
    phone_patterns = [
        r'\+\d{1,4}[\s\-\.]?\d{1,4}[\s\-\.]?\d{1,4}[\s\-\.]?\d{1,4}',
        r'phone["\']?\s*[:=]\s*["\']?([+\d\s\-\.()]+)["\']?'
    ]

    for pattern in phone_patterns:
        for area_html in contact_areas:
            matches = re.findall(pattern, area_html, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                
                clean_phone = re.sub(r'[^\d+]', '', match)
                if len(clean_phone) >= 8:
                    ok = False
                    for i in range(1, 5):
                        cc = clean_phone[:i]
                        if '+' + cc in valid_country_codes or clean_phone.startswith(tuple(valid_country_codes)):
                            ok = True
                            break
                    if ok and len(match.strip()) >= 10:
                        phones.add(match.strip())

    # Tel linklerini çıkar
    for link in soup.find_all('a', href=re.compile(r'^tel:', re.I)):
        href = link.get('href', '')
        if href.startswith('tel:'):
            phone = href[4:].strip()
            if phone:
                clean_phone = re.sub(r'[^\d+]', '', phone)
                if len(clean_phone) >= 8:
                    phones.add(phone)

    return set(list(phones)[:2])  # Hızlı çıkarma için azaltıldı


def _extract_contact_info(base_url: str, soup: BeautifulSoup, driver: webdriver.Chrome) -> Dict[str, Any]:
    contact_info: Dict[str, Any] = {
        "address": "",
        "country": "",
        "language": "",
        "emails": set(),
        "phones": set(),
    }

    contact_links: List[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        text = a.get_text().lower()
        if any(word in href or word in text for word in ["contact", "iletisim", "kontakt", "contacto", "contatto"]):
            contact_links.append(urllib.parse.urljoin(base_url, a["href"]))

    about_links: List[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        text = a.get_text().lower()
        if any(word in href or word in text for word in ["about", "hakkimizda", "uber-uns", "acerca", "chi-siamo"]):
            about_links.append(urllib.parse.urljoin(base_url, a["href"]))

    for link in (contact_links + about_links)[:3]:
        try:
            driver.get(link)
            time.sleep(2)
            page_html = driver.page_source
            page_soup = BeautifulSoup(page_html, "lxml")

            contact_info["emails"].update(_extract_emails_advanced(base_url, page_soup, page_html))
            contact_info["phones"].update(_extract_phones_advanced(page_html, page_soup))

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
                r'(?i)(Netherlands|Hollanda)',
            ]
            for pattern in country_patterns:
                matches = re.findall(pattern, page_text)
                if matches and not contact_info["country"]:
                    contact_info["country"] = matches[0].strip()
        except Exception:
            continue

    main_emails = _extract_emails_advanced(base_url, soup, driver.page_source)
    main_phones = _extract_phones_advanced(driver.page_source, soup)
    contact_info["emails"].update(main_emails)
    contact_info["phones"].update(main_phones)

    try:
        html_lang = soup.find("html", {"lang": True})
        if html_lang:
            contact_info["language"] = html_lang.get("lang", "")[:10]
    except Exception:
        pass

    return contact_info


# ---- Akıllı bekleme stratejileri ----
def _human_like_delay(min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
    """İnsan benzeri rastgele bekleme süresi"""
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)

def _smart_wait_between_requests(request_count: int) -> None:
    """İstek sayısına göre akıllı bekleme"""
    if request_count < 5:
        _human_like_delay(2.0, 4.0)
    elif request_count < 15:
        _human_like_delay(4.0, 7.0)
    elif request_count < 30:
        _human_like_delay(8.0, 15.0)
    else:
        _human_like_delay(15.0, 30.0)

# ---- Gelişmiş Session Management ----
def _is_browser_alive(driver: webdriver.Chrome) -> bool:
    """Tarayıcının hala çalışıp çalışmadığını kontrol et"""
    try:
        driver.current_url
        return True
    except Exception:
        return False

def _save_partial_data(domain_data: Dict[str, Dict[str, Any]], out_dir: Path, reason: str = "partial") -> None:
    """Kısmi verileri kaydet - düzenli format"""
    try:
        if not domain_data:
            return
            
        # Düzenli veri formatı
        rows = []
        for domain, data in domain_data.items():
            # Veri temizleme ve düzenleme
            company_name = data.get("Firma Adı", "").strip()
            website = data.get("Firma Websitesi", "").strip()
            address = data.get("Firma Adresi", "").strip()
            country = data.get("Firma Ülkesi/Dil", "").strip()
            
            # Telefon numaralarını temizle ve düzenle
            phones = data.get("Telefon Numaraları", set())
            phone_str = "; ".join(sorted([p.strip() for p in phones if p.strip()]))
            
            # Email adreslerini temizle ve düzenle
            emails = data.get("Email Adresleri", set())
            email_str = "; ".join(sorted([e.strip() for e in emails if e.strip()]))
            
            # Sosyal medya linklerini temizle ve düzenle
            socials = data.get("Sosyal Medya", set())
            social_str = "; ".join(sorted([s.strip() for s in socials if s.strip()]))
            
            # Diğer veriler
            company_type = data.get("Firma Tipi", "").strip()
            page_title = data.get("Sayfa Başlığı", "").strip()
            summary = data.get("Özet Metin", "").strip()
            visit_count = data.get("Toplam Veri Sayısı", 1)
            
            rows.append({
                "Firma Adı": company_name,
                "Firma Websitesi": website,
                "Firma Adresi": address,
                "Firma Ülkesi/Dil": country,
                "Telefon Numaraları": phone_str,
                "Email Adresleri": email_str,
                "Sosyal Medya": social_str,
                "Firma Tipi": company_type,
                "Sayfa Başlığı": page_title,
                "Özet Metin": summary,
                "Ziyaret Edilen Sayfa Sayısı": visit_count,
                "Durum": f"Kısmi Veri ({reason})"
            })
        
        # DataFrame oluştur ve düzenle
        df = pd.DataFrame(rows)
        
        # Boş satırları temizle
        df = df.dropna(subset=['Firma Websitesi'])
        df = df[df['Firma Websitesi'].str.strip() != '']
        
        # Sıralama
        df = df.sort_values(['Firma Adı', 'Firma Websitesi'])
        
        # Dosya adı
        timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
        filename = f"C_search_results_{reason}_{timestamp}.csv"
        
        # CSV kaydet
        save_csv(df.to_dict(orient="records"), out_dir / filename)
        print(f"💾 Kısmi veriler kaydedildi: {filename} ({len(df)} firma)")
        
    except Exception as e:
        print(f"⚠️ Kısmi veri kaydetme hatası: {str(e)}")


# ---- Arama (sayfalı) ----
def _get_search_results_with_pagination(driver: webdriver.Chrome, keyword: str, engine: str, per_keyword_limit: int) -> List[str]:
    all_links: List[str] = []
    pages_needed = max(1, (per_keyword_limit + 9) // 10)  # ~10 sonuç/sayfa

    if engine == "DuckDuckGo":
        base_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(keyword)}"
        result_selectors = ["a.result__a", "a[data-testid='result-title-a']", "a.result__url", "h2.result__title a"]
        next_page_selector = "a.result--more__btn, a[data-testid='pagination-next']"
        print(f"🦆 DuckDuckGo ile arama yapılıyor: {base_url}")
    else:
        print(f"⚠️ Desteklenmeyen arama motoru: {engine}")
        return []

    for page in range(min(pages_needed, 10)):
        if page == 0:
            url = base_url
        else:
            if engine == "DuckDuckGo":
                url = f"{base_url}&s={page * 10}"

        try:
            print(f"Sayfa {page + 1} taraniyor: {engine}")
            
            # Minimal bekleme - hızlandırıldı
            time.sleep(0.3)
            
            driver.get(url)

            # Hızlı bekleme - minimal süre
            time.sleep(0.5)

            links: List[str] = []
            if engine == "DuckDuckGo":
                # DuckDuckGo için özel parsing - yeni format desteği
                duckduckgo_selectors = [
                    "a.result__a",  # Ana sonuç linkleri
                    "a[data-testid='result-title-a']",  # Yeni format
                    "a.result__url",  # Alternatif format
                    "h2.result__title a",  # Başlık linkleri
                    ".result__title a",  # Başlık linkleri alternatif
                    ".result__url a",  # URL linkleri
                    ".result a[href]",  # Genel result linkleri
                ]
                
                for selector in duckduckgo_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for elem in elements:
                            href = elem.get_attribute("href")
                            if href:
                                # DuckDuckGo redirect linklerini çöz
                                if href.startswith("//duckduckgo.com/l/?uddg="):
                                    try:
                                        # URL decode işlemi
                                        decoded_url = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
                                        if decoded_url.startswith("http"):
                                            links.append(decoded_url)
                                    except Exception:
                                        continue
                                elif href.startswith("http") and "duckduckgo.com" not in href.lower():
                                    # Normal HTTP linkleri
                                    if not any(domain in href.lower() for domain in ["duckduckgo.com", "search.", "webcache", "translate.google"]):
                                        if href not in links:
                                            links.append(href)
                    except Exception:
                        continue
                
                # Eğer hiç link bulunamadıysa, HTML'den manuel parsing yap
                if not links:
                    try:
                        page_source = driver.page_source
                        # DuckDuckGo redirect linklerini regex ile bul
                        redirect_pattern = r'//duckduckgo\.com/l/\?uddg=([^&"\'>\s]+)'
                        redirect_matches = re.findall(redirect_pattern, page_source)
                        for match in redirect_matches:
                            try:
                                decoded_url = urllib.parse.unquote(match)
                                if decoded_url.startswith("http"):
                                    links.append(decoded_url)
                            except Exception:
                                continue
                        
                        # Normal href linklerini de ara
                        href_pattern = r'href=["\']([^"\']*http[^"\']*)["\']'
                        href_matches = re.findall(href_pattern, page_source)
                        for match in href_matches:
                            if "duckduckgo.com" not in match.lower() and match not in links:
                                links.append(match)
                    except Exception:
                        pass
                
                print(f"    📊 DuckDuckGo: {len(links)} sonuç bulundu")
                if links:
                    print(f"    🔗 İlk link örneği: {links[0][:100]}...")
            # Sadece DuckDuckGo destekleniyor

            for link in links:
                if not _is_filtered_domain(link):
                    all_links.append(link)
                    if len(all_links) >= per_keyword_limit:
                        return all_links

        except Exception as e:
            print(f"Sayfa {page + 1} hatasi ({engine}): {str(e)[:120]}")
            continue

    return all_links


# ---- Public API ----
def search_and_collect(
    keywords: List[str],
    engines: List[str],
    max_sites_total: int,
    per_keyword_limit: int,
    dwell_seconds: int,
    out_dir: Path,
    # CAPTCHA sistemi tamamen kaldırıldı
    use_stealth_mode: bool = False,
    headless_mode: bool = False,
    use_proxy: bool = False,
    proxy_list: Optional[List[str]] = None,
) -> pd.DataFrame:

    ensure_dir(out_dir)
    domain_data: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "Firma Adı": "",
        "Firma Websitesi": "",
        "Firma Adresi": "",
        "Firma Ülkesi/Dil": "",
        "Telefon Numaraları": set(),
        "Email Adresleri": set(),
        "Sosyal Medya": set(),
        "Sayfa Başlığı": "",
        "Özet Metin": "",
        "Firma Tipi": "",
        "Ziyaret Edilen Sayfalar": set(),
        "Toplam Veri Sayısı": 0,
    })

    visited_domains: Set[str] = set()

    print(f"Toplam {len(keywords)} anahtar kelime, {len(engines)} arama motoru")
    print(f"Maksimum {max_sites_total} site, her kelime için {per_keyword_limit} sonuç")
    print(f"Site başına {dwell_seconds} saniye bekleme")

    # Proxy manager başlat
    proxy_manager = None
    if use_proxy and proxy_list:
        try:
            from .proxy_manager import ProxyManager
            proxy_manager = ProxyManager()
            proxy_manager.add_proxy_list(proxy_list)
            print(f"🌐 Proxy kullanımı aktif: {len(proxy_list)} proxy")
        except Exception as e:
            print(f"⚠️ Proxy yüklenemedi: {str(e)}")
            use_proxy = False
    
    # Driver seçimi
    if use_stealth_mode:
        driver = _stealth_driver(headless=headless_mode)
        print(f"🥷 Stealth mode aktif (Headless: {headless_mode})")
    else:
        driver = _driver(headless=headless_mode)
        print(f"🔧 Normal mode aktif (Headless: {headless_mode})")
    
    request_count = 0
    total_keywords = len(keywords)
    total_engines = len(engines)
    total_expected_requests = total_keywords * total_engines
    
    print(f"📊 Toplam {total_keywords} anahtar kelime, {total_engines} arama motoru")
    print(f"🎯 Hedef: {max_sites_total} site, anahtar kelime başına {per_keyword_limit} sonuç")
    print(f"⏱️ Site başına {dwell_seconds} saniye bekleme")
    
    try:
        for kw_idx, kw in enumerate(keywords, 1):
            if len(visited_domains) >= max_sites_total:
                print(f"✅ Site limiti aşıldı: {len(visited_domains)}/{max_sites_total}")
                break
                
            for eng_idx, eng in enumerate(engines, 1):
                if len(visited_domains) >= max_sites_total:
                    print(f"✅ Site limiti aşıldı: {len(visited_domains)}/{max_sites_total}")
                    break
                if eng not in SEARCH_ENGINES:
                    continue

                request_count += 1
                
                # Progress tracking
                progress_percent = (request_count / total_expected_requests) * 100
                print(f"📈 İlerleme: {request_count}/{total_expected_requests} ({progress_percent:.1f}%)")
                print(f"🏠 Ziyaret edilen site sayısı: {len(visited_domains)}/{max_sites_total}")
                
                print(f"🔍 [{kw_idx}/{total_keywords}] DuckDuckGo ile aranıyor: {kw} - {eng} (İstek #{request_count}) [CAPTCHA'sız]")
                
                # İstek sayısına göre minimal bekleme - hızlandırıldı
                if request_count > 1:
                    time.sleep(0.5)  # Minimal bekleme - 0.5 saniye
                
                try:
                    links = _get_search_results_with_pagination(driver, kw, eng, per_keyword_limit)
                except Exception as e:
                    if "invalid session id" in str(e).lower() or "session deleted" in str(e).lower():
                        print(f"⚠️ Selenium session hatası, driver yeniden başlatılıyor...")
                        try:
                            driver.quit()
                        except:
                            pass
                        # Driver'ı yeniden oluştur
                        if use_stealth_mode:
                            driver = _stealth_driver(headless=headless_mode)
                        else:
                            driver = _driver(headless=headless_mode)
                            
                        # Session ayarlarını yeniden yap
                        driver.set_page_load_timeout(15)
                        driver.implicitly_wait(10)
                        driver.set_script_timeout(30)
                        
                        print(f"🔄 Driver yeniden başlatıldı")
                        # Yeniden deneme
                        try:
                            links = _get_search_results_with_pagination(driver, kw, eng, per_keyword_limit)
                        except Exception as retry_e:
                            print(f"❌ Yeniden deneme başarısız: {str(retry_e)}")
                            links = []
                    else:
                        print(f"❌ Arama hatası: {str(e)}")
                        links = []
                
                # Sonuç loglama
                print(f"✅ {eng} arama sonucu: {len(links)} link bulundu [CAPTCHA'sız]")

                if not links:
                    print("UYARI: Hiç link bulunamadı!")

                for lnk in links:
                    # Site limiti kontrolü - ziyaret edilen domain sayısına göre
                    if len(visited_domains) >= max_sites_total:
                        print(f"✅ Site limiti aşıldı: {len(visited_domains)}/{max_sites_total}")
                        break

                    base_domain = _get_base_domain(lnk)
                    clean_domain = _get_clean_domain(lnk)

                    if clean_domain in visited_domains:
                        print(f"Atlanıyor (zaten ziyaret edildi): {clean_domain}")
                        continue

                    try:
                        print(f"🌐 Site ziyaret ediliyor: {base_domain}")
                        
                        # DuckDuckGo için özel optimizasyonlar
                        if "duckduckgo" in lnk.lower():
                            print(f"    🦆 DuckDuckGo sonucu ziyaret ediliyor...")
                        
                        # Minimal bekleme - hızlandırıldı
                        time.sleep(0.3)
                        
                        driver.set_page_load_timeout(15)  # Orta timeout - 15 saniye
                        try:
                            driver.get(lnk)
                            
                            # DuckDuckGo için minimal bekleme - hızlandırıldı
                            if "duckduckgo" in lnk.lower():
                                print(f"    ⏳ DuckDuckGo sayfası yükleniyor...")
                                time.sleep(0.5)  # Minimal bekleme - 0.5 saniye
                            
                            # Tarayıcı durumu kontrolü
                            if not _is_browser_alive(driver):
                                print(f"⚠️ Tarayıcı kapatıldı, kısmi veriler kaydediliyor...")
                                _save_partial_data(domain_data, out_dir, "browser_closed")
                                return pd.DataFrame()
                                
                        except TimeoutException:
                            print(f"⏰ Timeout: {base_domain} - 15s sonra devam")
                        except WebDriverException as e:
                            error_msg = str(e).lower()
                            if "invalid session id" in error_msg or "session deleted" in error_msg:
                                print(f"⚠️ Session hatası: {base_domain}, driver yeniden başlatılıyor...")
                                try:
                                    driver.quit()
                                except:
                                    pass
                                # Driver'ı yeniden oluştur
                                if use_stealth_mode:
                                    driver = _stealth_driver(headless=headless_mode)
                                else:
                                    driver = _driver(headless=headless_mode)
                                    
                                # Session ayarlarını yeniden yap
                                driver.set_page_load_timeout(15)
                                driver.implicitly_wait(10)
                                driver.set_script_timeout(30)
                                
                                print(f"🔄 Driver yeniden başlatıldı, site tekrar deneniyor...")
                                try:
                                    driver.get(lnk)
                                    if not _is_browser_alive(driver):
                                        print(f"⚠️ Tarayıcı kapatıldı, kısmi veriler kaydediliyor...")
                                        _save_partial_data(domain_data, out_dir, "browser_closed")
                                        return pd.DataFrame()
                                except Exception as retry_e:
                                    print(f"❌ Yeniden deneme başarısız: {base_domain} - {str(retry_e)[:120]}")
                                    visited_domains.add(clean_domain)
                                    continue
                            else:
                                print(f"Sayfa yükleme hatası: {base_domain} - {str(e)[:120]}")
                                visited_domains.add(clean_domain)
                                continue

                        visited_domains.add(clean_domain)
                        
                        # Hızlı sayfa inceleme - minimal bekleme
                        time.sleep(0.5)  # Minimal bekleme - 0.5 saniye

                        html = driver.page_source
                        soup = BeautifulSoup(html, "lxml")
                        title = (soup.title.string if soup.title else "") or ""

                        # Veri çıkarma süreci - DuckDuckGo için optimize edildi
                        print(f"    📊 Veri çıkarılıyor: {base_domain}")
                        
                        # DuckDuckGo sonuçları için özel veri çıkarma
                        if "duckduckgo" in lnk.lower():
                            print(f"    🦆 DuckDuckGo sonucundan veri çıkarılıyor...")
                            # DuckDuckGo için daha agresif veri çıkarma
                            main_emails = _extract_emails_advanced(base_domain, soup, html)
                            main_phones = _extract_phones_advanced(html, soup)
                        else:
                            # Normal site ziyareti için standart veri çıkarma
                            main_emails = _extract_emails_advanced(base_domain, soup, html)
                            main_phones = _extract_phones_advanced(html, soup)

                        # Sosyal medya linklerini çıkar
                        socials = set()
                        social_domains = ["facebook.com", "instagram.com", "linkedin.com", "x.com", "twitter.com", "youtube.com", "t.me"]
                        for dom in social_domains:
                            for a in soup.find_all("a", href=True):
                                if dom in a["href"]:
                                    socials.add(a["href"])

                        # İletişim bilgilerini çıkar (DuckDuckGo için optimize edildi)
                        contact_info = _extract_contact_info(base_domain, soup, driver)

                        # Tüm verileri birleştir
                        all_emails = main_emails.union(contact_info.get('emails', set()))
                        all_phones = main_phones.union(contact_info.get('phones', set()))

                        page_text = soup.get_text().lower()
                        company_type = _classify_company_type(page_text, title.lower())
                        
                        # Veri çıkarma sonuçları
                        print(f"    📧 Email: {len(all_emails)}, 📞 Telefon: {len(all_phones)}, 🔗 Sosyal: {len(socials)}")
                        if all_emails:
                            print(f"    📧 Emails: {', '.join(list(all_emails)[:3])}{'...' if len(all_emails) > 3 else ''}")
                        if all_phones:
                            print(f"    📞 Telefonlar: {', '.join(list(all_phones)[:3])}{'...' if len(all_phones) > 3 else ''}")
                        if socials:
                            print(f"    🔗 Sosyal medya: {', '.join(list(socials)[:2])}{'...' if len(socials) > 2 else ''}")

                        if clean_domain not in domain_data:
                            domain_data[clean_domain] = {
                                "Firma Adı": title[:200] if title else clean_domain.split('.')[0].title(),
                                "Firma Websitesi": base_domain,
                                "Firma Adresi": contact_info.get("address", ""),
                                "Firma Ülkesi/Dil": f"{contact_info.get('country', '')} / {contact_info.get('language', '')}".strip(" /"),
                                "Telefon Numaraları": all_phones,
                                "Email Adresleri": all_emails,
                                "Sosyal Medya": socials,
                                "Sayfa Başlığı": title,
                                "Özet Metin": soup.get_text()[:500],
                                "Firma Tipi": company_type,
                                "Ziyaret Edilen Sayfalar": {lnk},
                                "Toplam Veri Sayısı": 1,
                            }
                            print(f"    ✅ Yeni firma verisi eklendi: {clean_domain}")
                        else:
                            domain_data[clean_domain]["Telefon Numaraları"].update(all_phones)
                            domain_data[clean_domain]["Email Adresleri"].update(all_emails)
                            domain_data[clean_domain]["Sosyal Medya"].update(socials)
                            domain_data[clean_domain]["Ziyaret Edilen Sayfalar"].add(lnk)
                            domain_data[clean_domain]["Toplam Veri Sayısı"] += 1

                            if not domain_data[clean_domain]["Firma Adresi"] and contact_info.get("address"):
                                domain_data[clean_domain]["Firma Adresi"] = contact_info["address"]

                            if not domain_data[clean_domain]["Firma Ülkesi/Dil"] and (contact_info.get("country") or contact_info.get("language")):
                                domain_data[clean_domain]["Firma Ülkesi/Dil"] = f"{contact_info.get('country', '')} / {contact_info.get('language', '')}".strip(" /")

                            if not domain_data[clean_domain]["Firma Tipi"] and company_type:
                                domain_data[clean_domain]["Firma Tipi"] = company_type
                            
                            print(f"    🔄 Mevcut firma verisi güncellendi: {clean_domain}")

                    except Exception as e:
                        print(f"Hata: {clean_domain} - {str(e)}")
                        visited_domains.add(clean_domain)
                        continue

                if len(visited_domains) >= max_sites_total:
                    print(f"✅ Site limiti aşıldı: {len(visited_domains)}/{max_sites_total}")
                    break
            if len(visited_domains) >= max_sites_total:
                print(f"✅ Site limiti aşıldı: {len(visited_domains)}/{max_sites_total}")
                break
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    print(f"\n🎉 ARAMA TAMAMLANDI!")
    print(f"🎉 DUCKDUCKGO ARAMA TAMAMLANDI!")
    print(f"📊 Toplam {len(visited_domains)} benzersiz domain ziyaret edildi")
    print(f"✅ {len(domain_data)} siteden veri toplandı")
    print(f"📈 {request_count} DuckDuckGo arama isteği gerçekleştirildi")
    print(f"🎯 Site limiti: {len(visited_domains)}/{max_sites_total}")
    
    if len(domain_data) == 0:
        print("⚠️ Hiçbir siteden veri toplanamadı!")
        print("💡 DuckDuckGo arama sonuçlarını kontrol edin ve site ziyaret ayarlarını gözden geçirin")
    else:
        print(f"💾 Veriler CSV dosyasına kaydediliyor...")
        print(f"🦆 DuckDuckGo ile başarılı veri toplama tamamlandı!")

    rows = []
    for domain, data in domain_data.items():
        rows.append({
            "Firma Adı": data["Firma Adı"],
            "Firma Websitesi": data["Firma Websitesi"],
            "Firma Adresi": data["Firma Adresi"],
            "Firma Ülkesi/Dil": data["Firma Ülkesi/Dil"],
            "Telefon Numaraları": "; ".join(sorted(data["Telefon Numaraları"])),
            "Email Adresleri": "; ".join(sorted(data["Email Adresleri"])),
            "Sosyal Medya": "; ".join(sorted(data["Sosyal Medya"])),
            "Firma Tipi": data["Firma Tipi"],
            "Sayfa Başlığı": data["Sayfa Başlığı"],
            "Özet Metin": data["Özet Metin"],
            "Ziyaret Edilen Sayfa Sayısı": data["Toplam Veri Sayısı"],
        })

    df = pd.DataFrame(rows)
    save_csv(df.to_dict(orient="records"), out_dir / "C_search_results.csv")
    return df
