import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import AMAZON, CRAWLING
from utils.logger import setup_logger

logger = setup_logger(__name__)

class StoreCrawler:
    def __init__(self, browser_manager):
        self.browser = browser_manager
        self.driver = browser_manager.driver
        self.product_urls = []
    
    def crawl_store(self, store_id):
        """스토어의 모든 상품 URL 수집"""
        store_url = AMAZON["store_url_pattern"].format(store_id=store_id)
        success = self.browser.get_page(store_url)
        
        if not success:
            logger.error(f"Failed to access store page: {store_url}")
            return []
        
        # 페이지 로딩 대기
        try:
            self.browser.wait_for_element(By.CSS_SELECTOR, ".ProductGridItem__itemOuter__KUtvv")
        except TimeoutException:
            logger.error("Store page structure not found or has changed")
            return []
        
        # 여러 페이지를 처리하기 위한 로직 (페이지네이션이 있을 경우)
        current_page = 1
        
        while len(self.product_urls) < CRAWLING["max_products"]:
            logger.info(f"Crawling store page {current_page}")
            
            # 현재 페이지의 상품 항목 추출
            product_items = self.driver.find_elements(By.CSS_SELECTOR, ".ProductGridItem__itemOuter__KUtvv")
            
            if not product_items:
                logger.warning(f"No product items found on page {current_page}")
                break
            
            # 각 상품의 URL 추출
            for item in product_items:
                try:
                    # 상품 링크 추출
                    link_element = item.find_element(By.CSS_SELECTOR, "a.ProductGridItem__overlay__IQ3Kw")
                    product_url = link_element.get_attribute("href")
                    
                    if product_url:
                        product_url = self._normalize_url(product_url)
                        if product_url not in self.product_urls:
                            self.product_urls.append(product_url)
                            logger.debug(f"Found product URL: {product_url}")
                    
                    # 최대 상품 수 도달 시 중단
                    if len(self.product_urls) >= CRAWLING["max_products"]:
                        logger.info(f"Reached maximum number of products: {CRAWLING['max_products']}")
                        break
                        
                except NoSuchElementException as e:
                    logger.warning(f"Error extracting product URL: {str(e)}")
                    continue
            
            # 다음 페이지로 이동 (페이지네이션 처리)
            if not self._go_to_next_page():
                logger.info("No more pages available")
                break
                
            current_page += 1
            
        logger.info(f"Collected {len(self.product_urls)} product URLs from store {store_id}")
        return self.product_urls
    
    def _normalize_url(self, url):
        """URL 정규화 (추적 매개변수 제거 등)"""
        # ASIN을 추출하고 표준 URL 형식으로 변환
        if "/dp/" in url:
            asin_start = url.find("/dp/") + 4
            asin_end = url.find("/", asin_start) if url.find("/", asin_start) > 0 else None
            asin = url[asin_start:asin_end] if asin_end else url[asin_start:]
            
            if "?" in asin:
                asin = asin.split("?")[0]
            
            return f"{AMAZON['base_url']}/dp/{asin}"
        return url
    
    def _go_to_next_page(self):
        """다음 페이지로 이동 (페이지네이션 처리)"""
        try:
            # 페이지네이션 버튼이 있는지 확인
            next_button = self.browser.find_element(By.CSS_SELECTOR, "li.a-last a")
            if next_button:
                self.browser.scroll_to_element(next_button)
                next_button.click()
                self.browser.random_delay()
                return True
            return False
        except NoSuchElementException:
            return False