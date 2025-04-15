import os
from pathlib import Path

# 기본 경로 설정
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = os.path.join(BASE_DIR, "data_output")
LOG_DIR = os.path.join(BASE_DIR, "logs")

# 데이터베이스 설정
DATABASE = {
    "type": "sqlite",  # sqlite, mysql, postgresql 등
    "path": os.path.join(DATA_DIR, "amazon_data.db"),
}

# 브라우저 설정
BROWSER = {
    "headless": False,  # 헤드리스 모드 여부
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "window_size": (1920, 1080),
    "implicitly_wait": 3,  # 암시적 대기 시간(초) - 값 축소
    "page_load_timeout": 15,  # 페이지 로드 타임아웃(초) - 값 축소
}

# 크롤링 설정
CRAWLING = {
    "delay": {
        "min": 0.5,  # 최소 지연 시간(초) - 값 축소
        "max": 1.5,  # 최대 지연 시간(초) - 값 축소
    },
    "retry": {
        "max_attempts": 2,  # 최대 재시도 횟수 - 값 축소
        "backoff_factor": 1.5,  # 재시도 간격 증가 인자 - 값 축소
    },
    "max_products": 100,  # 스토어당 최대 상품 수집 수
    "max_reviews": 100,  # 상품당 최대 리뷰 수집 수
}

# 아마존 URL 설정
AMAZON = {
    "base_url": "https://www.amazon.com",
    "store_url_pattern": "https://www.amazon.com/stores/{store_id}",
}

# 프록시 설정 (필요한 경우)
PROXIES = []

# 폴더 생성
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)