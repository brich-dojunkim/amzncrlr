import json
from datetime import datetime

class Product:
    def __init__(self):
        self.asin = ""
        self.url = ""
        self.title = ""
        self.price = 0.0
        self.rating = 0.0
        self.review_count = 0
        self.description = ""
        self.features = []
        self.details = {}
        self.variations = []
        self.images = []
        self.brand = ""
        self.crawl_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def to_dict(self):
        """객체를 딕셔너리로 변환"""
        return {
            "asin": self.asin,
            "url": self.url,
            "title": self.title,
            "price": self.price,
            "rating": self.rating,
            "review_count": self.review_count,
            "description": self.description,
            "features": self.features,
            "details": self.details,
            "variations": self.variations,
            "images": self.images,
            "brand": self.brand,
            "crawl_date": self.crawl_date
        }
    
    def to_json(self):
        """객체를 JSON 문자열로 변환"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_dict(cls, data):
        """딕셔너리에서 객체 생성"""
        product = cls()
        for key, value in data.items():
            if hasattr(product, key):
                setattr(product, key, value)
        return product