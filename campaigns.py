
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List
from pathlib import Path
import uuid, os, json, datetime
from .utils import CAMPAIGNS_DIR, ensure_dir, write_json, read_json, slugify

@dataclass
class Campaign:
    id: str
    name: str
    created_at: str
    firm_name: str
    firm_site: str
    products: List[str]
    target_country: str
    ai_temperature: float = 0.2
    ai_max_tokens: int = 1200
    model: str = "gpt-5.1-mini"

    def save(self):
        cdir = ensure_dir(CAMPAIGNS_DIR / self.id)
        write_json(cdir / "campaign.json", asdict(self))
        return cdir

def create_campaign(firm_name: str, firm_site: str, products: List[str], target_country: str, ai_temperature: float, ai_max_tokens: int, model: str) -> Campaign:
    uid = str(uuid.uuid4())[:8]
    base_name = f"{firm_name}-{target_country}-{uid}"
    name = slugify(base_name)
    camp = Campaign(
        id=name,
        name=name,
        created_at=datetime.datetime.utcnow().isoformat()+"Z",
        firm_name=firm_name,
        firm_site=firm_site,
        products=products,
        target_country=target_country,
        ai_temperature=ai_temperature,
        ai_max_tokens=ai_max_tokens,
        model=model
    )
    camp.save()
    ensure_dir(CAMPAIGNS_DIR / camp.id / "outputs")
    return camp

def load_campaigns() -> Dict[str, Any]:
    out = {}
    for p in CAMPAIGNS_DIR.glob("*/campaign.json"):
        data = read_json(p, {})
        if data:
            out[data["id"]] = data
    return out

def load_campaign(camp_id: str) -> Optional[Campaign]:
    data = read_json(CAMPAIGNS_DIR / camp_id / "campaign.json", None)
    if not data: return None
    return Campaign(**data)
