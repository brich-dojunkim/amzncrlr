import argparse
import time
import os

from utils.browser_manager import BrowserManager
from utils.logger import setup_logger
from utils.proxy_rotator import ProxyRotator
from crawlers.store_crawler import StoreCrawler
from crawlers.product_crawler import ProductCrawler
from crawlers.review_crawler import ReviewCrawler
from data.db_manager import DBManager
from config import CRAWLING, DATA_DIR

logger = setup_logger(__name__)

def parse_arguments():
    """명령행 인자 파싱"""
    parser = argparse.ArgumentParser(description="Amazon Store & Product Crawler")
    
    # 필수 인자
    parser.add_argument("--mode", type=str, choices=["store", "product", "review", "all"], required=True,
                        help="Crawling mode: store, product, review, or all")
    
    # 선택적 인자
    parser.add_argument("--store-id", type=str, help="Amazon store ID to crawl")
    parser.add_argument("--product-url", type=str, help="Amazon product URL to crawl")
    parser.add_argument("--product-list", type=str, help="Path to a text file containing product URLs")
    parser.add_argument("--output-dir", type=str, default=DATA_DIR, help="Directory to save output files")
    parser.add_argument("--max-products", type=int, default=CRAWLING["max_products"], 
                        help="Maximum number of products to crawl from store")
    parser.add_argument("--max-reviews", type=int, default=CRAWLING["max_reviews"], 
                        help="Maximum number of reviews to crawl per product")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--use-proxy", action="store_true", help="Use proxy rotation")
    parser.add_argument("--proxy-file", type=str, help="Path to a file containing proxy list")
    
    return parser.parse_args()

def crawl_store(args, browser_manager, db_manager):
    """스토어 크롤링 실행"""
    if not args.store_id:
        logger.error("Store ID is required for store crawling mode")
        return False
    
    store_crawler = StoreCrawler(browser_manager)
    product_urls = store_crawler.crawl_store(args.store_id)
    
    if not product_urls:
        logger.warning("No product URLs found")
        return False
    
    # 결과 저장
    output_file = os.path.join(args.output_dir, f"store_{args.store_id}_products.txt")
    with open(output_file, "w") as f:
        for url in product_urls:
            f.write(f"{url}\n")
    
    logger.info(f"Saved {len(product_urls)} product URLs to {output_file}")
    
    # 스토어 모드에서 상품 정보까지 크롤링할 경우
    if args.mode == "all":
        crawl_products_from_list(product_urls, args, browser_manager, db_manager)
    
    return True

def crawl_single_product(product_url, args, browser_manager, db_manager):
    """단일 상품 크롤링"""
    # 상품 정보 크롤링
    product_crawler = ProductCrawler(browser_manager)
    product = product_crawler.crawl_product(product_url)
    
    if not product:
        logger.error(f"Failed to crawl product: {product_url}")
        return False
    
    # 데이터베이스에 저장
    db_manager.save_product(product)
    
    # 리뷰 크롤링
    if args.mode in ["review", "all"]:
        review_crawler = ReviewCrawler(browser_manager)
        reviews = review_crawler.crawl_reviews(product_url, args.max_reviews)
        
        if reviews:
            # 각 리뷰에 상품 ASIN 설정
            for review in reviews:
                review.asin = product.asin
            
            # 데이터베이스에 저장
            db_manager.save_reviews(reviews)
            
            # 리뷰 CSV 내보내기
            db_manager.export_reviews_to_csv(product.asin)
    
    return True

def crawl_products_from_list(product_urls, args, browser_manager, db_manager):
    """여러 상품 크롤링"""
    total_products = len(product_urls)
    success_count = 0
    
    logger.info(f"Starting to crawl {total_products} products")
    
    for i, url in enumerate(product_urls, 1):
        logger.info(f"Crawling product {i}/{total_products}: {url}")
        
        if crawl_single_product(url, args, browser_manager, db_manager):
            success_count += 1
        
        # 상품 크롤링 간 지연 시간 추가
        if i < total_products:
            delay = browser_manager.random_delay()
    
    logger.info(f"Completed crawling {success_count}/{total_products} products successfully")
    
    # 성공적으로 크롤링한 상품 CSV 내보내기
    db_manager.export_products_to_csv()
    
    return success_count > 0

def main():
    """메인 실행 함수"""
    args = parse_arguments()
    
    # 출력 디렉토리 확인
    os.makedirs(args.output_dir, exist_ok=True)
    
    # 프록시 설정
    proxy_rotator = None
    if args.use_proxy:
        proxy_rotator = ProxyRotator()
        if args.proxy_file:
            proxy_rotator.load_proxies_from_file(args.proxy_file)
    
    # 브라우저 관리자 초기화
    browser_manager = BrowserManager()
    
    # 데이터베이스 관리자 초기화
    db_manager = DBManager()
    
    try:
        # 모드에 따른 크롤링 실행
        if args.mode == "store" or (args.mode == "all" and args.store_id):
            # 스토어 크롤링
            crawl_store(args, browser_manager, db_manager)
            
        elif args.mode in ["product", "review", "all"] and args.product_url:
            # 단일 상품 크롤링
            crawl_single_product(args.product_url, args, browser_manager, db_manager)
            
        elif args.mode in ["product", "review", "all"] and args.product_list:
            # 파일에서 상품 URL 목록 로드
            with open(args.product_list, "r") as f:
                product_urls = [line.strip() for line in f.readlines() if line.strip()]
            
            if product_urls:
                crawl_products_from_list(product_urls, args, browser_manager, db_manager)
            else:
                logger.error(f"No product URLs found in {args.product_list}")
        
        else:
            logger.error("Invalid combination of mode and arguments")
    
    except KeyboardInterrupt:
        logger.info("Crawling interrupted by user")
    except Exception as e:
        logger.error(f"An error occurred during crawling: {str(e)}", exc_info=True)
    finally:
        # 리소스 정리
        db_manager.close()
        browser_manager.close()
        logger.info("Crawling process finished")

if __name__ == "__main__":
    main()