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
    
    def is_login_page(self):
        """로그인 페이지인지 확인"""
        try:
            # 로그인 관련 요소 확인
            login_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                "#ap_email, .a-section.a-spacing-base.auth-pagelet-container, #signIn, input[name='email'], .a-box.a-spacing-base, form[name='signIn']")
            
            # URL 확인
            current_url = self.driver.current_url.lower()
            login_urls = ["signin", "ap/signin", "ap/sign-in", "amazonlogin", "auth/signin"]
            
            is_login_url = any(login_url in current_url for login_url in login_urls)
            
            # 페이지 제목 확인
            page_title = self.driver.title.lower()
            login_titles = ["sign in", "amazon sign", "로그인", "amazon 로그인"]
            is_login_title = any(login_title in page_title for login_title in login_titles)
            
            return len(login_elements) > 0 or is_login_url or is_login_title
        except:
            return False

    def wait_for_login(self, timeout=300):
        """로그인 대기 (최대 5분)"""
        start_time = time.time()
        logger.info("로그인이 필요합니다. 브라우저에서 로그인을 진행해주세요...")
        print("\n====== 로그인 필요 ======")
        print("아마존 로그인이 필요합니다. 브라우저 창에서 로그인을 진행해주세요.")
        print(f"로그인 완료 후 자동으로 크롤링이 계속됩니다 (최대 {timeout}초 대기)")
        print("로그인이 끝난 후 크롤링을 즉시 계속하려면 Enter 키를 누르세요.")
        print("=======================\n")
        
        # 별도 스레드에서 Enter 키 입력 대기
        import threading
        import sys
        
        continue_flag = [False]
        
        def wait_for_enter():
            input("로그인 완료 후 Enter 키를 눌러주세요...")
            continue_flag[0] = True
        
        # 입력 대기 스레드 시작
        input_thread = threading.Thread(target=wait_for_enter)
        input_thread.daemon = True
        input_thread.start()
        
        while time.time() - start_time < timeout:
            # Enter 키 입력 확인
            if continue_flag[0]:
                logger.info("사용자 입력으로 크롤링을 계속합니다.")
                print("\n크롤링을 계속합니다.\n")
                time.sleep(1)
                return True
            
            # 로그인 페이지 벗어남 확인
            if not self.is_login_page():
                logger.info("로그인이 완료되었습니다. 크롤링을 계속합니다.")
                print("\n로그인이 완료되었습니다. 크롤링을 계속합니다.\n")
                # 로그인 후 페이지 로드 대기
                time.sleep(3)
                return True
                
            time.sleep(2)
        
        logger.warning("로그인 제한 시간이 초과되었습니다.")
        print("\n로그인 제한 시간이 초과되었습니다. 크롤링이 취소될 수 있습니다.\n")
        return False
    
    def get_page(self, url, retry=0):
        """페이지 접근 및 재시도 로직"""
        try:
            logger.info(f"Navigating to: {url}")
            self.driver.get(url)
            self.random_delay(min_delay=1.0, max_delay=2.0)  # 더 짧은 지연 시간
            
            # 최초 페이지 로드 대기
            self.wait_for_page_load(timeout=5)
            
            # 로그인 페이지 확인
            if self.is_login_page():
                logger.info("로그인 페이지 감지됨")
                if not self.wait_for_login():
                    return False
                
                # 로그인 후 리디렉션 대기
                self.wait_for_page_load(timeout=5)
                
                # 리디렉션 후 원래 URL로 다시 접근 (로그인 후 홈으로 가는 경우 대비)
                if "amazon.com" in self.driver.current_url and not url in self.driver.current_url:
                    logger.info("로그인 후 원래 URL로 다시 접근합니다.")
                    self.driver.get(url)
                    self.random_delay(min_delay=1.0, max_delay=2.0)
            
            # 캡차 페이지 확인 및 처리 - 더 정확한 감지 조건 사용
            page_source = self.driver.page_source.lower()
            
            # 캡차 페이지일 때만 실행 (텍스트와 이미지 둘 다 확인)
            if ("captcha" in page_source and "enter the characters" in page_source) or \
               ("robot" in page_source and "not a robot" in page_source) or \
               ("automated access" in page_source and "verify" in page_source):
                
                # 실제 캡차 이미지 요소 확인
                captcha_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                    "img[src*='captcha'], img[alt*='captcha'], img[src*='Captcha'], form[action*='captcha']")
                
                if captcha_elements:
                    print("\n====== 보안 확인(캡차) 감지 ======")
                    print("아마존 보안 확인이 필요합니다. 브라우저 창에서 보안 확인을 완료해주세요.")
                    print("완료 후 Enter 키를 누르면 크롤링이 계속됩니다.")
                    input("Enter 키를 눌러 계속...")
                    print("크롤링을 계속합니다.\n")
                    
                    # 캡차 완료 후 페이지 새로고침
                    self.driver.refresh()
                    self.random_delay(min_delay=1.0, max_delay=2.0)
            
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
    
    def wait_for_page_load(self, timeout=None):
        """페이지 로드 완료 대기"""
        timeout = timeout or BROWSER["page_load_timeout"]
        try:
            # 페이지 로드 완료 기다리기
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            return True
        except TimeoutException as e:
            logger.warning(f"Timeout waiting for page to load: {str(e)}")
            return False
    
    def random_delay(self, min_delay=None, max_delay=None):
        """무작위 지연 시간 추가 (사용자 지정 가능)"""
        min_delay = min_delay or CRAWLING["delay"]["min"]
        max_delay = max_delay or CRAWLING["delay"]["max"]
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)
        return delay
    
    def scroll_to_element(self, element):
        """특정 요소로 스크롤"""
        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
        self.random_delay(min_delay=0.5, max_delay=1.0)
    
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