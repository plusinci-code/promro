from typing import Optional
import re
import requests
from bs4 import BeautifulSoup

COUNTRY_TO_LANG = {
    "germany":"de","deutschland":"de","de":"de",
    "spain":"es","españa":"es","es":"es",
    "france":"fr","fr":"fr",
    "italy":"it","italia":"it","it":"it",
    "portugal":"pt","pt":"pt",
    "netherlands":"nl","holland":"nl","nl":"nl",
    "sweden":"sv","sv":"sv","se":"sv",
    "norway":"no","no":"no",
    "denmark":"da","dk":"da",
    "poland":"pl","pl":"pl",
    "czechia":"cs","czech republic":"cs","cz":"cs",
    "romania":"ro","ro":"ro",
    "russia":"ru","ru":"ru",
    "united kingdom":"en","uk":"en","england":"en","great britain":"en",
    "united states":"en","usa":"en","us":"en",
    "canada":"en",
    "mexico":"es",
    "brazil":"pt",
    "turkey":"tr","türkiye":"tr","tr":"tr",
    "austria":"de",
    "switzerland":"de",
    "belgium":"nl",
    "greece":"el","gr":"el",
    "hungary":"hu","hu":"hu",
    "ukraine":"uk","ua":"uk",
    "bulgaria":"bg",
    "croatia":"hr",
    "slovakia":"sk",
    "slovenia":"sl",
    "lithuania":"lt",
    "latvia":"lv",
    "estonia":"et",
    "japan":"ja",
    "china":"zh",
    "south korea":"ko","korea":"ko"
}

def country_to_lang(country: str, default: str = "en") -> str:
    if not country:
        return default
    key = country.strip().lower()
    return COUNTRY_TO_LANG.get(key, default)

def detect_site_lang(url: str) -> Optional[str]:
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        html = resp.text
        soup = BeautifulSoup(html, "lxml")
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):
            return html_tag.get("lang").split("-")[0].lower()
        for link in soup.find_all("link", attrs={"rel":"alternate"}):
            hl = link.get("hreflang")
            if hl and hl.lower() not in ("x-default","all"):
                return hl.split("-")[0].lower()
        meta = soup.find("meta", attrs={"http-equiv": re.compile("content-language", re.I)})
        if meta and meta.get("content"):
            return meta.get("content").split(",")[0].strip().lower()
    except Exception:
        return None
    return None