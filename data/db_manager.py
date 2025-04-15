import sqlite3
import json
import os
import csv
from datetime import datetime

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DATABASE, DATA_DIR
from utils.logger import setup_logger
from data.product_model import Product
from data.review_model import Review

logger = setup_logger(__name__)

class DBManager:
    def __init__(self):
        self.db_path = DATABASE["path"]
        self.conn = None
        self.cursor = None
        self.initialize_db()
    
    def initialize_db(self):
        """데이터베이스 초기화 및 테이블 생성"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            
            # 상품 테이블 생성
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                asin TEXT PRIMARY KEY,
                url TEXT,
                title TEXT,
                price REAL,
                rating REAL,
                review_count INTEGER,
                description TEXT,
                features TEXT,
                details TEXT,
                variations TEXT,
                images TEXT,
                brand TEXT,
                crawl_date TEXT
            )
            ''')
            
            # 리뷰 테이블 생성
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                review_id TEXT PRIMARY KEY,
                asin TEXT,
                title TEXT,
                rating REAL,
                date TEXT,
                reviewer_name TEXT,
                verified_purchase INTEGER,
                body TEXT,
                helpful_count INTEGER,
                crawl_date TEXT,
                FOREIGN KEY (asin) REFERENCES products (asin)
            )
            ''')
            
            self.conn.commit()
            logger.info("Database initialized successfully")
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {str(e)}")
    
    def save_product(self, product):
        """상품 정보 저장"""
        try:
            self.cursor.execute('''
            INSERT OR REPLACE INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                product.asin,
                product.url,
                product.title,
                product.price,
                product.rating,
                product.review_count,
                product.description,
                json.dumps(product.features),
                json.dumps(product.details),
                json.dumps(product.variations),
                json.dumps(product.images),
                product.brand,
                product.crawl_date
            ))
            self.conn.commit()
            logger.info(f"Product saved: {product.asin} - {product.title}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Error saving product to database: {str(e)}")
            return False
    
    def save_review(self, review):
        """리뷰 정보 저장"""
        try:
            self.cursor.execute('''
            INSERT OR REPLACE INTO reviews VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                review.review_id,
                review.asin,
                review.title,
                review.rating,
                review.date,
                review.reviewer_name,
                1 if review.verified_purchase else 0,
                review.body,
                review.helpful_count,
                review.crawl_date
            ))
            self.conn.commit()
            logger.debug(f"Review saved: {review.review_id}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Error saving review to database: {str(e)}")
            return False
    
    def save_reviews(self, reviews):
        """여러 리뷰 정보 일괄 저장"""
        try:
            for review in reviews:
                self.save_review(review)
            logger.info(f"Saved {len(reviews)} reviews")
            return True
        except Exception as e:
            logger.error(f"Error saving reviews to database: {str(e)}")
            return False
    
    def export_products_to_csv(self, file_path=None):
        """상품 정보를 CSV 파일로 내보내기"""
        if file_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = os.path.join(DATA_DIR, f"products_{timestamp}.csv")
        
        try:
            self.cursor.execute("SELECT * FROM products")
            products = self.cursor.fetchall()
            
            # 테이블 열 이름 가져오기
            column_names = [description[0] for description in self.cursor.description]
            
            with open(file_path, 'w', newline='', encoding='utf-8') as csv_file:
                csv_writer = csv.writer(csv_file)
                csv_writer.writerow(column_names)  # 헤더 작성
                csv_writer.writerows(products)     # 데이터 작성
            
            logger.info(f"Products exported to CSV: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error exporting products to CSV: {str(e)}")
            return False
    
    def export_reviews_to_csv(self, asin=None, file_path=None):
        """리뷰 정보를 CSV 파일로 내보내기"""
        if file_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"reviews_{asin}_{timestamp}.csv" if asin else f"reviews_all_{timestamp}.csv"
            file_path = os.path.join(DATA_DIR, file_name)
        
        try:
            if asin:
                self.cursor.execute("SELECT * FROM reviews WHERE asin = ?", (asin,))
            else:
                self.cursor.execute("SELECT * FROM reviews")
                
            reviews = self.cursor.fetchall()
            
            # 테이블 열 이름 가져오기
            column_names = [description[0] for description in self.cursor.description]
            
            with open(file_path, 'w', newline='', encoding='utf-8') as csv_file:
                csv_writer = csv.writer(csv_file)
                csv_writer.writerow(column_names)  # 헤더 작성
                csv_writer.writerows(reviews)      # 데이터 작성
            
            logger.info(f"Reviews exported to CSV: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error exporting reviews to CSV: {str(e)}")
            return False
    
    def get_product(self, asin):
        """ASIN으로 상품 정보 조회"""
        try:
            self.cursor.execute("SELECT * FROM products WHERE asin = ?", (asin,))
            result = self.cursor.fetchone()
            
            if result:
                column_names = [description[0] for description in self.cursor.description]
                product_dict = {column_names[i]: result[i] for i in range(len(column_names))}
                
                # JSON 문자열을 리스트/딕셔너리로 변환
                product_dict["features"] = json.loads(product_dict["features"])
                product_dict["details"] = json.loads(product_dict["details"])
                product_dict["variations"] = json.loads(product_dict["variations"])
                product_dict["images"] = json.loads(product_dict["images"])
                
                return Product.from_dict(product_dict)
            return None
        except sqlite3.Error as e:
            logger.error(f"Error retrieving product from database: {str(e)}")
            return None
    
    def get_reviews(self, asin, limit=None):
        """ASIN으로 상품 리뷰 조회"""
        try:
            if limit:
                self.cursor.execute("SELECT * FROM reviews WHERE asin = ? LIMIT ?", (asin, limit))
            else:
                self.cursor.execute("SELECT * FROM reviews WHERE asin = ?", (asin,))
                
            results = self.cursor.fetchall()
            reviews = []
            
            if results:
                column_names = [description[0] for description in self.cursor.description]
                
                for result in results:
                    review_dict = {column_names[i]: result[i] for i in range(len(column_names))}
                    # Boolean 값 변환
                    review_dict["verified_purchase"] = bool(review_dict["verified_purchase"])
                    reviews.append(Review.from_dict(review_dict))
            
            return reviews
        except sqlite3.Error as e:
            logger.error(f"Error retrieving reviews from database: {str(e)}")
            return []
    
    def close(self):
        """데이터베이스 연결 종료"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")