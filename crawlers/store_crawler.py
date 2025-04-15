import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import re

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
        """스토어 ID로 스토어의 모든 상품 URL 수집 (기존 메서드 유지)"""
        store_url = AMAZON["store_url_pattern"].format(store_id=store_id)
        return self.crawl_store_by_url(store_url)
    
    def crawl_store_by_url(self, store_url, max_products=None):
        """스토어 URL로 모든 상품 URL 수집 (새로운 메서드)"""
        max_products = max_products or CRAWLING["max_products"]
        self.product_urls = []  # 재설정
        
        success = self.browser.get_page(store_url)
        
        if not success:
            logger.error(f"스토어 페이지 접근 실패: {store_url}")
            return []
        
        # 페이지 로딩 대기 - 여러 선택자 시도
        selectors = [
            ".ProductGridItem__itemOuter__KUtvv",  # 아마존 스토어 페이지 선택자
            ".s-result-item",                      # 검색 결과 페이지 선택자
            ".a-carousel-card",                    # 캐러셀 선택자
            "[data-component-type='s-search-result']",  # 다른 검색 결과 선택자
            ".a-link-normal.a-text-normal"         # 일반 링크 선택자
        ]
        
        page_loaded = False
        for selector in selectors:
            try:
                self.browser.wait_for_element(By.CSS_SELECTOR, selector, timeout=5)
                logger.info(f"페이지 구조 감지됨: {selector}")
                page_loaded = True
                break
            except TimeoutException:
                continue
        
        if not page_loaded:
            # 페이지는 로드되었지만 알려진 구조가 없음 - 계속 진행하고 다른 방법 시도
            logger.warning("알려진 스토어 페이지 구조를 찾을 수 없습니다. 대체 방법으로 시도합니다.")
        
        # 여러 페이지를 처리하기 위한 로직 (페이지네이션이 있을 경우)
        current_page = 1
        
        while len(self.product_urls) < max_products:
            logger.info(f"스토어 페이지 {current_page} 크롤링 중")
            
            # 페이지 구조에 따라 상품 항목 추출 시도
            product_items = []
            
            # 여러 선택자 시도
            for selector in [
                ".ProductGridItem__itemOuter__KUtvv",  # 아마존 스토어 페이지
                "[data-component-type='s-search-result']",  # 검색 결과
                ".s-result-item",                      # 다른 검색 결과 형식
                ".a-carousel-card",                    # 캐러셀 항목
                ".a-link-normal[href*='/dp/']"         # 상품 링크가 포함된 일반 링크
            ]:
                product_items = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if product_items:
                    logger.info(f"{len(product_items)}개의 상품 항목을 찾았습니다 (선택자: {selector})")
                    break
            
            # 상품 항목이 없으면 링크 직접 추출 시도
            if not product_items:
                logger.warning("상품 항목을 찾을 수 없습니다. 링크 직접 추출을 시도합니다.")
                self._extract_all_product_links()
                
                if self.product_urls:
                    logger.info(f"{len(self.product_urls)}개의 상품 URL을 직접 추출했습니다.")
                    break
                else:
                    logger.error("상품 URL을 찾을 수 없습니다.")
                    break
            
            # 각 상품의 URL 추출
            for item in product_items:
                try:
                    # 여러 선택자 시도
                    link_element = None
                    for link_selector in [
                        "a.ProductGridItem__overlay__IQ3Kw",  # 스토어 페이지
                        "a.a-link-normal",                  # 일반 링크
                        "a.a-text-normal",                  # 텍스트 링크
                        "a[href*='/dp/']"                   # 상품 상세 페이지 링크
                    ]:
                        try:
                            link_elements = item.find_elements(By.CSS_SELECTOR, link_selector)
                            if link_elements:
                                link_element = link_elements[0]
                                break
                        except NoSuchElementException:
                            continue
                    
                    if link_element:
                        product_url = link_element.get_attribute("href")
                        
                        if product_url:
                            product_url = self._normalize_url(product_url)
                            if product_url and product_url not in self.product_urls:
                                self.product_urls.append(product_url)
                                logger.debug(f"상품 URL 발견: {product_url}")
                    
                    # 최대 상품 수 도달 시 중단
                    if len(self.product_urls) >= max_products:
                        logger.info(f"최대 상품 수에 도달: {max_products}")
                        break
                        
                except Exception as e:
                    logger.warning(f"상품 URL 추출 중 오류: {str(e)}")
                    continue
            
            # 다음 페이지로 이동 (페이지네이션 처리)
            if not self._go_to_next_page():
                logger.info("더 이상 페이지가 없습니다.")
                break
                
            current_page += 1
            
        logger.info(f"스토어에서 {len(self.product_urls)}개의 상품 URL을 수집했습니다")
        return self.product_urls
    
    def _extract_all_product_links(self):
        """페이지에서 모든 상품 링크를 직접 추출"""
        try:
            # 아마존 상품 링크 패턴에 맞는 모든 링크 추출
            all_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/dp/']")
            
            for link in all_links:
                try:
                    url = link.get_attribute("href")
                    if url and "/dp/" in url:
                        normalized_url = self._normalize_url(url)
                        if normalized_url and normalized_url not in self.product_urls:
                            self.product_urls.append(normalized_url)
                except Exception:
                    continue
            
            return len(all_links) > 0
        except Exception as e:
            logger.error(f"링크 직접 추출 중 오류: {str(e)}")
            return False
    
    def _normalize_url(self, url):
        """URL 정규화 (추적 매개변수 제거 등)"""
        if not url:
            return None
            
        # ASIN을 추출하고 표준 URL 형식으로 변환
        if "/dp/" in url:
            asin_match = re.search(r"/dp/([A-Z0-9]{10})", url)
            if asin_match:
                asin = asin_match.group(1)
                return f"{AMAZON['base_url']}/dp/{asin}"
            
            # 정규식으로 찾지 못한 경우 다른 방법 시도
            asin_start = url.find("/dp/") + 4
            asin_end = url.find("/", asin_start) if url.find("/", asin_start) > 0 else None
            if asin_end:
                asin = url[asin_start:asin_end]
            else:
                asin = url[asin_start:]
                if "?" in asin:
                    asin = asin.split("?")[0]
            
            if len(asin) == 10 and re.match(r"[A-Z0-9]{10}", asin):
                return f"{AMAZON['base_url']}/dp/{asin}"
        
        return url
    
    def _go_to_next_page(self):
        """다음 페이지로 이동 (페이지네이션 처리)"""
        try:
            # 여러 선택자 시도
            next_button = None
            for selector in [
                "li.a-last a",                             # 일반적인 페이지네이션
                "a.s-pagination-next",                     # 새로운 스타일의 페이지네이션
                ".a-pagination .a-last a",                 # 다른 페이지네이션 스타일
                "a[href*='page='][aria-label='Next']"      # href에 page 파라미터가 있는 다음 버튼
            ]:
                try:
                    next_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if next_elements:
                        for elem in next_elements:
                            if elem.is_displayed() and elem.is_enabled():
                                next_button = elem
                                break
                    if next_button:
                        break
                except NoSuchElementException:
                    continue
            
            if next_button:
                self.browser.scroll_to_element(next_button)
                next_button.click()
                self.browser.random_delay(min_delay=1.0, max_delay=2.0)
                
                # 페이지 로드 확인
                self.browser.wait_for_page_load()
                return True
                
            return False
        except (NoSuchElementException, TimeoutException) as e:
            logger.warning(f"다음 페이지 이동 중 오류: {str(e)}")
            return False