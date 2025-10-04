# 🤖 GPT-5 Powered Product & Manufacturer Analyzer

**AI destekli ürün tanımlama, üretici analizi ve pazar önerileri sistemi**

## 🎯 Özellikler

### 🔍 Ürün Tanımlama
- **Akıllı Ürün Analizi**: GPT-5 ile ürün açıklamalarından otomatik bilgi çıkarma
- **Kategori Belirleme**: Ürünlerin doğru kategorilere otomatik sınıflandırılması
- **Marka ve Üretici Tanıma**: Marka ve üretici firma bilgilerinin otomatik tespiti
- **Fiyat Aralığı Tahmini**: Pazar verilerine dayalı fiyat tahminleri

### 🏭 Üretici Analizi
- **Firma Profili**: Üretici firmaların detaylı analizi
- **İtibar Skoru**: 0-10 arası güvenilirlik değerlendirmesi
- **Pazar Varlığı**: Global, bölgesel veya yerel pazar analizi
- **Ürün Portföyü**: Ana ürün grupları ve çeşitlilik analizi

### 📊 Pazar Analizi
- **Hedef Müşteri Segmentleri**: Kimler bu ürünü alabilir?
- **Pazar Büyüklüğü**: Toplam adreslenebilir pazar (TAM) tahmini
- **Rekabet Analizi**: Mevcut rekabet seviyesi değerlendirmesi
- **Büyüme Potansiyeli**: Gelecek projeksiyonları
- **Mevsimsel Trendler**: Satış döngüleri ve mevsimsel etkiler

### 💡 Akıllı Öneriler
- **Alıcılar İçin**: Satın alma kararı için rehberlik
- **Üreticiler İçin**: Pazarlama ve satış stratejileri
- **Pazar Fırsatları**: Yeni fırsat alanları
- **Risk Faktörleri**: Potansiyel tehditler ve önlemler
- **6-12 Aylık Yol Haritası**: Adım adım eylem planı

## 🚀 Kurulum

### 1. Gereksinimler
```bash
# Python 3.8+ gerekli
python --version

# Sanal ortam oluştur
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

### 2. Bağımlılıkları Yükle
```bash
pip install -r requirements.txt
```

### 3. API Anahtarı Konfigürasyonu
```bash
# .env dosyasını oluştur
cp .env.example .env

# .env dosyasını düzenle ve API anahtarını ekle
OPENAI_API_KEY=sk-your-api-key-here
```

## 🎮 Kullanım

### 1. Web Arayüzü (Önerilen)
```bash
cd app
streamlit run product_analyzer_app.py
```

Tarayıcıda `http://localhost:8501` adresini açın.

### 2. Demo Script
```bash
python demo_product_analyzer.py
```

### 3. Programatik Kullanım
```python
import asyncio
from product_ai_analyzer import ProductAIAnalyzer

async def analyze_product():
    analyzer = ProductAIAnalyzer("your-api-key")
    
    result = await analyzer.comprehensive_analysis(
        "iPhone 15 Pro Max 256GB Titanium Blue",
        "Turkey"
    )
    
    print(result)

asyncio.run(analyze_product())
```

## 📱 Web Arayüzü Özellikleri

### Ana Ekran
- **Ürün Açıklama Girişi**: Metin tabanlı ürün tanımı
- **Görsel Yükleme**: Ürün fotoğrafı analizi (opsiyonel)
- **Hedef Bölge Seçimi**: Turkey, Europe, North America, Asia, Global
- **Dil Desteği**: Türkçe ve İngilizce

### Analiz Sonuçları
- **📱 Ürün Sekmesi**: Detaylı ürün bilgileri ve özellikler
- **🏭 Üretici Sekmesi**: Firma analizi ve itibar skoru
- **📊 Pazar Sekmesi**: Pazar büyüklüğü ve rekabet analizi
- **💡 Öneriler Sekmesi**: Kapsamlı öneriler ve yol haritası
- **📥 Dışa Aktar**: JSON formatında sonuç indirme

### Görsel Öğeler
- **İtibar Skoru Göstergesi**: Interaktif gauge chart
- **Progress Bar**: Analiz ilerlemesi takibi
- **Renkli Kartlar**: Kategorize edilmiş bilgi sunumu

## 🔧 API Referansı

### ProductAIAnalyzer Sınıfı

#### `identify_product(product_description, image_url=None)`
Ürün tanımlama ve temel bilgi çıkarma.

**Parametreler:**
- `product_description` (str): Ürün açıklaması
- `image_url` (str, opsiyonel): Ürün görsel URL'si

**Döndürür:** `Product` objesi

#### `analyze_manufacturer(manufacturer_name)`
Üretici firma detaylı analizi.

**Parametreler:**
- `manufacturer_name` (str): Üretici firma adı

**Döndürür:** `Manufacturer` objesi

#### `market_analysis(product, target_region="Turkey")`
Pazar analizi ve müşteri segmentasyonu.

**Parametreler:**
- `product` (Product): Ürün bilgileri
- `target_region` (str): Hedef pazar bölgesi

**Döndürür:** `MarketAnalysis` objesi

#### `generate_recommendations(product, manufacturer, market_analysis)`
Kapsamlı öneriler ve yol haritası üretimi.

**Döndürür:** `Recommendations` objesi

#### `comprehensive_analysis(product_description, target_region="Turkey")`
Tüm analiz modüllerini birleştiren ana fonksiyon.

**Döndürür:** Tam analiz sonuçları (dict)

## 📊 Örnek Kullanım Senaryoları

### 1. E-ticaret Platformu
```python
# Yeni ürün ekleme sürecinde otomatik kategorizasyon
result = await analyzer.identify_product(
    "Samsung 65 inch QLED 4K Smart TV"
)
print(f"Kategori: {result.category}")
print(f"Hedef Pazar: {result.target_market}")
```

### 2. Yatırım Analizi
```python
# Yatırım kararı için pazar analizi
analysis = await analyzer.market_analysis(product, "Europe")
print(f"Pazar Büyüklüğü: {analysis.market_size}")
print(f"Büyüme Potansiyeli: {analysis.growth_potential}")
```

### 3. Satış Stratejisi
```python
# Satış ekibi için öneriler
recommendations = await analyzer.generate_recommendations(
    product, manufacturer, market_analysis
)
for tip in recommendations.for_manufacturers:
    print(f"• {tip}")
```

## 🌍 Desteklenen Bölgeler

- **Turkey** (Türkiye) - Varsayılan
- **Europe** (Avrupa)
- **North America** (Kuzey Amerika)
- **Asia** (Asya)
- **Global** (Küresel)

## 🔒 Güvenlik ve Gizlilik

- **API Anahtarları**: Çevre değişkenlerinde güvenli saklama
- **Veri Önbelleği**: Yerel geçici önbellek (opsiyonel)
- **Loglar**: Hassas bilgilerin loglanmaması
- **Rate Limiting**: API çağrı limitlerinin yönetimi

## 🐛 Sorun Giderme

### Yaygın Hatalar

#### "OPENAI_API_KEY bulunamadı"
```bash
# .env dosyasını kontrol edin
cat .env | grep OPENAI_API_KEY

# API anahtarını ekleyin
echo "OPENAI_API_KEY=sk-your-key" >> .env
```

#### "Analiz hatası: Rate limit exceeded"
OpenAI API limitine takıldınız. Birkaç dakika bekleyin veya plan yükseltin.

#### "ModuleNotFoundError"
```bash
# Bağımlılıkları yeniden yükleyin
pip install -r requirements.txt
```

### Debug Modu
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Detaylı log çıktıları göreceksiniz
```

## 📈 Performans Optimizasyonu

### Önbellek Kullanımı
```python
# Önbellek etkinleştirme
analyzer = ProductAIAnalyzer(api_key, cache_enabled=True)
```

### Batch İşleme
```python
# Çoklu ürün analizi
products = ["iPhone 15", "Samsung S24", "Google Pixel 8"]
results = await asyncio.gather(*[
    analyzer.identify_product(p) for p in products
])
```

## 🤝 Katkıda Bulunma

1. Fork yapın
2. Feature branch oluşturun (`git checkout -b feature/amazing-feature`)
3. Commit yapın (`git commit -m 'Add amazing feature'`)
4. Push yapın (`git push origin feature/amazing-feature`)
5. Pull Request açın

## 📄 Lisans

Bu proje eğitim ve araştırma amaçlıdır. Ticari kullanım için OpenAI API şartlarına uygun olduğunuzdan emin olun.

## 🆘 Destek

- **Issues**: GitHub issues sayfasını kullanın
- **Dokümantasyon**: Bu README dosyasını inceleyin
- **API Referansı**: Kod içi docstring'leri kontrol edin

## 🔮 Gelecek Özellikler

- [ ] Görsel analiz desteği (GPT-4 Vision)
- [ ] Çoklu dil desteği (Almanca, Fransızca, vb.)
- [ ] REST API endpoint'leri
- [ ] Veritabanı entegrasyonu
- [ ] Gerçek zamanlı pazar verileri
- [ ] Sosyal medya sentiment analizi
- [ ] Rakip ürün karşılaştırması

---

**Made with ❤️ using GPT-5 and Streamlit**
