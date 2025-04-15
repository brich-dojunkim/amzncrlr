import random
import requests
import json
import time
from selenium import webdriver

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import PROXIES
from utils.logger import setup_logger

logger = setup_logger(__name__)

class ProxyRotator:
    def __init__(self, proxies=None):
        self.proxies = proxies or PROXIES
        self.current_proxy = None
        self.last_rotation_time = 0
        self.min_rotation_interval = 60  # 최소 로테이션 간격(초)
    
    def get_proxy(self):
        """랜덤 프록시 반환"""
        if not self.proxies:
            logger.warning("No proxies available")
            return None
        
        current_time = time.time()
        # 마지막 로테이션 후 일정 시간이 지났거나 현재 프록시가 없는 경우 새 프록시 선택
        if (current_time - self.last_rotation_time > self.min_rotation_interval) or (self.current_proxy is None):
            self.current_proxy = random.choice(self.proxies)
            self.last_rotation_time = current_time
            logger.info(f"Proxy rotated to: {self.current_proxy}")
        
        return self.current_proxy
    
    def rotate_proxy(self):
        """강제로 프록시 변경"""
        if not self.proxies or len(self.proxies) <= 1:
            logger.warning("Not enough proxies to rotate")
            return False
        
        # 현재 프록시를 제외한 리스트에서 새 프록시 선택
        available_proxies = [p for p in self.proxies if p != self.current_proxy]
        if not available_proxies:
            logger.warning("No alternative proxies available")
            return False
        
        self.current_proxy = random.choice(available_proxies)
        self.last_rotation_time = time.time()
        logger.info(f"Force proxy rotation to: {self.current_proxy}")
        return True
    
    def apply_proxy_to_webdriver(self, chrome_options):
        """웹드라이버에 프록시 설정 적용"""
        proxy = self.get_proxy()
        if proxy:
            chrome_options.add_argument(f'--proxy-server={proxy}')
            logger.info(f"Applied proxy to webdriver: {proxy}")
            return True
        return False
    
    def check_proxy_status(self, proxy=None):
        """프록시 상태 확인"""
        proxy_to_check = proxy or self.current_proxy
        if not proxy_to_check:
            logger.warning("No proxy to check")
            return False
        
        try:
            # 테스트용 요청
            response = requests.get('https://httpbin.org/ip', 
                                   proxies={'http': proxy_to_check, 'https': proxy_to_check},
                                   timeout=10)
            
            if response.status_code == 200:
                ip_info = json.loads(response.text)
                logger.info(f"Proxy {proxy_to_check} is working. Current IP: {ip_info.get('origin')}")
                return True
            else:
                logger.warning(f"Proxy {proxy_to_check} returned non-200 status: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Proxy {proxy_to_check} check failed: {str(e)}")
            return False
    
    def load_proxies_from_file(self, file_path):
        """파일에서 프록시 목록 로드"""
        try:
            with open(file_path, 'r') as f:
                new_proxies = [line.strip() for line in f.readlines() if line.strip()]
            
            if new_proxies:
                self.proxies = new_proxies
                logger.info(f"Loaded {len(new_proxies)} proxies from {file_path}")
                return True
            else:
                logger.warning(f"No proxies found in {file_path}")
                return False
        except Exception as e:
            logger.error(f"Error loading proxies from file: {str(e)}")
            return False