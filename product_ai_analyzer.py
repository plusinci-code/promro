"""
GPT-5 Powered Product & Manufacturer Analysis System
Ürün ve Üretici Analiz Sistemi - AI Destekli Pazar Analizi ve Öneriler
"""

import openai
import json
import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Product:
    """Ürün bilgi sınıfı"""
    name: str
    category: str
    brand: str
    manufacturer: str
    description: str
    price_range: str
    target_market: List[str]
    
@dataclass
class Manufacturer:
    """Üretici bilgi sınıfı"""
    name: str
    country: str
    industry: str
    products: List[str]
    market_presence: str
    reputation_score: float
    
@dataclass
class MarketAnalysis:
    """Pazar analizi sınıfı"""
    target_customers: List[str]
    market_size: str
    growth_potential: str
    competition_level: str
    price_sensitivity: str
    seasonal_trends: List[str]
    
@dataclass
class Recommendations:
    """Öneri sınıfı"""
    for_buyers: List[str]
    for_manufacturers: List[str]
    market_opportunities: List[str]
    risk_factors: List[str]
    roadmap: List[str]

class ProductAIAnalyzer:
    """GPT-5 destekli ürün ve üretici analiz sistemi"""
    
    def __init__(self, api_key: str):
        """
        AI Analyzer'ı başlat
        
        Args:
            api_key: OpenAI API anahtarı
        """
        self.client = openai.OpenAI(api_key=api_key)
        self.analysis_cache = {}
        
    async def identify_product(self, product_description: str, image_url: Optional[str] = None) -> Product:
        """
        Ürün tanımlama ve analiz
        
        Args:
            product_description: Ürün açıklaması
            image_url: Ürün görseli URL'si (opsiyonel)
            
        Returns:
            Product: Tanımlanmış ürün bilgileri
        """
        try:
            prompt = f"""
            Aşağıdaki ürün açıklamasını analiz et ve detaylı ürün bilgilerini çıkar:
            
            Ürün Açıklaması: {product_description}
            
            Lütfen şu bilgileri JSON formatında ver:
            - name: Ürün adı
            - category: Ürün kategorisi
            - brand: Marka
            - manufacturer: Üretici firma
            - description: Detaylı açıklama
            - price_range: Fiyat aralığı (USD)
            - target_market: Hedef pazar segmentleri
            
            Türkçe ve İngilizce karışık yanıt verebilirsin.
            """
            
            response = await self._call_gpt(prompt)
            product_data = json.loads(response)
            
            return Product(
                name=product_data.get('name', ''),
                category=product_data.get('category', ''),
                brand=product_data.get('brand', ''),
                manufacturer=product_data.get('manufacturer', ''),
                description=product_data.get('description', ''),
                price_range=product_data.get('price_range', ''),
                target_market=product_data.get('target_market', [])
            )
            
        except Exception as e:
            logger.error(f"Ürün tanımlama hatası: {e}")
            raise
    
    async def analyze_manufacturer(self, manufacturer_name: str) -> Manufacturer:
        """
        Üretici analizi
        
        Args:
            manufacturer_name: Üretici firma adı
            
        Returns:
            Manufacturer: Üretici analiz bilgileri
        """
        try:
            prompt = f"""
            '{manufacturer_name}' adlı üretici firma hakkında detaylı analiz yap:
            
            Şu bilgileri JSON formatında ver:
            - name: Firma adı
            - country: Ülke
            - industry: Sektör
            - products: Ana ürün grupları
            - market_presence: Pazar varlığı (Global/Regional/Local)
            - reputation_score: İtibar skoru (0-10 arası)
            
            Güncel pazar bilgilerini kullan.
            """
            
            response = await self._call_gpt(prompt)
            manufacturer_data = json.loads(response)
            
            return Manufacturer(
                name=manufacturer_data.get('name', ''),
                country=manufacturer_data.get('country', ''),
                industry=manufacturer_data.get('industry', ''),
                products=manufacturer_data.get('products', []),
                market_presence=manufacturer_data.get('market_presence', ''),
                reputation_score=float(manufacturer_data.get('reputation_score', 0))
            )
            
        except Exception as e:
            logger.error(f"Üretici analizi hatası: {e}")
            raise
    
    async def market_analysis(self, product: Product, target_region: str = "Turkey") -> MarketAnalysis:
        """
        Pazar analizi
        
        Args:
            product: Ürün bilgileri
            target_region: Hedef bölge
            
        Returns:
            MarketAnalysis: Pazar analiz sonuçları
        """
        try:
            prompt = f"""
            {product.name} ürünü için {target_region} pazarında detaylı analiz yap:
            
            Ürün Bilgileri:
            - Kategori: {product.category}
            - Marka: {product.brand}
            - Üretici: {product.manufacturer}
            - Fiyat Aralığı: {product.price_range}
            
            Şu bilgileri JSON formatında ver:
            - target_customers: Hedef müşteri grupları
            - market_size: Pazar büyüklüğü tahmini
            - growth_potential: Büyüme potansiyeli
            - competition_level: Rekabet seviyesi
            - price_sensitivity: Fiyat hassasiyeti
            - seasonal_trends: Mevsimsel trendler
            
            Türkiye pazarına özel bilgiler ver.
            """
            
            response = await self._call_gpt(prompt)
            market_data = json.loads(response)
            
            return MarketAnalysis(
                target_customers=market_data.get('target_customers', []),
                market_size=market_data.get('market_size', ''),
                growth_potential=market_data.get('growth_potential', ''),
                competition_level=market_data.get('competition_level', ''),
                price_sensitivity=market_data.get('price_sensitivity', ''),
                seasonal_trends=market_data.get('seasonal_trends', [])
            )
            
        except Exception as e:
            logger.error(f"Pazar analizi hatası: {e}")
            raise
    
    async def generate_recommendations(self, product: Product, manufacturer: Manufacturer, 
                                    market_analysis: MarketAnalysis) -> Recommendations:
        """
        Kapsamlı öneriler üret
        
        Args:
            product: Ürün bilgileri
            manufacturer: Üretici bilgileri
            market_analysis: Pazar analizi
            
        Returns:
            Recommendations: Öneriler ve yol haritası
        """
        try:
            prompt = f"""
            Aşağıdaki bilgilere dayalı kapsamlı öneriler ve yol haritası oluştur:
            
            ÜRÜN: {product.name} - {product.category}
            ÜRETİCİ: {manufacturer.name} - {manufacturer.country}
            PAZAR: {market_analysis.market_size} - {market_analysis.competition_level}
            
            Şu kategorilerde öneriler ver (JSON formatında):
            
            1. for_buyers: Alıcılar için öneriler
            2. for_manufacturers: Üreticiler için öneriler  
            3. market_opportunities: Pazar fırsatları
            4. risk_factors: Risk faktörleri
            5. roadmap: 6-12 aylık yol haritası adımları
            
            Pratik ve uygulanabilir öneriler ver.
            """
            
            response = await self._call_gpt(prompt)
            recommendations_data = json.loads(response)
            
            return Recommendations(
                for_buyers=recommendations_data.get('for_buyers', []),
                for_manufacturers=recommendations_data.get('for_manufacturers', []),
                market_opportunities=recommendations_data.get('market_opportunities', []),
                risk_factors=recommendations_data.get('risk_factors', []),
                roadmap=recommendations_data.get('roadmap', [])
            )
            
        except Exception as e:
            logger.error(f"Öneri üretme hatası: {e}")
            raise
    
    async def comprehensive_analysis(self, product_description: str, 
                                   target_region: str = "Turkey") -> Dict:
        """
        Kapsamlı analiz - tüm modülleri birleştir
        
        Args:
            product_description: Ürün açıklaması
            target_region: Hedef bölge
            
        Returns:
            Dict: Tüm analiz sonuçları
        """
        try:
            # 1. Ürün tanımlama
            product = await self.identify_product(product_description)
            
            # 2. Üretici analizi
            manufacturer = await self.analyze_manufacturer(product.manufacturer)
            
            # 3. Pazar analizi
            market_analysis = await self.market_analysis(product, target_region)
            
            # 4. Öneriler
            recommendations = await self.generate_recommendations(
                product, manufacturer, market_analysis
            )
            
            # Sonuçları birleştir
            return {
                'timestamp': datetime.now().isoformat(),
                'product': product.__dict__,
                'manufacturer': manufacturer.__dict__,
                'market_analysis': market_analysis.__dict__,
                'recommendations': recommendations.__dict__,
                'summary': await self._generate_summary(product, manufacturer, 
                                                      market_analysis, recommendations)
            }
            
        except Exception as e:
            logger.error(f"Kapsamlı analiz hatası: {e}")
            raise
    
    async def _call_gpt(self, prompt: str, model: str = "gpt-4") -> str:
        """GPT API çağrısı"""
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Sen uzman bir pazar analisti ve ürün uzmanısın. Türkçe ve İngilizce karışık yanıt verebilirsin. JSON formatında doğru ve yapılandırılmış yanıtlar ver."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"GPT API hatası: {e}")
            raise
    
    async def _generate_summary(self, product: Product, manufacturer: Manufacturer,
                              market_analysis: MarketAnalysis, recommendations: Recommendations) -> str:
        """Analiz özeti üret"""
        try:
            prompt = f"""
            Aşağıdaki analiz sonuçlarının kısa ve öz bir özetini oluştur:
            
            Ürün: {product.name} ({product.category})
            Üretici: {manufacturer.name} - İtibar: {manufacturer.reputation_score}/10
            Pazar: {market_analysis.market_size} - Rekabet: {market_analysis.competition_level}
            
            3-4 cümlelik öz bir değerlendirme yap.
            """
            
            return await self._call_gpt(prompt)
        except Exception as e:
            logger.error(f"Özet üretme hatası: {e}")
            return "Özet üretilemedi."

# Kullanım örneği
async def main():
    """Test fonksiyonu"""
    # API anahtarını .env dosyasından al
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        print("OPENAI_API_KEY bulunamadı!")
        return
    
    analyzer = ProductAIAnalyzer(api_key)
    
    # Test analizi
    product_desc = "Samsung Galaxy S24 Ultra akıllı telefon, 256GB depolama, 12GB RAM"
    
    try:
        result = await analyzer.comprehensive_analysis(product_desc, "Turkey")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Hata: {e}")

if __name__ == "__main__":
    asyncio.run(main())
