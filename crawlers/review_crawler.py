from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import re
import time

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import CRAWLING
from utils.logger import setup_logger
from data.review_model import Review

logger = setup_logger(__name__)

class ReviewCrawler:
    def __init__(self, browser_manager):
        self.browser = browser_manager
        self.driver = browser_manager.driver
        self.reviews = []
    
    def crawl_reviews(self, product_url, max_reviews=None):
        """상품 리뷰 크롤링"""
        max_reviews = max_reviews or CRAWLING["max_reviews"]
        
        # 상품 페이지 접근
        success = self.browser.get_page(product_url)
        if not success:
            logger.error(f"Failed to access product page: {product_url}")
            return []
        
        # 리뷰 섹션 찾기
        try:
            # 리뷰가 있는지 확인
            review_count_element = self.browser.find_element(By.CSS_SELECTOR, "span#acrCustomerReviewText, span[data-hook='total-review-count']")
            if not review_count_element:
                logger.info("No reviews found for this product")
                return []
            
            # 모든 리뷰 보기 링크 찾기
            try:
                all_reviews_link = self.browser.find_element(By.CSS_SELECTOR, "a[data-hook='see-all-reviews-link-foot']")
                if all_reviews_link:
                    all_reviews_url = all_reviews_link.get_attribute("href")
                    logger.info(f"Navigating to all reviews page: {all_reviews_url}")
                    success = self.browser.get_page(all_reviews_url)
                    if not success:
                        logger.error("Failed to access all reviews page")
                        return []
            except NoSuchElementException:
                # 모든 리뷰 링크가 없을 경우 현재 페이지에서 리뷰 추출 시도
                logger.info("No 'See all reviews' link found, extracting reviews from current page")
        
        except NoSuchElementException:
            logger.info("No reviews section found")
            return []
        
        # 리뷰 추출 시작
        page = 1
        
        while len(self.reviews) < max_reviews:
            logger.info(f"Crawling reviews page {page}")
            
            # 현재 페이지의 리뷰 추출
            review_elements = self.browser.find_elements(By.CSS_SELECTOR, "div[data-hook='review']")
            
            if not review_elements:
                logger.warning("No review elements found on current page")
                break
            
            for review_element in review_elements:
                try:
                    review = self._extract_review(review_element)
                    if review:
                        self.reviews.append(review)
                        logger.debug(f"Extracted review by {review.reviewer_name}: {review.title}")
                    
                    # 최대 리뷰 수 도달 시 중단
                    if len(self.reviews) >= max_reviews:
                        logger.info(f"Reached maximum number of reviews: {max_reviews}")
                        break
                        
                except Exception as e:
                    logger.warning(f"Error extracting review: {str(e)}")
                    continue
            
            # 다음 페이지로 이동
            if not self._go_to_next_page():
                logger.info("No more review pages available")
                break
                
            page += 1
            
        logger.info(f"Collected {len(self.reviews)} reviews")
        return self.reviews
    
    def _extract_review(self, review_element):
        """리뷰 요소에서 정보 추출"""
        try:
            review = Review()
            
            # 리뷰 ID
            review_id = review_element.get_attribute("id")
            review.review_id = review_id if review_id else ""
            
            # 별점
            try:
                rating_element = review_element.find_element(By.CSS_SELECTOR, "i[data-hook='review-star-rating'] span.a-icon-alt")
                if rating_element:
                    rating_text = rating_element.get_attribute("innerHTML")
                    rating_match = re.search(r"([\d.]+) out of 5", rating_text)
                    if rating_match:
                        review.rating = float(rating_match.group(1))
            except NoSuchElementException:
                review.rating = 0
            
            # 제목
            try:
                title_element = review_element.find_element(By.CSS_SELECTOR, "a[data-hook='review-title'] span")
                review.title = title_element.text.strip() if title_element else ""
            except NoSuchElementException:
                review.title = ""
            
            # 날짜
            try:
                date_element = review_element.find_element(By.CSS_SELECTOR, "span[data-hook='review-date']")
                review.date = date_element.text.strip() if date_element else ""
            except NoSuchElementException:
                review.date = ""
            
            # 리뷰어 이름
            try:
                name_element = review_element.find_element(By.CSS_SELECTOR, "span.a-profile-name")
                review.reviewer_name = name_element.text.strip() if name_element else ""
            except NoSuchElementException:
                review.reviewer_name = ""
            
            # 구매 확인 여부
            try:
                verified_element = review_element.find_element(By.CSS_SELECTOR, "span[data-hook='avp-badge']")
                review.verified_purchase = "Verified Purchase" in verified_element.text
            except NoSuchElementException:
                review.verified_purchase = False
            
            # 리뷰 내용
            try:
                body_element = review_element.find_element(By.CSS_SELECTOR, "span[data-hook='review-body'] span")
                review.body = body_element.text.strip() if body_element else ""
            except NoSuchElementException:
                review.body = ""
            
            # 도움이 됨 수
            try:
                helpful_element = review_element.find_element(By.CSS_SELECTOR, "span[data-hook='helpful-vote-statement']")
                if helpful_element:
                    helpful_text = helpful_element.text
                    helpful_match = re.search(r"(\d+)\s+people", helpful_text)
                    if helpful_match:
                        review.helpful_count = int(helpful_match.group(1))
            except NoSuchElementException:
                review.helpful_count = 0
            
            return review
            
        except Exception as e:
            logger.error(f"Error parsing review: {str(e)}")
            return None
    
    def _go_to_next_page(self):
        """다음 리뷰 페이지로 이동"""
        try:
            next_page_link = self.browser.find_element(By.CSS_SELECTOR, "li.a-last a")
            if next_page_link:
                self.browser.scroll_to_element(next_page_link)
                next_page_link.click()
                self.browser.random_delay()
                # 페이지 로드 확인
                self.browser.wait_for_element(By.CSS_SELECTOR, "div[data-hook='review']")
                return True
            return False
        except (NoSuchElementException, TimeoutException):
            return False