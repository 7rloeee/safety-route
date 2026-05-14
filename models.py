from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    google_id = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    picture_url = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    frequent_places = relationship("FrequentPlace", back_populates="owner", cascade="all, delete-orphan")
    emergency_contacts = relationship("EmergencyContact", back_populates="owner", cascade="all, delete-orphan")

class FrequentPlace(Base):
    __tablename__ = "frequent_places"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String)  # 예: 우리집, 회사
    address = Column(String)

    owner = relationship("User", back_populates="frequent_places")

class EmergencyContact(Base):
    __tablename__ = "emergency_contacts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String)      # 이름
    relation = Column(String)  # 관계 (아빠, 엄마 등)
    phone = Column(String)

    owner = relationship("User", back_populates="emergency_contacts")
