
# -*- coding: utf-8 -*-
import os
import sys
import re
import json
import time
import csv
import uuid
import datetime
import pathlib
import hashlib
import logging
import shutil
import random
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd

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

LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=LOG_DIR / "app.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

ROOT = Path(__file__).resolve().parents[2]
CAMPAIGNS_DIR = ROOT / "campaigns"
DATA_DIR = ROOT / "data"

def slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_\-]+","-", s.strip())
    s = re.sub(r"-+","-", s)
    return s.strip("-").lower() or "campaign"

def now_iso() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat()+"Z"

def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path

def save_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False, encoding="utf-8-sig")

def read_json(path: Path, default: Any=None) -> Any:
    if not path.exists():
        return default
    with open(path,"r",encoding="utf-8") as f:
        return json.load(f)

def write_json(path: Path, obj: Any) -> None:
    with open(path,"w",encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def uniq_list(seq: List[str]) -> List[str]:
    seen=set(); out=[]
    for x in seq:
        k = x.strip()
        if k and k not in seen:
            seen.add(k); out.append(k)
    return out

def detect_lang_from_domain(domain: str) -> str:
    # naive heuristic by TLD
    tld = domain.split(".")[-1].lower()
    mapping = {
        "tr":"tr","de":"de","es":"es","fr":"fr","it":"it","pt":"pt","nl":"nl",
        "se":"sv","no":"no","dk":"da","pl":"pl","cz":"cs","ro":"ro","ru":"ru",
        "gr":"el","hu":"hu","uk":"uk","ua":"uk",
    }
    return mapping.get(tld, "en")

def sanitize_email(e: str) -> str:
    e=e.strip()
    if "<" in e and ">" in e:
        e = re.sub(r".*<([^>]+)>.*", r"\1", e)
    return e

def merge_tables(primary: List[Dict[str,Any]], secondary: List[Dict[str,Any]], key="Firma Websitesi") -> List[Dict[str,Any]]:
    by = { (row.get(key) or "").lower(): row for row in primary if row.get(key) }
    for r in secondary:
        k = (r.get(key) or "").lower()
        if not k: 
            continue
        if k in by:
            by[k].update({k2:v for k2,v in r.items() if v not in ("",None)})
        else:
            by[k]=r
    return list(by.values())
