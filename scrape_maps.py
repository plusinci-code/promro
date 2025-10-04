from typing import List, Dict, Any
import time, urllib.parse
from pathlib import Path
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from fake_useragent import UserAgent
import random

from .utils import save_csv, ensure_dir

def _driver(headless: bool=False):
    """Create optimized Chrome driver with anti-detection features and better session management"""
    options = webdriver.ChromeOptions()
    
    # Basic options
    if headless:
        options.add_argument("--headless=new")
    
    # Anti-detection options
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-translate")
    options.add_argument("--hide-scrollbars")
    options.add_argument("--mute-audio")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-field-trial-config")
    options.add_argument("--disable-back-forward-cache")
    options.add_argument("--disable-ipc-flooding-protection")
    
    # Session management options
    options.add_argument("--disable-session-crashed-bubble")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-logging")
    options.add_argument("--disable-permissions-api")
    options.add_argument("--disable-popup-blocking")
    
    # Window size
    options.add_argument("--window-size=1920,1080")
    
    # User agent
    try:
        ua = UserAgent().random
        options.add_argument(f"user-agent={ua}")
    except Exception:
        # Fallback user agent
        options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Experimental options for better performance and session management
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_experimental_option("prefs", {
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_settings.popups": 0,
        "profile.managed_default_content_settings.images": 1,  # Allow images for better detection
        "profile.default_content_setting_values.geolocation": 2,
        "profile.default_content_setting_values.media_stream": 2,
    })
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # Set timeouts for better session management
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        
        # Execute script to remove webdriver property
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
    except Exception as e:
        raise Exception(f"Failed to create Chrome driver: {str(e)}")

def maps_scrape(keywords: List[str], per_keyword_limit: int, dwell_seconds: int, out_dir: Path) -> pd.DataFrame:
    """
    Enhanced Google Maps scraping with robust session management and updated URL format
    """
    ensure_dir(out_dir)
    rows: List[Dict[str,Any]] = []
    driver = None
    
    try:
        for i, kw in enumerate(keywords):
            print(f"Processing keyword {i+1}/{len(keywords)}: {kw}")
            
            # Create fresh driver for each keyword to avoid session issues
            driver = _driver(headless=False)
            wait = WebDriverWait(driver, 15)
            
            try:
                # Multiple search strategies with fresh driver
                success = False
                for attempt in range(3):  # Try up to 3 times per keyword
                    try:
                        if attempt > 0:
                            print(f"Retry attempt {attempt + 1} for keyword: {kw}")
                            time.sleep(random.uniform(2, 4))  # Random delay between retries
                        
                        # Strategy 1: Updated direct search URL format
                        if attempt == 0:
                            success = _search_with_updated_url(driver, wait, kw, per_keyword_limit, dwell_seconds, rows)
                        
                        # Strategy 2: Traditional search box method
                        elif attempt == 1:
                            success = _search_with_searchbox(driver, wait, kw, per_keyword_limit, dwell_seconds, rows)
                        
                        # Strategy 3: Alternative selectors
                        else:
                            success = _search_with_alternative_selectors(driver, wait, kw, per_keyword_limit, dwell_seconds, rows)
                        
                        if success:
                            break
                            
                    except Exception as e:
                        print(f"Attempt {attempt + 1} failed for {kw}: {str(e)}")
                        if attempt == 2:  # Last attempt
                            print(f"All attempts failed for keyword: {kw}")
                        break
                        time.sleep(random.uniform(3, 6))
                
            finally:
                # Always close driver after each keyword to prevent session issues
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                    driver = None
            
            # Small delay between keywords
            if i < len(keywords) - 1:
                time.sleep(random.uniform(2, 4))
                
    except Exception as e:
        print(f"Critical error in maps_scrape: {str(e)}")
    finally:
        # Final cleanup
        if driver:
            try:
                driver.quit()
            except:
                pass

    df = pd.DataFrame(rows)
    if len(df) > 0:
        save_csv(df.to_dict(orient="records"), out_dir / "D_maps_results.csv")
        print(f"Successfully scraped {len(df)} businesses from Google Maps")
    else:
        print("No data was scraped. Check your keywords and internet connection.")
    
    return df


def _search_with_updated_url(driver, wait, keyword, limit, dwell, rows):
    """Strategy 1: Use updated direct search URL format for better results"""
    try:
        # Encode keyword for URL using the specified format
        encoded_kw = urllib.parse.quote_plus(keyword)
        search_url = f"https://www.google.com/maps/search/{encoded_kw}/"
        
        print(f"Searching with URL: {search_url}")
        driver.get(search_url)
        time.sleep(3)  # Increased wait time for page load
        
        # Handle cookie banner
        _handle_cookie_banner(driver)
        
        # Wait for results with multiple selectors
        result_selectors = [
            "div[role='feed']",
            "div[data-value='Search results']",
            "div[aria-label*='Results']",
            ".Nv2PK",
            "a.hfpxzc",
            "div[role='article']",
            "div[data-result-index]"
        ]
        
        results_found = False
        for selector in result_selectors:
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                results_found = True
                print(f"Results found with selector: {selector}")
                break
            except TimeoutException:
                continue
        
        if not results_found:
            print(f"No results found for keyword: {keyword}")
            return False
        
        time.sleep(2)  # Additional wait for content to load
        return _extract_business_data(driver, wait, keyword, limit, dwell, rows)
        
    except Exception as e:
        print(f"Updated URL search failed: {str(e)}")
        return False


def _search_with_searchbox(driver, wait, keyword, limit, dwell, rows):
    """Strategy 2: Traditional search box method with improved selectors"""
    try:
        driver.get("https://www.google.com/maps")
        time.sleep(2)

        # Handle cookie banner
        _handle_cookie_banner(driver)
        
        # Multiple search box selectors
        search_selectors = [
            "input#searchboxinput",
            "input[placeholder*='Search']",
            "input[aria-label*='Search']",
            "input[data-value='Search']",
            "#searchboxinput"
        ]
        
        search_box = None
        for selector in search_selectors:
            try:
                if selector.startswith("#"):
                    search_box = wait.until(EC.presence_of_element_located((By.ID, selector[1:])))
                else:
                    search_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                break
            except TimeoutException:
                continue
        
        if not search_box:
            return False
        
        # Clear and search
        search_box.clear()
        time.sleep(0.5)
        search_box.send_keys(keyword)
        time.sleep(0.5)
        search_box.send_keys(Keys.ENTER)
        
        # Wait for results
        time.sleep(2)
        return _extract_business_data(driver, wait, keyword, limit, dwell, rows)
        
    except Exception as e:
        print(f"Search box method failed: {str(e)}")
        return False


def _search_with_alternative_selectors(driver, wait, keyword, limit, dwell, rows):
    """Strategy 3: Use alternative selectors and methods with updated URL format"""
    try:
        # Try different Google Maps URLs with updated format
        urls = [
            f"https://www.google.com/maps/search/{urllib.parse.quote_plus(keyword)}/",
            f"https://maps.google.com/maps?q={urllib.parse.quote_plus(keyword)}",
            f"https://www.google.com/maps/search/{urllib.parse.quote_plus(keyword)}/@0,0,2z",
            f"https://www.google.com/maps/search/{urllib.parse.quote_plus(keyword)}/@0,0,10z"
        ]
        
        for url in urls:
            try:
                print(f"Trying alternative URL: {url}")
                driver.get(url)
                time.sleep(4)  # Increased wait time
                
                # Handle cookie banner
                _handle_cookie_banner(driver)
                
                # Try to find any business listings with more selectors
                business_selectors = [
                    ".Nv2PK",
                    "a.hfpxzc", 
                    "div[role='article']",
                    "div[data-value='Search results'] > div",
                    "[data-result-index]",
                    "div[role='feed'] > div",
                    "div[jsaction*='pane']"
                ]
                
                for selector in business_selectors:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        print(f"Found {len(elements)} elements with selector: {selector}")
                        return _extract_business_data_alternative(driver, wait, keyword, limit, dwell, rows, elements)
                        
            except Exception as e:
                print(f"Alternative URL failed: {url} - {str(e)}")
                continue
        
        return False
        
    except Exception as e:
        print(f"Alternative selector method failed: {str(e)}")
        return False


def _handle_cookie_banner(driver):
    """Handle cookie consent banners"""
    try:
        cookie_selectors = [
            "button[aria-label*='Accept']",
            "button[aria-label*='I agree']", 
            "button[jsname='higCR']",
            "button[data-value='Accept all']",
            "button[data-value='I agree']",
            "#L2AGLb",  # Google's accept button ID
            "button[aria-label='Accept all']"
        ]
        
        for selector in cookie_selectors:
            try:
                buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                if buttons and buttons[0].is_displayed():
                    buttons[0].click()
                    time.sleep(1)
                    break
            except:
                continue
    except:
        pass


def _extract_business_data(driver, wait, keyword, limit, dwell, rows):
    """Extract business data from Google Maps results"""
    try:
        # Scroll to load more results
        _scroll_to_load_results(driver)
        
        # Find business cards with multiple selectors
        card_selectors = [
            "div[role='feed'] .Nv2PK",
            "a.hfpxzc",
            "div[role='article']",
            "div[data-result-index]",
            ".Nv2PK"
        ]
        
        cards = []
        for selector in card_selectors:
            cards = driver.find_elements(By.CSS_SELECTOR, selector)
            if cards:
                break
        
        if not cards:
            print(f"No business cards found for keyword: {keyword}")
            return False
        
        # Limit results
        cards = cards[:limit]
        print(f"Found {len(cards)} business cards for keyword: {keyword}")
        
        # Extract data from each card
        for i, card in enumerate(cards):
            try:
                business_data = _extract_single_business(driver, wait, card, keyword, dwell)
                if business_data:
                    rows.append(business_data)
                    print(f"Extracted business {i+1}/{len(cards)}: {business_data.get('Firma Adı', 'Unknown')}")
            except Exception as e:
                print(f"Failed to extract business {i+1}: {str(e)}")
                continue
        
        return len(rows) > 0
        
    except Exception as e:
        print(f"Error extracting business data: {str(e)}")
        return False


def _extract_business_data_alternative(driver, wait, keyword, limit, dwell, rows, elements):
    """Alternative extraction method for different page layouts"""
    try:
        elements = elements[:limit]
        print(f"Found {len(elements)} elements for keyword: {keyword}")
        
        for i, element in enumerate(elements):
            try:
                business_data = _extract_single_business_alternative(driver, wait, element, keyword, dwell)
                if business_data:
                    rows.append(business_data)
                    print(f"Extracted business {i+1}/{len(elements)}: {business_data.get('Firma Adı', 'Unknown')}")
            except Exception as e:
                print(f"Failed to extract business {i+1}: {str(e)}")
                continue
        
        return len(rows) > 0
        
    except Exception as e:
        print(f"Error in alternative extraction: {str(e)}")
        return False


def _scroll_to_load_results(driver):
    """Scroll to load more results"""
    try:
        # Find scrollable container
        scroll_selectors = [
            "div[role='feed']",
            "div[data-value='Search results']",
            "div[aria-label*='Results']"
        ]
        
        scroll_container = None
        for selector in scroll_selectors:
            try:
                scroll_container = driver.find_element(By.CSS_SELECTOR, selector)
                break
            except:
                continue
        
        if scroll_container:
            # Scroll multiple times to load more results
            for _ in range(3):
                driver.execute_script("arguments[0].scrollBy(0, 800);", scroll_container)
                time.sleep(0.8)
        else:
            # Fallback: scroll the page
            for _ in range(3):
                driver.execute_script("window.scrollBy(0, 800);")
                time.sleep(0.8)

    except Exception as e:
        print(f"Error scrolling: {str(e)}")


def _extract_single_business(driver, wait, card, keyword, dwell):
    """Extract data from a single business card"""
    try:
        # Click on the card
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
        time.sleep(0.5)
        
        try:
            driver.execute_script("arguments[0].click();", card)
        except:
            try:
                card.click()
            except:
                return None
        
        # Wait for business details to load
        time.sleep(max(1, dwell))
        
        # Extract business information with multiple selectors
        name_selectors = [
            "h1.DUwDvf",
            "h1[data-attrid='title']",
            "h1",
            ".x3AX1-LfntMc-header-title-title"
        ]
        
        name = _safe_extract_text(driver, name_selectors)
        
        # Extract address
        address_selectors = [
            "//button[contains(@data-item-id,'address')]",
            "//span[contains(@data-item-id,'address')]",
            "//div[contains(@data-item-id,'address')]",
            ".Io6YTe"
        ]
        
        address = _safe_extract_text(driver, address_selectors, use_xpath=True)
        
        # Extract phone
        phone_selectors = [
            "//button[contains(@data-item-id,'phone:tel')]",
            "//span[contains(@data-item-id,'phone:tel')]",
            "//div[contains(@data-item-id,'phone:tel')]"
        ]
        
        phone = _safe_extract_text(driver, phone_selectors, use_xpath=True)
        
        # Extract website
        website = _safe_extract_website(driver)
        
        # Go back to results
        _go_back_to_results(driver)
        
        if name:  # Only return if we got at least a name
            return {
                "Firma Adı": name,
                "Firma Adresi": address,
                "Telefon Numaraları": phone,
                "Firma Websitesi": website,
                "Firma Ülkesi/Dil": "",
                "Firma Tipi": "Google Maps",
                "Kaynak": "Google Maps",
                "Anahtar Kelime": keyword
            }
        
        return None
        
    except Exception as e:
        print(f"Error extracting single business: {str(e)}")
        return None


def _extract_single_business_alternative(driver, wait, element, keyword, dwell):
    """Alternative extraction for different page layouts"""
    try:
        # Try to get text directly from the element
        name = element.text.strip() if element.text else ""
        
        # Try to get href if it's a link
        website = ""
        try:
            if element.tag_name == "a":
                website = element.get_attribute("href")
        except:
            pass
        
        if name:
            return {
                    "Firma Adı": name,
                "Firma Adresi": "",
                "Telefon Numaraları": "",
                "Firma Websitesi": website,
                    "Firma Ülkesi/Dil": "",
                "Firma Tipi": "Google Maps",
                    "Kaynak": "Google Maps",
                "Anahtar Kelime": keyword
            }
        
        return None
        
    except Exception as e:
        print(f"Error in alternative extraction: {str(e)}")
        return None


def _safe_extract_text(driver, selectors, use_xpath=False):
    """Safely extract text using multiple selectors"""
    for selector in selectors:
        try:
            if use_xpath:
                elements = driver.find_elements(By.XPATH, selector)
            else:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
            
            if elements and elements[0].text.strip():
                return elements[0].text.strip()
        except:
            continue
    return ""


def _safe_extract_website(driver):
    """Safely extract website URL"""
    website_selectors = [
        "//a[contains(@data-item-id,'authority')]",
        "//a[contains(@href,'http') and not(contains(@href,'google.com'))]",
        "a[data-item-id*='authority']"
    ]
    
    for selector in website_selectors:
        try:
            if selector.startswith("//"):
                elements = driver.find_elements(By.XPATH, selector)
            else:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
            
            if elements:
                href = elements[0].get_attribute("href")
                if href and not "google.com" in href:
                    return href
        except:
            continue
    return ""


def _go_back_to_results(driver):
    """Go back to search results"""
    try:
        back_selectors = [
            "button[aria-label='Back']",
            "button[aria-label='Geri']",
            "button[jsname='ZUkOIc']",
            ".VfPpkd-icon-LiivKc"
        ]
        
        for selector in back_selectors:
            try:
                back_btn = driver.find_element(By.CSS_SELECTOR, selector)
                if back_btn.is_displayed():
                    back_btn.click()
                    time.sleep(1)
                    break
            except:
                continue
    except:
        pass