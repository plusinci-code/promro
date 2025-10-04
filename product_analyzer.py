# app/modules/product_analyzer.py

import json
import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import logging
from .llm import complete

logger = logging.getLogger(__name__)

@dataclass
class ProductInfo:
    """Ürün bilgi sınıfı"""
    name: str
    category: str
    brand: str
    manufacturer: str
    description: str
    price_range: str
    target_market: List[str]
    use_cases: List[str]

@dataclass
class ManufacturerInfo:
    """Üretici bilgi sınıfı"""
    name: str
    country: str
    industry: str
    products: List[str]
    market_presence: str
    reputation_score: float
    strengths: List[str]
    weaknesses: List[str]

@dataclass
class MarketAnalysis:
    """Pazar analizi sınıfı"""
    target_customers: List[str]
    market_size: str
    growth_potential: str
    competition_level: str
    price_sensitivity: str
    seasonal_trends: List[str]
    entry_barriers: List[str]
    opportunities: List[str]

@dataclass
class BuyerRecommendations:
    """Alıcı önerileri"""
    who_should_buy: List[str]
    purchase_considerations: List[str]
    price_expectations: List[str]
    timing_advice: List[str]
    risk_factors: List[str]

@dataclass
class SellerRecommendations:
    """Satıcı önerileri"""
    target_segments: List[str]
    marketing_strategies: List[str]
    pricing_recommendations: List[str]
    distribution_channels: List[str]
    competitive_advantages: List[str]

@dataclass
class RoadmapItem:
    """Yol haritası öğesi"""
    timeframe: str
    action: str
    priority: str
    expected_outcome: str

@dataclass
class ProductAnalysisResult:
    """Kapsamlı analiz sonucu"""
    timestamp: str
    product: ProductInfo
    manufacturer: ManufacturerInfo
    market_analysis: MarketAnalysis
    buyer_recommendations: BuyerRecommendations
    seller_recommendations: SellerRecommendations
    roadmap: List[RoadmapItem]
    summary: str

def analyze_products_from_campaign(
    products: List[str], 
    firm_name: str, 
    firm_site: str, 
    target_country: str,
    api_key: str,
    model: str = "gpt-4",
    temperature: float = 0.7,
    max_tokens: int = 2000
) -> Dict[str, ProductAnalysisResult]:
    """
    Kampanya ürünlerini analiz et
    
    Args:
        products: Ürün listesi
        firm_name: Firma adı
        firm_site: Firma websitesi
        target_country: Hedef ülke
        api_key: OpenAI API key
        model: AI model
        temperature: Temperature
        max_tokens: Max tokens
        
    Returns:
        Dict[str, ProductAnalysisResult]: Ürün adı -> analiz sonucu
    """
    results = {}
    
    for product in products:
        if not product.strip():
            continue
            
        try:
            result = analyze_single_product(
                product_name=product,
                firm_name=firm_name,
                firm_site=firm_site,
                target_country=target_country,
                api_key=api_key,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens
            )
            results[product] = result
        except Exception as e:
            logger.error(f"Ürün analiz hatası ({product}): {e}")
            
    return results

def analyze_single_product(
    product_name: str,
    firm_name: str,
    firm_site: str,
    target_country: str,
    api_key: str,
    model: str = "gpt-4",
    temperature: float = 0.7,
    max_tokens: int = 2000
) -> ProductAnalysisResult:
    """
    Tek ürün için kapsamlı analiz
    """
    
    # 1. Ürün Tanımlama
    product_info = identify_product(
        product_name, firm_name, firm_site, api_key, model, temperature, max_tokens
    )
    
    # 2. Üretici Analizi
    manufacturer_info = analyze_manufacturer(
        firm_name, firm_site, target_country, api_key, model, temperature, max_tokens
    )
    
    # 3. Pazar Analizi
    market_analysis = analyze_market(
        product_info, manufacturer_info, target_country, api_key, model, temperature, max_tokens
    )
    
    # 4. Alıcı Önerileri
    buyer_recommendations = generate_buyer_recommendations(
        product_info, market_analysis, target_country, api_key, model, temperature, max_tokens
    )
    
    # 5. Satıcı Önerileri
    seller_recommendations = generate_seller_recommendations(
        product_info, manufacturer_info, market_analysis, target_country, api_key, model, temperature, max_tokens
    )
    
    # 6. Yol Haritası
    roadmap = generate_roadmap(
        product_info, manufacturer_info, market_analysis, target_country, api_key, model, temperature, max_tokens
    )
    
    # 7. Özet
    summary = generate_summary(
        product_info, manufacturer_info, market_analysis, buyer_recommendations, seller_recommendations,
        api_key, model, temperature, max_tokens
    )
    
    return ProductAnalysisResult(
        timestamp=datetime.now().isoformat(),
        product=product_info,
        manufacturer=manufacturer_info,
        market_analysis=market_analysis,
        buyer_recommendations=buyer_recommendations,
        seller_recommendations=seller_recommendations,
        roadmap=roadmap,
        summary=summary
    )

def identify_product(
    product_name: str, firm_name: str, firm_site: str,
    api_key: str, model: str, temperature: float, max_tokens: int
) -> ProductInfo:
    """Ürün tanımlama ve detay çıkarma"""
    
    prompt = f"""
    Aşağıdaki ürün hakkında detaylı analiz yap:
    
    Ürün: {product_name}
    Üretici Firma: {firm_name}
    Firma Websitesi: {firm_site}
    
    Şu bilgileri JSON formatında ver:
    {{
        "name": "Ürün adı",
        "category": "Ürün kategorisi",
        "brand": "Marka adı",
        "manufacturer": "Üretici firma",
        "description": "Detaylı ürün açıklaması",
        "price_range": "Tahmini fiyat aralığı (USD)",
        "target_market": ["Hedef pazar segmenti 1", "Segment 2"],
        "use_cases": ["Kullanım alanı 1", "Kullanım alanı 2"]
    }}
    
    Türkçe ve pratik bilgiler ver.
    """
    
    response = complete(prompt, api_key=api_key, model=model, temperature=temperature, max_tokens=max_tokens)
    
    try:
        data = json.loads(response)
        return ProductInfo(
            name=data.get('name', product_name),
            category=data.get('category', ''),
            brand=data.get('brand', ''),
            manufacturer=data.get('manufacturer', firm_name),
            description=data.get('description', ''),
            price_range=data.get('price_range', ''),
            target_market=data.get('target_market', []),
            use_cases=data.get('use_cases', [])
        )
    except json.JSONDecodeError:
        # Fallback
        return ProductInfo(
            name=product_name,
            category="Belirtilmemiş",
            brand="",
            manufacturer=firm_name,
            description=response[:500],
            price_range="Belirtilmemiş",
            target_market=[],
            use_cases=[]
        )

def analyze_manufacturer(
    firm_name: str, firm_site: str, target_country: str,
    api_key: str, model: str, temperature: float, max_tokens: int
) -> ManufacturerInfo:
    """Üretici firma analizi"""
    
    prompt = f"""
    Aşağıdaki üretici firma hakkında detaylı analiz yap:
    
    Firma: {firm_name}
    Website: {firm_site}
    Hedef Pazar: {target_country}
    
    Şu bilgileri JSON formatında ver:
    {{
        "name": "Firma adı",
        "country": "Firma ülkesi",
        "industry": "Sektör/endüstri",
        "products": ["Ana ürün grubu 1", "Ürün grubu 2"],
        "market_presence": "Pazar varlığı (Global/Regional/Local)",
        "reputation_score": 7.5,
        "strengths": ["Güçlü yön 1", "Güçlü yön 2"],
        "weaknesses": ["Zayıf yön 1", "Zayıf yön 2"]
    }}
    
    İtibar skoru 0-10 arası olsun. Güncel pazar bilgilerini kullan.
    """
    
    response = complete(prompt, api_key=api_key, model=model, temperature=temperature, max_tokens=max_tokens)
    
    try:
        data = json.loads(response)
        return ManufacturerInfo(
            name=data.get('name', firm_name),
            country=data.get('country', ''),
            industry=data.get('industry', ''),
            products=data.get('products', []),
            market_presence=data.get('market_presence', ''),
            reputation_score=float(data.get('reputation_score', 5.0)),
            strengths=data.get('strengths', []),
            weaknesses=data.get('weaknesses', [])
        )
    except (json.JSONDecodeError, ValueError):
        return ManufacturerInfo(
            name=firm_name,
            country="Belirtilmemiş",
            industry="Belirtilmemiş",
            products=[],
            market_presence="Belirtilmemiş",
            reputation_score=5.0,
            strengths=[],
            weaknesses=[]
        )

def analyze_market(
    product_info: ProductInfo, manufacturer_info: ManufacturerInfo, target_country: str,
    api_key: str, model: str, temperature: float, max_tokens: int
) -> MarketAnalysis:
    """Pazar analizi"""
    
    prompt = f"""
    Aşağıdaki ürün için {target_country} pazarında detaylı analiz yap:
    
    Ürün: {product_info.name} ({product_info.category})
    Üretici: {manufacturer_info.name} - {manufacturer_info.country}
    Fiyat Aralığı: {product_info.price_range}
    
    Şu bilgileri JSON formatında ver:
    {{
        "target_customers": ["Hedef müşteri grubu 1", "Grup 2"],
        "market_size": "Pazar büyüklüğü tahmini",
        "growth_potential": "Büyüme potansiyeli değerlendirmesi",
        "competition_level": "Rekabet seviyesi (Düşük/Orta/Yüksek)",
        "price_sensitivity": "Fiyat hassasiyeti değerlendirmesi",
        "seasonal_trends": ["Mevsimsel trend 1", "Trend 2"],
        "entry_barriers": ["Giriş engeli 1", "Engel 2"],
        "opportunities": ["Fırsat 1", "Fırsat 2"]
    }}
    
    {target_country} pazarına özel bilgiler ver.
    """
    
    response = complete(prompt, api_key=api_key, model=model, temperature=temperature, max_tokens=max_tokens)
    
    try:
        data = json.loads(response)
        return MarketAnalysis(
            target_customers=data.get('target_customers', []),
            market_size=data.get('market_size', ''),
            growth_potential=data.get('growth_potential', ''),
            competition_level=data.get('competition_level', ''),
            price_sensitivity=data.get('price_sensitivity', ''),
            seasonal_trends=data.get('seasonal_trends', []),
            entry_barriers=data.get('entry_barriers', []),
            opportunities=data.get('opportunities', [])
        )
    except json.JSONDecodeError:
        return MarketAnalysis(
            target_customers=[],
            market_size="Belirtilmemiş",
            growth_potential="Belirtilmemiş",
            competition_level="Orta",
            price_sensitivity="Belirtilmemiş",
            seasonal_trends=[],
            entry_barriers=[],
            opportunities=[]
        )

def generate_buyer_recommendations(
    product_info: ProductInfo, market_analysis: MarketAnalysis, target_country: str,
    api_key: str, model: str, temperature: float, max_tokens: int
) -> BuyerRecommendations:
    """Alıcı önerileri üret"""
    
    prompt = f"""
    Aşağıdaki ürün için {target_country} pazarında alıcılara öneriler ver:
    
    Ürün: {product_info.name}
    Kategori: {product_info.category}
    Fiyat: {product_info.price_range}
    Pazar Durumu: {market_analysis.competition_level} rekabet
    
    Şu bilgileri JSON formatında ver:
    {{
        "who_should_buy": ["Bu ürünü kimler almalı 1", "Kimler 2"],
        "purchase_considerations": ["Satın alma kriteri 1", "Kriter 2"],
        "price_expectations": ["Fiyat beklentisi 1", "Beklenti 2"],
        "timing_advice": ["Zamanlama önerisi 1", "Öneri 2"],
        "risk_factors": ["Risk faktörü 1", "Risk 2"]
    }}
    
    Pratik ve uygulanabilir öneriler ver.
    """
    
    response = complete(prompt, api_key=api_key, model=model, temperature=temperature, max_tokens=max_tokens)
    
    try:
        data = json.loads(response)
        return BuyerRecommendations(
            who_should_buy=data.get('who_should_buy', []),
            purchase_considerations=data.get('purchase_considerations', []),
            price_expectations=data.get('price_expectations', []),
            timing_advice=data.get('timing_advice', []),
            risk_factors=data.get('risk_factors', [])
        )
    except json.JSONDecodeError:
        return BuyerRecommendations(
            who_should_buy=[],
            purchase_considerations=[],
            price_expectations=[],
            timing_advice=[],
            risk_factors=[]
        )

def generate_seller_recommendations(
    product_info: ProductInfo, manufacturer_info: ManufacturerInfo, market_analysis: MarketAnalysis, target_country: str,
    api_key: str, model: str, temperature: float, max_tokens: int
) -> SellerRecommendations:
    """Satıcı önerileri üret"""
    
    prompt = f"""
    Aşağıdaki ürün için {target_country} pazarında satıcılara/üreticilere öneriler ver:
    
    Ürün: {product_info.name}
    Üretici: {manufacturer_info.name}
    İtibar: {manufacturer_info.reputation_score}/10
    Pazar Fırsatları: {', '.join(market_analysis.opportunities[:3])}
    
    Şu bilgileri JSON formatında ver:
    {{
        "target_segments": ["Hedef segment 1", "Segment 2"],
        "marketing_strategies": ["Pazarlama stratejisi 1", "Strateji 2"],
        "pricing_recommendations": ["Fiyatlama önerisi 1", "Öneri 2"],
        "distribution_channels": ["Dağıtım kanalı 1", "Kanal 2"],
        "competitive_advantages": ["Rekabet avantajı 1", "Avantaj 2"]
    }}
    
    Satış artırıcı ve pratik öneriler ver.
    """
    
    response = complete(prompt, api_key=api_key, model=model, temperature=temperature, max_tokens=max_tokens)
    
    try:
        data = json.loads(response)
        return SellerRecommendations(
            target_segments=data.get('target_segments', []),
            marketing_strategies=data.get('marketing_strategies', []),
            pricing_recommendations=data.get('pricing_recommendations', []),
            distribution_channels=data.get('distribution_channels', []),
            competitive_advantages=data.get('competitive_advantages', [])
        )
    except json.JSONDecodeError:
        return SellerRecommendations(
            target_segments=[],
            marketing_strategies=[],
            pricing_recommendations=[],
            distribution_channels=[],
            competitive_advantages=[]
        )

def generate_roadmap(
    product_info: ProductInfo, manufacturer_info: ManufacturerInfo, market_analysis: MarketAnalysis, target_country: str,
    api_key: str, model: str, temperature: float, max_tokens: int
) -> List[RoadmapItem]:
    """6-12 aylık yol haritası üret"""
    
    prompt = f"""
    Aşağıdaki ürün için {target_country} pazarında 6-12 aylık yol haritası oluştur:
    
    Ürün: {product_info.name}
    Üretici: {manufacturer_info.name}
    Pazar Büyüklüğü: {market_analysis.market_size}
    Büyüme Potansiyeli: {market_analysis.growth_potential}
    
    6-8 adımlık yol haritasını JSON formatında ver:
    {{
        "roadmap": [
            {{
                "timeframe": "1-2 ay",
                "action": "Yapılacak eylem",
                "priority": "Yüksek/Orta/Düşük",
                "expected_outcome": "Beklenen sonuç"
            }}
        ]
    }}
    
    Gerçekçi ve uygulanabilir adımlar ver.
    """
    
    response = complete(prompt, api_key=api_key, model=model, temperature=temperature, max_tokens=max_tokens)
    
    try:
        data = json.loads(response)
        roadmap_data = data.get('roadmap', [])
        return [
            RoadmapItem(
                timeframe=item.get('timeframe', ''),
                action=item.get('action', ''),
                priority=item.get('priority', 'Orta'),
                expected_outcome=item.get('expected_outcome', '')
            )
            for item in roadmap_data
        ]
    except json.JSONDecodeError:
        return []

def generate_summary(
    product_info: ProductInfo, manufacturer_info: ManufacturerInfo, market_analysis: MarketAnalysis,
    buyer_recommendations: BuyerRecommendations, seller_recommendations: SellerRecommendations,
    api_key: str, model: str, temperature: float, max_tokens: int
) -> str:
    """Analiz özeti üret"""
    
    prompt = f"""
    Aşağıdaki ürün analizi sonuçlarının kısa ve öz bir özetini oluştur:
    
    Ürün: {product_info.name} ({product_info.category})
    Üretici: {manufacturer_info.name} - İtibar: {manufacturer_info.reputation_score}/10
    Pazar: {market_analysis.market_size} - Rekabet: {market_analysis.competition_level}
    Ana Hedef: {', '.join(buyer_recommendations.who_should_buy[:2])}
    
    3-4 cümlelik profesyonel bir değerlendirme yap. Türkçe olsun.
    """
    
    return complete(prompt, api_key=api_key, model=model, temperature=temperature, max_tokens=200)

def save_analysis_results(results: Dict[str, ProductAnalysisResult], output_dir) -> str:
    """Analiz sonuçlarını kaydet"""
    
    # JSON formatında kaydet
    json_data = {}
    for product_name, result in results.items():
        json_data[product_name] = {
            'timestamp': result.timestamp,
            'product': asdict(result.product),
            'manufacturer': asdict(result.manufacturer),
            'market_analysis': asdict(result.market_analysis),
            'buyer_recommendations': asdict(result.buyer_recommendations),
            'seller_recommendations': asdict(result.seller_recommendations),
            'roadmap': [asdict(item) for item in result.roadmap],
            'summary': result.summary
        }
    
    from .utils import write_json
    output_path = output_dir / "AA_product_analysis.json"
    write_json(output_path, json_data)
    
    return str(output_path)
