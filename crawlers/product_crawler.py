from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import json
import re

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import CRAWLING
from utils.logger import setup_logger
from data.product_model import Product

logger = setup_logger(__name__)

class ProductCrawler:
    def __init__(self, browser_manager):
        self.browser = browser_manager
        self.driver = browser_manager.driver
    
    def crawl_product(self, product_url):
        """상품 정보 크롤링"""
        success = self.browser.get_page(product_url)
        
        if not success:
            logger.error(f"Failed to access product page: {product_url}")
            return None
        
        # 페이지 로딩 대기
        try:
            self.browser.wait_for_element(By.ID, "productTitle")
        except TimeoutException:
            logger.error("Product page structure not found or has changed")
            return None
        
        # 상품 정보 추출
        try:
            product = Product()
            product.url = product_url
            product.asin = self._extract_asin(product_url)
            product.title = self._extract_title()
            product.price = self._extract_price()
            product.rating = self._extract_rating()
            product.review_count = self._extract_review_count()
            product.description = self._extract_description()
            product.features = self._extract_features()
            product.details = self._extract_details()
            product.variations = self._extract_variations()
            product.images = self._extract_images()
            
            logger.info(f"Successfully crawled product: {product.title}")
            return product
            
        except Exception as e:
            logger.error(f"Error during product crawling: {str(e)}")
            return None
    
    def _extract_asin(self, url):
        """URL에서 ASIN 추출"""
        asin_match = re.search(r"/dp/([A-Z0-9]{10})", url)
        if asin_match:
            return asin_match.group(1)
        
        # 페이지 내에서 ASIN 찾기
        try:
            detail_bullets = self.browser.find_element(By.ID, "detailBullets_feature_div")
            if detail_bullets:
                asin_element = detail_bullets.find_element(By.XPATH, ".//span[contains(text(), 'ASIN')]")
                if asin_element:
                    asin_text = asin_element.find_element(By.XPATH, "..").text
                    asin_match = re.search(r"ASIN\s*:\s*([A-Z0-9]{10})", asin_text)
                    if asin_match:
                        return asin_match.group(1)
        except NoSuchElementException:
            pass
        
        return ""
    
    def _extract_title(self):
        """상품 제목 추출"""
        try:
            title_element = self.browser.find_element(By.ID, "productTitle")
            return title_element.text.strip() if title_element else ""
        except NoSuchElementException:
            return ""
    
    def _extract_price(self):
        """상품 가격 추출"""
        try:
            # 여러 가격 요소 선택자 시도
            selectors = [
                "#priceblock_ourprice",
                "#priceblock_dealprice",
                ".a-price .a-offscreen",
                ".a-price .a-price-whole"
            ]
            
            for selector in selectors:
                try:
                    price_element = self.browser.find_element(By.CSS_SELECTOR, selector)
                    if price_element:
                        price_text = price_element.text.strip() if selector != ".a-price .a-offscreen" else price_element.get_attribute("innerText")
                        # 가격에서 숫자만 추출
                        price_num = re.search(r"[\d,]+\.?\d*", price_text)
                        if price_num:
                            return price_num.group().replace(",", "")
                except NoSuchElementException:
                    continue
            
            return ""
        except Exception:
            return ""
    
    def _extract_rating(self):
        """평점 추출"""
        try:
            rating_element = self.browser.find_element(By.CSS_SELECTOR, "span[data-hook='rating-out-of-text']")
            if rating_element:
                rating_text = rating_element.text
                rating_match = re.search(r"([\d.]+) out of 5", rating_text)
                if rating_match:
                    return float(rating_match.group(1))
            
            # 다른 방법으로 시도
            rating_element = self.browser.find_element(By.CSS_SELECTOR, "#acrPopover")
            if rating_element:
                rating_text = rating_element.get_attribute("title")
                rating_match = re.search(r"([\d.]+) out of 5", rating_text)
                if rating_match:
                    return float(rating_match.group(1))
            
            return 0.0
        except NoSuchElementException:
            return 0.0
    
    def _extract_review_count(self):
        """리뷰 수 추출"""
        try:
            review_count_element = self.browser.find_element(By.CSS_SELECTOR, "span[data-hook='total-review-count']")
            if review_count_element:
                review_text = review_count_element.text
                review_match = re.search(r"([\d,]+)", review_text)
                if review_match:
                    return int(review_match.group(1).replace(",", ""))
            
            # 다른 방법으로 시도
            review_count_element = self.browser.find_element(By.ID, "acrCustomerReviewText")
            if review_count_element:
                review_text = review_count_element.text
                review_match = re.search(r"([\d,]+)", review_text)
                if review_match:
                    return int(review_match.group(1).replace(",", ""))
            
            return 0
        except NoSuchElementException:
            return 0
    
    def _extract_description(self):
        """상품 설명 추출"""
        try:
            description_element = self.browser.find_element(By.ID, "productDescription")
            if description_element:
                return description_element.text.strip()
            
            # 다른 방법으로 시도
            feature_bullets = self.browser.find_element(By.ID, "feature-bullets")
            if feature_bullets:
                return feature_bullets.text.strip()
            
            return ""
        except NoSuchElementException:
            return ""
    
    def _extract_features(self):
        """상품 특징 추출"""
        features = []
        try:
            feature_list = self.browser.find_elements(By.CSS_SELECTOR, "#feature-bullets ul li span.a-list-item")
            for item in feature_list:
                features.append(item.text.strip())
            return features
        except NoSuchElementException:
            return []
    
    def _extract_details(self):
        """상품 세부 정보 추출"""
        details = {}
        try:
            # 상품 세부정보 테이블 또는 목록 추출
            detail_elements = self.browser.find_elements(By.CSS_SELECTOR, "#detailBullets_feature_div li span.a-list-item")
            
            for element in detail_elements:
                text = element.text.strip()
                if ":" in text:
                    key, value = text.split(":", 1)
                    details[key.strip()] = value.strip()
            
            # 기술 세부정보 테이블
            table_rows = self.browser.find_elements(By.CSS_SELECTOR, "#productDetails_techSpec_section_1 tr")
            for row in table_rows:
                try:
                    key = row.find_element(By.CSS_SELECTOR, "th").text.strip()
                    value = row.find_element(By.CSS_SELECTOR, "td").text.strip()
                    details[key] = value
                except NoSuchElementException:
                    continue
            
            return details
        except NoSuchElementException:
            return {}
    
    def _extract_variations(self):
        """상품 변형(옵션) 추출"""
        variations = []
        try:
            # 색상, 크기 등의 옵션 추출
            variation_elements = self.browser.find_elements(By.CSS_SELECTOR, "#variation_color_name li, #variation_size_name li")
            
            for element in variation_elements:
                try:
                    variation = {
                        "title": element.get_attribute("title"),
                        "value": element.text.strip(),
                        "selected": "selected" in element.get_attribute("class").split()
                    }
                    variations.append(variation)
                except:
                    continue
            
            return variations
        except NoSuchElementException:
            return []
    
    def _extract_images(self):
        """상품 이미지 URL 추출"""
        images = []
        try:
            # 썸네일 이미지 요소들 추출
            thumbnail_elements = self.browser.find_elements(By.CSS_SELECTOR, "#altImages .a-spacing-small.item img")
            
            for element in thumbnail_elements:
                try:
                    # 썸네일 URL에서 원본 이미지 URL로 변환
                    thumbnail_url = element.get_attribute("src")
                    if thumbnail_url and "images/I" in thumbnail_url:
                        # 이미지 ID 추출
                        img_id_match = re.search(r"images/I/([^.]+)", thumbnail_url)
                        if img_id_match:
                            img_id = img_id_match.group(1)
                            # 고해상도 이미지 URL 구성
                            full_img_url = f"https://m.media-amazon.com/images/I/{img_id}.jpg"
                            images.append(full_img_url)
                except:
                    continue
            
            return images
        except NoSuchElementException:
            return []