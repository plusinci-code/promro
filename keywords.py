from typing import List, Optional
from .llm import complete
import json

# Country to domain mapping for site-specific searches
COUNTRY_DOMAINS = {
    "Germany": ".de", "Deutschland": ".de", "Almanya": ".de",
    "Spain": ".es", "España": ".es", "İspanya": ".es", 
    "France": ".fr", "Francia": ".fr", "Fransa": ".fr",
    "Italy": ".it", "Italia": ".it", "İtalya": ".it",
    "Australia": ".com.au", "Avustralya": ".com.au",
    "United Kingdom": ".co.uk", "UK": ".co.uk", "İngiltere": ".co.uk",
    "Canada": ".ca", "Kanada": ".ca",
    "Netherlands": ".nl", "Hollanda": ".nl",
    "Belgium": ".be", "Belçika": ".be",
    "Austria": ".at", "Avusturya": ".at",
    "Switzerland": ".ch", "İsviçre": ".ch",
    "Poland": ".pl", "Polonya": ".pl",
    "Czech Republic": ".cz", "Çekya": ".cz",
    "Turkey": ".com.tr", "Türkiye": ".com.tr",
    "Brazil": ".com.br", "Brezilya": ".com.br",
    "Mexico": ".com.mx", "Meksika": ".com.mx",
    "Japan": ".co.jp", "Japonya": ".co.jp",
    "South Korea": ".co.kr", "Güney Kore": ".co.kr",
    "India": ".co.in", "Hindistan": ".co.in",
    "China": ".cn", "Çin": ".cn",
    "Russia": ".ru", "Rusya": ".ru"
}

# Language mapping for target countries
COUNTRY_LANGUAGES = {
    "Germany": "de", "Deutschland": "de", "Almanya": "de",
    "Spain": "es", "España": "es", "İspanya": "es",
    "France": "fr", "Francia": "fr", "Fransa": "fr", 
    "Italy": "it", "Italia": "it", "İtalya": "it",
    "Australia": "en", "Avustralya": "en",
    "United Kingdom": "en", "UK": "en", "İngiltere": "en",
    "Canada": "en", "Kanada": "en",
    "Netherlands": "nl", "Hollanda": "nl",
    "Belgium": "nl", "Belçika": "nl",
    "Austria": "de", "Avusturya": "de",
    "Switzerland": "de", "İsviçre": "de",
    "Poland": "pl", "Polonya": "pl",
    "Czech Republic": "cs", "Çekya": "cs",
    "Turkey": "tr", "Türkiye": "tr",
    "Brazil": "pt", "Brezilya": "pt",
    "Mexico": "es", "Meksika": "es",
    "Japan": "ja", "Japonya": "ja",
    "South Korea": "ko", "Güney Kore": "ko",
    "India": "en", "Hindistan": "en",
    "China": "zh", "Çin": "zh",
    "Russia": "ru", "Rusya": "ru"
}

SYSTEM = (
    "You are an expert B2B export marketer specializing in manufacturer-to-buyer keyword generation. "
    "You understand that manufacturers need to find distributors, wholesalers, retailers, and industrial users - NOT end consumers. "
    "Generate precise, high-intent B2B keywords in the specified language. "
    "Output strictly as a JSON array of strings, no explanations, no duplicates."
)

def generate_keywords(
    api_key: str,
    model: str,
    firm_name: str,
    products: List[str],
    target_country: str,
    firm_profile: str,
    target_lang: str,
    max_terms: int = 40,
    temperature: Optional[float] = None
) -> List[str]:
    """Generate intelligent B2B buyer-intent keywords based on product type and target market."""
    
    # Auto-detect language if not specified properly
    detected_lang = COUNTRY_LANGUAGES.get(target_country, target_lang)
    domain_suffix = COUNTRY_DOMAINS.get(target_country, ".com")
    
    # Create product-specific examples
    product_str = ", ".join(products) if isinstance(products, list) else str(products)
    
    prompt = f"""
MANUFACTURER: {firm_name}
PRODUCTS: {product_str}
TARGET COUNTRY: {target_country}
TARGET LANGUAGE: {detected_lang}
DOMAIN SUFFIX: {domain_suffix}
COMPANY PROFILE: {firm_profile}

TASK: Generate B2B keywords for finding potential buyers, distributors, wholesalers, and industrial users.

CRITICAL REQUIREMENTS:
1. Keywords must be in {detected_lang} language (not English unless target is English-speaking)
2. Focus on B2B buyers - manufacturers need distributors/wholesalers/retailers, NOT end consumers
3. Include site-specific searches using {domain_suffix} domain
4. Consider what industries would USE these products (not who makes them)
5. Include buying intent terms: wholesale, distributor, importer, supplier, dealer, retailer

KEYWORD CATEGORIES TO GENERATE:
1. Direct product searches with buying intent:
   - "wholesale [product] site:{domain_suffix}"
   - "buy [product] bulk site:{domain_suffix}"
   - "[product] distributor site:{domain_suffix}"

2. Industry-specific buyer searches:
   - "[industry that uses product] manufacturer {target_country}"
   - "[industry] factory {target_country}"
   - "[industry] company {target_country}"

3. Business type searches:
   - "[product] importer {target_country}"
   - "[product] wholesaler {target_country}"
   - "[product] dealer {target_country}"

EXAMPLES FOR CONTEXT:
- If product is "shotgun": target gun shops, sporting goods stores, hunting equipment dealers
- If product is "checkweigher": target food manufacturers, pharmaceutical companies, packaging companies
- If product is "pump": target industrial companies, construction firms, agricultural businesses

Generate {max_terms} unique keywords in {detected_lang} language, returned as JSON array.
""".strip()

    out = complete(
        prompt,
        api_key=api_key,
        model=model,
        temperature=0.7,
        system=SYSTEM
    )

    try:
        # Try to parse as JSON first
        arr = json.loads(out)
        if isinstance(arr, list):
            keywords = [s.strip() for s in arr if isinstance(s, str) and s.strip()]
        else:
            raise ValueError("Not a JSON array")
    except Exception:
        # Fallback: parse line by line
        lines = out.strip().split('\n')
        keywords = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('[') and not line.startswith(']'):
                # Remove JSON formatting artifacts
                line = line.strip('",[]')
                if line:
                    keywords.append(line)
    
    # Clean and enhance keywords
    final_keywords = []
    seen = set()
    
    for keyword in keywords[:max_terms]:
        keyword = keyword.strip()
        if not keyword or keyword.lower() in seen:
            continue
            
        # Add country context if missing
        if target_country.lower() not in keyword.lower():
            keyword = f"{keyword} {target_country}"
            
        seen.add(keyword.lower())
        final_keywords.append(keyword)
    
    return final_keywords[:max_terms]