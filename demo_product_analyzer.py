"""
GPT-5 Product Analyzer Demo Script
Ürün Analiz Sistemi Demo ve Test Scripti
"""

import asyncio
import json
import os
from dotenv import load_dotenv
from product_ai_analyzer import ProductAIAnalyzer

# .env dosyasını yükle
load_dotenv()

async def demo_analysis():
    """Demo analiz çalıştır"""
    
    print("🤖 GPT-5 Product Analyzer Demo")
    print("=" * 50)
    
    # API key kontrolü
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY bulunamadı!")
        print("Lütfen .env dosyanızda API anahtarınızı tanımlayın.")
        return
    
    # Analyzer'ı başlat
    try:
        analyzer = ProductAIAnalyzer(api_key)
        print("✅ AI Analyzer başlatıldı")
    except Exception as e:
        print(f"❌ Analyzer başlatma hatası: {e}")
        return
    
    # Demo ürünler
    demo_products = [
        {
            "name": "iPhone 15 Pro Max",
            "description": "Apple iPhone 15 Pro Max, 256GB depolama, Titanium Blue renk, A17 Pro işlemci, 48MP kamera sistemi"
        },
        {
            "name": "Samsung Galaxy S24 Ultra", 
            "description": "Samsung Galaxy S24 Ultra akıllı telefon, 512GB depolama, 12GB RAM, S Pen dahil, AI özellikli kamera"
        },
        {
            "name": "Tesla Model 3",
            "description": "Tesla Model 3 elektrikli sedan, Long Range versiyonu, Autopilot özellikli, 500km menzil"
        }
    ]
    
    for i, product in enumerate(demo_products, 1):
        print(f"\n🔍 Demo {i}: {product['name']}")
        print("-" * 30)
        
        try:
            # Kapsamlı analiz
            result = await analyzer.comprehensive_analysis(
                product['description'], 
                "Turkey"
            )
            
            # Sonuçları göster
            print(f"✅ Analiz tamamlandı: {product['name']}")
            print(f"📱 Ürün: {result['product']['name']}")
            print(f"🏭 Üretici: {result['manufacturer']['name']}")
            print(f"📊 Pazar: {result['market_analysis']['market_size']}")
            print(f"💡 Özet: {result['summary'][:100]}...")
            
            # JSON dosyasına kaydet
            filename = f"demo_analysis_{i}_{product['name'].replace(' ', '_')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"💾 Sonuçlar kaydedildi: {filename}")
            
        except Exception as e:
            print(f"❌ Analiz hatası: {e}")
        
        # Kısa bekleme
        await asyncio.sleep(2)
    
    print("\n🎉 Demo tamamlandı!")
    print("Streamlit uygulamasını çalıştırmak için:")
    print("cd app && streamlit run product_analyzer_app.py")

async def interactive_demo():
    """İnteraktif demo"""
    
    print("\n🎯 İnteraktif Ürün Analizi")
    print("=" * 30)
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY bulunamadı!")
        return
    
    analyzer = ProductAIAnalyzer(api_key)
    
    while True:
        print("\nÜrün açıklaması girin (çıkmak için 'q'):")
        user_input = input("> ")
        
        if user_input.lower() in ['q', 'quit', 'exit', 'çık']:
            break
        
        if not user_input.strip():
            print("Lütfen geçerli bir ürün açıklaması girin.")
            continue
        
        try:
            print("🔍 Analiz yapılıyor...")
            result = await analyzer.comprehensive_analysis(user_input, "Turkey")
            
            print(f"\n📱 Ürün: {result['product']['name']}")
            print(f"🏭 Üretici: {result['manufacturer']['name']} ({result['manufacturer']['country']})")
            print(f"⭐ İtibar: {result['manufacturer']['reputation_score']}/10")
            print(f"📊 Pazar: {result['market_analysis']['market_size']}")
            print(f"💡 Özet: {result['summary']}")
            
            # Önerileri göster
            if result['recommendations']['for_buyers']:
                print("\n🛒 Alıcı Önerileri:")
                for rec in result['recommendations']['for_buyers'][:3]:
                    print(f"  • {rec}")
            
        except Exception as e:
            print(f"❌ Hata: {e}")
    
    print("👋 Görüşmek üzere!")

def main():
    """Ana fonksiyon"""
    print("GPT-5 Product Analyzer")
    print("1. Demo analiz çalıştır")
    print("2. İnteraktif mod")
    print("3. Streamlit uygulamasını başlat")
    
    choice = input("\nSeçiminiz (1-3): ")
    
    if choice == "1":
        asyncio.run(demo_analysis())
    elif choice == "2":
        asyncio.run(interactive_demo())
    elif choice == "3":
        print("Streamlit uygulaması başlatılıyor...")
        os.system("cd app && streamlit run product_analyzer_app.py")
    else:
        print("Geçersiz seçim!")

if __name__ == "__main__":
    main()
