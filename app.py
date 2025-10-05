
# -*- coding: utf-8 -*-
import os
import sys
import json
import time
import pandas as pd
from pathlib import Path
from urllib.parse import urlparse
import streamlit as st
from dotenv import load_dotenv

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

from modules.utils import ensure_dir, save_csv, read_json, write_json, CAMPAIGNS_DIR
from modules.llm import complete, translate
from modules.campaigns import create_campaign, load_campaigns, load_campaign
from modules.keywords import generate_keywords
from modules.scrape_search import search_and_collect
# Alternatif arama motorları kaldırıldı
from modules.proxy_manager import ProxyManager, get_free_proxy_list, get_premium_proxy_list, get_proxy_recommendations
from modules.scrape_maps import maps_scrape
from modules.enrichment import enrich_dataframe
from modules.emailer import send_email_smtp
from modules.imap_reader import fetch_important
from modules.forms import batch_fill_from_df
from modules.lang_helper import country_to_lang, detect_site_lang
from modules.website_analyzer import batch_analyze_websites, analyze_company_website

load_dotenv()
st.set_page_config(page_title="Export LeadGen Pro", layout="wide")

# Helper functions for F step
def analyze_c_data_for_email(c_data_df):
    """
    C adımından gelen verileri email üretimi için analiz eder
    """
    analysis = {}
    
    for _, row in c_data_df.iterrows():
        firma = str(row.get("Firma Adı", "") or "").strip()
        if not firma:
            continue
            
        # C adımı verilerinden analiz çıkar
        company_analysis = {
            'firma_adi': firma,
            'website': str(row.get("Firma Websitesi", "") or ""),
            'ulke': str(row.get("Firma Ülkesi/Dil", "") or ""),
            'firma_tipi': str(row.get("Firma Tipi", "") or ""),
            'ozet_metin': str(row.get("Özet Metin", "") or "")[:1000],
            'email_adresleri': str(row.get("Email Adresleri", "") or ""),
            'telefon': str(row.get("Telefon", "") or ""),
            'adres': str(row.get("Adres", "") or ""),
            'urun_kategorileri': [],
            'is_turu': '',
            'firma_buyuklugu': '',
            'dil': '',
            'ana_icerik': str(row.get("Özet Metin", "") or "")[:500]
        }
        
        # Firma tipinden iş türü çıkar
        firma_tipi = str(row.get("Firma Tipi", "") or "").lower()
        if 'üretici' in firma_tipi or 'manufacturer' in firma_tipi:
            company_analysis['is_turu'] = 'manufacturer'
        elif 'toptancı' in firma_tipi or 'wholesale' in firma_tipi:
            company_analysis['is_turu'] = 'wholesaler'
        elif 'mağaza' in firma_tipi or 'retail' in firma_tipi:
            company_analysis['is_turu'] = 'retailer'
        elif 'distribütör' in firma_tipi or 'distributor' in firma_tipi:
            company_analysis['is_turu'] = 'distributor'
        else:
            company_analysis['is_turu'] = 'unknown'
        
        # Özet metinden ürün kategorileri çıkar
        ozet = str(row.get("Özet Metin", "") or "").lower()
        product_keywords = ['shotgun', 'rifle', 'pistol', 'ammunition', 'accessory', 'hunting', 'sporting', 'firearm']
        for keyword in product_keywords:
            if keyword in ozet:
                company_analysis['urun_kategorileri'].append(keyword)
        
        # Dil tespiti
        if 'türkçe' in ozet or 'turkish' in ozet:
            company_analysis['dil'] = 'turkish'
        elif 'english' in ozet or 'ingilizce' in ozet:
            company_analysis['dil'] = 'english'
        elif 'spanish' in ozet or 'ispanyolca' in ozet:
            company_analysis['dil'] = 'spanish'
        elif 'french' in ozet or 'fransızca' in ozet:
            company_analysis['dil'] = 'french'
        elif 'german' in ozet or 'almanca' in ozet:
            company_analysis['dil'] = 'german'
        else:
            company_analysis['dil'] = 'unknown'
        
        # Firma büyüklüğü tahmini
        if 'global' in ozet or 'international' in ozet or 'worldwide' in ozet:
            company_analysis['firma_buyuklugu'] = 'large'
        elif 'local' in ozet or 'regional' in ozet or 'small' in ozet:
            company_analysis['firma_buyuklugu'] = 'sme'
        else:
            company_analysis['firma_buyuklugu'] = 'unknown'
        
        analysis[firma] = company_analysis
    
    return analysis

def create_advanced_html_prompt(firma, ulke, ozet, c_analysis, website_analysis, html_template, active, analysis_depth, use_personalized_subjects):
    """Gelişmiş HTML email prompt'u oluşturur - 20+ yıllık ihracat deneyimi ile"""
    
    # C adımı analizi bilgilerini hazırla
    c_analysis_info = ""
    if c_analysis:
        c_analysis_info = f"""
C ADIMI VERİ ANALİZİ:
- Firma Adı: {c_analysis.get('firma_adi', 'Bilinmiyor')}
- Website: {c_analysis.get('website', 'Bilinmiyor')}
- Ülke: {c_analysis.get('ulke', 'Bilinmiyor')}
- Firma Tipi: {c_analysis.get('firma_tipi', 'Bilinmiyor')}
- İş Türü: {c_analysis.get('is_turu', 'Bilinmiyor')}
- Firma Büyüklüğü: {c_analysis.get('firma_buyuklugu', 'Bilinmiyor')}
- Tespit Edilen Dil: {c_analysis.get('dil', 'Bilinmiyor')}
- Ürün Kategorileri: {', '.join(c_analysis.get('urun_kategorileri', [])[:5])}
- Ana İçerik: {c_analysis.get('ana_icerik', 'Bilinmiyor')[:500]}
- İletişim: {c_analysis.get('email_adresleri', 'Bilinmiyor')}
"""
    
    # Web sitesi analizi bilgilerini hazırla (opsiyonel)
    website_analysis_info = ""
    if website_analysis and website_analysis.get('status') != 'error':
        website_analysis_info = f"""
DETAYLI WEB SİTESİ ANALİZİ:
- Site Başlığı: {website_analysis.get('title', 'Bilinmiyor')}
- Meta Açıklama: {website_analysis.get('description', 'Bilinmiyor')}
- Tespit Edilen Dil: {website_analysis.get('detected_language', 'Bilinmiyor')}
- İş Türü: {website_analysis.get('business_type', 'Bilinmiyor')}
- Firma Büyüklüğü: {website_analysis.get('estimated_size', 'Bilinmiyor')}
- Ana İçerik: {website_analysis.get('main_content', 'Bilinmiyor')[:500]}
- Ürün Kategorileri: {', '.join(website_analysis.get('product_categories', [])[:5])}
- İletişim Bilgileri: {', '.join(website_analysis.get('emails', [])[:3])}
"""
    
    return f"""
Sen dünyanın en deneyimli B2B ihracat pazarlama uzmanısın. 20+ yıllık deneyiminle, 50+ ülkede binlerce firma ile çalışmış, ihracat pazarlama konusunda uzmanlaşmış bir profesyonelsin. Her firmanın kendine özgü ihtiyaçlarını, kültürel farklılıklarını ve pazar dinamiklerini derinlemesine anlayarak, onlara en uygun çözümleri sunuyorsun.

UZMANLIK ALANLARIN:
- Uluslararası B2B pazarlama stratejileri
- Kültürel adaptasyon ve yerelleştirme
- Firma analizi ve ihtiyaç tespiti
- Değer önerisi geliştirme
- İhracat süreçleri ve lojistik
- Uluslararası ticaret hukuku
- Pazar araştırması ve rekabet analizi

HEDEF FİRMA BİLGİLERİ:
- Firma Adı: {firma}
- Ülke/Dil: {ulke or active.target_country}
- Mevcut Özet: {ozet}
- Hedef Ürünlerimiz: {', '.join(active.products) if active.products else 'Genel ürün portföyü'}
- Bizim Firma: {active.firm_name}
- Bizim Website: {active.firm_site}

{c_analysis_info}

{website_analysis_info}

GÖREV:
1. Yukarıdaki analiz bilgilerini kullanarak firmayı derinlemesine anla
2. Onların iş modelini, ürün portföyünü, pazar konumunu ve ihtiyaçlarını tespit et
3. Bizim ürünlerimizin onlara nasıl değer katacağını, hangi faydaları sağlayacağını belirle
4. Firma kültürüne, pazar dinamiklerine ve iş modeline uygun ton ve yaklaşım belirle
5. Aşağıdaki HTML şablonunu kullanarak, firmaya özel, son derece kişiselleştirilmiş bir email oluştur

HTML ŞABLONU:
---
{html_template}
---

KURALLAR:
- HTML kodlarını ve yapısını aynen koru
- Sadece metin içeriklerini firmaya özel olarak değiştir
- Firma adı, ürünler, ülke bilgilerini uygun yerlere yerleştir
- HTML etiketlerini bozma, sadece içerikleri kişiselleştir
- Profesyonel ama samimi, güven veren bir ton kullan
- Firmaya özel faydalar ve değer önerileri sun
- Call-to-action'ları güçlü, net ve eyleme geçirici yap
- Kültürel hassasiyetleri göz önünde bulundur
- Firma büyüklüğüne ve sektöre uygun yaklaşım sergile

ÇIKTI FORMATI:
KONU: [Firmaya özel, çekici ve kişiselleştirilmiş konu başlığı]
HTML_İÇERİK: [Kişiselleştirilmiş HTML kodu]

HTML içeriği tam ve geçerli HTML olmalı. Sadece metin kısımları firmaya özel olsun.
"""

def process_custom_prompt(custom_prompt, firma, ulke, ozet, template, website_url, email_addresses, active):
    """
    Özel prompt'u işler ve değişkenleri değiştirir
    """
    # Değişkenleri değiştir
    processed_prompt = custom_prompt.replace("{FIRMA_ADI}", firma)
    processed_prompt = processed_prompt.replace("{ULKE}", ulke or active.target_country)
    processed_prompt = processed_prompt.replace("{OZET}", ozet[:500])
    processed_prompt = processed_prompt.replace("{TEMPLATE}", template)
    processed_prompt = processed_prompt.replace("{WEBSITE}", website_url)
    processed_prompt = processed_prompt.replace("{EMAIL_ADRESLERI}", email_addresses)
    processed_prompt = processed_prompt.replace("{BIZIM_FIRMA}", active.firm_name)
    processed_prompt = processed_prompt.replace("{BIZIM_WEBSITE}", active.firm_site)
    processed_prompt = processed_prompt.replace("{URUNLER}", ', '.join(active.products) if active.products else 'Genel ürün portföyü')
    
    return processed_prompt

def create_advanced_text_prompt(firma, ulke, ozet, c_analysis, website_analysis, template, active, analysis_depth, use_personalized_subjects):
    """Gelişmiş text email prompt'u oluşturur - 20+ yıllık ihracat deneyimi ile"""
    
    # C adımı analizi bilgilerini hazırla
    c_analysis_info = ""
    if c_analysis:
        c_analysis_info = f"""
C ADIMI VERİ ANALİZİ:
- Firma Adı: {c_analysis.get('firma_adi', 'Bilinmiyor')}
- Website: {c_analysis.get('website', 'Bilinmiyor')}
- Ülke: {c_analysis.get('ulke', 'Bilinmiyor')}
- Firma Tipi: {c_analysis.get('firma_tipi', 'Bilinmiyor')}
- İş Türü: {c_analysis.get('is_turu', 'Bilinmiyor')}
- Firma Büyüklüğü: {c_analysis.get('firma_buyuklugu', 'Bilinmiyor')}
- Tespit Edilen Dil: {c_analysis.get('dil', 'Bilinmiyor')}
- Ürün Kategorileri: {', '.join(c_analysis.get('urun_kategorileri', [])[:5])}
- Ana İçerik: {c_analysis.get('ana_icerik', 'Bilinmiyor')[:500]}
- İletişim: {c_analysis.get('email_adresleri', 'Bilinmiyor')}
"""
    
    # Web sitesi analizi bilgilerini hazırla (opsiyonel)
    website_analysis_info = ""
    if website_analysis and website_analysis.get('status') != 'error':
        website_analysis_info = f"""
DETAYLI WEB SİTESİ ANALİZİ:
- Site Başlığı: {website_analysis.get('title', 'Bilinmiyor')}
- Meta Açıklama: {website_analysis.get('description', 'Bilinmiyor')}
- Tespit Edilen Dil: {website_analysis.get('detected_language', 'Bilinmiyor')}
- İş Türü: {website_analysis.get('business_type', 'Bilinmiyor')}
- Firma Büyüklüğü: {website_analysis.get('estimated_size', 'Bilinmiyor')}
- Ana İçerik: {website_analysis.get('main_content', 'Bilinmiyor')[:500]}
- Ürün Kategorileri: {', '.join(website_analysis.get('product_categories', [])[:5])}
- İletişim Bilgileri: {', '.join(website_analysis.get('emails', [])[:3])}
"""
    
    return f"""
Sen dünyanın en deneyimli B2B ihracat pazarlama uzmanısın. 20+ yıllık deneyiminle, 50+ ülkede binlerce firma ile çalışmış, ihracat pazarlama konusunda uzmanlaşmış bir profesyonelsin. Her firmanın kendine özgü ihtiyaçlarını, kültürel farklılıklarını ve pazar dinamiklerini derinlemesine anlayarak, onlara en uygun çözümleri sunuyorsun.

UZMANLIK ALANLARIN:
- Uluslararası B2B pazarlama stratejileri
- Kültürel adaptasyon ve yerelleştirme
- Firma analizi ve ihtiyaç tespiti
- Değer önerisi geliştirme
- İhracat süreçleri ve lojistik
- Uluslararası ticaret hukuku
- Pazar araştırması ve rekabet analizi

HEDEF FİRMA BİLGİLERİ:
- Firma Adı: {firma}
- Ülke/Dil: {ulke or active.target_country}
- Mevcut Özet: {ozet}
- Hedef Ürünlerimiz: {', '.join(active.products) if active.products else 'Genel ürün portföyü'}
- Bizim Firma: {active.firm_name}
- Bizim Website: {active.firm_site}

{c_analysis_info}

{website_analysis_info}

GÖREV:
1. Yukarıdaki analiz bilgilerini kullanarak firmayı derinlemesine anla
2. Onların iş modelini, ürün portföyünü, pazar konumunu ve ihtiyaçlarını tespit et
3. Bizim ürünlerimizin onlara nasıl değer katacağını, hangi faydaları sağlayacağını belirle
4. Firma kültürüne, pazar dinamiklerine ve iş modeline uygun ton ve yaklaşım belirle
5. Aşağıdaki şablonu kullanarak, firmaya özel, son derece kişiselleştirilmiş bir email oluştur

ŞABLON:
---
{template}
---

KURALLAR:
- Şablonu firmaya özel bilgilerle akıllıca birleştir
- Firma adı, konumu, ürünleri gibi bilgileri uygun yerlere yerleştir
- Profesyonel ama samimi, güven veren bir ton kullan
- Firmaya özel faydalar ve değer önerileri sun
- Call-to-action'ları güçlü, net ve eyleme geçirici yap
- Kültürel hassasiyetleri göz önünde bulundur
- Firma büyüklüğüne ve sektöre uygun yaklaşım sergile
- 200-300 kelime, ana dil seviyesinde yaz

ÇIKTI FORMATI:
KONU: [Firmaya özel, çekici ve kişiselleştirilmiş konu başlığı]
İÇERİK: [E-posta içeriği]

E-POSTAYI SADECE hedef dilde yaz. Konu başlığı da firmaya özel ve çekici olsun.
"""

def parse_email_response(response, template_source, subject_input, use_personalized_subjects):
    """Email response'unu parse eder"""
    personalized_subject = subject_input  # Fallback
    body = response
    html_body = ""
    
    # HTML şablon için özel parsing
    if template_source == "HTML Dosyası Yükle" and "HTML_İÇERİK:" in response:
        if "KONU:" in response and "HTML_İÇERİK:" in response:
            parts = response.split("HTML_İÇERİK:")
            if len(parts) >= 2:
                subject_part = parts[0].replace("KONU:", "").strip()
                html_body = parts[1].strip()
                body = html_body  # HTML içeriği
                if subject_part and subject_part.strip() and use_personalized_subjects:
                    personalized_subject = subject_part
    else:
        # Normal parsing
        if "KONU:" in response and "İÇERİK:" in response:
            parts = response.split("İÇERİK:")
            if len(parts) >= 2:
                subject_part = parts[0].replace("KONU:", "").strip()
                body = parts[1].strip()
                if subject_part and subject_part.strip() and use_personalized_subjects:
                    personalized_subject = subject_part
    
    return personalized_subject, body, html_body

# Sidebar: Global config
st.sidebar.header("🔐 OpenAI & Global Ayarlar")
api_key = st.sidebar.text_input("OpenAI API Key", value=os.getenv("OPENAI_API_KEY",""), type="password")
model = st.sidebar.text_input("OpenAI Model", value=os.getenv("OPENAI_MODEL","gpt-4"))
default_temp = st.sidebar.number_input("Default Temperature", 0.0, 2.0, float(os.getenv("OPENAI_TEMPERATURE",0.2)), 0.1)
default_max_tokens = st.sidebar.number_input("Default Max Tokens", 256, 8000, int(os.getenv("OPENAI_MAX_TOKENS",3000)), 64)

st.title("🚀 Export LeadGen Pro")
st.caption("Kampanyalar, scraping, enrichment, kişiselleştirilmiş e‑posta, SMTP/IMAP, form doldurma — hepsi bir arada.")

# Campaign creation
st.subheader("1) Kampanya Oluştur / Yükle")

with st.form("create_campaign"):
    c1, c2 = st.columns(2)
    with c1:
        firm_name = st.text_input("Firma Adı", "")
        firm_site = st.text_input("Firma Websitesi", "")
        products = st.text_area("Ürün(ler)", placeholder="Virgülle ayırınız: Shotgun, Pump Action...")
    with c2:
        target_country = st.text_input("Hedef Ülke", "")
        temp = st.number_input("Bu kampanya Temperature", 0.0, 2.0, default_temp, 0.1)
        max_tok = st.number_input("Bu kampanya Max Tokens", 256, 4000, default_max_tokens, 64)
    submitted = st.form_submit_button("Kampanya Oluştur")
    if submitted:
        camp = create_campaign(
            firm_name=firm_name.strip(),
            firm_site=firm_site.strip(),
            products=[p.strip() for p in products.split(",") if p.strip()],
            target_country=target_country.strip(),
            ai_temperature=float(temp),
            ai_max_tokens=int(max_tok),
            model=model.strip()
        )
        st.success(f"Kampanya oluşturuldu: {camp.id}")

# Existing campaigns
camps = load_campaigns()
camp_ids = sorted(camps.keys())
active_id = st.selectbox("Varolan kampanyayı aç", options=["—"]+camp_ids)
active = load_campaign(active_id) if active_id!="—" else None

if not active:
    st.info("Bir kampanya seçin veya oluşturun.")
    st.stop()

st.success(f"Aktif kampanya: **{active.name}** ({active.firm_name} → {active.target_country})")

# 3A) Üreticiyi ve Ürünleri Tanıma
st.header("A) Üreticiyi ve Ürünleri Tanıma")
with st.expander("🔍 Gelişmiş Firma Profil Analizi - GPT ile kapsamlı analiz", expanded=False):
    
    # Analiz seçenekleri
    col_a1, col_a2 = st.columns([2, 1])
    
    with col_a1:
        st.write(f"**Analiz Edilecek Firma:** {active.firm_name}")
        st.write(f"**Website:** {active.firm_site}")
        st.write(f"**Ürünler:** {', '.join(active.products) if active.products else 'Belirtilmemiş'}")
        st.write(f"**Hedef Ülke:** {active.target_country}")
    
    with col_a2:
        analysis_depth = st.selectbox(
            "Analiz Derinliği",
            ["Temel Profil", "Detaylı Analiz", "Kapsamlı İnceleme"],
            index=1
        )
        
        include_competitors = st.checkbox("Rakip analizi dahil et", value=True)
        include_market_insights = st.checkbox("Pazar içgörüleri ekle", value=True)
        include_buyer_personas = st.checkbox("Alıcı profillerini detaylandır", value=True)
    
    do_profile = st.button("🚀 Gelişmiş Profil Analizi Başlat", type="primary")
    
    if do_profile:
        if not (api_key or os.getenv("OPENAI_API_KEY")):
            st.error("OpenAI API Key gerekli!")
        else:
            with st.spinner("🤖 Kapsamlı firma analizi yapılıyor..."):
                
                # Analiz derinliğine göre token ve temperature ayarları
                if analysis_depth == "Temel Profil":
                    max_tokens = 3000
                    temperature = 0.3
                elif analysis_depth == "Detaylı Analiz":
                    max_tokens = 3500
                    temperature = 0.5
                else:  # Kapsamlı İnceleme
                    max_tokens = 4000
                    temperature = 0.7
                
                # Gelişmiş prompt oluşturma
                prompt = f"""
Sen uzman bir B2B pazar analisti ve iş geliştirme uzmanısın. Aşağıdaki firma hakkında kapsamlı bir analiz yap:

FIRMA BİLGİLERİ:
- Firma Adı: {active.firm_name}
- Website: {active.firm_site}
- Ürünler: {', '.join(active.products) if active.products else 'Genel ürün portföyü'}
- Hedef Pazar: {active.target_country}

GÖREV: Bu firmayı conceptual olarak analiz et ve aşağıdaki başlıklar altında detaylı bilgi ver:

## 🏢 FİRMA KİMLİĞİ VE KONUMU
- Firmanın sektördeki konumu ve uzmanlik alanları
- Kuruluş geçmişi ve deneyim seviyesi (tahmin)
- Coğrafi faaliyet alanı ve pazar varlığı

## 📦 ÜRÜN VE HİZMET PORTFÖYÜ
- Ana ürün/hizmet kategorileri
- Ürün kalitesi ve teknoloji seviyesi
- Öne çıkan özellikler ve yenilikçi çözümler
- Fiyat segmenti (ekonomik/orta/premium)

## 🎯 HEDEF MÜŞTERİ PROFİLİ{"" if not include_buyer_personas else " (DETAYLI)"}
- Birincil hedef müşteri segmentleri
- Müşteri büyüklüğü (KOBİ/Kurumsal/Enterprise)
- Sektörel odak alanları
{"- Karar verici profilleri ve satın alma süreçleri" if include_buyer_personas else ""}
{"- Müşteri ihtiyaçları ve beklentileri" if include_buyer_personas else ""}

## 💪 GÜÇLÜ YÖNLER VE FARKLILIŞTIRICILAR
- Rekabet avantajları
- Teknik uzmanlık alanları
- Hizmet kalitesi ve müşteri yaklaşımı
- İnovasyon kapasitesi

## ⚠️ ZAYIF YÖNLER VE GELİŞİM ALANLARI
- Potansiyel eksiklikler
- Gelişim fırsatları
- Pazar sınırlamaları

{"## 🏆 RAKIP ANALIZI" if include_competitors else ""}
{"- Ana rakipler ve konumları" if include_competitors else ""}
{"- Rekabet avantajları/dezavantajları" if include_competitors else ""}
{"- Pazar payı tahmini" if include_competitors else ""}

{"## 📊 PAZAR İÇGÖRÜLERİ" if include_market_insights else ""}
{"- " + active.target_country + " pazarındaki fırsatlar" if include_market_insights else ""}
{"- Sektörel trendler ve gelişmeler" if include_market_insights else ""}
{"- Büyüme potansiyeli değerlendirmesi" if include_market_insights else ""}

## 🚀 İŞ GELİŞTİRME ÖNERİLERİ
- Pazarlama ve satış stratejileri
- Potansiyel iş birliği alanları
- Büyüme için öneriler
- Dijital dönüşüm fırsatları

Her başlık altında 3-5 detaylı madde ver. Profesyonel, analitik ve eylem odaklı bir dil kullan. Türkçe yaz.
"""
                
                try:
                    with st.spinner("GPT ile profil analizi yapılıyor..."):
                        profile_text = complete(
                            prompt, 
                            api_key=api_key, 
                            model=model, 
                            temperature=temperature, 
                            max_tokens=max_tokens
                        )
                    
                    if profile_text and len(profile_text.strip()) > 10:
                        # Sonuçları kaydet
                        analysis_data = {
                            "profile": profile_text.strip(),
                            "analysis_depth": analysis_depth,
                            "include_competitors": include_competitors,
                            "include_market_insights": include_market_insights,
                            "include_buyer_personas": include_buyer_personas,
                            "timestamp": pd.Timestamp.now().isoformat()
                        }
                        
                        write_json(CAMPAIGNS_DIR/active.id/"outputs"/"A_profile.json", analysis_data)
                        st.success("✅ Profil analizi tamamlandı!")
                        st.rerun()
                    else:
                        st.error("❌ GPT'den yanıt alınamadı. API key'inizi kontrol edin.")
                    
                except Exception as e:
                    st.error(f"❌ Hata: {str(e)}")

# Analiz sonuçlarını göster
prof_path = CAMPAIGNS_DIR/active.id/"outputs"/"A_profile.json"
prof_json = read_json(prof_path, {})

if "profile" in prof_json and prof_json["profile"].strip():
    st.subheader("📋 Firma Profil Analizi Sonuçları")
    
    # Analiz bilgileri
    if prof_json.get("timestamp"):
        col_info1, col_info2, col_info3 = st.columns(3)
        with col_info1:
            st.info(f"**Analiz Tarihi:** {prof_json.get('timestamp', 'Bilinmiyor')[:10]}")
        with col_info2:
            st.info(f"**Analiz Derinliği:** {prof_json.get('analysis_depth', 'Standart')}")
        with col_info3:
            depth_options = []
            if prof_json.get('include_competitors'): depth_options.append("Rakip Analizi")
            if prof_json.get('include_market_insights'): depth_options.append("Pazar İçgörüleri")
            if prof_json.get('include_buyer_personas'): depth_options.append("Detaylı Alıcı Profilleri")
            st.info(f"**Ek Analizler:** {', '.join(depth_options) if depth_options else 'Temel'}")
    
    # Ana analiz içeriği - Büyük görüntüleme alanı
    st.markdown("---")
    
    # Tam genişlik analiz alanı
    with st.container():
        st.markdown("### 📊 Detaylı Firma Analizi")
        
        # Analiz içeriğini büyük bir text area'da göster
        analysis_content = prof_json["profile"]
        
        # Scrollable text area ile analiz sonuçlarını göster
        st.text_area(
            label="Analiz Sonuçları",
            value=analysis_content,
            height=600,
            disabled=True,
            key="analysis_display"
        )
        
        # Markdown formatında da göster
        with st.expander("📖 Formatlanmış Görünüm", expanded=False):
            st.markdown(analysis_content)
    
    # Eylem butonları
    col_action1, col_action2, col_action3 = st.columns(3)
    
    with col_action1:
        if st.button("📥 TXT İndir"):
            download_content = f"""FIRMA PROFIL ANALİZİ
{'='*50}

Firma: {active.firm_name}
Website: {active.firm_site}
Hedef Ülke: {active.target_country}
Analiz Tarihi: {prof_json.get('timestamp', 'Bilinmiyor')}
Analiz Derinliği: {prof_json.get('analysis_depth', 'Standart')}

{'='*50}

{analysis_content}

{'='*50}
Bu analiz Export LeadGen Pro tarafından GPT ile oluşturulmuştur."""
            
            st.download_button(
                label="💾 Dosyayı İndir",
                data=download_content.encode('utf-8'),
                file_name=f"{active.firm_name.replace(' ', '_')}_profil_analizi.txt",
                mime="text/plain",
                key="download_txt"
            )
    
    with col_action2:
        if st.button("🔄 Analizi Yenile"):
            st.rerun()
    
    with col_action3:
        if st.button("🗑️ Analizi Sil"):
            import os
            try:
                os.remove(prof_path)
                st.success("Analiz silindi!")
                st.rerun()
            except:
                st.error("Analiz silinemedi!")

elif prof_json and not str(prof_json.get("profile", "") or "").strip():
    st.warning("⚠️ Analiz dosyası mevcut ancak içerik boş. Lütfen analizi yeniden çalıştırın.")
    if st.button("🔄 Yeniden Dene"):
        st.rerun()

# 3B) Anahtar Kelime
st.header("B) Anahtar Kelime")
colB1, colB2 = st.columns(2)
with colB1:
    manual_kw = st.text_area("Manuel Anahtar Kelimeler (satır başına bir tane)")
with colB2:
    target_lang = st.text_input("Hedef Dil (ör. de, es, en, tr)", value="en")
    keyword_count = st.select_slider("Üretilecek Kelime Sayısı", options=[5, 10, 20, 50, 100], value=20)
    gen_kw = st.button("GPT ile Anahtar Kelime Üret")
    if gen_kw:
        try:
            prof = read_json(CAMPAIGNS_DIR/active.id/"outputs"/"A_profile.json", {}).get("profile","")
            kws = generate_keywords(
                api_key=api_key or os.getenv("OPENAI_API_KEY"), 
                model=model, 
                firm_name=active.firm_name, 
                products=active.products, 
                target_country=active.target_country, 
                firm_profile=prof, 
                target_lang=target_lang, 
                max_terms=keyword_count
            )
            write_json(CAMPAIGNS_DIR/active.id/"outputs"/"B_keywords.json", {"keywords": kws})
            st.success("Anahtar kelimeler üretildi.")
        except Exception as e:
            st.error(f"Anahtar kelime hatası: {str(e)}")
kws_data = read_json(CAMPAIGNS_DIR/active.id/"outputs"/"B_keywords.json", {})
if manual_kw.strip():
    extra = [x.strip() for x in manual_kw.splitlines() if x.strip()]
    kws_data.setdefault("keywords", [])
    kws_data["keywords"].extend(extra)
    kws_data["keywords"] = sorted(set(kws_data["keywords"]))
    write_json(CAMPAIGNS_DIR/active.id/"outputs"/"B_keywords.json", kws_data)
st.write(kws_data.get("keywords", []))

# 3C) Arama Motoru Bazlı Data Çıkarma
st.header("C) Arama Motoru Bazlı Data Çıkarma")

# Arama yöntemi seçimi
st.subheader("🚀 Arama Yöntemi Seçimi")
search_method = st.radio(
    "Hangi arama yöntemini kullanmak istiyorsunuz?",
    ["Gelişmiş Selenium (Mevcut)"],
    help="Sadece Gelişmiş Selenium arama motoru mevcut"
)

# Sadece Gelişmiş Selenium seçeneği kaldı
col_c1, col_c2 = st.columns(2)
with col_c1:
    st.subheader("🔍 Arama Motoru Ayarları")
    engines = st.multiselect(
        "Arama Motorları", 
        ["DuckDuckGo"], 
        default=["DuckDuckGo"],
        help="Sadece DuckDuckGo arama motoru mevcut."
    )

per_kw = st.select_slider(
    "Anahtar kelime başına sonuç limiti", 
    options=[1, 5, 10, 30, 50, 100, 200, 1000], 
    value=30,
    help="Her anahtar kelime için kaç sonuç alınacak (sayfalama ile)"
)

with col_c2:
    st.subheader("⚙️ Gezinme Ayarları")
    total_sites = st.select_slider(
        "Toplam site limiti", 
        options=[10, 30, 50, 100, 200, 500, 650, 1000, 10000], 
        value=100,
        help="Toplamda kaç siteye ziyaret edilecek"
    )
    
    dwell = st.select_slider(
        "Site başı gezinme süresi (saniye)", 
        options=[2,10, 20, 30], 
        value=2,
        help="Her sitede ne kadar süre geçirilecek"
    )

# Stealth mode seçeneği (sadece Selenium için)
if search_method == "Gelişmiş Selenium (Mevcut)":
    st.subheader("🥷 Stealth Mode Ayarları")
    col_stealth1, col_stealth2 = st.columns(2)
    
    with col_stealth1:
        use_stealth_mode = st.checkbox(
            "Gelişmiş Stealth Mode Kullan", 
            value=False,
            help="Gelişmiş stealth teknikleri"
        )
        
        headless_mode = st.checkbox(
            "Headless (Görünmez) Mod", 
            value=False,
            help="Tarayıcı penceresi görünmez olur, daha hızlı çalışır"
        )
    
    with col_stealth2:
        if use_stealth_mode:
            st.success("✅ **Stealth Mode Aktif**")
            st.caption("• Gelişmiş anti-detection")
            st.caption("• İnsan benzeri davranış")
            st.caption("• Gelişmiş fingerprinting koruması")
        else:
            st.info("ℹ️ **Normal Mode**")
            st.caption("• Standart Selenium ayarları")
            st.caption("• Daha hızlı başlatma")
            st.caption("• Temel stealth koruması")
else:
    use_stealth_mode = False
    headless_mode = False

# Proxy ayarları (sadece Selenium için)
if search_method == "Gelişmiş Selenium (Mevcut)":
    st.subheader("🌐 Proxy Ayarları")
    col_proxy1, col_proxy2 = st.columns(2)
    
    with col_proxy1:
        use_proxy = st.checkbox(
            "Proxy Kullan", 
            value=False,
            help="Farklı IP adresleri kullanarak güvenliği artırır"
        )
        
        proxy_type = st.selectbox(
            "Proxy Türü",
            ["free", "premium", "custom"],
            help="Proxy türünü seçin"
        )
    
    with col_proxy2:
        if use_proxy:
            if proxy_type == "custom":
                custom_proxies = st.text_area(
                    "Özel Proxy Listesi",
                    placeholder="proxy1.com:8080\nproxy2.com:3128\nproxy3.com:8080",
                    help="Her satıra bir proxy (format: host:port)"
                )
                proxy_list = [p.strip() for p in custom_proxies.split('\n') if p.strip()] if custom_proxies else []
            elif proxy_type == "free":
                proxy_list = get_free_proxy_list()
                st.info(f"📋 {len(proxy_list)} ücretsiz proxy yüklendi")
            else:  # premium
                proxy_list = get_premium_proxy_list()
                st.info(f"💎 {len(proxy_list)} premium proxy yüklendi")
            
            # Proxy önerileri
            recommendations = get_proxy_recommendations()
            st.caption(f"💡 **{proxy_type.title()} Proxy:** {recommendations.get(proxy_type, 'Açıklama yok')}")
        else:
            proxy_list = []
            st.info("ℹ️ Proxy kullanılmıyor")
else:
    use_proxy = False
    proxy_list = []

# Gelişmiş ayarlar
st.subheader("⚙️ Gelişmiş Ayarlar")
col_adv1, col_adv2 = st.columns(2)
with col_adv1:
    st.info("🔧 **Otomatik Optimizasyon:** Sistem otomatik olarak en iyi performansı sağlar")
with col_adv2:
    st.info("🛡️ **Güvenlik:** Gelişmiş anti-detection teknikleri aktif")

# Bilgilendirme
if engines and per_kw and total_sites:
    expected_pages = min(5, (per_kw + 9) // 10)  # Her sayfa ~10 sonuç
    st.info(f"📊 **Tahmini işlem:** {len(engines)} arama motoru × {expected_pages} sayfa × {len(engines)} kelime = ~{len(engines) * expected_pages * 5} site ziyareti")

# Buton metnini dinamik yap
button_text = "🚀 C Adımını Çalıştır (Selenium)"

do_c = st.button(button_text, type="primary")
if do_c:
    kws = read_json(CAMPAIGNS_DIR/active.id/"outputs"/"B_keywords.json", {}).get("keywords", [])
    if not kws:
        st.error("❌ Anahtar kelime bulunamadı. Önce B adımını çalıştırın.")
    else:
        out_dir = CAMPAIGNS_DIR/active.id/"outputs"
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Sadece Gelişmiş Selenium yöntemi
                if not engines:
                    st.error("❌ En az bir arama motoru seçin.")
                else:
                    try:
                        with st.spinner("🔍 Gelişmiş Selenium ile arama motorlarında tarama başlıyor..."):
                            df = search_and_collect(
                                keywords=kws, 
                                engines=engines, 
                                max_sites_total=int(total_sites), 
                                per_keyword_limit=int(per_kw), 
                                dwell_seconds=int(dwell), 
                                out_dir=out_dir,
                                # CAPTCHA sistemi kaldırıldı
                                use_stealth_mode=use_stealth_mode,
                                headless_mode=headless_mode,
                                use_proxy=use_proxy,
                                proxy_list=proxy_list
                            )
                    except Exception as e:
                        st.error(f"❌ Arama sırasında hata oluştu: {str(e)}")
                        st.stop()
                        
                    progress_bar.progress(100)
                    status_text.success("✅ Gelişmiş Selenium ile tamamlandı!")
                    
                    if len(df) > 0:
                        st.success(f"🎉 **{len(df)} firma** verisi toplandı!")
                        
                        # Firma tipi dağılımını göster
                        if "Firma Tipi" in df.columns:
                            st.subheader("📊 Firma Tipi Dağılımı")
                            type_counts = df["Firma Tipi"].value_counts()
                            col_chart1, col_chart2 = st.columns(2)
                            
                            with col_chart1:
                                st.bar_chart(type_counts)
                            
                            with col_chart2:
                                for ftype, count in type_counts.items():
                                    st.metric(ftype, count)
                        
                        # Veri tablosunu göster
                        st.subheader("📋 Toplanan Veriler")
                        st.dataframe(df.head(100), use_container_width=True)
                        
                        # İndirme butonu
                        csv_data = df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8')
                        st.download_button(
                            label="📥 CSV İndir",
                            data=csv_data,
                            file_name=f"C_search_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.warning("⚠️ Hiç veri toplanamadı. Arama kriterlerini gözden geçirin.")
                
        except Exception as e:
            progress_bar.progress(0)
            status_text.error(f"❌ Hata: {str(e)}")
            st.error(f"Bir hata oluştu: {str(e)}")
            st.info("💡 **Çözüm önerileri:**\n- Chrome tarayıcısının güncel olduğundan emin olun\n- İnternet bağlantınızı kontrol edin\n- Alternatif arama yöntemlerini deneyin")

# 3D) Google Maps Bazlı Data Çıkarma
st.header("D) Google Maps Bazlı Data Çıkarma")

# Enhanced D step interface
st.subheader("🚀 Gelişmiş Google Maps Scraping")
col_d1, col_d2 = st.columns(2)

with col_d1:
    st.markdown("### ⚙️ Arama Ayarları")
    per_kw_m = st.select_slider(
        "Anahtar kelime başına firma limiti", 
        options=[1, 5, 10, 20, 30, 50, 100, 200, 500], 
        value=10,
        help="Her anahtar kelime için kaç firma toplanacak. 1 seçeneği hızlı test için idealdir."
    )
    
    dwell_m = st.select_slider(
        "Kart başı bekleme süresi (saniye)", 
        options=[1, 2, 3, 5, 8, 10], 
        value=2,
        help="Her firma kartında ne kadar süre beklenecek. Düşük değerler daha hızlıdır."
    )
    
    # Performance mode
    performance_mode = st.selectbox(
        "Performans Modu",
        ["Hızlı (Önerilen)", "Orta", "Güvenli"],
        help="Hızlı: Daha az bekleme, Orta: Dengeli, Güvenli: Daha fazla bekleme"
    )

with col_d2:
    st.markdown("### 📊 Beklenen Sonuçlar")
    kws = read_json(CAMPAIGNS_DIR/active.id/"outputs"/"B_keywords.json", {}).get("keywords", [])
    
    if kws:
        total_expected = len(kws) * per_kw_m
        st.info(f"**Anahtar Kelime Sayısı:** {len(kws)}")
        st.info(f"**Kelime Başı Limit:** {per_kw_m}")
        st.success(f"**Beklenen Toplam Firma:** {total_expected}")
        
        # Performance estimation
        if performance_mode == "Hızlı (Önerilen)":
            estimated_time = len(kws) * per_kw_m * 3  # 3 seconds per business
        elif performance_mode == "Orta":
            estimated_time = len(kws) * per_kw_m * 5  # 5 seconds per business
        else:  # Güvenli
            estimated_time = len(kws) * per_kw_m * 8  # 8 seconds per business
        
        st.info(f"**Tahmini Süre:** {estimated_time//60} dakika {estimated_time%60} saniye")
    else:
        st.warning("⚠️ Önce B adımını çalıştırarak anahtar kelimeler oluşturun")

# Advanced options
with st.expander("🔧 Gelişmiş Seçenekler", expanded=False):
    col_adv1, col_adv2 = st.columns(2)
    
    with col_adv1:
        retry_failed = st.checkbox("Başarısız anahtar kelimeleri tekrar dene", value=True)
        show_browser = st.checkbox("Tarayıcıyı görünür tut", value=True, help="İşlemleri takip etmek için")
        save_partial = st.checkbox("Kısmi sonuçları kaydet", value=True, help="Hata durumunda bile toplanan verileri kaydet")
    
    with col_adv2:
        max_retries = st.slider("Maksimum deneme sayısı", 1, 5, 3)
        delay_between_keywords = st.slider("Anahtar kelimeler arası bekleme (sn)", 0, 5, 1)

# Run button with enhanced feedback
button_text = f"🚀 D Adımını Çalıştır - Google Maps Scraping"
if per_kw_m == 1:
    button_text += " (Hızlı Test)"

do_d = st.button(button_text, type="primary", disabled=not kws)

if do_d:
    if not kws:
        st.error("❌ Anahtar kelime bulunamadı. Önce B adımını çalıştırın.")
    else:
        out_dir = CAMPAIGNS_DIR/active.id/"outputs"
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Performance mode adjustments
        if performance_mode == "Hızlı (Önerilen)":
            dwell_m = max(1, dwell_m - 1)
        elif performance_mode == "Güvenli":
            dwell_m = dwell_m + 2
        
        try:
            with st.spinner("🗺️ Google Maps'te firma aranıyor..."):
                status_text.text(f"🔍 {len(kws)} anahtar kelime ile Google Maps scraping başlıyor...")
                
                # Enhanced maps_scrape call with progress tracking
                df = maps_scrape(kws, per_kw_m, dwell_m, out_dir=out_dir)
                
                progress_bar.progress(100)
                status_text.success("✅ Google Maps scraping tamamlandı!")
                
                if len(df) > 0:
                    st.success(f"🎉 **{len(df)} firma** Google Maps'ten başarıyla toplandı!")
                    
                    # Show statistics
                    col_stats1, col_stats2, col_stats3 = st.columns(3)
                    with col_stats1:
                        st.metric("📊 Toplam Firma", len(df))
                    with col_stats2:
                        websites_found = len(df[df["Firma Websitesi"].str.strip() != ""])
                        st.metric("🌐 Website Bulunan", websites_found)
                    with col_stats3:
                        phones_found = len(df[df["Telefon Numaraları"].str.strip() != ""])
                        st.metric("📞 Telefon Bulunan", phones_found)
                    
                    # Show data preview
                    st.subheader("📋 Toplanan Veriler")
                    st.dataframe(df.head(100), use_container_width=True)
                    
                    # Download button
                    csv_data = df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8')
                    st.download_button(
                        label="📥 CSV İndir",
                        data=csv_data,
                        file_name=f"D_maps_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv"
                    )
                    
                    # Data quality analysis
                    with st.expander("📈 Veri Kalitesi Analizi", expanded=False):
                        col_quality1, col_quality2 = st.columns(2)
                        
                        with col_quality1:
                            st.markdown("**Eksik Veri Oranları:**")
                            total_rows = len(df)
                            missing_website = (df["Firma Websitesi"].str.strip() == "").sum()
                            missing_phone = (df["Telefon Numaraları"].str.strip() == "").sum()
                            missing_address = (df["Firma Adresi"].str.strip() == "").sum()
                            
                            st.metric("Website Eksik", f"{missing_website}/{total_rows} ({missing_website/total_rows*100:.1f}%)")
                            st.metric("Telefon Eksik", f"{missing_phone}/{total_rows} ({missing_phone/total_rows*100:.1f}%)")
                            st.metric("Adres Eksik", f"{missing_address}/{total_rows} ({missing_address/total_rows*100:.1f}%)")
                        
                        with col_quality2:
                            st.markdown("**Anahtar Kelime Dağılımı:**")
                            keyword_counts = df["Anahtar Kelime"].value_counts()
                            st.bar_chart(keyword_counts)
                
                else:
                    st.warning("⚠️ Hiç veri toplanamadı. Anahtar kelimelerinizi kontrol edin.")
                    st.info("💡 **Çözüm önerileri:**\n- Anahtar kelimelerinizi daha spesifik yapın\n- Farklı anahtar kelimeler deneyin\n- İnternet bağlantınızı kontrol edin")
        
        except Exception as e:
            progress_bar.progress(0)
            status_text.error(f"❌ Hata: {str(e)}")
            st.error(f"Google Maps scraping sırasında hata oluştu: {str(e)}")
            st.info("💡 **Çözüm önerileri:**\n- Chrome tarayıcısının güncel olduğundan emin olun\n- İnternet bağlantınızı kontrol edin\n- Farklı performans modu deneyin")

# 3E) Data Enrichment
st.header("E) Data Enrichment")
prov = st.selectbox("Sağlayıcı", ["Hunter","Apollo","RocketReach"])
api = st.text_input("API Key (sağlayıcıya göre)", value=os.getenv(f"{prov.upper()}_API_KEY",""))
do_e = st.button("E Çalıştır (API)")
if do_e:
    out_dir = CAMPAIGNS_DIR/active.id/"outputs"
    # Merge C & D
    C_path = out_dir / "C_search_results.csv"
    D_path = out_dir / "D_maps_results.csv"
    base_df = pd.DataFrame()
    if C_path.exists():
        base_df = pd.read_csv(C_path)
    if D_path.exists():
        d_df = pd.read_csv(D_path)
        if base_df.empty:
            base_df = d_df
        else:
            base_df = pd.concat([base_df, d_df], ignore_index=True)
    if base_df.empty:
        st.error("C veya D verisi bulunamadı.")
    else:
        enriched = enrich_dataframe(base_df, prov, api)
        enriched.to_csv(out_dir/"E_enriched_contacts.csv", index=False, encoding="utf-8-sig")
        st.success(f"Enriched kişi sayısı: {len(enriched)}")
        st.dataframe(enriched.head(50))

# 3F) Kişiselleştirilmiş Eposta İçerik Üretimi
st.header("F) Kişiselleştirilmiş Eposta İçerik Üretimi")

# Gelişmiş analiz seçenekleri
st.subheader("🔍 Firma Analizi ve İçerik Üretimi")
col_f_analysis1, col_f_analysis2 = st.columns(2)

with col_f_analysis1:
    use_c_data = st.checkbox("C adımı verilerini kullan", value=True, help="C adımından toplanan firma verilerini kullanarak kişiselleştirilmiş içerik üretir")
    enable_website_analysis = st.checkbox("Ek web sitesi analizi yap", value=False, help="C adımı verilerine ek olarak web sitesi analizi yapar (yavaş)")
    analysis_depth = st.selectbox(
        "Analiz Derinliği",
        ["Temel", "Detaylı", "Kapsamlı"],
        index=1,
        help="Temel: Sadece temel bilgiler, Detaylı: Ürün/hizmet analizi, Kapsamlı: Tam analiz"
    )

with col_f_analysis2:
    batch_size = st.select_slider("Kaç firma için üretilecek?", options=[5,10,20,30,50,100, 300], value=20)
    analysis_delay = st.slider("Site başı bekleme süresi (saniye)", 1, 5, 2, help="Web siteleri arasında bekleme süresi")

# Şablon kaynağı seçimi
st.subheader("📝 Email Şablonu")
col_f1, col_f2 = st.columns(2)
with col_f1:
    template_source = st.radio("Şablon Kaynağı", ["Manuel Giriş", "HTML Dosyası Yükle"])
    mode = st.radio("Şablon modu", ["Plain Text","HTML"])
    
with col_f2:
    subject_input = st.text_input("Email Konu Başlığı (Fallback)", "Partnership Opportunity / İş Birliği Teklifi", help="GPT'den konu gelmezse bu kullanılır")
    use_personalized_subjects = st.checkbox("Kişiselleştirilmiş konu başlıkları kullan", value=True, help="Her firma için özel konu başlığı oluştur")

# Özel Prompt Sistemi
st.subheader("🤖 AI Prompt Sistemi")
col_prompt1, col_prompt2 = st.columns([2, 1])

with col_prompt1:
    use_custom_prompt = st.checkbox(
        "Özel Prompt Kullan", 
        value=False, 
        help="✅ İşaretlenirse: Kendi prompt'unuzu kullanır, sistem prompt'u devre dışı kalır\n❌ İşaretlenmezse: Sistemin gelişmiş prompt'unu kullanır"
    )
    
    if use_custom_prompt:
        custom_prompt = st.text_area(
            "🎯 Özel Prompt Giriniz",
            height=300,
            placeholder="""Örnek özel prompt:

Sen bir B2B satış uzmanısın. Aşağıdaki firma bilgilerini kullanarak kişiselleştirilmiş email oluştur:

Firma: {FIRMA_ADI}
Ülke: {ULKE}
Özet: {OZET}
Şablon: {TEMPLATE}

Kurallar:
- Profesyonel ve samimi ton kullan
- Firma adını ve ülkeyi uygun yerlere yerleştir
- Şablonu firmaya özel hale getir

Çıktı formatı:
KONU: [Konu başlığı]
İÇERİK: [Email içeriği]""",
            help="""💡 Kullanılabilir değişkenler:
- {FIRMA_ADI}: Firma adı
- {ULKE}: Firma ülkesi
- {OZET}: Firma özet bilgisi
- {TEMPLATE}: Email şablonu
- {WEBSITE}: Firma websitesi
- {EMAIL_ADRESLERI}: E-posta adresleri

🎯 Çıktı formatı zorunlu:

İÇERİK: [Email içeriği]"""
        )
    else:
        custom_prompt = ""
        st.info("ℹ️ Sistemin gelişmiş prompt'u kullanılacak (C adımı analizi + web sitesi analizi dahil)")

with col_prompt2:
    st.markdown("### 📋 Prompt Seçenekleri")
    
    if use_custom_prompt:
        st.success("✅ **Özel Prompt Aktif**")
        st.markdown("""
        - Kendi prompt'unuz kullanılır
        - Sistem analizi devre dışı
        - Tam kontrol sizde
        - Hızlı işlem
        """)
    else:
        st.info("ℹ️ **Sistem Prompt Aktif**")
        st.markdown("""
        - Gelişmiş AI analizi
        - C adımı verileri dahil
        - Web sitesi analizi
        - Profesyonel sonuçlar
        """)
    
    st.markdown("---")
    st.markdown("### 🔄 Geçiş Önerisi")
    if not use_custom_prompt:
        st.markdown("""**Sistem prompt'u kullanın eğer:**
        - İlk kez kullanıyorsanız
        - En iyi sonucu istiyorsanız
        - Zamanınız varsa""")
    else:
        st.markdown("""**Özel prompt kullanın eğer:**
        - Belirli bir yaklaşım istiyorsanız
        - Hızlı işlem istiyorsanız
        - Kendi stratejiniz var""")

# Şablon içeriği
template = ""
html_template = ""

if template_source == "Manuel Giriş":
    template = st.text_area("Email Şablonu", height=200, placeholder="Firma tanıtım şablonunuzu buraya giriniz... {FIRMA_ADI} {ULKE} değişkenleri desteklenir.")
else:
    uploaded_html = st.file_uploader("HTML Email Şablonu Yükle", type=["html", "htm"], help="HTML email şablonunuzu yükleyin. İçerik firmaya göre kişiselleştirilecek.")
    if uploaded_html is not None:
        html_content = uploaded_html.read().decode('utf-8')
        html_template = html_content
        template = html_content  # Prompt için kullanılacak
        
        # HTML önizleme
        with st.expander("📄 HTML Şablon Önizleme", expanded=False):
            st.code(html_content[:1000] + "..." if len(html_content) > 1000 else html_content, language="html")
            st.components.v1.html(html_content, height=400, scrolling=True)
    else:
        st.info("👆 HTML email şablonunuzu yükleyin")

# Çalıştırma butonu ve kontroller
can_run = template.strip() if template_source == "Manuel Giriş" else bool(html_template)
if use_custom_prompt and not custom_prompt.strip():
    can_run = False
    st.warning("⚠️ Özel prompt kullanmak istiyorsanız lütfen prompt giriniz")
elif not can_run:
    st.warning("⚠️ Lütfen bir şablon girin veya HTML dosyası yükleyin")

# Buton metnini dinamik yap
button_text = "🚀 F Çalıştır - "
if use_custom_prompt:
    button_text += "Özel Prompt ile Email Üret"
else:
    button_text += "Gelişmiş Analiz ile Email Üret"

do_f = st.button(button_text, disabled=not can_run, type="primary")
if do_f and can_run:
    out_dir = CAMPAIGNS_DIR/active.id/"outputs"
    C_path = out_dir / "C_search_results.csv"
    if not C_path.exists():
        st.error("C verisi gereklidir.")
    else:
        base = pd.read_csv(C_path)
        base = base.head(batch_size)
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # C adımı verilerini analiz et - Özel prompt kullanılıyorsa atla
        c_data_analysis = {}
        if use_c_data and not (use_custom_prompt and custom_prompt.strip()):
            status_text.text("📊 C adımı verileri analiz ediliyor...")
            c_data_analysis = analyze_c_data_for_email(base)
        elif use_custom_prompt and custom_prompt.strip():
            st.info("ℹ️ Özel prompt kullanıldığı için C adımı analizi atlandı")
        
        # Web sitesi analizi yap (opsiyonel) - Özel prompt kullanılıyorsa atla
        website_analyses = []
        if enable_website_analysis and not (use_custom_prompt and custom_prompt.strip()):
            status_text.text("🔍 Web siteleri analiz ediliyor...")
            website_analyses = batch_analyze_websites(base.to_dict('records'), max_companies=batch_size)
        elif use_custom_prompt and custom_prompt.strip():
            st.info("ℹ️ Özel prompt kullanıldığı için web sitesi analizi atlandı")
        
        rows = []
        total_companies = len(base)
        
        for i, (_, r) in enumerate(base.iterrows()):
            # Progress update
            progress = (i + 1) / total_companies
            progress_bar.progress(progress)
            status_text.text(f"📧 Email üretiliyor: {i+1}/{total_companies}")
            
            firma = str(r.get("Firma Adı","") or "").strip() or str(r.get("Firma Websitesi","") or "")
            ulke = str(r.get("Firma Ülkesi/Dil","") or "")
            ozet = str(r.get("Özet Metin","") or "")[:800]
            website_url = str(r.get("Firma Websitesi", "") or "")
            
            # E-posta adresi kontrolü - F adımı için kritik
            email_addresses = str(r.get("Email Adresleri", "") or "").strip()
            if not email_addresses or email_addresses == "nan" or email_addresses == "":
                st.warning(f"⚠️ {firma} için e-posta adresi bulunamadı, atlanıyor...")
                continue
            
            # C adımı verilerini kullan - Özel prompt kullanılıyorsa boş bırak
            c_analysis = c_data_analysis.get(firma, {}) if (use_c_data and not (use_custom_prompt and custom_prompt.strip())) else {}
            
            # Web sitesi analizi varsa kullan - Özel prompt kullanılıyorsa boş bırak
            website_analysis = {}
            if not (use_custom_prompt and custom_prompt.strip()) and i < len(website_analyses):
                website_analysis = website_analyses[i]
            
            # Prompt seçimi ve oluşturma
            if use_custom_prompt and custom_prompt.strip():
                # Özel prompt kullan
                prompt = process_custom_prompt(
                    custom_prompt, firma, ulke, ozet, template, website_url, email_addresses, active
                )
            else:
                # Sistem prompt'u kullan
                if template_source == "HTML Dosyası Yükle" and html_template:
                    prompt = create_advanced_html_prompt(
                        firma, ulke, ozet, c_analysis, website_analysis, html_template, 
                        active, analysis_depth, use_personalized_subjects
                    )
                else:
                    prompt = create_advanced_text_prompt(
                        firma, ulke, ozet, c_analysis, website_analysis, template, 
                        active, analysis_depth, use_personalized_subjects
                    )
            
            try:
                response = complete(
                    prompt, 
                    api_key=api_key or os.getenv("OPENAI_API_KEY"), 
                    model=active.model, 
                    temperature=active.ai_temperature, 
                    max_tokens=active.ai_max_tokens
                )
                
                # Konu ve içeriği ayır
                personalized_subject, body, html_body = parse_email_response(
                    response, template_source, subject_input, use_personalized_subjects
                )
                
                rows.append({
                    "Firma": firma,
                    "Website": website_url,
                    "Email_Adresleri": email_addresses,  # E-posta adreslerini kaydet
                    "Konu": personalized_subject,
                    "İçerik": body,
                    "HTML_İçerik": html_body if html_body else body,
                    "Şablon_Tipi": "HTML" if template_source == "HTML Dosyası Yükle" else mode,
                    "Web_Analizi": json.dumps(website_analysis) if website_analysis else "",
                    "Analiz_Derinliği": analysis_depth
                })
                
            except Exception as e:
                st.warning(f"⚠️ {firma} için email üretilemedi: {str(e)}")
                # Fallback email
                rows.append({
                    "Firma": firma,
                    "Website": website_url,
                    "Email_Adresleri": email_addresses,  # E-posta adreslerini kaydet
                    "Konu": subject_input,
                    "İçerik": f"Merhaba {firma} ekibi,\n\n{template}",
                    "HTML_İçerik": f"<p>Merhaba {firma} ekibi,</p><p>{template}</p>",
                    "Şablon_Tipi": "HTML" if template_source == "HTML Dosyası Yükle" else mode,
                    "Web_Analizi": "",
                    "Analiz_Derinliği": "Hata"
                })
        
        # Sonuçları kaydet
        df = pd.DataFrame(rows)
        df.to_csv(out_dir/"F_personalized_emails.csv", index=False, encoding="utf-8-sig")
        
        progress_bar.progress(1.0)
        status_text.success("✅ Tüm email içerikleri oluşturuldu!")
        
        # Sonuçları göster
        col_result1, col_result2 = st.columns(2)
        with col_result1:
            st.subheader("📊 Özet")
            st.metric("Toplam İçerik", len(df))
            st.metric("Web Analizi", "✅ Yapıldı" if enable_website_analysis else "❌ Yapılmadı")
            st.metric("Analiz Derinliği", analysis_depth)
            if template_source == "HTML Dosyası Yükle":
                st.info("🎨 HTML şablonlar kişiselleştirildi")
        
        with col_result2:
            st.subheader("👀 Önizleme")
            if len(df) > 0:
                preview_idx = st.selectbox("Firma seç", range(len(df)), format_func=lambda x: df.iloc[x]['Firma'])
                selected_row = df.iloc[preview_idx]
                st.write(f"**Konu:** {selected_row['Konu']}")
                
                if selected_row.get('Şablon_Tipi') == 'HTML':
                    with st.expander("HTML Önizleme"):
                        st.components.v1.html(selected_row['HTML_İçerik'], height=300, scrolling=True)
                    with st.expander("HTML Kod"):
                        st.code(selected_row['HTML_İçerik'], language="html")
                else:
                    st.text_area("İçerik", selected_row['İçerik'], height=200, disabled=True)
                
                # Web sitesi analizi göster
                if selected_row.get('Web_Analizi'):
                    with st.expander("🔍 Web Sitesi Analizi"):
                        analysis = json.loads(selected_row['Web_Analizi'])
                        st.json(analysis)
        
        # Tablo görünümü
        with st.expander("📋 Tüm İçerikler", expanded=False):
            st.dataframe(df.head(20), use_container_width=True)

# 3G) Toplu Email Gönderimi
st.header("G) Toplu Email Gönderimi & SMTP")

# SMTP Ayarları
col_g1, col_g2 = st.columns(2)
with col_g1:
    st.subheader("📧 SMTP Ayarları")
    smtp_host = st.text_input("SMTP Host", os.getenv("SMTP_HOST",""))
    smtp_port = st.number_input("SMTP Port", 1, 65535, int(os.getenv("SMTP_PORT","587")))
    smtp_user = st.text_input("SMTP Username", os.getenv("SMTP_USERNAME",""))
    smtp_pass = st.text_input("SMTP Password", os.getenv("SMTP_PASSWORD",""), type="password")

with col_g2:
    st.subheader("👤 Gönderen Bilgileri")
    smtp_from_name = st.text_input("Gönderen İsim", os.getenv("SMTP_FROM_NAME","Your Company"))
    smtp_from_email = st.text_input("Gönderen Email", os.getenv("SMTP_FROM_EMAIL","you@example.com"))
    smtp_tls = st.checkbox("STARTTLS kullan", value=os.getenv("SMTP_USE_TLS","true").lower()=="true")
    
    # Test email input
    st.subheader("🧪 Test Email")
    test_email = st.text_input("Test için email adresi", placeholder="test@example.com", help="Bu adrese son hazırlanan içerik gönderilir")

# Hedef Firma Filtreleme
st.subheader("🎯 Hedef Firma Filtreleme")
col_filter1, col_filter2 = st.columns(2)

with col_filter1:
    # Firma tipi filtreleme
    available_types = ["E-ticaret Firması", "Toptancı", "İthalatçı", "Mağaza", "Üretici", "İhracatçı", "Distribütör", "Bayi / Yetkili satıcı", "Servis + yedek parça", "Kurum/Devlet"]
    
    filter_by_type = st.checkbox("Firma tipine göre filtrele")
    selected_types = []
    if filter_by_type:
        selected_types = st.multiselect(
            "Hangi firma tiplerine e-posta gönderilecek?",
            available_types,
            default=["Üretici", "Toptancı", "İhracatçı", "Distribütör"],
            help="Birden fazla tip seçebilirsiniz"
        )

with col_filter2:
    # Diğer filtreler
    use_enriched = st.checkbox("E adımındaki enrichment maillerini de dahil et")
    content_source = st.selectbox("Gönderilecek içerik", ["F kişiselleştirilmiş","Şablon (Plain/HTML)"])
    send_test_first = st.checkbox("Önce test emaili gönder", help="Toplu gönderimden önce test adresine örnek gönder")
    send_count = st.select_slider("Maksimum gönderim sayısı", options=[5,10,20,30,50,100,500,1000], value=50)

# Önizleme
if filter_by_type and selected_types:
    st.info(f"📊 **Seçilen firma tipleri:** {', '.join(selected_types)}")

col_send1, col_send2 = st.columns(2)
with col_send1:
    do_g = st.button("🚀 G Adımını Çalıştır (E-posta Gönder)", type="primary")
with col_send2:
    send_test_only = st.button("🧪 Sadece Test Email Gönder", help="Sadece test adresine gönder")

if do_g or send_test_only:
    out_dir = CAMPAIGNS_DIR/active.id/"outputs"
    sent_rows=[]
    
    # Load and filter data from C step
    C_path = out_dir/"C_search_results.csv"
    companies_with_emails = []
    
    if C_path.exists():
        cdf = pd.read_csv(C_path)
        
        # Apply company type filtering if enabled
        if filter_by_type and selected_types:
            if "Firma Tipi" in cdf.columns:
                cdf = cdf[cdf["Firma Tipi"].isin(selected_types)]
                st.info(f"🎯 Firma tipi filtrelemesi uygulandı: {len(cdf)} firma seçildi")
            else:
                st.warning("⚠️ Firma Tipi sütunu bulunamadı. Filtreleme atlanıyor.")
        
        # Limit the number of companies
        cdf = cdf.head(send_count)
        
        # Extract email addresses and company info - her firma için ayrı ayrı
        for _, r in cdf.iterrows():
            emails = str(r.get("Email Adresleri",""))
            company_name = str(r.get("Firma Adı",""))
            company_type = str(r.get("Firma Tipi",""))
            website = str(r.get("Firma Websitesi",""))
            
            if emails and emails != "nan" and emails.strip():
                # E-posta adreslerini ayır ve temizle
                email_list = []
                for e in emails.split(";"):
                    e = e.strip()
                    if e and "@" in e:
                        email_list.append(e)
                
                if email_list:
                    companies_with_emails.append({
                        "company_name": company_name,
                        "company_type": company_type,
                        "website": website,
                        "emails": email_list
                    })
    
    # Enrichment verilerini de ekle
    if use_enriched:
        E_path = out_dir/"E_enriched_contacts.csv"
        if E_path.exists():
            edf = pd.read_csv(E_path).head(send_count)
            for _, r in edf.iterrows():
                e = str(r.get("Email","")).strip()
                company_name = str(r.get("Firma Adı","") or "Enriched Contact")
                if e and "@" in e:
                    companies_with_emails.append({
                        "company_name": company_name,
                        "company_type": "Enriched",
                        "website": "",
                        "emails": [e]
                    })
    
    if not companies_with_emails:
        st.error("❌ Gönderilecek email adresi bulunamadı. C adımından veri toplandığından emin olun.")
        st.stop()
    
    # Toplam e-posta sayısını hesapla
    total_emails = sum(len(company["emails"]) for company in companies_with_emails)
    st.info(f"📊 **Gönderim özeti:** {len(companies_with_emails)} firma, {total_emails} e-posta adresine {content_source} içerik gönderilecek")

    # Test email functionality
    if send_test_only and test_email and "@" in test_email:
        if content_source.startswith("F"):
            F_path = out_dir/"F_personalized_emails.csv"
            if not F_path.exists():
                st.error("F kişiselleştirilmiş içerikler bulunamadı.")
            else:
                fdf = pd.read_csv(F_path)
                if len(fdf) > 0:
                    # İlk kişiselleştirilmiş içeriği kullan
                    test_subject = fdf.iloc[0]["Konu"]
                    test_body = str(fdf.iloc[0]["İçerik"] or "")
                    
                    # HTML içerik kontrolü
                    is_html_template = fdf.iloc[0].get("Şablon_Tipi") == "HTML"
                    html_content = fdf.iloc[0].get("HTML_İçerik", "") if is_html_template else None
                    
                    try:
                        send_email_smtp(
                            host=smtp_host, port=int(smtp_port), username=smtp_user, password=smtp_pass,
                            from_name=smtp_from_name, from_email=smtp_from_email, to_email=test_email,
                            subject=test_subject, 
                            body_html=html_content if is_html_template else None, 
                            body_text=test_body if not is_html_template else None, 
                            use_tls=smtp_tls
                        )
                        st.success(f"✅ Test emaili gönderildi: {test_email}")
                        st.info(f"**Konu:** {test_subject}")
                        
                        if is_html_template:
                            st.info("📧 HTML email gönderildi")
                            with st.expander("HTML Önizleme"):
                                st.components.v1.html(html_content, height=300, scrolling=True)
                        else:
                            st.text_area("Gönderilen içerik:", test_body, height=200, disabled=True)
                    except Exception as e:
                        st.error(f"❌ Test email hatası: {e}")
        else:
            # Şablon içeriği
            try:
                send_email_smtp(
                    host=smtp_host, port=int(smtp_port), username=smtp_user, password=smtp_pass,
                    from_name=smtp_from_name, from_email=smtp_from_email, to_email=test_email,
                    subject=subject_input, body_html=template if mode=="HTML" else None, 
                    body_text=template if mode=="Plain Text" else None, use_tls=smtp_tls
                )
                st.success(f"✅ Test emaili gönderildi: {test_email}")
                st.info(f"**Konu:** {subject_input}")
                st.text_area("Gönderilen içerik:", template, height=200, disabled=True)
            except Exception as e:
                st.error(f"❌ Test email hatası: {e}")
        st.stop()
    
    # Test email before bulk send
    if send_test_first and test_email and "@" in test_email and not send_test_only:
        st.info("🧪 Önce test emaili gönderiliyor...")
        if content_source.startswith("F"):
            F_path = out_dir/"F_personalized_emails.csv"
            if F_path.exists():
                fdf = pd.read_csv(F_path)
                if len(fdf) > 0:
                    test_subject = fdf.iloc[0]["Konu"]
                    test_body = str(fdf.iloc[0]["İçerik"] or "")
                    
                    # HTML içerik kontrolü
                    is_html_template = fdf.iloc[0].get("Şablon_Tipi") == "HTML"
                    html_content = fdf.iloc[0].get("HTML_İçerik", "") if is_html_template else None
                    
                    try:
                        send_email_smtp(
                            host=smtp_host, port=int(smtp_port), username=smtp_user, password=smtp_pass,
                            from_name=smtp_from_name, from_email=smtp_from_email, to_email=test_email,
                            subject=test_subject, 
                            body_html=html_content if is_html_template else None,
                            body_text=test_body if not is_html_template else None, 
                            use_tls=smtp_tls
                        )
                        st.success(f"✅ Test emaili gönderildi: {test_email}")
                    except Exception as e:
                        st.warning(f"⚠️ Test email hatası: {e}")
        else:
            try:
                send_email_smtp(
                    host=smtp_host, port=int(smtp_port), username=smtp_user, password=smtp_pass,
                    from_name=smtp_from_name, from_email=smtp_from_email, to_email=test_email,
                    subject=subject_input, body_html=template if mode=="HTML" else None,
                    body_text=template if mode=="Plain Text" else None, use_tls=smtp_tls
                )
                st.success(f"✅ Test emaili gönderildi: {test_email}")
            except Exception as e:
                st.warning(f"⚠️ Test email hatası: {e}")
    
    # Skip bulk sending if only test was requested
    if send_test_only:
        st.stop()
    
    # content
    if content_source.startswith("F"):
        F_path = out_dir/"F_personalized_emails.csv"
        if not F_path.exists():
            st.error("F kişiselleştirilmiş içerikler bulunamadı.")
        else:
            fdf = pd.read_csv(F_path)
            
            # F verilerini firma adına göre indeksle
            f_data_by_company = {}
            for _, row in fdf.iterrows():
                company_name = str(row.get("Firma", "")).strip()
                if company_name:
                    f_data_by_company[company_name] = row
            
            # Her firma için ayrı ayrı gönder
            for company_data in companies_with_emails:
                company_name = company_data["company_name"]
                emails = company_data["emails"]
                
                # Bu firma için F adımında üretilen içeriği bul
                if company_name in f_data_by_company:
                    row_data = f_data_by_company[company_name]
                    personalized_subject = row_data["Konu"]
                    body_text = str(row_data["İçerik"] or "")
                    
                    # HTML şablon kontrolü
                    is_html_template = row_data.get("Şablon_Tipi") == "HTML"
                    
                    if is_html_template:
                        html_content = row_data.get("HTML_İçerik", body_text)
                        body_html = html_content
                        body_text_final = None
                    else:
                        if "HTML" in mode:
                            body_html = "<div>" + body_text.replace("\n", "<br>") + "</div>"
                            body_text_final = body_text
                        else:
                            body_html = None
                            body_text_final = body_text
                    
                    # Bu firmanın tüm e-posta adreslerine ayrı ayrı gönder
                    for email_address in emails:
                        try:
                            send_email_smtp(
                                host=smtp_host, port=int(smtp_port), username=smtp_user, password=smtp_pass,
                                from_name=smtp_from_name, from_email=smtp_from_email, to_email=email_address,
                                subject=personalized_subject, 
                                body_html=body_html, 
                                body_text=body_text_final, 
                                use_tls=smtp_tls
                            )
                            email_type = "HTML" if is_html_template else "Text"
                            sent_rows.append({
                                "company": company_name,
                                "to": email_address,
                                "subject": personalized_subject,
                                "type": email_type,
                                "status": "sent"
                            })
                        except ConnectionError as e:
                            error_msg = f"Bağlantı hatası: {str(e)}"
                            sent_rows.append({
                                "company": company_name,
                                "to": email_address,
                                "subject": personalized_subject,
                                "type": "Error",
                                "status": error_msg
                            })
                            st.warning(f"⚠️ {email_address} ({company_name}) için bağlantı hatası: {error_msg}")
                        except Exception as e:
                            error_msg = f"SMTP hatası: {str(e)}"
                            sent_rows.append({
                                "company": company_name,
                                "to": email_address,
                                "subject": personalized_subject,
                                "type": "Error",
                                "status": error_msg
                            })
                            st.warning(f"⚠️ {email_address} ({company_name}) için email gönderilemedi: {error_msg}")
                else:
                    # F adımında bu firma için içerik bulunamadı
                    st.warning(f"⚠️ {company_name} için F adımında üretilmiş içerik bulunamadı, atlanıyor...")
    else:
        # Use template directly - her firma için ayrı ayrı gönder
        subj = subject_input
        body_txt = template if mode=="Plain Text" else None
        body_htm = template if mode=="HTML" else None
        
        for company_data in companies_with_emails:
            company_name = company_data["company_name"]
            emails = company_data["emails"]
            
            for email_address in emails:
                try:
                    send_email_smtp(
                        host=smtp_host, port=int(smtp_port), username=smtp_user, password=smtp_pass,
                        from_name=smtp_from_name, from_email=smtp_from_email, to_email=email_address,
                        subject=subj, body_html=body_htm, body_text=body_txt, use_tls=smtp_tls
                    )
                    sent_rows.append({
                        "company": company_name,
                        "to": email_address,
                        "subject": subj,
                        "status": "sent"
                    })
                except ConnectionError as e:
                    error_msg = f"Bağlantı hatası: {str(e)}"
                    sent_rows.append({
                        "company": company_name,
                        "to": email_address,
                        "subject": subj,
                        "status": error_msg
                    })
                    st.warning(f"⚠️ {email_address} ({company_name}) için bağlantı hatası: {error_msg}")
                except Exception as e:
                    error_msg = f"SMTP hatası: {str(e)}"
                    sent_rows.append({
                        "company": company_name,
                        "to": email_address,
                        "subject": subj,
                        "status": error_msg
                    })
                    st.warning(f"⚠️ {email_address} ({company_name}) için email gönderilemedi: {error_msg}")
    if sent_rows:
        sdf = pd.DataFrame(sent_rows)
        sdf.to_csv(out_dir/"G_sent_log.csv", index=False, encoding="utf-8-sig")
        successful_sends = sum(1 for r in sent_rows if r['status']=='sent')
        st.success(f"📧 Gönderim tamamlandı! {successful_sends}/{len(sent_rows)} başarılı.")
        
        # Gönderim istatistikleri
        html_count = sum(1 for r in sent_rows if r.get('type') == 'HTML' and r['status'] == 'sent')
        text_count = sum(1 for r in sent_rows if r.get('type') == 'Text' and r['status'] == 'sent')
        
        col_stats1, col_stats2, col_stats3 = st.columns(3)
        with col_stats1:
            st.metric("📧 Toplam Başarılı", successful_sends)
        with col_stats2:
            st.metric("🎨 HTML Email", html_count)
        with col_stats3:
            st.metric("📝 Text Email", text_count)
        
        # Başarılı ve başarısız gönderimler için ayrı gösterim
        col_success, col_error = st.columns(2)
        with col_success:
            successful = sdf[sdf['status'] == 'sent']
            if len(successful) > 0:
                st.subheader(f"✅ Başarılı ({len(successful)})")
                st.dataframe(successful, use_container_width=True)
        
        with col_error:
            failed = sdf[sdf['status'] != 'sent']
            if len(failed) > 0:
                st.subheader(f"❌ Başarısız ({len(failed)})")
                st.dataframe(failed, use_container_width=True)
        
        # Tam log
        with st.expander("📋 Detaylı Log"):
            st.dataframe(sdf, use_container_width=True)


# 3H) IMAP ile Geri Dönüş İzleme
st.header("H) IMAP ile Geri Dönüş İzleme")
imap_host = st.text_input("IMAP Host", os.getenv("IMAP_HOST",""))
imap_port = st.number_input("IMAP Port", 1, 65535, int(os.getenv("IMAP_PORT","993")))
imap_user = st.text_input("IMAP Username", os.getenv("IMAP_USERNAME",""))
imap_pass = st.text_input("IMAP Password", os.getenv("IMAP_PASSWORD",""), type="password")
do_h = st.button("H Çalıştır (IMAP)")
if do_h:
    out_dir = CAMPAIGNS_DIR/active.id/"outputs"
    df = fetch_important(imap_host, int(imap_port), imap_user, imap_pass, limit=300)
    df.to_csv(out_dir/"H_important_replies.csv", index=False, encoding="utf-8-sig")
    st.success(f"Önemli dönüş: {len(df)}")
    st.dataframe(df.head(50))

# 3I) Otomatik Form Doldurma & Gönderme
st.header("I) Websiteler üzerinde Otomatik Form Doldurma & Gönderme")

# Veri kaynağı seçimi
col_i1, col_i2 = st.columns(2)
with col_i1:
    st.subheader("📊 Veri Kaynağı")
    data_source = st.radio(
        "Hangi sitelere form gönderilecek?",
        ["C adımından toplanan siteler", "Özel domain listesi (.txt)"],
        help="C adımından toplanan siteleri kullanın veya kendi domain listenizi yükleyin"
    )
    
    custom_file = None
    if data_source == "Özel domain listesi (.txt)":
        custom_file = st.file_uploader("Domain listesi .txt (her satır 1 domain/URL)", type=["txt"])

with col_i2:
    st.subheader("⚙️ Form Ayarları")
    max_sites = st.select_slider("Maksimum site sayısı", options=[5,10,20,30,50,100], value=20)
    dwell_forms = st.select_slider("Site başı bekleme süresi (saniye)", options=[3,5,8,10,15,20], value=8)
    headless_forms = st.checkbox("Headless (görünmez tarayıcı)", value=False, help="Tarayıcı görünür olsun ki işlemleri takip edebilin")

# Gelişmiş Ayarlar
st.subheader("⚙️ Gelişmiş Ayarlar")
col_adv1, col_adv2 = st.columns(2)
with col_adv1:
    st.info("🔧 **Otomatik Optimizasyon:** Sistem otomatik olarak en iyi performansı sağlar")
with col_adv2:
    st.info("🛡️ **Güvenlik:** Gelişmiş anti-detection teknikleri aktif")

# Form bilgileri
st.subheader("📝 Form Bilgileri")
col_form1, col_form2 = st.columns(2)
with col_form1:
    name = st.text_input("İsim", "John")
    surname = st.text_input("Soyisim", "Smith")
    email_addr = st.text_input("Email", "john.smith@company.com")
with col_form2:
    phone = st.text_input("Telefon", "+1-555-0123")
    subject_line = st.text_input("Konu", "Business Partnership Inquiry")
    company_name = st.text_input("Şirket Adı", active.firm_name)

# Mesaj içeriği
st.subheader("💬 Mesaj İçeriği")
form_content_source = st.selectbox(
    "Form Mesaj İçerik Kaynağı",
    ["F adımı kişiselleştirilmiş", "Özel mesaj", "Şablon"],
    help="F adımından kişiselleştirilmiş içerik kullanın veya özel mesaj yazın"
)

if form_content_source == "Özel mesaj":
    message_txt = st.text_area("Mesaj", height=150, placeholder="Kişiselleştirilmiş mesaj içeriği...")
else:
    message_txt = ""

do_i = st.button("🚀 I Adımını Çalıştır (Form Doldurma)", type="primary")
if do_i:
    out_dir = CAMPAIGNS_DIR/active.id/"outputs"
    
    # Veri kaynağını belirle
    websites_to_visit = []
    
    if data_source == "Özel domain listesi (.txt)":
        if custom_file is not None:
            raw = custom_file.read().decode("utf-8", errors="ignore")
            websites_to_visit = [ln.strip() for ln in raw.splitlines() if ln.strip()]
            if not websites_to_visit:
                st.error("❌ Yüklediğiniz .txt dosyasında geçerli bir domain/URL bulunamadı.")
                st.stop()
        else:
            st.error("❌ Lütfen domain listesi dosyasını yükleyin.")
            st.stop()
    else:
        # C adımından veri al
        C_path = out_dir/"C_search_results.csv"
        if not C_path.exists():
            st.error("❌ C adımı verisi bulunamadı. Önce C adımını çalıştırın.")
            st.stop()
        
        # C verisini oku ve website listesini çıkar
        c_df = pd.read_csv(C_path)
        if "Firma Websitesi" in c_df.columns:
            websites_to_visit = c_df["Firma Websitesi"].dropna().tolist()
        else:
            st.error("❌ C verisinde 'Firma Websitesi' sütunu bulunamadı.")
            st.stop()
    
    # Website listesini sınırla
    websites_to_visit = websites_to_visit[:max_sites]
    
    if not websites_to_visit:
        st.error("❌ Ziyaret edilecek website bulunamadı.")
        st.stop()
    
    # F adımından kişiselleştirilmiş içerikleri al
    f_map = {}
    F_path = out_dir/"F_personalized_emails.csv"
    if F_path.exists() and form_content_source == "F adımı kişiselleştirilmiş":
        fdf = pd.read_csv(F_path)
        for _, r in fdf.iterrows():
            company = str(r.get("Firma", "")).strip()
            content = str(r.get("İçerik", "")).strip()
            if company and content:
                f_map[company] = content
    
    # Form payload hazırla
    form_payload = {
        "name": name,
        "surname": surname,
        "email": email_addr,
        "phone": phone,
        "subject": subject_line,
        "company": company_name,
        "message": message_txt
    }
    
    # Progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()
    results_container = st.empty()
    
    st.info(f"🎯 **{len(websites_to_visit)} website** ziyaret edilecek")
    
    try:
        with st.spinner("🤖 Websitelerde otomatik form doldurma başlıyor..."):
            # batch_fill_from_df fonksiyonunu çağır
            results_df = batch_fill_from_df(
                df=pd.DataFrame({"Firma Websitesi": websites_to_visit}),
                form_payload=form_payload,
                max_sites=max_sites,
                dwell_seconds=float(dwell_forms),
                headless=headless_forms,
                # CAPTCHA sistemi kaldırıldı
                domain_list_file=None,  # Zaten website listesi hazır
                personalized_content_map=f_map if f_map else None
            )
        
        progress_bar.progress(100)
        status_text.success("✅ Form doldurma tamamlandı!")
        
        if len(results_df) > 0:
            # Sonuçları kaydet
            results_df.to_csv(out_dir/"I_form_results.csv", index=False, encoding="utf-8-sig")
            
            # Başarı istatistikleri
            success_count = len(results_df[results_df.get("Status", "") == "Success"])
            total_count = len(results_df)
            
            st.success(f"🎉 **{success_count}/{total_count}** sitede form başarıyla dolduruldu!")
            
            # Sonuç tablosu
            st.subheader("📋 Form Doldurma Sonuçları")
            st.dataframe(results_df, use_container_width=True)
            
            # İndirme butonu
            csv_data = results_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8')
            st.download_button(
                label="📥 Sonuçları CSV İndir",
                data=csv_data,
                file_name=f"I_form_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )
            
            # Durum dağılımı
            if "Status" in results_df.columns:
                status_counts = results_df["Status"].value_counts()
                st.subheader("📊 Durum Dağılımı")
                for status, count in status_counts.items():
                    st.metric(status, count)
        else:
            st.warning("⚠️ Hiçbir sitede form doldurulamadı.")
            
    except Exception as e:
        progress_bar.progress(0)
        status_text.error(f"❌ Hata: {str(e)}")
        st.error(f"Form doldurma sırasında hata oluştu: {str(e)}")
        st.info("💡 **Çözüm önerileri:**\n- Chrome tarayıcısının güncel olduğundan emin olun\n- Website listesini kontrol edin")
