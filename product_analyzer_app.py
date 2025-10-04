"""
GPT-5 Powered Product & Manufacturer Analysis Web Interface
Streamlit tabanlı web arayüzü
"""

import streamlit as st
import asyncio
import json
import os
import sys
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import Dict, Any

# Ana dizini path'e ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from product_ai_analyzer import ProductAIAnalyzer

# Sayfa konfigürasyonu
st.set_page_config(
    page_title="AI Product Analyzer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS stilleri
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #667eea;
    }
    .recommendation-box {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #28a745;
        margin: 1rem 0;
    }
    .risk-box {
        background: #fff3cd;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #ffc107;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

def initialize_session_state():
    """Session state'i başlat"""
    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = None
    if 'analyzer' not in st.session_state:
        st.session_state.analyzer = None

def load_analyzer():
    """AI Analyzer'ı yükle"""
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        st.error("⚠️ OPENAI_API_KEY environment variable bulunamadı!")
        st.info("Lütfen .env dosyanızda OPENAI_API_KEY'i tanımlayın.")
        return None
    
    try:
        return ProductAIAnalyzer(api_key)
    except Exception as e:
        st.error(f"AI Analyzer yüklenirken hata: {e}")
        return None

async def run_analysis(analyzer, product_description, target_region):
    """Analizi çalıştır"""
    try:
        return await analyzer.comprehensive_analysis(product_description, target_region)
    except Exception as e:
        st.error(f"Analiz hatası: {e}")
        return None

def display_product_info(product_data: Dict):
    """Ürün bilgilerini göster"""
    st.subheader("📱 Ürün Bilgileri")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <h4>Ürün Adı</h4>
            <p>{product_data.get('name', 'N/A')}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <h4>Kategori</h4>
            <p>{product_data.get('category', 'N/A')}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <h4>Marka</h4>
            <p>{product_data.get('brand', 'N/A')}</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.write(f"**Açıklama:** {product_data.get('description', 'N/A')}")
    st.write(f"**Fiyat Aralığı:** {product_data.get('price_range', 'N/A')}")
    
    # Hedef pazar
    if product_data.get('target_market'):
        st.write("**Hedef Pazarlar:**")
        for market in product_data['target_market']:
            st.write(f"• {market}")

def display_manufacturer_info(manufacturer_data: Dict):
    """Üretici bilgilerini göster"""
    st.subheader("🏭 Üretici Analizi")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Firma", manufacturer_data.get('name', 'N/A'))
    
    with col2:
        st.metric("Ülke", manufacturer_data.get('country', 'N/A'))
    
    with col3:
        st.metric("Sektör", manufacturer_data.get('industry', 'N/A'))
    
    with col4:
        reputation = manufacturer_data.get('reputation_score', 0)
        st.metric("İtibar Skoru", f"{reputation}/10")
    
    # İtibar skoru grafiği
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = reputation,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "İtibar Skoru"},
        delta = {'reference': 7},
        gauge = {
            'axis': {'range': [None, 10]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, 5], 'color': "lightgray"},
                {'range': [5, 8], 'color': "gray"},
                {'range': [8, 10], 'color': "green"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 9
            }
        }
    ))
    fig.update_layout(height=300)
    st.plotly_chart(fig, use_container_width=True)
    
    # Ürün grupları
    if manufacturer_data.get('products'):
        st.write("**Ana Ürün Grupları:**")
        for product in manufacturer_data['products']:
            st.write(f"• {product}")

def display_market_analysis(market_data: Dict):
    """Pazar analizini göster"""
    st.subheader("📊 Pazar Analizi")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Hedef Müşteriler:**")
        if market_data.get('target_customers'):
            for customer in market_data['target_customers']:
                st.write(f"• {customer}")
        
        st.write(f"**Pazar Büyüklüğü:** {market_data.get('market_size', 'N/A')}")
        st.write(f"**Büyüme Potansiyeli:** {market_data.get('growth_potential', 'N/A')}")
    
    with col2:
        st.write(f"**Rekabet Seviyesi:** {market_data.get('competition_level', 'N/A')}")
        st.write(f"**Fiyat Hassasiyeti:** {market_data.get('price_sensitivity', 'N/A')}")
        
        # Mevsimsel trendler
        if market_data.get('seasonal_trends'):
            st.write("**Mevsimsel Trendler:**")
            for trend in market_data['seasonal_trends']:
                st.write(f"• {trend}")

def display_recommendations(recommendations_data: Dict):
    """Önerileri göster"""
    st.subheader("💡 Öneriler ve Yol Haritası")
    
    # Alıcılar için öneriler
    if recommendations_data.get('for_buyers'):
        st.markdown("### 🛒 Alıcılar İçin Öneriler")
        for rec in recommendations_data['for_buyers']:
            st.markdown(f"""
            <div class="recommendation-box">
                • {rec}
            </div>
            """, unsafe_allow_html=True)
    
    # Üreticiler için öneriler
    if recommendations_data.get('for_manufacturers'):
        st.markdown("### 🏭 Üreticiler İçin Öneriler")
        for rec in recommendations_data['for_manufacturers']:
            st.markdown(f"""
            <div class="recommendation-box">
                • {rec}
            </div>
            """, unsafe_allow_html=True)
    
    # Pazar fırsatları
    if recommendations_data.get('market_opportunities'):
        st.markdown("### 🎯 Pazar Fırsatları")
        for opp in recommendations_data['market_opportunities']:
            st.markdown(f"""
            <div class="recommendation-box">
                • {opp}
            </div>
            """, unsafe_allow_html=True)
    
    # Risk faktörleri
    if recommendations_data.get('risk_factors'):
        st.markdown("### ⚠️ Risk Faktörleri")
        for risk in recommendations_data['risk_factors']:
            st.markdown(f"""
            <div class="risk-box">
                • {risk}
            </div>
            """, unsafe_allow_html=True)
    
    # Yol haritası
    if recommendations_data.get('roadmap'):
        st.markdown("### 🗺️ 6-12 Aylık Yol Haritası")
        for i, step in enumerate(recommendations_data['roadmap'], 1):
            st.write(f"**{i}.** {step}")

def export_results(results: Dict):
    """Sonuçları dışa aktar"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"product_analysis_{timestamp}.json"
    
    # JSON olarak kaydet
    json_str = json.dumps(results, indent=2, ensure_ascii=False)
    st.download_button(
        label="📥 Analiz Sonuçlarını İndir (JSON)",
        data=json_str,
        file_name=filename,
        mime="application/json"
    )

def main():
    """Ana uygulama"""
    initialize_session_state()
    
    # Ana başlık
    st.markdown("""
    <div class="main-header">
        <h1>🤖 GPT-5 Powered Product Analyzer</h1>
        <p>Ürün ve Üretici Analizi • Pazar İnceleme • AI Destekli Öneriler</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    st.sidebar.title("⚙️ Ayarlar")
    
    # API Key kontrolü
    if not os.getenv('OPENAI_API_KEY'):
        st.sidebar.error("OPENAI_API_KEY bulunamadı!")
        st.sidebar.info("Lütfen .env dosyanızda API anahtarınızı tanımlayın.")
        return
    
    # Hedef bölge seçimi
    target_region = st.sidebar.selectbox(
        "🌍 Hedef Bölge",
        ["Turkey", "Europe", "North America", "Asia", "Global"],
        index=0
    )
    
    # Dil seçimi
    language = st.sidebar.selectbox(
        "🗣️ Dil",
        ["Türkçe", "English"],
        index=0
    )
    
    # Ana içerik
    st.subheader("🔍 Ürün Analizi")
    
    # Ürün açıklama girişi
    product_description = st.text_area(
        "Ürün Açıklaması",
        placeholder="Örnek: iPhone 15 Pro Max, 256GB, Titanium Blue...",
        height=100
    )
    
    # Görsel yükleme (opsiyonel)
    uploaded_image = st.file_uploader(
        "Ürün Görseli (Opsiyonel)",
        type=['png', 'jpg', 'jpeg'],
        help="Ürün görselini yükleyerek daha detaylı analiz alabilirsiniz."
    )
    
    # Analiz butonu
    if st.button("🚀 Analizi Başlat", type="primary"):
        if not product_description.strip():
            st.error("Lütfen ürün açıklaması girin!")
            return
        
        # Analyzer'ı yükle
        if not st.session_state.analyzer:
            st.session_state.analyzer = load_analyzer()
        
        if not st.session_state.analyzer:
            return
        
        # Progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Analizi çalıştır
            status_text.text("🔍 Ürün tanımlanıyor...")
            progress_bar.progress(25)
            
            # Asyncio event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            status_text.text("🏭 Üretici analiz ediliyor...")
            progress_bar.progress(50)
            
            status_text.text("📊 Pazar analizi yapılıyor...")
            progress_bar.progress(75)
            
            status_text.text("💡 Öneriler üretiliyor...")
            progress_bar.progress(90)
            
            # Analizi çalıştır
            results = loop.run_until_complete(
                run_analysis(st.session_state.analyzer, product_description, target_region)
            )
            
            progress_bar.progress(100)
            status_text.text("✅ Analiz tamamlandı!")
            
            if results:
                st.session_state.analysis_results = results
                st.success("Analiz başarıyla tamamlandı!")
            else:
                st.error("Analiz sırasında bir hata oluştu.")
                
        except Exception as e:
            st.error(f"Hata: {e}")
        finally:
            progress_bar.empty()
            status_text.empty()
    
    # Sonuçları göster
    if st.session_state.analysis_results:
        results = st.session_state.analysis_results
        
        # Özet
        if results.get('summary'):
            st.info(f"**Özet:** {results['summary']}")
        
        # Sekmeler
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📱 Ürün", "🏭 Üretici", "📊 Pazar", "💡 Öneriler", "📥 Dışa Aktar"
        ])
        
        with tab1:
            if results.get('product'):
                display_product_info(results['product'])
        
        with tab2:
            if results.get('manufacturer'):
                display_manufacturer_info(results['manufacturer'])
        
        with tab3:
            if results.get('market_analysis'):
                display_market_analysis(results['market_analysis'])
        
        with tab4:
            if results.get('recommendations'):
                display_recommendations(results['recommendations'])
        
        with tab5:
            st.subheader("📥 Sonuçları Dışa Aktar")
            export_results(results)
            
            # JSON görüntüleme
            if st.checkbox("JSON Verilerini Göster"):
                st.json(results)

if __name__ == "__main__":
    main()
