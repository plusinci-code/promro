# -*- coding: utf-8 -*-
"""
Gelişmiş CAPTCHA Çözme Modülü
Cloudflare, reCAPTCHA, hCaptcha ve diğer CAPTCHA türlerini Anti-Captcha API ile çözer
"""

import time
import re
from typing import Optional, Dict, Any
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from python_anticaptcha import AnticaptchaClient, NoCaptchaTaskProxylessTask, ImageToTextTask
except ImportError as e:
    print(f"Import hatası: {e}")
    # Fallback imports
    pass


class AdvancedCaptchaSolver:
    """Gelişmiş CAPTCHA çözme sınıfı"""
    
    def __init__(self, api_key: str):
        """
        Args:
            api_key: Anti-Captcha API anahtarı
        """
        self.client = AnticaptchaClient(api_key)
        self.api_key = api_key
    
    def detect_captcha_type(self, driver) -> Optional[str]:
        """Sayfadaki CAPTCHA türünü tespit eder"""
        try:
            # Cloudflare kontrolü
            if self._is_cloudflare_challenge(driver):
                return "cloudflare"
            
            # reCAPTCHA v2 kontrolü
            if self._is_recaptcha_v2(driver):
                return "recaptcha_v2"
            
            # reCAPTCHA v3 kontrolü
            if self._is_recaptcha_v3(driver):
                return "recaptcha_v3"
            
            # hCaptcha kontrolü
            if self._is_hcaptcha(driver):
                return "hcaptcha"
            
            # Görsel CAPTCHA kontrolü
            if self._is_image_captcha(driver):
                return "image_captcha"
            
            return None
            
        except Exception as e:
            print(f"CAPTCHA türü tespit hatası: {e}")
            return None
    
    def _is_cloudflare_challenge(self, driver) -> bool:
        """Cloudflare challenge sayfası kontrolü"""
        try:
            # Cloudflare challenge sayfası göstergeleri
            cloudflare_indicators = [
                "Checking your browser before accessing",
                "Please wait while your request is being verified",
                "DDoS protection by Cloudflare",
                "cf-browser-verification",
                "cf-challenge-running",
                "Ray ID:",
                "cloudflare"
            ]
            
            page_source = driver.page_source.lower()
            title = driver.title.lower()
            
            # Sayfa içeriği kontrolü
            for indicator in cloudflare_indicators:
                if indicator.lower() in page_source or indicator.lower() in title:
                    return True
            
            # Cloudflare elementleri kontrolü
            cf_selectors = [
                "[data-ray]",
                ".cf-browser-verification",
                "#cf-challenge-running",
                ".cf-error-details",
                ".cf-wrapper"
            ]
            
            for selector in cf_selectors:
                if driver.find_elements(By.CSS_SELECTOR, selector):
                    return True
                    
            return False
            
        except Exception:
            return False
    
    def _is_recaptcha_v2(self, driver) -> bool:
        """reCAPTCHA v2 kontrolü"""
        try:
            selectors = [
                ".g-recaptcha",
                "[data-sitekey]",
                "iframe[src*='recaptcha']",
                "#recaptcha",
                ".recaptcha"
            ]
            
            for selector in selectors:
                if driver.find_elements(By.CSS_SELECTOR, selector):
                    return True
            return False
        except Exception:
            return False
    
    def _is_recaptcha_v3(self, driver) -> bool:
        """reCAPTCHA v3 kontrolü"""
        try:
            # v3 genellikle gizlidir, script kontrolü
            scripts = driver.find_elements(By.TAG_NAME, "script")
            for script in scripts:
                src = script.get_attribute("src") or ""
                if "recaptcha/releases/v3" in src or "recaptcha/api.js" in src:
                    return True
            return False
        except Exception:
            return False
    
    def _is_hcaptcha(self, driver) -> bool:
        """hCaptcha kontrolü"""
        try:
            selectors = [
                ".h-captcha",
                "[data-hcaptcha-sitekey]",
                "iframe[src*='hcaptcha']"
            ]
            
            for selector in selectors:
                if driver.find_elements(By.CSS_SELECTOR, selector):
                    return True
            return False
        except Exception:
            return False
    
    def _is_image_captcha(self, driver) -> bool:
        """Görsel CAPTCHA kontrolü"""
        try:
            selectors = [
                "img[src*='captcha']",
                "img[alt*='captcha']",
                ".captcha-image",
                "#captcha-image"
            ]
            
            for selector in selectors:
                if driver.find_elements(By.CSS_SELECTOR, selector):
                    return True
            return False
        except Exception:
            return False
    
    def solve_cloudflare_challenge(self, driver, max_wait: int = 30) -> bool:
        """Cloudflare challenge çözümü"""
        try:
            print("🔄 Cloudflare challenge tespit edildi, çözülüyor...")
            
            # Cloudflare'in otomatik çözümünü bekle
            start_time = time.time()
            while time.time() - start_time < max_wait:
                try:
                    # Challenge tamamlandı mı kontrol et
                    if not self._is_cloudflare_challenge(driver):
                        print("✅ Cloudflare challenge başarıyla çözüldü")
                        return True
                    
                    # Checkbox varsa tıkla
                    checkbox_selectors = [
                        "input[type='checkbox']",
                        ".cf-turnstile",
                        "#challenge-form input[type='checkbox']"
                    ]
                    
                    for selector in checkbox_selectors:
                        try:
                            checkbox = WebDriverWait(driver, 2).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                            )
                            checkbox.click()
                            print("☑️ Cloudflare checkbox tıklandı")
                            time.sleep(2)
                            break
                        except:
                            continue
                    
                    time.sleep(2)
                    
                except Exception:
                    continue
            
            # Son kontrol
            if not self._is_cloudflare_challenge(driver):
                print("✅ Cloudflare challenge çözüldü")
                return True
            else:
                print("❌ Cloudflare challenge çözülemedi")
                return False
                
        except Exception as e:
            print(f"❌ Cloudflare challenge çözüm hatası: {e}")
            return False
    
    def solve_recaptcha_v2(self, driver) -> bool:
        """reCAPTCHA v2 çözümü"""
        try:
            print("🔄 reCAPTCHA v2 tespit edildi, çözülüyor...")
            
            # Site key bul
            site_key = self._get_recaptcha_sitekey(driver)
            if not site_key:
                print("❌ reCAPTCHA site key bulunamadı")
                return False
            
            current_url = driver.current_url
            
            # Anti-Captcha ile çöz
            task = NoCaptchaTaskProxylessTask(current_url, site_key)
            job = self.client.createTask(task)
            job.join()
            
            solution = job.get_solution_response()
            if not solution:
                print("❌ reCAPTCHA çözülemedi")
                return False
            
            # Çözümü sayfaya uygula
            driver.execute_script(f"""
                document.getElementById('g-recaptcha-response').innerHTML = '{solution}';
                if (typeof grecaptcha !== 'undefined') {{
                    grecaptcha.getResponse = function() {{ return '{solution}'; }};
                }}
            """)
            
            print("✅ reCAPTCHA v2 çözüldü")
            return True
            
        except Exception as e:
            print(f"❌ reCAPTCHA v2 çözüm hatası: {e}")
            return False
    
    def solve_image_captcha(self, driver) -> bool:
        """Görsel CAPTCHA çözümü"""
        try:
            print("🔄 Görsel CAPTCHA tespit edildi, çözülüyor...")
            
            # CAPTCHA resmini bul
            img_selectors = [
                "img[src*='captcha']",
                "img[alt*='captcha']",
                ".captcha-image img",
                "#captcha-image"
            ]
            
            captcha_img = None
            for selector in img_selectors:
                try:
                    captcha_img = driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except:
                    continue
            
            if not captcha_img:
                print("❌ CAPTCHA resmi bulunamadı")
                return False
            
            # Resmi screenshot al
            screenshot = captcha_img.screenshot_as_png
            
            # Anti-Captcha ile çöz
            task = ImageToTextTask(screenshot)
            job = self.client.createTask(task)
            job.join()
            
            captcha_text = job.get_captcha_text()
            if not captcha_text:
                print("❌ Görsel CAPTCHA çözülemedi")
                return False
            
            # Input alanını bul ve doldur
            input_selectors = [
                "input[name*='captcha']",
                "input[id*='captcha']",
                ".captcha-input",
                "#captcha-input"
            ]
            
            for selector in input_selectors:
                try:
                    captcha_input = driver.find_element(By.CSS_SELECTOR, selector)
                    captcha_input.clear()
                    captcha_input.send_keys(captcha_text)
                    print(f"✅ Görsel CAPTCHA çözüldü: {captcha_text}")
                    return True
                except:
                    continue
            
            print("❌ CAPTCHA input alanı bulunamadı")
            return False
            
        except Exception as e:
            print(f"❌ Görsel CAPTCHA çözüm hatası: {e}")
            return False
    
    def _get_recaptcha_sitekey(self, driver) -> Optional[str]:
        """reCAPTCHA site key'ini çıkarır"""
        try:
            # data-sitekey attribute'u ara
            elements = driver.find_elements(By.CSS_SELECTOR, "[data-sitekey]")
            for element in elements:
                sitekey = element.get_attribute("data-sitekey")
                if sitekey:
                    return sitekey
            
            # Script içinde site key ara
            scripts = driver.find_elements(By.TAG_NAME, "script")
            for script in scripts:
                script_content = script.get_attribute("innerHTML") or ""
                match = re.search(r'sitekey["\']?\s*:\s*["\']([^"\']+)["\']', script_content)
                if match:
                    return match.group(1)
            
            return None
            
        except Exception:
            return None


def _detect_and_solve_captcha(driver, captcha_client: Optional[AnticaptchaClient]) -> bool:
    """CAPTCHA tespit eder ve çözer"""
    if not captcha_client:
        return False
    
    try:
        solver = AdvancedCaptchaSolver(captcha_client.client_key)
        captcha_type = solver.detect_captcha_type(driver)
        
        if not captcha_type:
            return False
        
        print(f"🔍 CAPTCHA tespit edildi: {captcha_type}")
        
        if captcha_type == "cloudflare":
            return solver.solve_cloudflare_challenge(driver)
        elif captcha_type == "recaptcha_v2":
            return solver.solve_recaptcha_v2(driver)
        elif captcha_type == "image_captcha":
            return solver.solve_image_captcha(driver)
        else:
            print(f"⚠️ Desteklenmeyen CAPTCHA türü: {captcha_type}")
            return False
            
    except Exception as e:
        print(f"❌ CAPTCHA çözüm hatası: {e}")
        return False
