# app/models/history.py
from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class ProductStatusHistory(BaseModel):
    __tablename__ = "product_status_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"))
    old_status = Column(String(20))
    new_status = Column(String(20), nullable=False)
    changed_by = Column(String(36))  
    reason = Column(Text)
    comment = Column(Text)
    
   
    product = relationship("Product")