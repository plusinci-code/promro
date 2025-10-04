# -*- coding: utf-8 -*-
"""
Otomatik Form Doldurma & Gönderme (headless veya görünür)

Bu sürümde büyük geliştirmeler:
- Menüden çok dilli "iletişim" linki çıkarımı + dil-özgü whitelist permalink denemesi
- Zorunlu alanları (required/aria-required/pattern/minlength/maxlength) akıllı doldurma
- select/checkbox/radio gibi alanlar için baz mantık
- Submit: çok dilli metin + CSS class + role=button tespiti, JS click, JS submit, Enter fallback
- Başarı tespiti: i18n "teşekkürler/gönderildi" kökleri + URL değişimi + invalid uyarılar
- CAPTCHA güvenli işleyiş:
    * captcha_mode="skip"    -> siteden çık, "captcha_detected" olarak raporla
    * captcha_mode="manual"  -> kullanıcıya süre tanı (headless=False gerekir), süre zarfında kullanıcı çözünce devam et
    * captcha_mode="solver"  -> Anti-Captcha API kullanarak otomatik çözüm
- **Yeni:** Newsletter/abone formlarını ayıkla — sadece iletişim formlarını doldur
"""

import re
import time
import random
import base64
from typing import List, Optional, Tuple, Dict
from urllib.parse import urlsplit, urlunsplit, urljoin

import pandas as pd
from bs4 import BeautifulSoup
try:
    from twocaptcha import TwoCaptcha
    CAPTCHA_AVAILABLE = True
except ImportError:
    CAPTCHA_AVAILABLE = False
    print("⚠️ 2captcha-python kütüphanesi bulunamadı. CAPTCHA çözme özelliği devre dışı.")

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC


# --- Yol / dil yardımcıları --------------------------------------------------

def get_root_url(any_url: str) -> str:
    """Her zaman kök domain (scheme://netloc) döndürür."""
    if not any_url:
        return ""
    u = any_url.strip()
    if not re.match(r"^https?://", u, re.I):
        u = "https://" + u
    parts = urlsplit(u)
    scheme = parts.scheme or "https"
    netloc = parts.netloc
    return urlunsplit((scheme, netloc, "", "", ""))


LANG_RE = re.compile(r"<html[^>]*\blang=['\"]([a-zA-Z-]{2,10})['\"]", re.I)
HREFLANG_RE = re.compile(r"\bhreflang=['\"]([a-zA-Z-]{2,10})['\"]", re.I)

def detect_lang(html: str, default: str = "en") -> str:
    """HTML içeriğinden dil tespiti yapar."""
    if not html:
        return default
    m = LANG_RE.search(html)
    if m:
        return m.group(1).lower().split("-")[0]
    m = HREFLANG_RE.search(html)
    if m:
        return m.group(1).lower().split("-")[0]
    return default


# ---- Çok dilli sözlükler ----------------------------------------------------

CONTACT_KEYWORDS = {
    "en": ["contact", "contact us", "get in touch", "get-in-touch", "reach us", "contact form"],
    "de": ["kontakt", "kontaktformular", "kontakt aufnehmen", "kontaktiere uns", "kontaktieren", "ansprechpartner"],
    "fr": ["contact", "nous contacter", "contactez-nous", "formulaire de contact", "prendre contact"],
    "it": ["contatti", "contattaci", "contatto", "contattare", "modulo di contatto"],
    "es": ["contacto", "contáctanos", "contactanos", "contactar", "formulario de contacto"],
    "pt": ["contato", "contacto", "entre em contato", "fale conosco", "formulário de contato"],
    "ru": ["контакты", "связаться", "обратная связь", "написать нам", "контактная форма"],
    "sr": ["kontakt", "контакт", "kontaktirajte", "kontaktirajte nas", "kontakt forma"],
    "hr": ["kontakt", "kontaktirajte", "kontaktirajte nas", "kontakt forma"],
    "tr": ["iletişim", "bize ulaşın", "iletişime geçin", "iletişim formu"],
    "ar": ["اتصل بنا", "تواصل معنا", "اتصل", "اتصل-بنا", "نموذج الاتصال"],
    "nl": ["contact", "contacteer ons", "neem contact op", "contactformulier", "bereik ons"],
    "pl": ["kontakt", "skontaktuj się", "formularz kontaktowy", "napisz do nas", "kontaktuj"],
    "cs": ["kontakt", "kontaktujte nás", "kontaktní formulář", "napište nám", "spojte se s námi"],
    "sk": ["kontakt", "kontaktujte nás", "kontaktný formulár", "napíšte nám", "spojte sa s nami"],
    "hu": ["kapcsolat", "lépjen kapcsolatba", "kapcsolatfelvétel", "írjon nekünk", "kapcsolati űrlap"],
    "ro": ["contact", "contactați-ne", "luați legătura", "formular de contact", "scrieți-ne"],
    "bg": ["контакт", "свържете се", "контактна форма", "пишете ни", "връзка с нас"],
    "el": ["επικοινωνία", "επικοινωνήστε", "φόρμα επικοινωνίας", "γράψτε μας", "επαφή"],
    "sv": ["kontakt", "kontakta oss", "kontaktformulär", "skriv till oss", "ta kontakt"],
    "no": ["kontakt", "kontakt oss", "kontaktskjema", "skriv til oss", "ta kontakt"],
    "da": ["kontakt", "kontakt os", "kontaktformular", "skriv til os", "tag kontakt"],
    "fi": ["yhteystiedot", "ota yhteyttä", "yhteydenottolomake", "kirjoita meille", "kontakti"],
    "ja": ["お問い合わせ", "連絡", "コンタクト", "問い合わせフォーム", "ご連絡"],
    "ko": ["연락처", "문의", "연락하기", "문의 양식", "컨택트"],
    "zh": ["联系", "联系我们", "联系方式", "联系表单", "取得联系"],
    "hi": ["संपर्क", "हमसे संपर्क करें", "संपर्क फॉर्म", "लिखें", "संपर्क करें"],
}

CONTACT_PATHS = {
    "en": ["/contact/", "/contact-us/", "/contacts/", "/get-in-touch/", "/contact-form/"],
    "de": ["/kontakt/", "/kontaktformular/", "/kontakt-aufnehmen/", "/ansprechpartner/"],
    "fr": ["/contact/", "/nous-contacter/", "/contactez-nous/", "/formulaire-contact/"],
    "it": ["/contatti/", "/contattaci/", "/contatto/", "/modulo-contatto/"],
    "es": ["/contacto/", "/contactanos/", "/contáctanos/", "/contactar/", "/formulario-contacto/"],
    "pt": ["/contato/", "/contacto/", "/entre-em-contato/", "/fale-conosco/"],
    "ru": ["/контакты/", "/связаться/", "/obratnaya-svyaz/", "/kontakty/", "/svyazatsya/"],
    "sr": ["/kontakt/", "/контакт/", "/kontakti/", "/kontakt-forma/"],
    "hr": ["/kontakt/", "/kontakti/", "/kontakt-forma/"],
    "tr": ["/iletisim/", "/iletisim-bilgileri/", "/bize-ulasin/", "/iletisim-formu/"],
    "ar": ["/اتصل-بنا/", "/اتصل/", "/تواصل-معنا/", "/contact/", "/contactus/"],
    "nl": ["/contact/", "/contacteer-ons/", "/neem-contact-op/", "/contactformulier/"],
    "pl": ["/kontakt/", "/skontaktuj-sie/", "/formularz-kontaktowy/", "/napisz-do-nas/"],
    "cs": ["/kontakt/", "/kontaktujte-nas/", "/kontaktni-formular/", "/napiste-nam/"],
    "sk": ["/kontakt/", "/kontaktujte-nas/", "/kontaktny-formular/", "/napiste-nam/"],
    "hu": ["/kapcsolat/", "/lepjen-kapcsolatba/", "/kapcsolatfelvetel/", "/irjon-nekunk/"],
    "ro": ["/contact/", "/contactati-ne/", "/luati-legatura/", "/formular-contact/"],
    "bg": ["/контакт/", "/свържете-се/", "/контактна-форма/", "/пишете-ни/"],
    "el": ["/επικοινωνία/", "/επικοινωνήστε/", "/φόρμα-επικοινωνίας/", "/γράψτε-μας/"],
    "sv": ["/kontakt/", "/kontakta-oss/", "/kontaktformular/", "/skriv-till-oss/"],
    "no": ["/kontakt/", "/kontakt-oss/", "/kontaktskjema/", "/skriv-til-oss/"],
    "da": ["/kontakt/", "/kontakt-os/", "/kontaktformular/", "/skriv-til-os/"],
    "fi": ["/yhteystiedot/", "/ota-yhteytta/", "/yhteydenottolomake/", "/kirjoita-meille/"],
    "ja": ["/お問い合わせ/", "/連絡/", "/コンタクト/", "/問い合わせフォーム/", "/contact/"],
    "ko": ["/연락처/", "/문의/", "/연락하기/", "/문의-양식/", "/contact/"],
    "zh": ["/联系/", "/联系我们/", "/联系方式/", "/联系表单/", "/contact/"],
    "hi": ["/संपर्क/", "/हमसे-संपर्क-करें/", "/संपर्क-फॉर्म/", "/contact/"],
}
DEFAULT_PATHS = ["/contact/", "/contact-us/", "/contacts/"]

# istenmeyen slug'ları engelleyen whitelist regex - genişletilmiş
SAFE_CONTACT_PATTERN = re.compile(
    r"^/([a-z0-9\-%]+/)*("
    r"contact|contact-us|contacts|get-in-touch|contact-form|"
    r"kontakt|kontaktformular|kontakt-aufnehmen|ansprechpartner|"
    r"nous-contacter|contactez-nous|formulaire-contact|"
    r"contatti|contattaci|contatto|modulo-contatto|"
    r"contacto|contactanos|contáctanos|contactar|formulario-contacto|"
    r"contato|entre-em-contato|fale-conosco|"
    r"контакты|связаться|obratnaya-svyaz|kontakty|svyazatsya|"
    r"kontaktirajte|kontakti|контакт|kontakt-forma|"
    r"iletisim|iletisim-bilgileri|bize-ulasin|iletisim-formu|"
    r"%D8%A7%D8%AA%D8%B5%D9%84-%D8%A8%D9%86%D8%A7|%D8%A7%D8%AA%D8%B5%D9%84|%D8%AA%D9%88%D8%A7%D8%B5%D9%84-%D9%85%D8%B9%D9%86%D8%A7|contactus"
    r")/?$",
    re.I
)

def normalize_paths_for_lang(lang: str) -> List[str]:
    paths = CONTACT_PATHS.get(lang, [])
    if not paths:
        paths = CONTACT_PATHS.get("en", []) + DEFAULT_PATHS
    norm = []
    for p in paths:
        p = (p or "").strip()
        if not p:
            continue
        if not p.startswith("/"):
            p = "/" + p
        if not p.endswith("/"):
            p = p + "/"
        if SAFE_CONTACT_PATTERN.match(p) and p not in norm:
            norm.append(p)
    if not norm:
        norm = DEFAULT_PATHS
    return norm

# --- Alan tespiti ve doldurma ------------------------------------------------

EMAIL_RE = re.compile(r"@[a-z0-9.-]+\.[a-z]{2,}$", re.I)
DIGIT_RE = re.compile(r"\d+")

KWFIELD_PATTERNS = {
    "name": [
        # Turkish
        "ad", "isim", "adınız", "isminiz", "ad soyad", "adı soyadı", "tam ad",
        # English
        "name", "your name", "full name", "first name", "last name", "firstname", "lastname",
        # French
        "nom", "prénom", "nom complet", "nom et prénom",
        # Italian
        "nome", "cognome", "nome completo", "nome e cognome",
        # Spanish
        "nombre", "apellido", "nombre completo", "nombre y apellido",
        # Portuguese
        "nome", "sobrenome", "nome completo", "nome e sobrenome",
        # German
        "name", "vorname", "nachname", "vollständiger name", "vor- und nachname",
        # Russian
        "имя", "фамилия", "полное имя", "имя и фамилия",
        # Arabic
        "الاسم", "اسم", "الاسم الكامل", "الاسم الأول", "اسم العائلة",
        # Serbian/Croatian
        "ime", "prezime", "puno ime", "ime i prezime",
        # Dutch
        "naam", "voornaam", "achternaam", "volledige naam",
        # Polish
        "imię", "nazwisko", "pełne imię", "imię i nazwisko",
        # Czech/Slovak
        "jméno", "příjmení", "celé jméno", "jméno a příjmení",
        # Hungarian
        "név", "keresztnév", "vezetéknév", "teljes név",
        # Romanian
        "nume", "prenume", "nume complet", "nume și prenume",
        # Bulgarian
        "име", "фамилия", "пълно име", "име и фамилия",
        # Greek
        "όνομα", "επώνυμο", "πλήρες όνομα", "όνομα και επώνυμο",
        # Scandinavian
        "navn", "fornavn", "etternavn", "fullt navn", "för- och efternamn",
        # Finnish
        "nimi", "etunimi", "sukunimi", "koko nimi",
        # Japanese
        "名前", "氏名", "お名前", "フルネーム",
        # Korean
        "이름", "성명", "전체 이름", "성함",
        # Chinese
        "姓名", "全名", "名字", "您的姓名",
        # Hindi
        "नाम", "पूरा नाम", "आपका नाम"
    ],
    "email": [
        # Turkish
        "e-posta", "eposta", "email", "e-mail", "mail", "e posta", "elektronik posta",
        # English
        "email address", "e-mail address", "your email", "email",
        # Spanish
        "correo", "correo electrónico", "dirección de correo",
        # French
        "courriel", "adresse e-mail", "e-mail", "adresse électronique",
        # Italian
        "posta elettronica", "indirizzo email", "e-mail",
        # German
        "e-mail-adresse", "email-adresse", "elektronische post",
        # Portuguese
        "endereço de email", "correio eletrônico", "e-mail",
        # Russian
        "электронная почта", "адрес электронной почты", "емейл",
        # Arabic
        "البريد الإلكتروني", "ايميل", "عنوان البريد الإلكتروني",
        # Serbian/Croatian
        "mejl", "e-mail adresa", "elektronska pošta",
        # Dutch
        "e-mailadres", "elektronisch postadres",
        # Polish
        "adres e-mail", "poczta elektroniczna", "email",
        # Czech/Slovak
        "e-mailová adresa", "elektronická pošta",
        # Hungarian
        "e-mail cím", "elektronikus levelezés",
        # Romanian
        "adresa de email", "poștă electronică",
        # Bulgarian
        "имейл адрес", "електронна поща",
        # Greek
        "διεύθυνση email", "ηλεκτρονικό ταχυδρομείο",
        # Scandinavian
        "e-postadresse", "epostadress", "sähköpostiosoite",
        # Finnish
        "sähköposti", "sähköpostiosoite",
        # Japanese
        "メールアドレス", "電子メール", "Eメール",
        # Korean
        "이메일 주소", "전자우편", "이메일",
        # Chinese
        "电子邮件", "邮箱地址", "电子邮箱",
        # Hindi
        "ईमेल पता", "इलेक्ट्रॉनिक मेल"
    ],
    "phone": [
        # Turkish
        "telefon", "tel", "telefon numarası", "telefon no", "gsm", "cep telefonu",
        # English
        "phone", "telephone", "phone number", "mobile", "cell", "mobile number",
        # Spanish
        "teléfono", "número de teléfono", "móvil", "celular",
        # French
        "téléphone", "numéro de téléphone", "portable", "mobile",
        # Italian
        "telefono", "numero di telefono", "cellulare", "mobile",
        # German
        "telefon", "telefonnummer", "handy", "mobilnummer",
        # Portuguese
        "telefone", "número de telefone", "celular", "móvel",
        # Russian
        "телефон", "номер телефона", "мобильный", "сотовый",
        # Arabic
        "رقم الهاتف", "هاتف", "جوال", "رقم الجوال",
        # Serbian/Croatian
        "telefon broj", "broj telefona", "mobilni", "telefon",
        # Dutch
        "telefoonnummer", "telefoon", "mobiel", "gsm",
        # Polish
        "numer telefonu", "telefon", "komórka", "mobile",
        # Czech/Slovak
        "telefonní číslo", "telefon", "mobil", "mobilní číslo",
        # Hungarian
        "telefonszám", "telefon", "mobil", "mobilszám",
        # Romanian
        "numărul de telefon", "telefon", "mobil", "celular",
        # Bulgarian
        "телефонен номер", "телефон", "мобилен", "GSM",
        # Greek
        "αριθμός τηλεφώνου", "τηλέφωνο", "κινητό",
        # Scandinavian
        "telefonnummer", "telefon", "mobil", "mobilnummer",
        # Finnish
        "puhelinnumero", "puhelin", "matkapuhelin", "kännykkä",
        # Japanese
        "電話番号", "電話", "携帯電話", "ケータイ",
        # Korean
        "전화번호", "전화", "휴대폰", "핸드폰",
        # Chinese
        "电话号码", "电话", "手机号", "联系电话",
        # Hindi
        "फोन नंबर", "टेलीफोन", "मोबाइल"
    ],
    "subject": [
        # Turkish
        "konu", "başlık", "konu başlığı",
        # English
        "subject", "topic", "title", "subject line",
        # Spanish
        "asunto", "tema", "título",
        # French
        "objet", "sujet", "titre",
        # Italian
        "oggetto", "argomento", "titolo",
        # German
        "betreff", "thema", "titel",
        # Portuguese
        "assunto", "tópico", "título",
        # Russian
        "тема", "предмет", "заголовок",
        # Arabic
        "الموضوع", "العنوان", "المحتوى",
        # Serbian/Croatian
        "tema", "naslov", "predmet",
        # Dutch
        "onderwerp", "titel", "onderwerpregel",
        # Polish
        "temat", "tytuł", "przedmiot",
        # Czech/Slovak
        "předmět", "téma", "titul",
        # Hungarian
        "tárgy", "téma", "cím",
        # Romanian
        "subiect", "temă", "titlu",
        # Bulgarian
        "тема", "заглавие", "предмет",
        # Greek
        "θέμα", "τίτλος", "αντικείμενο",
        # Scandinavian
        "emne", "ämne", "titel", "overskrift",
        # Finnish
        "aihe", "otsikko", "asia",
        # Japanese
        "件名", "タイトル", "主題",
        # Korean
        "제목", "주제", "건명",
        # Chinese
        "主题", "标题", "题目",
        # Hindi
        "विषय", "शीर्षक", "टाइटल"
    ],
    "message": [
        # Turkish
        "mesaj", "mesajınız", "mesaj içeriği", "içerik", "açıklama", "yorumunuz",
        # English
        "message", "your message", "comments", "enquiry", "inquiry", "content", "description",
        # Spanish
        "mensaje", "su mensaje", "comentarios", "consulta", "descripción",
        # French
        "message", "votre message", "commentaires", "demande", "description",
        # Italian
        "messaggio", "il tuo messaggio", "commenti", "richiesta", "descrizione",
        # German
        "nachricht", "ihre nachricht", "kommentare", "anfrage", "beschreibung",
        # Portuguese
        "mensagem", "sua mensagem", "comentários", "consulta", "descrição",
        # Russian
        "сообщение", "ваше сообщение", "комментарии", "запрос", "описание",
        # Arabic
        "رسالة", "رسالتك", "تعليقات", "استفسار", "وصف",
        # Serbian/Croatian
        "poruka", "vaša poruka", "komentari", "upit", "opis",
        # Dutch
        "bericht", "uw bericht", "opmerkingen", "vraag", "beschrijving",
        # Polish
        "wiadomość", "twoja wiadomość", "komentarze", "zapytanie", "opis",
        # Czech/Slovak
        "zpráva", "vaše zpráva", "komentáře", "dotaz", "popis",
        # Hungarian
        "üzenet", "az ön üzenete", "megjegyzések", "kérdés", "leírás",
        # Romanian
        "mesaj", "mesajul dumneavoastră", "comentarii", "întrebare", "descriere",
        # Bulgarian
        "съобщение", "вашето съобщение", "коментари", "запитване", "описание",
        # Greek
        "μήνυμα", "το μήνυμά σας", "σχόλια", "ερώτηση", "περιγραφή",
        # Scandinavian
        "melding", "din melding", "kommentarer", "forespørsel", "beskrivelse",
        # Finnish
        "viesti", "viestisi", "kommentit", "kysely", "kuvaus",
        # Japanese
        "メッセージ", "お問い合わせ内容", "コメント", "質問", "説明",
        # Korean
        "메시지", "문의내용", "댓글", "질문", "설명",
        # Chinese
        "消息", "您的消息", "评论", "询问", "描述",
        # Hindi
        "संदेश", "आपका संदेश", "टिप्पणी", "पूछताछ", "विवरण",
        "textarea"
    ],
    "company": [
        # Turkish
        "şirket", "firma", "şirket adı", "firma adı", "kurum", "organizasyon",
        # English
        "company", "company name", "organization", "business", "firm",
        # Spanish
        "empresa", "nombre de empresa", "organización", "compañía",
        # French
        "entreprise", "nom d'entreprise", "société", "organisation",
        # Italian
        "azienda", "nome azienda", "società", "organizzazione",
        # German
        "unternehmen", "firmenname", "gesellschaft", "organisation",
        # Portuguese
        "empresa", "nome da empresa", "organização", "companhia",
        # Russian
        "компания", "название компании", "организация", "фирма",
        # Arabic
        "شركة", "اسم الشركة", "منظمة", "مؤسسة",
        # Serbian/Croatian
        "kompanija", "ime kompanije", "organizacija", "firma",
        # Dutch
        "bedrijf", "bedrijfsnaam", "organisatie", "onderneming",
        # Polish
        "firma", "nazwa firmy", "organizacja", "przedsiębiorstwo",
        # Czech/Slovak
        "společnost", "název společnosti", "organizace", "firma",
        # Hungarian
        "cég", "cégnév", "szervezet", "vállalat",
        # Romanian
        "companie", "numele companiei", "organizație", "firmă",
        # Bulgarian
        "компания", "име на компанията", "организация", "фирма",
        # Greek
        "εταιρεία", "όνομα εταιρείας", "οργανισμός", "επιχείρηση",
        # Scandinavian
        "selskap", "firmanavn", "organisasjon", "företag",
        # Finnish
        "yritys", "yrityksen nimi", "organisaatio", "firma",
        # Japanese
        "会社", "会社名", "組織", "企業",
        # Korean
        "회사", "회사명", "조직", "기업",
        # Chinese
        "公司", "公司名称", "组织", "企业",
        # Hindi
        "कंपनी", "कंपनी का नाम", "संगठन", "व्यवसाय"
    ]
}

# submit tespiti için daha geniş yelpaze - 25+ dil desteği
SUBMIT_TEXTS = [
    # English
    "send", "submit", "send message", "submit message", "contact", "submit form", "send inquiry", "get in touch",
    # Turkish
    "gönder", "mesaj gönder", "formu gönder", "ilet", "kaydet", "iletişim kur", "mesajı ilet",
    # German
    "senden", "absenden", "abschicken", "einreichen", "nachricht senden", "formular senden", "kontakt aufnehmen",
    # French
    "envoyer", "soumettre", "envoyer le message", "envoyer formulaire", "contacter", "prendre contact",
    # Italian
    "invia", "inviare", "invia messaggio", "invia modulo", "contatta", "invia richiesta",
    # Spanish
    "enviar", "enviar mensaje", "enviar formulario", "contactar", "enviar consulta", "mandar",
    # Portuguese
    "enviar", "enviar mensagem", "enviar formulário", "contactar", "entrar em contato", "mandar",
    # Russian
    "отправить", "отправка", "отослать", "послать", "связаться", "отправить сообщение",
    # Arabic
    "إرسال", "ارسال", "أرسل", "إرسال الرسالة", "اتصل", "تواصل",
    # Serbian/Croatian
    "pošalji", "pošaljite", "po\u0161alji", "po\u0161aljite", "kontaktiraj", "pošaljite poruku",
    # Dutch
    "verzenden", "versturen", "bericht verzenden", "contact opnemen", "formulier verzenden",
    # Polish
    "wyślij", "wyślij wiadomość", "wyślij formularz", "skontaktuj się", "prześlij",
    # Czech/Slovak
    "odeslat", "odeslat zprávu", "odeslat formulář", "kontaktovat", "poslat",
    # Hungarian
    "küldés", "üzenet küldése", "űrlap küldése", "kapcsolatfelvétel", "elküld",
    # Romanian
    "trimite", "trimite mesaj", "trimite formular", "contactează", "ia legătura",
    # Bulgarian
    "изпрати", "изпрати съобщение", "изпрати формуляр", "свържи се", "изпращане",
    # Greek
    "αποστολή", "στείλε", "στείλε μήνυμα", "επικοινωνία", "υποβολή",
    # Swedish/Norwegian/Danish
    "skicka", "skicka meddelande", "skicka formulär", "kontakta", "ta kontakt", "send",
    # Finnish
    "lähetä", "lähetä viesti", "lähetä lomake", "ota yhteyttä", "lähetys",
    # Japanese
    "送信", "送る", "メッセージを送信", "お問い合わせ", "連絡する",
    # Korean
    "보내기", "전송", "메시지 보내기", "문의하기", "연락하기",
    # Chinese
    "发送", "提交", "发送消息", "联系", "发送表单",
    # Hindi
    "भेजें", "संदेश भेजें", "संपर्क करें", "फॉर्म भेजें"
]

SUCCESS_SNIPPETS = [
    # çok dilli "teşekkürler / mesaj alındı" gibi göstergeler
    "thank you", "thanks for", "your message has been sent", "success",
    "teşekkür", "mesajınız alınmıştır", "başarıyla gönderildi",
    "vielen dank", "ihre nachricht wurde", "erfolgreich gesendet",
    "merci", "votre message a été envoyé", "bien reçu",
    "gracias", "su mensaje ha sido", "enviado correctamente",
    "grazie", "il tuo messaggio è stato inviato",
    "спасибо", "ваше сообщение отправлено", "успешно отправлено",
    "شكرا", "تم إرسال رسالتك", "بنجاح",
    "hvala", "vaša poruka je poslana", "uspešno poslata",
]

def keyword_score(text: str, keys: List[str]) -> int:
    t = (text or "").lower()
    score = 0
    for k in keys:
        if k in t:
            score += 2
    return score

def text_features(el) -> str:
    feats = []
    for attr in ("name", "id", "placeholder", "aria-label"):
        try:
            v = el.get_attribute(attr) or ""
            if v:
                feats.append(v.strip().lower())
        except Exception:
            pass
    try:
        t = (el.get_attribute("type") or "").lower()
        if t:
            feats.append(f"type={t}")
    except Exception:
        pass
    return " ".join(feats)


# --- Newsletter form ayıklama ------------------------------------------------

NEWSLETTER_HINTS = [
    "newsletter", "subscribe", "subscription", "mailing list", "mailinglist",
    "abonelik", "bülten", "bulten", "haber bülteni", "e-bülten",
    "abone ol", "abone", "e-bulten", "e bülten",
]

NEWSLETTER_PROVIDER_DOMAINS = [
    "list-manage.com",   # Mailchimp
    "mailchimp.com",
    "klaviyo", "klaviyo.com",
    "campaignmonitor", "createsend.com",
    "sendinblue", "brevo.com",
    "convertkit", "convertkit.com",
    "newsletter", "subscribe",
]

def _el_text(el) -> str:
    try:
        parts = [
            (el.text or "").strip().lower(),
            (el.get_attribute("id") or "").strip().lower(),
            (el.get_attribute("name") or "").strip().lower(),
            (el.get_attribute("class") or "").strip().lower(),
            (el.get_attribute("placeholder") or "").strip().lower(),
            (el.get_attribute("aria-label") or "").strip().lower(),
        ]
        return " ".join(p for p in parts if p)
    except Exception:
        return ""

def is_in_footer(form_el) -> bool:
    # footer ya da role=contentinfo içinde mi?
    try:
        # XPath ile yukarı tırman: footer veya role=contentinfo
        anc = form_el.find_elements(By.XPATH, "ancestor::footer | ancestor::*[@role='contentinfo']")
        return len(anc) > 0
    except Exception:
        return False

def is_newsletter_form(form_el, base_url: str) -> bool:
    """
    Newsletter/abone formlarını sezgisel olarak ayıkla:
    - footer/contentinfo içinde olması
    - form action'ı newsletter sağlayıcılarına gitmesi
    - tek alanlı (çoğunlukla sadece email) + textarea yok
    - metinlerde newsletter/subscribe ipuçları
    """
    try:
        # action analizi
        action = (form_el.get_attribute("action") or "").strip().lower()
        if action:
            for d in NEWSLETTER_PROVIDER_DOMAINS:
                if d in action:
                    return True
            # aksi halde /subscribe, /newsletter gibi relatif aksiyonlar
            if any(x in action for x in ["subscribe", "newsletter"]):
                return True
    except Exception:
        pass

    # içerik analizi
    try:
        inputs = form_el.find_elements(By.CSS_SELECTOR, "input, textarea, button, label")
    except Exception:
        inputs = []

    # Alan tipi dağılımı
    email_inputs = 0
    textareas = 0
    text_inputs = 0
    # newsletter ipuçları
    n_hints = 0

    for el in inputs:
        try:
            tag = (el.tag_name or "").lower()
        except Exception:
            tag = "input"
        features = _el_text(el)
        t = (el.get_attribute("type") or "").lower()

        if tag == "textarea":
            textareas += 1
        if t == "email":
            email_inputs += 1
        if t in ("text", "") and tag == "input":
            text_inputs += 1

        if any(h in features for h in NEWSLETTER_HINTS):
            n_hints += 1

    # footer içinde mi?
    in_footer = is_in_footer(form_el)

    # Newsletter için güçlü kurallar:
    # - textarea yok (mesaj alanı yok) VE
    #   (en az bir email inputu var ya da newsletter ipucu var)
    # - ya da footer içinde ve newsletter ipuçları var
    if textareas == 0 and (email_inputs >= 1 or n_hints >= 1):
        return True
    if in_footer and (email_inputs >= 1 or n_hints >= 1 or text_inputs <= 1):
        return True

    # Ayrıca form üzerindeki genel metinler:
    form_blob = _el_text(form_el)
    if any(h in form_blob for h in NEWSLETTER_HINTS):
        return True

    return False


# --- Submit buton tespiti ve alternatifleri ---------------------------------

def find_submit_candidates(driver, form_root=None) -> List:
    """Submit butonlarını bul - gelişmiş çok dilli tespit."""
    scope = form_root or driver
    cands = []

    # 1) input[type=submit]
    try:
        cands += scope.find_elements(By.CSS_SELECTOR, "input[type=submit]")
    except Exception:
        pass

    # 2) button[type=submit]
    try:
        cands += scope.find_elements(By.CSS_SELECTOR, "button[type=submit]")
    except Exception:
        pass

    # 3) button (type belirtilmemiş)
    try:
        btns = scope.find_elements(By.TAG_NAME, "button")
        for b in btns:
            t = (b.get_attribute("type") or "").lower()
            if not t or t == "submit":
                cands.append(b)
    except Exception:
        pass

    # 4) Metin bazlı arama - gelişmiş
    try:
        # Önce button ve input elementlerini kontrol et
        potential_elements = []
        potential_elements += scope.find_elements(By.TAG_NAME, "button")
        potential_elements += scope.find_elements(By.TAG_NAME, "input")
        potential_elements += scope.find_elements(By.CSS_SELECTOR, "a[role='button']")
        potential_elements += scope.find_elements(By.CSS_SELECTOR, "div[role='button']")
        potential_elements += scope.find_elements(By.CSS_SELECTOR, "span[role='button']")
        
        for el in potential_elements:
            txt = _el_text(el).lower()
            value = (el.get_attribute("value") or "").lower()
            title = (el.get_attribute("title") or "").lower()
            aria_label = (el.get_attribute("aria-label") or "").lower()
            
            all_text = f"{txt} {value} {title} {aria_label}"
            
            if any(st.lower() in all_text for st in SUBMIT_TEXTS):
                if el not in cands:
                    cands.append(el)
    except Exception:
        pass

    # 5) CSS class ve ID bazlı arama
    try:
        submit_selectors = [
            "[class*='submit']", "[class*='send']", "[class*='contact']",
            "[id*='submit']", "[id*='send']", "[id*='contact']",
            "[class*='btn-submit']", "[class*='btn-send']", "[class*='button-submit']"
        ]
        for selector in submit_selectors:
            try:
                elements = scope.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.tag_name.lower() in ['button', 'input', 'a', 'div', 'span'] and el not in cands:
                        cands.append(el)
            except Exception:
                continue
    except Exception:
        pass

    return cands

def score_submit_button(btn) -> int:
    """Submit butonunu skorla - çok dilli."""
    score = 0
    try:
        txt = _el_text(btn).lower()
        t = (btn.get_attribute("type") or "").lower()
        value = (btn.get_attribute("value") or "").lower()
        class_name = (btn.get_attribute("class") or "").lower()
        btn_id = (btn.get_attribute("id") or "").lower()
        aria_label = (btn.get_attribute("aria-label") or "").lower()
        
        all_text = f"{txt} {value} {class_name} {btn_id} {aria_label}"
        
        # Yüksek puan - kesin submit göstergeleri
        if t == "submit": score += 15
        
        # Çok dilli submit tespiti
        high_score_keywords = [
            "submit", "send", "gönder", "senden", "envoyer", "invia", "enviar", 
            "отправить", "إرسال", "pošalji", "verzenden", "wyślij", "odeslat",
            "küldés", "trimite", "изпрати", "αποστολή", "skicka", "lähetä",
            "送信", "보내기", "发送", "भेजें"
        ]
        
        medium_score_keywords = [
            "contact", "message", "inquiry", "iletişim", "mesaj", "kontakt",
            "contacter", "contatta", "contactar", "связаться", "اتصل",
            "kontaktiraj", "contact", "skontaktuj", "kontaktovat", "kapcsolat",
            "contactează", "свържи", "επικοινωνία", "kontakta", "yhteyttä",
            "問い合わせ", "문의", "联系", "संपर्क"
        ]
        
        for keyword in high_score_keywords:
            if keyword in all_text:
                score += 10
                
        for keyword in medium_score_keywords:
            if keyword in all_text:
                score += 6
        
        # Form içinde olma bonusu
        try:
            if btn.find_element(By.XPATH, "./ancestor::form"):
                score += 5
        except Exception:
            pass
            
        # CSS class bonusu
        if any(cls in class_name for cls in ['btn-primary', 'btn-submit', 'submit-btn', 'send-btn']):
            score += 8
            
        # Negatif puanlar - çok dilli
        negative_keywords = [
            "cancel", "reset", "clear", "iptal", "temizle", "sıfırla",
            "abbrechen", "zurücksetzen", "annuler", "réinitialiser",
            "annulla", "ripristina", "cancelar", "restablecer",
            "отмена", "сброс", "إلغاء", "إعادة تعيين",
            "otkaži", "resetuj", "annuleren", "resetten",
            "anuluj", "resetuj", "zrušit", "resetovat",
            "mégse", "visszaállít", "anulează", "resetează",
            "отказ", "нулиране", "ακύρωση", "επαναφορά",
            "avbryt", "återställ", "peruuta", "nollaa",
            "キャンセル", "リセット", "취소", "재설정",
            "取消", "重置", "रद्द करें", "रीसेट करें"
        ]
        
        for keyword in negative_keywords:
            if keyword in all_text:
                score -= 15
        
    except Exception:
        pass
    return max(0, score)  # Negatif skor olmasın

def click_submit_safely(driver, el, form_root=None, dwell_seconds=2.0) -> bool:
    """Birden çok yöntemle submit etmeyi dener."""
    try:
        driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth',block:'center'});", el)
    except Exception:
        pass
    time.sleep(0.2)
    old_url = driver.current_url

    # 1) normal click
    try:
        el.click()
        time.sleep(dwell_seconds)
        if driver.current_url != old_url:
            return True
    except Exception:
        pass

    # 2) JS click
    try:
        driver.execute_script("arguments[0].click();", el)
        time.sleep(dwell_seconds)
        if driver.current_url != old_url:
            return True
    except Exception:
        pass

    # 3) Enter tuşu
    try:
        el.send_keys(Keys.ENTER)
        time.sleep(dwell_seconds)
        if driver.current_url != old_url:
            return True
    except Exception:
        pass

    # 4) Form submit (JS)
    if form_root is not None:
        try:
            driver.execute_script("""
                const f = arguments[0];
                if (!f) return;
                f.dispatchEvent(new Event('submit', {bubbles:true,cancelable:true}));
                if (typeof f.submit === 'function') { f.submit(); }
            """, form_root)
            time.sleep(dwell_seconds)
            if driver.current_url != old_url:
                return True
        except Exception:
            pass

    # URL değişmediyse de başarı metinleri arayalım
    try:
        html = (driver.page_source or "").lower()
        if any(sn in html for sn in SUCCESS_SNIPPETS):
            return True
    except Exception:
        pass

    return False


# --- Başarı / hata sinyali ---------------------------------------------------

def has_invalid_state(driver, root=None) -> bool:
    """Sayfada ':invalid' eleman var mı? Basit kontrol."""
    try:
        return driver.execute_script("return !!document.querySelector(':invalid');")
    except Exception:
        # bazı tarayıcılarda :invalid desteklenmeyebilir
        return False

def fill_value_for_input(payload, kind: str, fallback=""):
    """Zorunlu alanlara konacak değerleri üret."""
    name = (payload.get("name") or "").strip()
    surname = (payload.get("surname") or "").strip()
    fullname = (name + " " + surname).strip() or name or "John Doe"
    email = (payload.get("email") or "").strip() or "contact@example.com"
    phone = (payload.get("phone") or "").strip() or "+1 202 555 0199"
    subject = (payload.get("subject") or "").strip() or "Business Inquiry"
    message = (payload.get("message") or "").strip() or "Hello, we would like to get in touch."

    if kind == "email": return email
    if kind == "tel" or kind == "phone" or kind == "number": return re.sub(r"\D+", "", phone)[:15] or "1234567"
    if kind == "subject": return subject
    if kind == "message": return message
    if kind == "name": return fullname
    return fallback or fullname

def js_set_value(driver, el, text: str):
    driver.execute_script("""
        const el = arguments[0], val = arguments[1];
        if (!el) return;
        el.scrollIntoView({behavior:'smooth', block:'center'});
        if (el.isContentEditable) {
            el.innerHTML = '';
            el.textContent = val;
        } else {
            el.value = '';
            el.value = val;
        }
        const evts = ['input','change','keyup'];
        evts.forEach(e => el.dispatchEvent(new Event(e, {bubbles:true})));
    """, el, text)

def safe_type(driver, el, text: str) -> bool:
    try:
        js_set_value(driver, el, text)
        return True
    except Exception:
        try:
            el.clear()
        except Exception:
            pass
        try:
            el.send_keys(text)
            return True
        except Exception:
            return False

def satisfy_required_fields(driver, form_root, payload: dict):
    """
    required/aria-required alanları tipine göre doldurur.
    select/radio/checkbox dahil temel mantık.
    """
    scope = form_root or driver

    def set_any(el, val):
        if el is None:
            return False
        tag = (el.tag_name or "").lower()
        t = (el.get_attribute("type") or "").lower()
        if tag == "select":
            try:
                sel = Select(el)
                # placeholder olmayan ilk uygun seçeneği seç
                options = sel.options
                chosen = None
                for opt in options:
                    txt = (opt.text or "").strip().lower()
                    if not txt or "select" in txt or "choose" in txt or "seçiniz" in txt or "auswählen" in txt or "choisir" in txt:
                        continue
                    chosen = opt
                    break
                if not chosen and options:
                    chosen = options[min(1, len(options)-1)]
                if chosen is not None:
                    sel.select_by_visible_text(chosen.text)
                    return True
            except Exception:
                return False
        elif t in ("checkbox",):
            try:
                # zorunluysa işaretle
                checked = el.get_attribute("checked")
                if not checked:
                    el.click()
                return True
            except Exception:
                return False
        elif t in ("radio",):
            try:
                # aynı isimli gruptan ilkini işaretle
                name = el.get_attribute("name") or ""
                if name:
                    group = scope.find_elements(By.CSS_SELECTOR, f"input[type=radio][name='{name}']")
                    for r in group:
                        try:
                            r.click()
                            return True
                        except Exception:
                            continue
                # tek radio ise onu dene
                el.click()
                return True
            except Exception:
                return False
        else:
            return safe_type(driver, el, val)
        return False

    # 1) :invalid varsa onunla başlayalım (en doğrudan ipucu)
    try:
        invalids = scope.find_elements(By.CSS_SELECTOR, ":invalid")
    except Exception:
        invalids = []

    def features(e):
        feat = (e.get_attribute("name") or "") + " " + (e.get_attribute("id") or "") + " " + (e.get_attribute("placeholder") or "")
        feat = feat.lower()
        t = (e.get_attribute("type") or "").lower()
        return feat, t

    def value_for_element(e):
        feat, t = features(e)
        if "mail" in feat or t == "email":
            return fill_value_for_input(payload, "email")
        if "phone" in feat or "tel" in feat or t in ("tel", "phone", "number"):
            return fill_value_for_input(payload, "phone")
        if "subject" in feat:
            return fill_value_for_input(payload, "subject")
        if "message" in feat or "comment" in feat:
            return fill_value_for_input(payload, "message")
        if "name" in feat or "ad" in feat or "soyad" in feat or "vorname" in feat or "nachname" in feat:
            return fill_value_for_input(payload, "name")
        # pattern varsa basit uyumla doldur
        pat = e.get_attribute("pattern") or ""
        if pat:
            # çok basit: \d+ istiyorsa rakam ver
            if "\\d" in pat or "[0-9]" in pat:
                return "123456"
        # minlength/maxlength
        minlen = e.get_attribute("minlength")
        maxlen = e.get_attribute("maxlength")
        base = fill_value_for_input(payload, "name")
        if maxlen:
            try:
                ml = int(maxlen)
                if len(base) > ml:
                    base = base[:ml]
            except Exception:
                pass
        if minlen:
            try:
                mn = int(minlen)
                while len(base) < mn:
                    base += "x"
            except Exception:
                pass
        return base

    changed_any = False

    # Önce invalid'leri doldur
    for e in invalids:
        try:
            val = value_for_element(e)
            changed_any |= set_any(e, val)
        except Exception:
            continue

    # 2) required & aria-required alanları doldur
    req_selectors = ["[required]", "[aria-required='true']"]
    for sel in req_selectors:
        try:
            reqs = scope.find_elements(By.CSS_SELECTOR, sel)
        except Exception:
            reqs = []
        for e in reqs:
            try:
                # boşsa doldur
                val_now = (e.get_attribute("value") or "").strip()
                if not val_now:
                    val = value_for_element(e)
                    changed_any |= set_any(e, val)
            except Exception:
                continue

    return changed_any


# --- İletişim linki çıkarımı -------------------------------------------------

def detect_lang_from_links(html: str) -> Optional[str]:
    """Menü/link metinlerinden dili tahmin etmeye çalış."""
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return None
    scores = {lang: 0 for lang in CONTACT_KEYWORDS.keys()}
    for a in soup.find_all("a"):
        text = " ".join(filter(None, [
            (a.get_text() or "").strip().lower(),
            (a.get("title") or "").strip().lower(),
            (a.get("aria-label") or "").strip().lower(),
        ]))
        if not text:
            continue
        for lang, kws in CONTACT_KEYWORDS.items():
            for k in kws:
                if k in text:
                    scores[lang] += 1
    best = max(scores.items(), key=lambda x: x[1]) if scores else (None, 0)
    return best[0] if best and best[1] > 0 else None

def extract_contact_links(base_url: str, html: str, lang: str) -> List[Tuple[str, int]]:
    """Sayfadaki <a> linklerinden çok dilli 'iletişim' eşleşmesi yapan aday linkleri çıkarır."""
    results: List[Tuple[str, int]] = []
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return results

    def score_anchor(a) -> int:
        parts = [
            (a.get_text() or "").strip().lower(),
            (a.get("title") or "").strip().lower(),
            (a.get("aria-label") or "").strip().lower(),
            " ".join(a.get("rel", [])).lower() if a.get("rel") else "",
            (a.get("class") and " ".join(a.get("class")).lower() or ""),
            (a.get("id") or "").lower(),
        ]
        blob = " ".join([p for p in parts if p])
        score = 0
        for k in CONTACT_KEYWORDS.get(lang, []):
            if k in blob:
                score += 5
        for l2, kws in CONTACT_KEYWORDS.items():
            if l2 == lang:
                continue
            for k in kws:
                if k in blob:
                    score += 1
        return score

    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        url = urljoin(base_url, href)
        path = urlsplit(url).path or "/"
        safe_bonus = 2 if SAFE_CONTACT_PATTERN.match(path) else 0
        s = score_anchor(a) + safe_bonus
        if s <= 0:
            continue
        if url not in seen:
            seen.add(url)
            results.append((url, s))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


# --- WebDriver & Cookie banner kapatma --------------------------------------

COOKIE_SELECTORS = [
    "#onetrust-accept-btn-handler", ".ot-sdk-container .accept",
    "button[aria-label*='accept' i]", "button[aria-label*='kabul' i]",
    "button:contains('Accept')", "button:contains('Kabul')",
    ".cookie-accept", ".cc-allow", ".eu-cookie-compliance-default-button",
]

def create_driver(headless=True):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1440,1100")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--lang=en-US")
    return webdriver.Chrome(options=opts)

def try_close_cookies(driver):
    try:
        for sel in COOKIE_SELECTORS:
            try:
                eles = driver.find_elements(By.CSS_SELECTOR, sel)
            except Exception:
                eles = []
            for e in eles:
                try:
                    driver.execute_script("arguments[0].click();", e)
                    time.sleep(0.2)
                    return
                except Exception:
                    continue
    except Exception:
        pass


# --- CAPTCHA Çözücü Sınıfı ---------------------------------------------------

class CaptchaSolver:
    """Modern CAPTCHA çözücü sınıfı - 2captcha API kullanır."""

    def __init__(self, api_key: str):
        """API anahtarı ile çözücüyü başlat.
        Args:
            api_key: 2captcha API anahtarı
        """
        if not CAPTCHA_AVAILABLE:
            raise ImportError("2captcha-python kütüphanesi yüklü değil")
        self.solver = TwoCaptcha(api_key)

    def solve_image_captcha(self, image_path: str = None, image_url: str = None,
                           image_element = None, driver = None) -> Optional[str]:
        """Görsel CAPTCHA'yı çözer."""
        try:
            # Elementten resim al
            if image_element and driver:
                screenshot = image_element.screenshot_as_png
                captcha_text = self._solve_from_bytes(screenshot)
            elif image_url:
                result = self.solver.normal(image_url)
                captcha_text = result['code']
            elif image_path:
                with open(image_path, 'rb') as f:
                    image_data = f.read()
                captcha_text = self._solve_from_bytes(image_data)
            else:
                print("CAPTCHA çözümü için geçerli bir resim kaynağı sağlanmadı")
                return None
            return captcha_text if captcha_text else None
        except Exception as e:
            print(f"CAPTCHA çözümü sırasında hata: {str(e)}")
            return None

    def _solve_from_bytes(self, image_data: bytes) -> Optional[str]:
        """Byte verisinden CAPTCHA çözer."""
        try:
            # Geçici dosya oluştur
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                tmp_file.write(image_data)
                tmp_file.flush()
                
                result = self.solver.normal(tmp_file.name)
                captcha_text = result['code']
                
                # Geçici dosyayı sil
                import os
                os.unlink(tmp_file.name)
                
                return captcha_text
        except Exception as e:
            print(f"Byte verisinden CAPTCHA çözümü sırasında hata: {str(e)}")
            return None


# --- CAPTCHA Tespit ve Çözüm Fonksiyonları -----------------------------------

def detect_captcha(driver) -> bool:
    """Sayfada CAPTCHA olup olmadığını tespit eder."""
    captcha_selectors = [
        'img[src*="captcha"]',
        'img[src*="CAPTCHA"]',
        'div[class*="captcha"]',
        'div[class*="CAPTCHA"]',
        'div[class*="recaptcha"]',
        'div[class*="Recaptcha"]',
        'iframe[src*="recaptcha"]',
        'iframe[src*="google.com/recaptcha"]',
        'input[type="hidden"][name*="captcha"]',
        'input[type="hidden"][name*="recaptcha"]'
    ]
    for selector in captcha_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                return True
        except:
            continue
    return False


def solve_captchas(driver, captcha_mode: str, captcha_solver: CaptchaSolver = None) -> bool:
    """Sayfadaki CAPTCHA'ları çözer."""
    if captcha_mode == "skip":
        print("CAPTCHA tespit edildi, skip modu etkin - atlanıyor")
        return False

    captcha_elements = []
    captcha_selectors = [
        'img[src*="captcha"]',
        'img[src*="CAPTCHA"]',
        'div[class*="captcha"]',
        'div[class*="CAPTCHA"]'
    ]
    for selector in captcha_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            captcha_elements.extend(elements)
        except:
            continue

    if not captcha_elements:
        print("CAPTCHA tespit edildi ancak çözülecek element bulunamadı")
        return False

    if captcha_mode == "manual":
        print("CAPTCHA tespit edildi, manual mod etkin - lütfen CAPTCHA'yı manuel çözün")
        print("30 saniye bekleniyor...")
        time.sleep(30)
        return True

    if captcha_mode == "solver" and captcha_solver:
        print("CAPTCHA tespit edildi, solver mod etkin - çözülüyor...")
        for captcha_element in captcha_elements:
            try:
                captcha_text = captcha_solver.solve_image_captcha(
                    image_element=captcha_element,
                    driver=driver
                )
                if captcha_text:
                    print(f"CAPTCHA çözüldü: {captcha_text}")
                    input_selectors = [
                        'input[name*="captcha"]',
                        'input[name*="CAPTCHA"]',
                        'input[type="text"][id*="captcha"]',
                        'input[type="text"][id*="CAPTCHA"]'
                    ]
                    for selector in input_selectors:
                        try:
                            input_field = driver.find_element(By.CSS_SELECTOR, selector)
                            input_field.clear()
                            input_field.send_keys(captcha_text)
                            print("CAPTCHA metni input alanına yazıldı")
                            return True
                        except:
                            continue
                    print("CAPTCHA çözüldü ancak input alanı bulunamadı")
                else:
                    print("CAPTCHA çözülemedi")
            except Exception as e:
                print(f"CAPTCHA çözümü sırasında hata: {str(e)}")
    return False


# --- Form puanlama (newsletter ayıklamalı) -----------------------------------

def score_form(form_el, base_url: str) -> int:
    """
    İletişim formu olma ihtimalini puanlar.
    Newsletter ise büyük negatif puan verir.
    """
    if is_newsletter_form(form_el, base_url):
        return -100  # newsletter formu → çok düşük puan

    score = 0
    try:
        ins = form_el.find_elements(By.CSS_SELECTOR, "input, textarea, select, button, label")
    except Exception:
        ins = []

    # Alan sayısı baz puan
    score += len(ins)

    # textarea (mesaj) +3
    try:
        if any(i.tag_name.lower() == "textarea" for i in ins):
            score += 3
    except Exception:
        pass

    # e-posta, konu, telefon alanları +2
    try:
        has_email = any((i.get_attribute("type") or "").lower() == "email" for i in ins if i.tag_name.lower()=="input")
        has_subject = any("subject" in _el_text(i) for i in ins)
        has_phone = any((i.get_attribute("type") or "").lower() in ("tel","phone","number") for i in ins if i.tag_name.lower()=="input")
        if has_email: score += 2
        if has_subject: score += 2
        if has_phone: score += 2
    except Exception:
        pass

    # submit adayı var mı? +2
    try:
        if find_submit_candidates(None, form_el):
            score += 2
    except Exception:
        pass

    return score


# --- Form doldurma & submit --------------------------------------------------

def fill_and_submit_form(driver, form_payload: dict, captcha_mode: str = "skip",
                        api_key: str = None, headless: bool = True, dwell_seconds: float = 5.0, form_element=None):
    """
    Formu doldurur ve gönderir.
    """
    captcha_solver = None
    if captcha_mode == "solver" and api_key:
        try:
            captcha_solver = CaptchaSolver(api_key)
            print("CAPTCHA solver başlatıldı")
        except Exception as e:
            print(f"CAPTCHA solver başlatılamadı: {str(e)}")
            captcha_mode = "skip"  # Fallback to skip mode

    # CAPTCHA kontrolü
    if detect_captcha(driver):
        if not solve_captchas(driver, captcha_mode, captcha_solver):
            return {"status": "captcha_detected", "message": "CAPTCHA atlandı"}

    # Form seçimi (newsletter filtresiyle) - eğer form_element parametre olarak verilmemişse
    if form_element is None:
        try:
            forms = driver.find_elements(By.TAG_NAME, "form")
            if forms:
                forms = sorted(forms, key=lambda f: score_form(f, driver.current_url), reverse=True)
                # sadece pozitif puanlı ilk formu seç
                for f in forms:
                    if score_form(f, driver.current_url) > 0:
                        form_element = f
                        break
        except Exception:
            pass

    if form_element is None:
        print("❌ Uygun iletişim formu bulunamadı")
        return {"status": "error", "message": "Uygun iletişim formu bulunamadı (newsletter olabilir)."}

    # Alan rolleri
    def guess_field_roles(local_driver, form_root=None) -> Dict[str, object]:
        scope = form_root or local_driver
        inputs = []
        try:
            inputs += scope.find_elements(By.CSS_SELECTOR, "input")
        except Exception:
            pass
        try:
            inputs += scope.find_elements(By.CSS_SELECTOR, "textarea")
        except Exception:
            pass

        scored = {"name": [], "email": [], "phone": [], "subject": [], "message": []}

        for el in inputs:
            try:
                tag = el.tag_name.lower()
            except Exception:
                tag = "input"
            feats = text_features(el)
            t = (el.get_attribute("type") or "").lower()

            s_name = keyword_score(feats, KW["name"])
            s_mail = keyword_score(feats, KW["email"])
            s_tel  = keyword_score(feats, KW["phone"])
            s_subj = keyword_score(feats, KW["subject"])
            s_msg  = keyword_score(feats, KW["message"])

            if t == "email": s_mail += 6
            if t == "tel":   s_tel  += 4
            if tag == "textarea": s_msg += 8

            if s_name > 0:   scored["name"].append((s_name, el))
            if s_mail > 0:   scored["email"].append((s_mail, el))
            if s_tel > 0:    scored["phone"].append((s_tel, el))
            if s_subj > 0:   scored["subject"].append((s_subj, el))
            if s_msg > 0:    scored["message"].append((s_msg, el))

        chosen = {}
        for k in scored:
            if scored[k]:
                scored[k].sort(key=lambda x: x[0], reverse=True)
                chosen[k] = scored[k][0][1]
            else:
                chosen[k] = None

        # e-posta güvenlik kontrolü
        mail_el = chosen.get("email")
        if mail_el:
            t = (mail_el.get_attribute("type") or "").lower()
            feats = text_features(mail_el)
            if not (t == "email" or "mail" in feats or "e-mail" in feats or "correo" in feats or "courriel" in feats):
                chosen["email"] = None

        # mesaj tercihi: textarea yoksa ara
        if not chosen.get("message"):
            try:
                txs = scope.find_elements(By.TAG_NAME, "textarea")
                if txs:
                    chosen["message"] = txs[0]
            except Exception:
                pass
        # Son çare contenteditable
        if not chosen.get("message"):
            try:
                eds = scope.find_elements(By.CSS_SELECTOR, "[contenteditable='true']")
                if eds:
                    chosen["message"] = eds[0]
            except Exception:
                pass

        return chosen

    chosen = guess_field_roles(driver, form_element)
    print(f"🔍 Form alanları tespit edildi: {list(chosen.keys())}")

    # Alanlara doldurma
    email_val = (form_payload.get("email") or "").strip()
    name_val = (form_payload.get("name") or "").strip()
    surname_val = (form_payload.get("surname") or "").strip()
    full_name_val = (name_val + " " + surname_val).strip() if surname_val else name_val
    phone_val = (form_payload.get("phone") or "").strip()
    subject_val = (form_payload.get("subject") or "").strip()
    message_val = (form_payload.get("message") or "").strip()

    filled_fields = []
    if email_val and chosen.get("email") and EMAIL_RE.search(email_val):
        if safe_type(driver, chosen["email"], email_val):
            filled_fields.append("email")
            print(f"✅ Email alanı dolduruldu: {email_val}")
    if full_name_val and chosen.get("name"):
        if safe_type(driver, chosen["name"], full_name_val):
            filled_fields.append("name")
            print(f"✅ İsim alanı dolduruldu: {full_name_val}")
    if phone_val and chosen.get("phone"):
        phone_clean = re.sub(r"\D+", "", phone_val)[:15] or phone_val
        if safe_type(driver, chosen["phone"], phone_clean):
            filled_fields.append("phone")
            print(f"✅ Telefon alanı dolduruldu: {phone_clean}")
    if subject_val and chosen.get("subject"):
        if safe_type(driver, chosen["subject"], subject_val):
            filled_fields.append("subject")
            print(f"✅ Konu alanı dolduruldu: {subject_val}")
    if message_val and chosen.get("message"):
        if safe_type(driver, chosen["message"], message_val):
            filled_fields.append("message")
            print(f"✅ Mesaj alanı dolduruldu: {message_val[:50]}...")
    
    print(f"📝 Toplam {len(filled_fields)} alan dolduruldu: {filled_fields}")

    # Zorunlu alanları tatmin et
    satisfy_required_fields(driver, form_element or driver, form_payload)

    # Submit butonları skorla ve tıkla
    cands = find_submit_candidates(driver, form_element or driver)
    cands = sorted(cands, key=score_submit_button, reverse=True)
    print(f"🎯 {len(cands)} submit butonu bulundu")

    success = False
    for i, btn in enumerate(cands[:6]):
        btn_text = _el_text(btn)
        btn_score = score_submit_button(btn)
        print(f"🔘 Submit butonu {i+1}: '{btn_text}' (skor: {btn_score})")
        
        if click_submit_safely(driver, btn, form_element, dwell_seconds=max(1.0, float(dwell_seconds))):
            print(f"✅ Submit başarılı: '{btn_text}'")
            success = True
            break
        else:
            print(f"❌ Submit başarısız: '{btn_text}'")

    # Eğer butonlar işe yaramadıysa formu JS ile submit etmeyi dene
    if not success and form_element is not None:
        print("🔄 JS ile form submit deneniyor...")
        try:
            old = driver.current_url
            driver.execute_script("""
                const f = arguments[0];
                if (!f) return;
                f.dispatchEvent(new Event('submit', {bubbles:true,cancelable:true}));
                if (typeof f.submit === 'function') { f.submit(); }
            """, form_element)
            time.sleep(max(1.0, float(dwell_seconds)))
            html2 = (driver.page_source or "").lower()
            if driver.current_url != old or any(sn in html2 for sn in SUCCESS_SNIPPETS):
                print("✅ JS submit başarılı")
                success = True
            else:
                print("❌ JS submit başarısız")
        except Exception as e:
            print(f"❌ JS submit hatası: {e}")

    if success:
        print("🎉 Form başarıyla gönderildi!")
        return {"status": "success", "message": "Form başarıyla gönderildi"}
    else:
        if has_invalid_state(driver, form_element or driver):
            print("⚠️ Formda geçersiz alanlar var")
            return {"status": "error", "message": "Formda geçersiz alanlar var"}
        else:
            print("❌ Form gönderilemedi")
            return {"status": "error", "message": "Form gönderilemedi veya form bulunamadı"}


# --- Ana Fonksiyon -----------------------------------------------------------

def batch_fill_from_df(df: pd.DataFrame,
                       form_payload: dict,
                       locales: dict = None,
                       max_sites: int = 10,
                       dwell_seconds: float = 5.0,
                       out_dir=None,
                       headless: bool = True,
                       sites_override: Optional[List[str]] = None,
                       captcha_mode: str = "skip",
                       api_key: str = None,
                       domain_list_file: str = None,
                       personalized_content_map: dict = None) -> pd.DataFrame:
    """
    DataFrame'den websiteleri alır ve otomatik form doldurma yapar.
    
    Args:
        df: Website bilgilerini içeren DataFrame
        form_payload: Form alanları için veri
        locales: Dil ayarları (opsiyonel)
        max_sites: Maksimum ziyaret edilecek site sayısı
        dwell_seconds: Her sitede geçirilecek süre
        out_dir: Çıktı dizini (opsiyonel)
        headless: Tarayıcı görünür olsun mu
        sites_override: Özel site listesi (opsiyonel)
        captcha_mode: "skip", "manual", "solver"
        api_key: Anti-Captcha API anahtarı
        domain_list_file: Domain listesi dosyası (opsiyonel)
        personalized_content_map: Kişiselleştirilmiş içerik haritası
    """
    driver = create_driver(headless=headless)
    rows_out = []

    # Siteleri topla - önce txt dosyası kontrol et
    websites = []
    if domain_list_file:
        try:
            # Dosya yolu kontrolü ve okuma
            import os
            if os.path.exists(domain_list_file):
                print(f"Domain listesi dosyası okunuyor: {domain_list_file}")
                with open(domain_list_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        s = line.strip()
                        if s and not s.startswith('#') and s not in websites:  # Yorum satırlarını atla
                            # http/https ekle eğer yoksa
                            if not s.startswith(('http://', 'https://')):
                                s = 'https://' + s
                            websites.append(s)
                print(f"Txt dosyasından {len(websites)} domain yüklendi")
            else:
                print(f"Domain listesi dosyası bulunamadı: {domain_list_file}")
        except Exception as e:
            print(f"Domain listesi okuma hatası: {e}")
    
    # Eğer txt dosyasından domain yüklenmediyse, DataFrame'den al
    if not websites:
        print("DataFrame'den websiteleri alınıyor...")
        for _, r in df.iterrows():
            site = r.get("Firma Websitesi") or r.get("Website") or r.get("Firma Web Sitesi") or r.get("Firma Websitesi ") or ""
            site = str(site).strip()
            if site and site not in websites:
                # http/https ekle eğer yoksa
                if not site.startswith(('http://', 'https://')):
                    site = 'https://' + site
                websites.append(site)
            if len(websites) >= max_sites:
                break
        print(f"DataFrame'den {len(websites)} website alındı")

    # payload değerleri (ileride gerekirse)
    for site in websites[:max_sites]:
        used_url = ""
        submitted = False
        reason = ""
        try:
            base = get_root_url(site)

            # 1) Ana sayfa → dil tespit + link çıkarımı
            start_url = base or site
            driver.get(start_url)
            try:
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            except Exception:
                pass
            try_close_cookies(driver)
            time.sleep(0.6)
            html = driver.page_source or ""

            lang = detect_lang(html, default="en")
            if not lang or lang == "en":
                lang2 = detect_lang_from_links(html)
                if lang2:
                    lang = lang2

            # menüden aday linkler
            anchor_candidates = extract_contact_links(base, html, lang)

            # 2) denenecek URL sırası
            candidates = [u for (u, _) in anchor_candidates]
            for p in normalize_paths_for_lang(lang):
                candidates.append(urljoin(base, p))

            # tekrarları kaldır
            seen = set()
            uniq_candidates = []
            for c in candidates:
                if c not in seen:
                    seen.add(c)
                    uniq_candidates.append(c)

            # 3) her aday URL’de formu doldur + submit et
            for c in uniq_candidates:
                used_url = c
                driver.get(c)
                try:
                    WebDriverWait(driver, 12).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                except Exception:
                    pass
                try_close_cookies(driver)
                time.sleep(0.6)

                # CAPTCHA kontrol ve çözüm
                if detect_captcha(driver):
                    if not solve_captchas(driver, captcha_mode, CaptchaSolver(api_key) if api_key else None):
                        reason = "captcha_detected"
                        break

                # Sayfadaki en iyi iletişim formunu seç (newsletter çıkartma ile)
                form_element = None
                try:
                    forms = driver.find_elements(By.TAG_NAME, "form")
                    if forms:
                        forms = sorted(forms, key=lambda f: score_form(f, driver.current_url), reverse=True)
                        for f in forms:
                            if score_form(f, driver.current_url) > 0:
                                form_element = f
                                break
                except Exception:
                    pass

                if form_element is None:
                    reason = "no_contact_form_found"
                    continue

                # Kişiselleştirilmiş içerik varsa kullan
                current_payload = {**form_payload}
                if personalized_content_map:
                    # Site domain'ini al
                    site_domain = get_root_url(site)
                    if site_domain:
                        site_domain = site_domain.replace('https://', '').replace('http://', '').replace('www.', '')
                    
                    # Kişiselleştirilmiş içeriği bul
                    personalized = None
                    for key, content in personalized_content_map.items():
                        if site_domain and (site_domain in key or key in site_domain):
                            personalized = content
                            break
                    
                    # Kişiselleştirilmiş içerik varsa mesajı güncelle
                    if personalized and isinstance(personalized, dict):
                        if personalized.get('message'):
                            current_payload['message'] = personalized['message']
                        if personalized.get('subject'):
                            current_payload['subject'] = personalized['subject']

                # Debug: Form doldurma başlıyor
                print(f"Form doldurma başlıyor - Site: {site}")
                print(f"Form payload: {current_payload}")
                
                # Seçili form için doldurma/gönderme
                result = fill_and_submit_form(driver, form_payload=current_payload, captcha_mode=captcha_mode,
                                              api_key=api_key, headless=headless, dwell_seconds=dwell_seconds, form_element=form_element)
                
                print(f"Form doldurma sonucu: {result}")

                if result.get("status") == "success":
                    submitted = True
                    reason = "submitted"
                    rows_out.append({
                        "Website": site,
                        "Contact URL": used_url,
                        "Language": lang,
                        "Status": "Success",
                        "Details": reason
                    })
                    break  # bir adayda başarılıysak diğer URL'leri denemeyelim
                elif result.get("status") == "captcha_detected":
                    reason = "captcha_detected"
                    break
                else:
                    reason = result.get("message", "no_submit_or_no_form")

            if not submitted and reason != "captcha_detected":
                rows_out.append({
                    "Website": site,
                    "Contact URL": used_url or base,
                    "Language": lang,
                    "Status": "Failed",
                    "Details": reason or "no_submit_or_no_form"
                })
            elif reason == "captcha_detected":
                rows_out.append({
                    "Website": site,
                    "Contact URL": used_url or base,
                    "Language": lang,
                    "Status": "Captcha Detected",
                    "Details": "captcha_detected"
                })
        except Exception as e:
            rows_out.append({
                "Website": site,
                "Contact URL": used_url or get_root_url(site),
                "Language": "unknown",
                "Status": "Error",
                "Details": f"error: {str(e)}"
            })

    try:
        driver.quit()
    except Exception:
        pass

    return pd.DataFrame(rows_out)


# --- Örnek Ana İşlem ---------------------------------------------------------

def main():
    """Ana işlem fonksiyonu örneği."""
    # API anahtarı (Anti-Captcha'dan alınan)
    API_KEY = "0a9e3361d9fb101befa798254ddc1901"

    # CAPTCHA modu: "skip", "manual" veya "solver"
    CAPTCHA_MODE = "solver"

    # Örnek DataFrame oluşturma
    df = pd.DataFrame([{
        "Firma Websitesi": "https://example.com"
    }])

    # Form doldurma payload
    form_payload = {
        "name": "John",
        "surname": "Doe",
        "email": "john@example.com",
        "phone": "+12025550199",
        "subject": "Business Inquiry",
        "message": "Hello, this is a test message."
    }

    # batch_fill_from_df çağrısı
    results_df = batch_fill_from_df(
        df=df,
        form_payload=form_payload,
        max_sites=1,
        dwell_seconds=5,
        headless=False,
        captcha_mode=CAPTCHA_MODE,
        api_key=API_KEY
    )

    print(results_df)


if __name__ == "__main__":
    main()