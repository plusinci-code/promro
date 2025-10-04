
from typing import List, Dict, Any, Optional
import os, httpx, time, re
from .utils import save_csv
import pandas as pd

def hunter_enrich(domain: str, api_key: str) -> List[Dict[str,Any]]:
    url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={api_key}"
    r = httpx.get(url, timeout=30)
    r.raise_for_status()
    data = r.json().get("data",{})
    out = []
    for e in data.get("emails",[]):
        out.append({
            "full_name": e.get("first_name","") + " " + e.get("last_name",""),
            "position": e.get("position",""),
            "email": e.get("value",""),
            "type": e.get("type",""),
            "confidence": e.get("confidence","")
        })
    return out

def apollo_enrich(domain: str, api_key: str) -> List[Dict[str,Any]]:
    # Placeholder: Apollo GraphQL or REST depending on plan
    # This is a simple domain people search endpoint example (may require org_id)
    headers = {"Authorization": api_key, "Content-Type":"application/json"}
    url = "https://api.apollo.io/v1/people/search"
    payload = {"q_organization_domains": domain, "page": 1}
    r = httpx.post(url, json=payload, headers=headers, timeout=45)
    if r.status_code >= 400:
        return []
    j = r.json()
    out=[]
    for p in j.get("people",[]):
        out.append({
            "full_name": p.get("name",""),
            "position": p.get("title",""),
            "email": p.get("email",""),
            "type": "person",
            "confidence": ""
        })
    return out

def rocketreach_enrich(domain: str, api_key: str) -> List[Dict[str,Any]]:
    headers={"Api-Key":api_key}
    url = f"https://api.rocketreach.co/v1/api/lookupProfile?company_domain={domain}"
    r = httpx.get(url, headers=headers, timeout=45)
    if r.status_code >= 400:
        return []
    j = r.json()
    out=[]
    for p in j.get("profiles",[]):
        out.append({
            "full_name": p.get("name",""),
            "position": p.get("current_title",""),
            "email": p.get("current_email",""),
            "type": "person",
            "confidence": ""
        })
    return out

def scrape_social_emails_from_serp(domain: str, engine_html: str) -> List[str]:
    # naive regex for emails in given html snippet (SERP description)
    emails = re.findall(r"[A-Za-z0-9._%+-]+@" + re.escape(domain), engine_html, flags=re.I)
    return sorted(set(emails))

def enrich_dataframe(df: pd.DataFrame, provider: str, api_key: str) -> pd.DataFrame:
    rows=[]
    for _,row in df.iterrows():
        site = row.get("Firma Websitesi","")
        domain = ""
        if site:
            try:
                import urllib.parse as up
                u = up.urlparse(site)
                domain = u.netloc
            except Exception:
                pass
        if not domain: 
            continue
        people=[]
        try:
            if provider=="Hunter" and api_key:
                people = hunter_enrich(domain, api_key)
            elif provider=="Apollo" and api_key:
                people = apollo_enrich(domain, api_key)
            elif provider=="RocketReach" and api_key:
                people = rocketreach_enrich(domain, api_key)
        except Exception:
            people=[]
        for p in people:
            rows.append({
                "Firma Websitesi": site,
                "Domain": domain,
                "Ad Soyad": p.get("full_name",""),
                "Ünvan": p.get("position",""),
                "Email": p.get("email",""),
                "Tür": p.get("type",""),
                "Güven": p.get("confidence","")
            })
    return pd.DataFrame(rows)
