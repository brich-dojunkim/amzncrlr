import random
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BROWSER, CRAWLING
from utils.logger import setup_logger

logger = setup_logger(__name__)

class BrowserManager:
    def __init__(self):
        self.driver = None
        self.options = None
        self.wait = None
        self.setup_browser()
    
    def setup_browser(self):
        """셀레늄 웹드라이버 초기화"""
        self.options = Options()
        
        if BROWSER["headless"]:
            self.options.add_argument("--headless")
        
        self.options.add_argument(f"--window-size={BROWSER['window_size'][0]},{BROWSER['window_size'][1]}")
        self.options.add_argument(f"user-agent={BROWSER['user_agent']}")
        self.options.add_argument("--disable-notifications")
        self.options.add_argument("--disable-popup-blocking")
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-dev-shm-usage")
        
        # 브라우저 탐지 우회
        self.options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.options.add_experimental_option("useAutomationExtension", False)
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=self.options)
        self.driver.implicitly_wait(BROWSER["implicitly_wait"])
        self.driver.set_page_load_timeout(BROWSER["page_load_timeout"])
        
        self.wait = WebDriverWait(self.driver, BROWSER["implicitly_wait"])
        
        logger.info("Browser initialized successfully")
    
    def get_page(self, url, retry=0):
        """페이지 접근 및 재시도 로직"""
        try:
            logger.info(f"Navigating to: {url}")
            self.driver.get(url)
            self.random_delay()
            return True
        except TimeoutException as e:
            if retry < CRAWLING["retry"]["max_attempts"]:
                wait_time = CRAWLING["retry"]["backoff_factor"] ** retry
                logger.warning(f"Timeout accessing {url}. Retrying in {wait_time}s... (Attempt {retry+1}/{CRAWLING['retry']['max_attempts']})")
                time.sleep(wait_time)
                return self.get_page(url, retry + 1)
            else:
                logger.error(f"Failed to access {url} after {CRAWLING['retry']['max_attempts']} attempts: {str(e)}")
                return False
    
    def find_element(self, by, value, timeout=None):
        """요소 찾기 및 대기"""
        timeout = timeout or BROWSER["implicitly_wait"]
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
        except (TimeoutException, NoSuchElementException) as e:
            logger.warning(f"Element not found: {by}={value}. Error: {str(e)}")
            return None
    
    def find_elements(self, by, value, timeout=None):
        """여러 요소 찾기 및 대기"""
        timeout = timeout or BROWSER["implicitly_wait"]
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.presence_of_all_elements_located((by, value))
            )
        except (TimeoutException, NoSuchElementException) as e:
            logger.warning(f"Elements not found: {by}={value}. Error: {str(e)}")
            return []
    
    def wait_for_element(self, by, value, condition=EC.visibility_of_element_located, timeout=None):
        """특정 조건으로 요소 대기"""
        timeout = timeout or BROWSER["implicitly_wait"]
        try:
            return WebDriverWait(self.driver, timeout).until(
                condition((by, value))
            )
        except TimeoutException as e:
            logger.warning(f"Timeout waiting for element: {by}={value}. Error: {str(e)}")
            return None
    
    def random_delay(self):
        """무작위 지연 시간 추가"""
        delay = random.uniform(CRAWLING["delay"]["min"], CRAWLING["delay"]["max"])
        time.sleep(delay)
    
    def scroll_to_element(self, element):
        """특정 요소로 스크롤"""
        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
        self.random_delay()
    
    def scroll_to_bottom(self, scroll_pause_time=1.0):
        """페이지 하단으로 스크롤"""
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        
        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_pause_time)
            
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
    
    def close(self):
        """브라우저 종료"""
        if self.driver:
            self.driver.quit()
            logger.info("Browser closed successfully")