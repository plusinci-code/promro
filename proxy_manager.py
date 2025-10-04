# -*- coding: utf-8 -*-
"""
proxy_manager.py
----------------
Proxy rotasyonu ve IP değiştirme sistemi.
CAPTCHA bypass için farklı IP adresleri kullanır.
"""

import random
import time
import requests
from typing import List, Dict, Optional, Tuple
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

class ProxyManager:
    """Proxy yönetimi ve rotasyonu için sınıf"""
    
    def __init__(self):
        self.proxy_list = []
        self.current_proxy_index = 0
        self.failed_proxies = set()
        self.proxy_timeouts = {}
        
    def add_proxy(self, proxy: str, proxy_type: str = "http") -> None:
        """Proxy listesine yeni proxy ekler"""
        if proxy not in [p["proxy"] for p in self.proxy_list]:
            self.proxy_list.append({
                "proxy": proxy,
                "type": proxy_type,
                "last_used": 0,
                "success_count": 0,
                "fail_count": 0
            })
    
    def add_proxy_list(self, proxies: List[str], proxy_type: str = "http") -> None:
        """Toplu proxy ekleme"""
        for proxy in proxies:
            self.add_proxy(proxy, proxy_type)
    
    def get_next_proxy(self) -> Optional[Dict]:
        """Sıradaki proxy'yi döndürür"""
        if not self.proxy_list:
            return None
            
        # Başarısız proxy'leri filtrele
        available_proxies = [p for p in self.proxy_list if p["proxy"] not in self.failed_proxies]
        
        if not available_proxies:
            # Tüm proxy'ler başarısızsa, listeyi sıfırla
            self.failed_proxies.clear()
            available_proxies = self.proxy_list
        
        # En az kullanılan proxy'yi seç
        available_proxies.sort(key=lambda x: (x["fail_count"], x["last_used"]))
        return available_proxies[0]
    
    def mark_proxy_success(self, proxy: str) -> None:
        """Proxy başarılı kullanımını işaretler"""
        for p in self.proxy_list:
            if p["proxy"] == proxy:
                p["success_count"] += 1
                p["last_used"] = time.time()
                break
    
    def mark_proxy_failed(self, proxy: str) -> None:
        """Proxy başarısız kullanımını işaretler"""
        for p in self.proxy_list:
            if p["proxy"] == proxy:
                p["fail_count"] += 1
                if p["fail_count"] >= 3:  # 3 başarısızlıkta listeye ekle
                    self.failed_proxies.add(proxy)
                break
    
    def test_proxy(self, proxy: str, timeout: int = 10) -> bool:
        """Proxy'nin çalışıp çalışmadığını test eder"""
        try:
            proxies = {
                "http": f"http://{proxy}",
                "https": f"http://{proxy}"
            }
            
            response = requests.get(
                "http://httpbin.org/ip", 
                proxies=proxies, 
                timeout=timeout
            )
            
            if response.status_code == 200:
                return True
        except Exception:
            pass
        
        return False
    
    def get_working_proxies(self, max_proxies: int = 10) -> List[str]:
        """Çalışan proxy'leri test eder ve döndürür"""
        working_proxies = []
        
        for proxy_info in self.proxy_list[:max_proxies]:
            proxy = proxy_info["proxy"]
            if self.test_proxy(proxy):
                working_proxies.append(proxy)
                self.mark_proxy_success(proxy)
            else:
                self.mark_proxy_failed(proxy)
        
        return working_proxies

def get_free_proxy_list() -> List[str]:
    """Ücretsiz proxy listesi döndürür"""
    # Bu örnek proxy'ler gerçek değil, sadece format gösterimi
    # Gerçek kullanımda proxy sağlayıcılarından alınmalı
    return [
        "proxy1.example.com:8080",
        "proxy2.example.com:3128",
        "proxy3.example.com:8080",
        "proxy4.example.com:3128",
        "proxy5.example.com:8080",
    ]

def get_premium_proxy_list() -> List[str]:
    """Premium proxy listesi döndürür"""
    # Premium proxy sağlayıcılarından alınacak
    return [
        "premium1.provider.com:8080",
        "premium2.provider.com:3128",
        "premium3.provider.com:8080",
    ]

def create_proxy_options(proxy: str) -> Options:
    """Proxy ile Chrome seçenekleri oluşturur"""
    options = Options()
    
    # Proxy ayarları
    options.add_argument(f"--proxy-server=http://{proxy}")
    
    # Proxy authentication (gerekirse)
    # options.add_argument(f"--proxy-auth=username:password")
    
    return options

def rotate_user_agent() -> str:
    """Rastgele user agent döndürür"""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0",
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/121.0",
    ]
    return random.choice(user_agents)

def get_random_delay() -> float:
    """Rastgele bekleme süresi döndürür"""
    return random.uniform(2.0, 8.0)

def create_stealth_proxy_driver(proxy: str, headless: bool = True) -> webdriver.Chrome:
    """Proxy ile stealth driver oluşturur"""
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    
    options = Options()
    
    # Proxy ayarları
    options.add_argument(f"--proxy-server=http://{proxy}")
    
    # Stealth ayarları
    if headless:
        options.add_argument("--headless=new")
    
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-translate")
    options.add_argument("--hide-scrollbars")
    options.add_argument("--mute-audio")
    
    # Rastgele user agent
    options.add_argument(f"user-agent={rotate_user_agent()}")
    
    # Stealth prefs
    prefs = {
        "profile.default_content_setting_values": {
            "notifications": 2,
            "geolocation": 2,
            "media_stream": 2,
        },
        "profile.default_content_settings.popups": 0,
        "profile.managed_default_content_settings.images": 1,
        "profile.password_manager_enabled": False,
        "credentials_enable_service": False,
        "webrtc.ip_handling_policy": "disable_non_proxied_udp",
        "webrtc.multiple_routes_enabled": False,
        "webrtc.nonproxied_udp_enabled": False
    }
    options.add_experimental_option("prefs", prefs)
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    # Stealth JavaScript injection
    try:
        stealth_script = """
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        Object.defineProperty(navigator, 'permissions', {get: () => ({query: () => Promise.resolve({state: 'granted'})})});
        window.chrome = {runtime: {}};
        Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
        Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 4});
        Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
        Object.defineProperty(screen, 'colorDepth', {get: () => 24});
        Object.defineProperty(screen, 'pixelDepth', {get: () => 24});
        """
        driver.execute_script(stealth_script)
    except Exception:
        pass
    
    return driver

def test_proxy_connection(proxy: str, test_url: str = "http://httpbin.org/ip") -> Tuple[bool, str]:
    """Proxy bağlantısını test eder"""
    try:
        proxies = {
            "http": f"http://{proxy}",
            "https": f"http://{proxy}"
        }
        
        response = requests.get(test_url, proxies=proxies, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            ip = data.get("origin", "Unknown")
            return True, ip
    except Exception as e:
        return False, str(e)
    
    return False, "Connection failed"

def get_proxy_recommendations() -> Dict[str, str]:
    """Proxy önerilerini döndürür"""
    return {
        "free": "Ücretsiz proxy'ler - Yavaş ama ücretsiz",
        "premium": "Premium proxy'ler - Hızlı ve güvenilir",
        "residential": "Residential proxy'ler - En güvenilir",
        "datacenter": "Datacenter proxy'ler - Hızlı ama tespit edilebilir",
        "mobile": "Mobile proxy'ler - Mobil IP'ler",
        "rotating": "Rotating proxy'ler - Otomatik IP değişimi"
    }

