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

def get_user_input():
    """대화형 콘솔에서 사용자 입력 받기"""
    print("\n===== 아마존 크롤러 =====")
    print("1. 스토어 크롤링")
    print("2. 상품 크롤링")
    print("3. 상품 및 리뷰 크롤링")
    print("4. 종료")
    
    choice = input("\n작업을 선택하세요 (1-4): ").strip()
    
    if choice == '1':
        mode = "store"
        store_url = input("스토어 URL을 입력하세요: ").strip()
        max_products = input(f"최대 수집할 상품 수 (기본값: {CRAWLING['max_products']}): ").strip()
        
        try:
            max_products = int(max_products) if max_products else CRAWLING["max_products"]
        except ValueError:
            print("유효하지 않은 숫자입니다. 기본값을 사용합니다.")
            max_products = CRAWLING["max_products"]
        
        crawl_reviews = input("스토어의 각 상품에 대한 리뷰도 수집하시겠습니까? (y/n): ").lower().strip() == 'y'
        
        max_reviews = CRAWLING["max_reviews"]
        if crawl_reviews:
            max_reviews_input = input(f"상품당 최대 수집할 리뷰 수 (기본값: {CRAWLING['max_reviews']}): ").strip()
            try:
                max_reviews = int(max_reviews_input) if max_reviews_input else CRAWLING["max_reviews"]
            except ValueError:
                print("유효하지 않은 숫자입니다. 기본값을 사용합니다.")
                max_reviews = CRAWLING["max_reviews"]
        
        return {
            "mode": mode,
            "store_url": store_url,
            "max_products": max_products,
            "crawl_reviews": crawl_reviews,
            "max_reviews": max_reviews
        }
    
    elif choice == '2':
        mode = "product"
        product_url = input("상품 URL을 입력하세요: ").strip()
        
        return {
            "mode": mode,
            "product_url": product_url
        }
    
    elif choice == '3':
        mode = "review"
        product_url = input("상품 URL을 입력하세요: ").strip()
        max_reviews = input(f"최대 수집할 리뷰 수 (기본값: {CRAWLING['max_reviews']}): ").strip()
        
        try:
            max_reviews = int(max_reviews) if max_reviews else CRAWLING["max_reviews"]
        except ValueError:
            print("유효하지 않은 숫자입니다. 기본값을 사용합니다.")
            max_reviews = CRAWLING["max_reviews"]
        
        return {
            "mode": mode,
            "product_url": product_url,
            "max_reviews": max_reviews
        }
    
    elif choice == '4':
        return {"mode": "exit"}
    
    else:
        print("잘못된 선택입니다. 다시 시도해주세요.")
        return get_user_input()

def crawl_store_by_url(store_url, args, browser_manager, db_manager):
    """URL로 스토어 크롤링 실행"""
    store_crawler = StoreCrawler(browser_manager)
    product_urls = store_crawler.crawl_store_by_url(store_url, args.get("max_products", CRAWLING["max_products"]))
    
    if not product_urls:
        logger.warning("상품 URL을 찾을 수 없습니다.")
        return False
    
    # 결과 저장
    # 스토어 URL에서 도메인과 경로를 추출하여 파일명 생성
    import re
    store_name = re.sub(r'[^\w]', '_', store_url.split('/')[-1])
    if not store_name:
        store_name = "amazon_store"
    
    output_file = os.path.join(DATA_DIR, f"{store_name}_products.txt")
    with open(output_file, "w") as f:
        for url in product_urls:
            f.write(f"{url}\n")
    
    logger.info(f"{len(product_urls)}개의 상품 URL을 {output_file}에 저장했습니다.")
    print(f"{len(product_urls)}개의 상품 URL을 {output_file}에 저장했습니다.")
    
    # 스토어 모드에서 상품 정보까지 크롤링할 경우
    if args.get("crawl_reviews", False):
        print(f"각 상품 및 리뷰 크롤링을 시작합니다... (상품당 최대 {args.get('max_reviews', CRAWLING['max_reviews'])}개 리뷰)")
        crawl_products_from_list(product_urls, args, browser_manager, db_manager)
    
    return True

def crawl_single_product(product_url, args, browser_manager, db_manager):
    """단일 상품 크롤링"""
    # 상품 정보 크롤링
    product_crawler = ProductCrawler(browser_manager)
    product = product_crawler.crawl_product(product_url)
    
    if not product:
        logger.error(f"상품 크롤링 실패: {product_url}")
        print(f"상품 크롤링 실패: {product_url}")
        return False
    
    # 데이터베이스에 저장
    db_manager.save_product(product)
    print(f"상품 정보 저장 완료: {product.title}")
    
    # 리뷰 크롤링 - 모드가 리뷰이거나 crawl_reviews 옵션이 활성화된 경우
    if args.get("mode") == "review" or args.get("crawl_reviews", False):
        review_crawler = ReviewCrawler(browser_manager)
        max_reviews = args.get("max_reviews", CRAWLING["max_reviews"])
        print(f"상품 '{product.title}' 리뷰 크롤링 시작 (최대 {max_reviews}개)...")
        reviews = review_crawler.crawl_reviews(product_url, max_reviews)
        
        if reviews:
            # 각 리뷰에 상품 ASIN 설정
            for review in reviews:
                review.asin = product.asin
            
            # 데이터베이스에 저장
            db_manager.save_reviews(reviews)
            print(f"{len(reviews)}개의 리뷰 저장 완료")
            
            # 리뷰 CSV 내보내기
            db_manager.export_reviews_to_csv(product.asin)
            print(f"리뷰 데이터 CSV 내보내기 완료")
        else:
            print("이 상품에 대한 리뷰를 찾을 수 없거나 수집할 수 없습니다.")
    
    return True

def crawl_products_from_list(product_urls, args, browser_manager, db_manager):
    """여러 상품 크롤링"""
    total_products = len(product_urls)
    success_count = 0
    
    # 진행 상황 표시 기능 추가
    from tqdm import tqdm
    
    logger.info(f"{total_products}개의 상품 크롤링을 시작합니다")
    print(f"{total_products}개의 상품 크롤링을 시작합니다")
    
    # tqdm으로 진행 상황 표시
    for i, url in enumerate(tqdm(product_urls, desc="상품 크롤링"), 1):
        logger.info(f"상품 크롤링 중 {i}/{total_products}: {url}")
        print(f"\n상품 크롤링 중 {i}/{total_products}: {url}")
        
        if crawl_single_product(url, args, browser_manager, db_manager):
            success_count += 1
        
        # 상품 크롤링 간 지연 시간 추가 (단축된 지연 시간 사용)
        if i < total_products:
            delay = browser_manager.random_delay(min_delay=0.5, max_delay=1.0)
    
    logger.info(f"{total_products}개 중 {success_count}개 상품을 성공적으로 크롤링했습니다")
    print(f"{total_products}개 중 {success_count}개 상품을 성공적으로 크롤링했습니다")
    
    # 성공적으로 크롤링한 상품 CSV 내보내기
    db_manager.export_products_to_csv()
    print("모든 상품 데이터 CSV 내보내기 완료")
    
    return success_count > 0

def main():
    """메인 실행 함수"""
    # 출력 디렉토리 확인
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # 브라우저 관리자 초기화
    browser_manager = BrowserManager()
    
    # 데이터베이스 관리자 초기화
    db_manager = DBManager()
    
    try:
        while True:
            args = get_user_input()
            
            if args["mode"] == "exit":
                print("프로그램을 종료합니다.")
                break
            
            # 모드에 따른 크롤링 실행
            if args["mode"] == "store":
                # 스토어 크롤링
                crawl_store_by_url(args["store_url"], args, browser_manager, db_manager)
                
            elif args["mode"] == "product":
                # 단일 상품 크롤링
                crawl_single_product(args["product_url"], args, browser_manager, db_manager)
                
            elif args["mode"] == "review":
                # 단일 상품 및 리뷰 크롤링
                crawl_single_product(args["product_url"], args, browser_manager, db_manager)
            
            # 작업 완료 후 계속할지 확인
            continue_choice = input("\n다른 작업을 진행하시겠습니까? (y/n): ").lower().strip()
            if continue_choice != 'y':
                print("프로그램을 종료합니다.")
                break
    
    except KeyboardInterrupt:
        logger.info("사용자에 의해 크롤링이 중단되었습니다")
        print("\n사용자에 의해 크롤링이 중단되었습니다")
    except Exception as e:
        logger.error(f"크롤링 중 오류 발생: {str(e)}", exc_info=True)
        print(f"크롤링 중 오류 발생: {str(e)}")
    finally:
        # 리소스 정리
        db_manager.close()
        browser_manager.close()
        logger.info("크롤링 프로세스 종료")

if __name__ == "__main__":
    main()