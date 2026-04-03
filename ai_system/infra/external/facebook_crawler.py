import logging
import time
import uuid
import os
from typing import Dict, Any, Iterator
from bs4 import BeautifulSoup

# Setup proper webdriver logging suppression before importing selenium
os.environ['WDM_LOG'] = '0'

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

logger = logging.getLogger(__name__)

class FacebookCrawler:
    """
    Crawler that uses headless Selenium to navigate to public Facebook groups
    and scrape recent posts for images and text content.
    """
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.driver = None

    def _init_driver(self):
        """Initializes the Chrome WebDriver."""
        logger.info("Initializing Facebook Crawler WebDriver...")
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless=new")
        
        # Anti-detection & performance flags
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Prevent WebDriver detection
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Load page strategy: Eager (interactive) instead of Normal (wait for all resources)
        chrome_options.page_load_strategy = 'eager'

        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            # Execute CDP commands to override navigator.webdriver
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                    })
                """
            })
            self.driver.implicitly_wait(10)
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            raise

    def close(self):
        """Closes the WebDriver."""
        if self.driver:
            pass # Keep alive for reuse or close later? Let's close it after each polling cycle
            try:
                self.driver.quit()
                logger.info("WebDriver closed.")
            except Exception as e:
                logger.error(f"Error closing WebDriver: {e}")
            finally:
                self.driver = None

    def scroll_page(self, scrolls: int = 3, scroll_pause_time: float = 2.0):
        """Scrolls the page down to load dynamic content."""
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        
        for i in range(scrolls):
            # Scroll down to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            # Wait to load page
            time.sleep(scroll_pause_time)
            
            # Calculate new scroll height and compare with last scroll height
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break # Reached the end
            last_height = new_height
            logger.debug(f"Scrolled {i+1}/{scrolls} times.")

    def poll_group(self, group_url: str) -> Iterator[Dict[str, Any]]:
        """
        Navigates to the given Facebook group URL, extracts recent posts,
        and yields them as dictionaries compatible with SocialMediaScraperAgent.
        """
        if not self.driver:
            self._init_driver()

        logger.info(f"Polling Facebook Group: {group_url}")
        
        try:
            self.driver.get(group_url)
            
            # Allow time for initial render, then scroll slightly
            time.sleep(3)
            self.scroll_page(scrolls=3, scroll_pause_time=2.5)
            
            # Use BeautifulSoup to parse the current DOM securely
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Facebook DOM changes constantly. We look for generic 'feed' patterns
            # Note: This is a best-effort, heuristic-based approach.
            # Most FB posts in feed view are enclosed in divs with role="article"
            posts = soup.find_all('div', role='article')
            
            if not posts:
                 logger.warning(f"No posts found using `role='article'` in {group_url}")
                 # Fallback strategy: look for specific data attributes if known, or generic feed blocks
                 # (Implementation can be extended as HTML structure is analyzed)
                 
            for post in posts:
                post_data = self._extract_post_data(post, group_url)
                if post_data and post_data.get("image_url"):
                    # We only yield posts that have images, as per current design (VLM weighting)
                    yield post_data
                    
        except TimeoutException:
            logger.error(f"Timeout while loading {group_url}")
        except WebDriverException as e:
            logger.error(f"WebDriver error for {group_url}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error scraping {group_url}: {e}")

    def _extract_post_data(self, post_html: BeautifulSoup, source_url: str) -> Dict[str, Any]:
        """
        Parses a single post HTML block and constructs the payload.
        """
        try:
            # 1. Text Content
            # Usually text is in paragraphs or spans with specific styling.
            # We'll extract all text reasonably contained within the post body.
            text_blocks = post_html.find_all(['div', 'span', 'p'], dir='auto')
            content_text = " ".join([block.get_text(strip=True) for block in text_blocks if block.get_text(strip=True)])
            
            # 2. Image URL
            # Look for img tags. FB often uses complex structures. 
            # We want the main image, not icons or profile pics.
            # Filtering out small images or specific domains might be needed.
            image_url = None
            imgs = post_html.find_all('img')
            for img in imgs:
                src = img.get('src', '')
                # Basic heuristic to avoid generic UI icons
                if src and 'scontent' in src and 'fbcdn' in src and not src.endswith('.svg') and 'p32x32' not in src:
                    image_url = src
                    break  # Take first main image
                    
            if not image_url and not content_text:
                return None

            # 3. Post ID
            # Extracting a reliable post ID from an unauthenticated feed is tricky.
            # We'll try to find a link that points to a specific post and use that hash,
            # otherwise generate a pseudo-hash based on text+image to avoid duplicates.
            post_id = None
            links = post_html.find_all('a', href=True)
            for a in links:
                href = a['href']
                if '/posts/' in href or '/groups/' in href and '/permalink/' in href:
                    post_id = href.split('?')[0] # rough try
                    break
            
            if not post_id:
               # Generate a deterministic ID based on content to act as deduplication key down the line
               import hashlib
               unique_str = f"{content_text[:50]}_{image_url}"
               post_id = f"fb_{hashlib.md5(unique_str.encode()).hexdigest()[:12]}"

            return {
                "post_id": post_id,
                "source": source_url,
                "image_url": image_url,
                "content_text": content_text,
                "location": "unknown", # Optional, VLM will override if it finds it
                "timestamp": self._get_current_timestamp()
            }
        except Exception as e:
            logger.debug(f"Error parsing specific post block: {e}")
            return None
            
    def _get_current_timestamp(self) -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
