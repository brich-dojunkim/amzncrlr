import json
from datetime import datetime

class Review:
    def __init__(self):
        self.review_id = ""
        self.asin = ""
        self.title = ""
        self.rating = 0.0
        self.date = ""
        self.reviewer_name = ""
        self.verified_purchase = False
        self.body = ""
        self.helpful_count = 0
        self.crawl_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def to_dict(self):
        """객체를 딕셔너리로 변환"""
        return {
            "review_id": self.review_id,
            "asin": self.asin,
            "title": self.title,
            "rating": self.rating,
            "date": self.date,
            "reviewer_name": self.reviewer_name,
            "verified_purchase": self.verified_purchase,
            "body": self.body,
            "helpful_count": self.helpful_count,
            "crawl_date": self.crawl_date
        }
    
    def to_json(self):
        """객체를 JSON 문자열로 변환"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_dict(cls, data):
        """딕셔너리에서 객체 생성"""
        review = cls()
        for key, value in data.items():
            if hasattr(review, key):
                setattr(review, key, value)
        return review