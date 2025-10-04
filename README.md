
# Export LeadGen Pro (Streamlit + Selenium + OpenAI)

**Hepsi bir arada ihracat pazarlama otomasyonu:** Kampanyalar, anahtar kelime üretimi, arama motoru & Google Maps veri çıkarma, zenginleştirme (API + sosyal arama), kişiselleştirilmiş e‑posta üretimi, toplu gönderim (SMTP), geri dönüş takibi (IMAP) ve web formlarını otomatik doldurma.

> ⚠️ ÖNEMLİ: Bu proje eğitim ve kişisel kullanım amaçlıdır. Kullandığınız arama motorlarının ve platformların **kullanım şartlarına** uyduğunuzdan emin olun. Toplu e‑posta ve scraping işlemleri ülkeden ülkeye değişen yasal kısıtlamalara tabidir. Sorumluluk kullanıcıya aittir.

## Kurulum (macOS / Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# .env dosyasını oluşturun
cp .env.example .env
# .env içindeki anahtarları doldurun
```

Selenium için Chrome yüklü olmalı. Sürücüyü `webdriver-manager` otomatik indirir.

## Çalıştırma

```bash
cd app
streamlit run app.py
```

## Proje Yapısı

- `app/app.py`: Streamlit ana uygulama
- `app/modules/*`: Modüler işlevler
- `campaigns/`: Her kampanya için kalıcı veri/çıktı klasörleri
- `data/`: Geçici veriler
- `logs/`: Loglar
- `scripts/`: Yardımcı bash/script’ler

## Notlar
- Google Maps ve arama motoru otomasyonu **deneyseldir**; sayfa şablonları değiştikçe ayar gerektirebilir.
- Enrichment API’leri için kendi anahtarlarınızı girin.
- SMTP/IMAP bilgileri kampanya bazında girilebilir.
