import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import re

from config import CRAWLING
from utils.logger import setup_logger
from data.review_model import Review

logger = setup_logger(__name__)

class ReviewCrawler:
    def __init__(self, browser_manager):
        self.browser = browser_manager
        self.driver = browser_manager.driver
        self.reviews = []
    
    # 리뷰 추출 시작 부분 수정 (속도 개선, 스레드 없음)
    def crawl_reviews(self, product_url, max_reviews=None):
        """상품 리뷰 크롤링"""
        max_reviews = max_reviews or CRAWLING["max_reviews"]
        self.reviews = []  # 리뷰 목록 초기화
        
        # ASIN 추출 - 바로 리뷰 페이지로 접근
        asin_match = re.search(r"/dp/([A-Z0-9]{10})", product_url)
        if asin_match:
            asin = asin_match.group(1)
            # 바로 리뷰 페이지로 이동 (상품 페이지 건너뛰기)
            reviews_url = f"https://www.amazon.com/product-reviews/{asin}/ref=cm_cr_dp_d_show_all_btm?ie=UTF8&reviewerType=all_reviews"
            logger.info(f"직접 리뷰 페이지로 이동: {reviews_url}")
            success = self.browser.get_page(reviews_url)
            if not success:
                logger.error("리뷰 페이지 접근 실패")
                return []
        else:
            # ASIN을 추출할 수 없을 경우 상품 페이지부터 시작
            success = self.browser.get_page(product_url)
            if not success:
                logger.error(f"상품 페이지 접근 실패: {product_url}")
                return []
            
            # 리뷰 섹션 찾기 & 모든 리뷰 페이지로 이동
            try:
                # 모든 리뷰 링크 찾기 (여러 선택자 시도)
                all_reviews_url = None
                selectors = [
                    "a[data-hook='see-all-reviews-link-foot']",
                    "a[href*='/product-reviews/']",
                    "a[href*='#customer-reviews']",
                    "a[href*='customerReviews']",
                    "a[href*='reviewsAjax']",
                    "a.a-link-emphasis[href*='reviews']"
                ]
                
                for selector in selectors:
                    try:
                        all_reviews_links = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for link in all_reviews_links:
                            href = link.get_attribute("href")
                            if href and ("/product-reviews/" in href or "/reviews/" in href):
                                all_reviews_url = href
                                break
                    except NoSuchElementException:
                        continue
                    
                    if all_reviews_url:
                        break
                
                if all_reviews_url:
                    logger.info(f"Navigating to all reviews page: {all_reviews_url}")
                    success = self.browser.get_page(all_reviews_url)
                    if not success:
                        logger.error("Failed to access all reviews page")
                        return []
            
            except Exception as e:
                logger.error(f"Error navigating to reviews: {str(e)}")
                return []
        
        # 리뷰 추출 시작
        page = 1
        
        while len(self.reviews) < max_reviews:
            logger.info(f"Crawling reviews page {page}")
            
            # 현재 페이지의 리뷰 추출 (가장 효과적인 선택자 우선 시도)
            review_elements = []
            
            selectors = [
                "div[id^='customer_review-']",           # 가장 정확한 선택자
                "div[data-hook='review']",              # 일반적인 선택자
                ".review",                              # 단순 클래스 선택자
                ".a-section.review",                    # 복합 클래스 선택자
                ".review-views .a-section.celwidget"    # 컨테이너 내부 선택자
            ]
            
            for selector in selectors:
                review_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if review_elements:
                    logger.info(f"Found {len(review_elements)} reviews with selector: {selector}")
                    break
            
            if not review_elements:
                logger.warning("No review elements found on current page")
                break
            
            # 단일 스레드로 리뷰 추출 (속도 최적화)
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
            if len(self.reviews) >= max_reviews:
                break
                
            if not self._go_to_next_page():
                logger.info("No more review pages available")
                break
                
            page += 1
            
        logger.info(f"Collected {len(self.reviews)} reviews")
        return self.reviews
    
    def _extract_review(self, review_element):
        """리뷰 요소에서 정보 추출 (최적화 버전)"""
        try:
            review = Review()
            
            # 리뷰 ID - 중요한 식별자
            review_id = review_element.get_attribute("id")
            review.review_id = review_id if review_id else ""
            
            # 효율적인 데이터 추출을 위한 방법
            # 1. 모든 텍스트 데이터를 한 번에 가져온 후 분석
            full_text = review_element.text
            
            # 2. 날짜는 특정 패턴으로 추출 (예: "Reviewed in the United States on April 5, 2025")
            date_match = re.search(r"Reviewed .+ on (.+\d{4})", full_text)
            if date_match:
                review.date = date_match.group(1).strip()
            
            # 3. 중요 요소는 직접 접근 (별점, 제목, 작성자, 구매확인)
            # 별점 (가장 많이 사용되는 선택자)
            try:
                rating_element = review_element.find_element(By.CSS_SELECTOR, 
                    "i[data-hook='review-star-rating'] span.a-icon-alt, i.a-icon-star")
                if rating_element:
                    rating_text = rating_element.get_attribute("innerHTML") or rating_element.get_attribute("class")
                    if "a-star-" in rating_text:
                        # 클래스에서 별점 추출 (예: a-star-4)
                        rating_match = re.search(r"a-star-(\d)", rating_text)
                        if rating_match:
                            review.rating = float(rating_match.group(1))
                    else:
                        # 텍스트에서 별점 추출 (예: 4.0 out of 5 stars)
                        rating_match = re.search(r"([\d.]+) out of 5", rating_text)
                        if rating_match:
                            review.rating = float(rating_match.group(1))
            except NoSuchElementException:
                # 텍스트에서 별점 패턴 찾기
                rating_match = re.search(r"(\d\.\d) out of 5 stars", full_text)
                if rating_match:
                    review.rating = float(rating_match.group(1))
                else:
                    review.rating = 0.0
            
            # 제목 (리뷰 제목 선택자)
            try:
                title_element = review_element.find_element(By.CSS_SELECTOR, 
                    "a[data-hook='review-title'] span, .review-title")
                if title_element:
                    review.title = title_element.text.strip()
            except NoSuchElementException:
                review.title = ""
            
            # 리뷰어 이름
            try:
                name_element = review_element.find_element(By.CSS_SELECTOR, 
                    "span.a-profile-name")
                if name_element:
                    review.reviewer_name = name_element.text.strip()
            except NoSuchElementException:
                review.reviewer_name = ""
            
            # 구매 확인 여부
            review.verified_purchase = "Verified Purchase" in full_text
            
            # 리뷰 내용
            try:
                body_element = review_element.find_element(By.CSS_SELECTOR, 
                    "span[data-hook='review-body'] span, .review-text-content span")
                if body_element:
                    review.body = body_element.text.strip()
            except NoSuchElementException:
                # 내용이 긴 경우 별도 추출
                body_parts = re.findall(r"stars(.+?)Helpful", full_text, re.DOTALL)
                if body_parts:
                    review.body = body_parts[0].strip()
                else:
                    review.body = ""
            
            # 도움이 됨 수
            helpful_match = re.search(r"(\d+)\s+people found this helpful", full_text)
            if helpful_match:
                review.helpful_count = int(helpful_match.group(1))
            else:
                review.helpful_count = 0
            
            return review
            
        except Exception as e:
            logger.error(f"Error parsing review: {str(e)}")
            return None
            
    def _go_to_next_page(self):
        """다음 리뷰 페이지로 이동"""
        try:
            # 여러 다음 페이지 버튼 선택자 시도
            next_selectors = [
                "li.a-last a", 
                "a.a-last", 
                ".a-pagination .a-last a", 
                "a.a-pagination-next",
                "a[href*='page='][aria-label='Next']"
            ]
            
            for selector in next_selectors:
                try:
                    next_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for next_element in next_elements:
                        if next_element.is_displayed() and next_element.is_enabled():
                            # 버튼이 활성화되어 있는지 확인 (비활성화된 버튼은 클릭하지 않음)
                            disabled_class = next_element.get_attribute("class") or ""
                            if "a-disabled" not in disabled_class:
                                self.browser.scroll_to_element(next_element)
                                next_element.click()
                                self.browser.random_delay(min_delay=1.0, max_delay=2.0)
                                # 페이지 로드 확인
                                self.browser.wait_for_page_load()
                                return True
                except NoSuchElementException:
                    continue
            
            # URL에서 페이지 번호 찾아 직접 다음 페이지로 이동 시도
            current_url = self.driver.current_url
            page_match = re.search(r'pageNumber=(\d+)', current_url)
            
            if page_match:
                current_page = int(page_match.group(1))
                next_page = current_page + 1
                next_url = re.sub(r'pageNumber=\d+', f'pageNumber={next_page}', current_url)
                
                if next_url != current_url:
                    logger.info(f"Moving to next page via URL: {next_url}")
                    self.browser.get_page(next_url)
                    return True
            elif "pageNumber" not in current_url:
                # 현재 URL에 페이지 번호가 없으면 첫 페이지로 가정하고 2페이지로 이동
                if "?" in current_url:
                    next_url = current_url + "&pageNumber=2"
                else:
                    next_url = current_url + "?pageNumber=2"
                
                logger.info(f"Moving to page 2 via URL: {next_url}")
                self.browser.get_page(next_url)
                return True
            
            return False
        except (NoSuchElementException, TimeoutException) as e:
            logger.warning(f"Error navigating to next page: {str(e)}")
            return False