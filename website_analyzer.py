# -*- coding: utf-8 -*-
"""
Website Analyzer Module
Firma web sitelerini ziyaret edip detaylı analiz yapan modül
"""

import sys
import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import urljoin, urlparse

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
import logging
from typing import Dict, List, Optional, Tuple
import json

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebsiteAnalyzer:
    """Firma web sitelerini analiz eden sınıf"""
    
    def __init__(self, timeout: int = 30, delay: float = 1.0):
        self.timeout = timeout
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def analyze_website(self, website_url: str, company_name: str = "") -> Dict:
        """
        Web sitesini analiz eder ve detaylı bilgi döndürür
        
        Args:
            website_url: Analiz edilecek web sitesi URL'i
            company_name: Firma adı (opsiyonel)
            
        Returns:
            Dict: Analiz sonuçları
        """
        try:
            # URL'i düzenle
            if not website_url.startswith(('http://', 'https://')):
                website_url = 'https://' + website_url
            
            logger.info(f"Analiz ediliyor: {website_url}")
            
            # Web sitesini ziyaret et
            response = self.session.get(website_url, timeout=self.timeout)
            response.raise_for_status()
            
            # HTML içeriğini parse et
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Temel bilgileri çıkar
            analysis = self._extract_basic_info(soup, website_url, company_name)
            
            # Detaylı analiz yap
            analysis.update(self._extract_detailed_info(soup, website_url))
            
            # Ürün/hizmet analizi
            analysis.update(self._extract_products_services(soup))
            
            # İletişim bilgileri
            analysis.update(self._extract_contact_info(soup))
            
            # Sosyal medya ve diğer linkler
            analysis.update(self._extract_links(soup, website_url))
            
            # Dil analizi
            analysis.update(self._analyze_language(soup))
            
            # Firma büyüklüğü tahmini
            analysis.update(self._estimate_company_size(soup, analysis))
            
            # Bekleme süresi
            time.sleep(self.delay)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Web sitesi analiz hatası {website_url}: {str(e)}")
            return {
                'error': str(e),
                'website_url': website_url,
                'company_name': company_name,
                'status': 'error'
            }
    
    def _extract_basic_info(self, soup: BeautifulSoup, url: str, company_name: str) -> Dict:
        """Temel web sitesi bilgilerini çıkarır"""
        info = {
            'website_url': url,
            'company_name': company_name,
            'title': '',
            'description': '',
            'keywords': '',
            'status': 'success'
        }
        
        # Title
        title_tag = soup.find('title')
        if title_tag:
            info['title'] = title_tag.get_text().strip()
        
        # Meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            info['description'] = meta_desc.get('content', '').strip()
        
        # Meta keywords
        meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
        if meta_keywords:
            info['keywords'] = meta_keywords.get('content', '').strip()
        
        return info
    
    def _extract_detailed_info(self, soup: BeautifulSoup, url: str) -> Dict:
        """Detaylı web sitesi bilgilerini çıkarır"""
        info = {}
        
        # Ana içerik metni
        main_content = soup.find('main') or soup.find('div', class_=re.compile(r'content|main|body'))
        if main_content:
            info['main_content'] = main_content.get_text()[:2000]  # İlk 2000 karakter
        
        # Tüm metin içeriği
        all_text = soup.get_text()
        info['all_text'] = all_text[:5000]  # İlk 5000 karakter
        
        # Başlıklar (h1, h2, h3)
        headings = []
        for tag in soup.find_all(['h1', 'h2', 'h3']):
            headings.append(tag.get_text().strip())
        info['headings'] = headings[:10]  # İlk 10 başlık
        
        # Paragraflar
        paragraphs = []
        for p in soup.find_all('p'):
            text = p.get_text().strip()
            if len(text) > 50:  # En az 50 karakterlik paragraflar
                paragraphs.append(text)
        info['paragraphs'] = paragraphs[:5]  # İlk 5 paragraf
        
        return info
    
    def _extract_products_services(self, soup: BeautifulSoup) -> Dict:
        """Ürün ve hizmet bilgilerini çıkarır"""
        products_info = {
            'products': [],
            'services': [],
            'product_categories': [],
            'business_type': ''
        }
        
        # Ürün/hizmet ile ilgili kelimeler
        product_keywords = [
            'product', 'products', 'service', 'services', 'catalog', 'catalogue',
            'shop', 'store', 'buy', 'sell', 'manufacturer', 'supplier',
            'wholesale', 'retail', 'distributor', 'dealer'
        ]
        
        # Ürün kategorileri
        category_keywords = [
            'category', 'categories', 'type', 'types', 'class', 'classes',
            'group', 'groups', 'section', 'sections'
        ]
        
        # Metin içeriğinde ürün/hizmet arama
        all_text = soup.get_text().lower()
        
        # Ürün linklerini bul
        product_links = []
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').lower()
            text = link.get_text().lower()
            if any(keyword in href or keyword in text for keyword in product_keywords):
                product_links.append({
                    'text': link.get_text().strip(),
                    'href': link.get('href')
                })
        
        products_info['product_links'] = product_links[:10]
        
        # Ürün kategorilerini bul
        for element in soup.find_all(['div', 'section', 'nav'], class_=re.compile(r'category|product|menu')):
            text = element.get_text().strip()
            if text and len(text) < 200:  # Kısa metinler
                products_info['product_categories'].append(text)
        
        # İş türü tahmini
        if any(word in all_text for word in ['manufacturer', 'factory', 'production']):
            products_info['business_type'] = 'manufacturer'
        elif any(word in all_text for word in ['wholesale', 'distributor', 'supplier']):
            products_info['business_type'] = 'wholesaler'
        elif any(word in all_text for word in ['retail', 'shop', 'store']):
            products_info['business_type'] = 'retailer'
        elif any(word in all_text for word in ['service', 'consulting', 'support']):
            products_info['business_type'] = 'service_provider'
        else:
            products_info['business_type'] = 'unknown'
        
        return products_info
    
    def _extract_contact_info(self, soup: BeautifulSoup) -> Dict:
        """İletişim bilgilerini çıkarır - gelişmiş filtreleme ile"""
        contact_info = {
            'emails': [],
            'phones': [],
            'addresses': [],
            'contact_forms': []
        }
        
        # Geçerli email domain'leri
        valid_email_domains = {
            'gmail.com', 'hotmail.com', 'outlook.com', 'yahoo.com', 'aol.com', 'icloud.com',
            'protonmail.com', 'yandex.com', 'mail.ru', 'zoho.com', 'fastmail.com'
        }
        
        # Geçerli ülke kodları - Tüm kıtalar (Avrupa, Afrika, Asya, Amerika, Okyanusya, Orta Doğu)
        valid_country_codes = {
            # Kuzey Amerika
            '+1',  # ABD/Kanada
            '+1-242', '+1-246', '+1-264', '+1-268', '+1-284', '+1-340', '+1-345', '+1-441', '+1-473', '+1-649', '+1-664', '+1-670', '+1-671', '+1-684', '+1-721', '+1-758', '+1-767', '+1-784', '+1-787', '+1-809', '+1-829', '+1-849', '+1-868', '+1-869', '+1-876',  # Karayip ve diğer
            '+52',  # Meksika
            
            # Güney Amerika
            '+54',  # Arjantin
            '+55',  # Brezilya
            '+56',  # Şili
            '+57',  # Kolombiya
            '+58',  # Venezuela
            '+51',  # Peru
            '+591',  # Bolivya
            '+593',  # Ekvador
            '+595',  # Paraguay
            '+598',  # Uruguay
            '+597',  # Surinam
            '+592',  # Guyana
            '+594',  # Fransız Guyanası
            
            # Avrupa
            '+30',  # Yunanistan
            '+31',  # Hollanda
            '+32',  # Belçika
            '+33',  # Fransa
            '+34',  # İspanya
            '+351',  # Portekiz
            '+352',  # Lüksemburg
            '+353',  # İrlanda
            '+354',  # İzlanda
            '+355',  # Arnavutluk
            '+356',  # Malta
            '+357',  # Kıbrıs
            '+358',  # Finlandiya
            '+359',  # Bulgaristan
            '+36',  # Macaristan
            '+370',  # Litvanya
            '+371',  # Letonya
            '+372',  # Estonya
            '+373',  # Moldova
            '+374',  # Ermenistan
            '+375',  # Belarus
            '+376',  # Andorra
            '+377',  # Monako
            '+378',  # San Marino
            '+380',  # Ukrayna
            '+381',  # Sırbistan
            '+382',  # Karadağ
            '+383',  # Kosova
            '+385',  # Hırvatistan
            '+386',  # Slovenya
            '+387',  # Bosna-Hersek
            '+389',  # Makedonya
            '+39',  # İtalya
            '+40',  # Romanya
            '+41',  # İsviçre
            '+420',  # Çek Cumhuriyeti
            '+421',  # Slovakya
            '+423',  # Liechtenstein
            '+43',  # Avusturya
            '+44',  # İngiltere
            '+45',  # Danimarka
            '+46',  # İsveç
            '+47',  # Norveç
            '+48',  # Polonya
            '+49',  # Almanya
            
            # Afrika
            '+20',  # Mısır
            '+212',  # Fas
            '+213',  # Cezayir
            '+216',  # Tunus
            '+218',  # Libya
            '+220',  # Gambiya
            '+221',  # Senegal
            '+222',  # Moritanya
            '+223',  # Mali
            '+224',  # Gine
            '+225',  # Fildişi Sahili
            '+226',  # Burkina Faso
            '+227',  # Nijer
            '+228',  # Togo
            '+229',  # Benin
            '+230',  # Mauritius
            '+231',  # Liberya
            '+232',  # Sierra Leone
            '+233',  # Gana
            '+234',  # Nijerya
            '+235',  # Çad
            '+236',  # Orta Afrika Cumhuriyeti
            '+237',  # Kamerun
            '+238',  # Yeşil Burun Adaları
            '+239',  # São Tomé ve Príncipe
            '+240',  # Ekvator Ginesi
            '+241',  # Gabon
            '+242',  # Kongo Cumhuriyeti
            '+243',  # Demokratik Kongo Cumhuriyeti
            '+244',  # Angola
            '+245',  # Gine-Bissau
            '+246',  # Britanya Hint Okyanusu Toprakları
            '+248',  # Seyşeller
            '+249',  # Sudan
            '+250',  # Ruanda
            '+251',  # Etiyopya
            '+252',  # Somali
            '+253',  # Cibuti
            '+254',  # Kenya
            '+255',  # Tanzanya
            '+256',  # Uganda
            '+257',  # Burundi
            '+258',  # Mozambik
            '+260',  # Zambiya
            '+261',  # Madagaskar
            '+262',  # Réunion
            '+263',  # Zimbabve
            '+264',  # Namibya
            '+265',  # Malavi
            '+266',  # Lesotho
            '+267',  # Botsvana
            '+268',  # Esvatini
            '+269',  # Komorlar
            '+27',  # Güney Afrika
            '+290',  # Saint Helena
            '+291',  # Eritre
            '+297',  # Aruba
            '+298',  # Faroe Adaları
            '+299',  # Grönland
            
            # Asya
            '+60',  # Malezya
            '+61',  # Avustralya
            '+62',  # Endonezya
            '+63',  # Filipinler
            '+64',  # Yeni Zelanda
            '+65',  # Singapur
            '+66',  # Tayland
            '+81',  # Japonya
            '+82',  # Güney Kore
            '+84',  # Vietnam
            '+86',  # Çin
            '+91',  # Hindistan
            '+92',  # Pakistan
            '+93',  # Afganistan
            '+94',  # Sri Lanka
            '+95',  # Myanmar
            '+98',  # İran
            '+850',  # Kuzey Kore
            '+852',  # Hong Kong
            '+853',  # Makao
            '+855',  # Kamboçya
            '+856',  # Laos
            '+880',  # Bangladeş
            '+886',  # Tayvan
            '+960',  # Maldivler
            '+961',  # Lübnan
            '+962',  # Ürdün
            '+963',  # Suriye
            '+964',  # Irak
            '+965',  # Kuveyt
            '+966',  # Suudi Arabistan
            '+967',  # Yemen
            '+968',  # Umman
            '+970',  # Filistin
            '+971',  # BAE
            '+972',  # İsrail
            '+973',  # Bahreyn
            '+974',  # Katar
            '+975',  # Bhutan
            '+976',  # Moğolistan
            '+977',  # Nepal
            '+992',  # Tacikistan
            '+993',  # Türkmenistan
            '+994',  # Azerbaycan
            '+995',  # Gürcistan
            '+996',  # Kırgızistan
            '+998',  # Özbekistan
            
            # Okyanusya
            '+672',  # Norfolk Adası
            '+673',  # Brunei
            '+674',  # Nauru
            '+675',  # Papua Yeni Gine
            '+676',  # Tonga
            '+677',  # Solomon Adaları
            '+678',  # Vanuatu
            '+679',  # Fiji
            '+680',  # Palau
            '+681',  # Wallis ve Futuna
            '+682',  # Cook Adaları
            '+683',  # Niue
            '+684',  # Amerikan Samoası
            '+685',  # Samoa
            '+686',  # Kiribati
            '+687',  # Yeni Kaledonya
            '+688',  # Tuvalu
            '+689',  # Fransız Polinezyası
            '+690',  # Tokelau
            '+691',  # Mikronezya
            '+692',  # Marshall Adaları
            
            # Orta Doğu ve Kafkasya
            '+7',  # Rusya/Kazakistan
            '+374',  # Ermenistan
            '+994',  # Azerbaycan
            '+995',  # Gürcistan
            '+996',  # Kırgızistan
            '+998',  # Özbekistan
            '+992',  # Tacikistan
            '+993',  # Türkmenistan
            
            # Diğer özel kodlar
            '+500',  # Falkland Adaları
            '+501',  # Belize
            '+502',  # Guatemala
            '+503',  # El Salvador
            '+504',  # Honduras
            '+505',  # Nikaragua
            '+506',  # Kosta Rika
            '+507',  # Panama
            '+508',  # Saint Pierre ve Miquelon
            '+509',  # Haiti
            '+590',  # Guadeloupe
            '+591',  # Bolivya
            '+592',  # Guyana
            '+593',  # Ekvador
            '+594',  # Fransız Guyanası
            '+595',  # Paraguay
            '+596',  # Martinik
            '+597',  # Surinam
            '+598',  # Uruguay
            '+599',  # Hollanda Antilleri
        }
        
        # İletişim alanlarını belirle (footer, contact sayfaları)
        contact_areas = []
        
        # Footer alanları
        footer_selectors = ['footer', '.footer', '#footer', '.site-footer', '#site-footer']
        for selector in footer_selectors:
            elements = soup.select(selector)
            for element in elements:
                contact_areas.append(element.get_text())
        
        # Ana sayfa içeriğini de ekle
        contact_areas.append(soup.get_text())
        
        # Email adresleri - sadece geçerli domain'ler
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.ico', '.bmp', '.tiff', '.avif', '.jfif', '.pjpeg', '.pjp'}
        
        for area_text in contact_areas:
            emails = re.findall(email_pattern, area_text)
            for email in emails:
                email = email.lower().strip()
                domain = email.split('@')[1] if '@' in email else ''
                
                # Resim dosyası kontrolü
                if any(ext in email for ext in image_extensions):
                    continue
                
                # Geçerli domain kontrolü
                if domain in valid_email_domains:
                    contact_info['emails'].append(email)
        
        # Telefon numaraları - sadece geçerli ülke kodları
        phone_patterns = [
            r'\+\d{1,4}[\s\-\.]?\d{1,4}[\s\-\.]?\d{1,4}[\s\-\.]?\d{1,4}[\s\-\.]?\d{1,4}',
            r'\+\d{1,4}[\s\-\.]?\(\d{1,4}\)[\s\-\.]?\d{1,4}[\s\-\.]?\d{1,4}[\s\-\.]?\d{1,4}',
        ]
        
        for area_text in contact_areas:
            for pattern in phone_patterns:
                phones = re.findall(pattern, area_text)
                for phone in phones:
                    clean_phone = re.sub(r'[^\d+]', '', phone)
                    if len(clean_phone) >= 8:
                        # Ülke kodu kontrolü
                        for i in range(1, 5):
                            country_code = clean_phone[:i]
                            if '+' + country_code in valid_country_codes:
                                contact_info['phones'].append(phone.strip())
                                break
        
        # Benzersiz ve sınırlı sayıda döndür
        contact_info['emails'] = list(set(contact_info['emails']))[:3]
        contact_info['phones'] = list(set(contact_info['phones']))[:2]
        
        # Adres bilgileri
        address_keywords = ['address', 'location', 'office', 'headquarters']
        for element in soup.find_all(['div', 'p', 'span']):
            text = element.get_text().strip()
            if any(keyword in text.lower() for keyword in address_keywords):
                if len(text) > 20 and len(text) < 200:  # Uygun uzunlukta
                    contact_info['addresses'].append(text)
        
        # İletişim formları
        for form in soup.find_all('form'):
            form_text = form.get_text().strip()
            if any(keyword in form_text.lower() for keyword in ['contact', 'message', 'inquiry']):
                contact_info['contact_forms'].append(form_text[:200])
        
        return contact_info
    
    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> Dict:
        """Sosyal medya ve diğer linkleri çıkarır"""
        links_info = {
            'social_media': [],
            'external_links': [],
            'internal_links': []
        }
        
        # Sosyal medya linkleri
        social_platforms = ['facebook', 'twitter', 'linkedin', 'instagram', 'youtube', 'tiktok']
        
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').lower()
            text = link.get_text().strip().lower()
            
            # Sosyal medya
            for platform in social_platforms:
                if platform in href or platform in text:
                    links_info['social_media'].append({
                        'platform': platform,
                        'url': link.get('href'),
                        'text': link.get_text().strip()
                    })
                    break
            
            # Dış linkler
            if href.startswith('http') and not href.startswith(urlparse(base_url).netloc):
                links_info['external_links'].append({
                    'url': link.get('href'),
                    'text': link.get_text().strip()
                })
        
        return links_info
    
    def _analyze_language(self, soup: BeautifulSoup) -> Dict:
        """Web sitesi dilini analiz eder"""
        language_info = {
            'detected_language': 'unknown',
            'language_indicators': []
        }
        
        # Dil tespiti için yaygın kelimeler
        language_indicators = {
            'english': ['the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'],
            'spanish': ['el', 'la', 'de', 'que', 'y', 'a', 'en', 'un', 'es', 'se', 'no', 'te', 'lo', 'le'],
            'french': ['le', 'la', 'de', 'et', 'à', 'un', 'il', 'être', 'et', 'en', 'avoir', 'que', 'pour'],
            'german': ['der', 'die', 'das', 'und', 'in', 'den', 'von', 'zu', 'dem', 'mit', 'sich', 'des'],
            'portuguese': ['o', 'a', 'de', 'e', 'do', 'da', 'em', 'um', 'para', 'com', 'não', 'uma', 'os'],
            'turkish': ['ve', 'bir', 'bu', 'için', 'olan', 'ile', 'da', 'de', 'gibi', 'kadar', 'daha', 'çok'],
            'italian': ['il', 'la', 'di', 'e', 'a', 'da', 'in', 'con', 'per', 'su', 'dal', 'della', 'del']
        }
        
        # Metin içeriğini analiz et
        all_text = soup.get_text().lower()
        
        # Her dil için skor hesapla
        language_scores = {}
        for lang, indicators in language_indicators.items():
            score = sum(1 for indicator in indicators if indicator in all_text)
            language_scores[lang] = score
        
        # En yüksek skorlu dili seç
        if language_scores:
            detected_lang = max(language_scores, key=language_scores.get)
            if language_scores[detected_lang] > 0:
                language_info['detected_language'] = detected_lang
                language_info['language_indicators'] = language_indicators[detected_lang]
        
        return language_info
    
    def _estimate_company_size(self, soup: BeautifulSoup, analysis: Dict) -> Dict:
        """Firma büyüklüğünü tahmin eder"""
        size_info = {
            'estimated_size': 'unknown',
            'size_indicators': []
        }
        
        all_text = soup.get_text().lower()
        
        # Büyük firma göstergeleri
        large_company_indicators = [
            'global', 'international', 'worldwide', 'multinational', 'corporation',
            'headquarters', 'branches', 'offices', 'subsidiaries', 'group'
        ]
        
        # KOBİ göstergeleri
        sme_indicators = [
            'family', 'local', 'regional', 'small', 'medium', 'independent',
            'specialized', 'niche', 'boutique', 'artisan'
        ]
        
        # Skor hesapla
        large_score = sum(1 for indicator in large_company_indicators if indicator in all_text)
        sme_score = sum(1 for indicator in sme_indicators if indicator in all_text)
        
        if large_score > sme_score and large_score > 2:
            size_info['estimated_size'] = 'large'
            size_info['size_indicators'] = [ind for ind in large_company_indicators if ind in all_text]
        elif sme_score > 0:
            size_info['estimated_size'] = 'sme'
            size_info['size_indicators'] = [ind for ind in sme_indicators if ind in all_text]
        
        return size_info

def analyze_company_website(website_url: str, company_name: str = "") -> Dict:
    """
    Firma web sitesini analiz eder
    
    Args:
        website_url: Web sitesi URL'i
        company_name: Firma adı
        
    Returns:
        Dict: Analiz sonuçları
    """
    analyzer = WebsiteAnalyzer()
    return analyzer.analyze_website(website_url, company_name)

def batch_analyze_websites(companies_data: List[Dict], max_companies: int = 20) -> List[Dict]:
    """
    Birden fazla firma web sitesini toplu analiz eder
    
    Args:
        companies_data: Firma verileri listesi
        max_companies: Maksimum analiz edilecek firma sayısı
        
    Returns:
        List[Dict]: Analiz sonuçları listesi
    """
    analyzer = WebsiteAnalyzer()
    results = []
    
    for i, company in enumerate(companies_data[:max_companies]):
        website_url = company.get('Firma Websitesi', '')
        company_name = company.get('Firma Adı', '')
        
        if website_url:
            result = analyzer.analyze_website(website_url, company_name)
            results.append(result)
        else:
            results.append({
                'error': 'No website URL',
                'company_name': company_name,
                'status': 'error'
            })
    
    return results


