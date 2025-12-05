from sqlalchemy import Column, Integer, String, Enum, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class SocialNetwork(str, enum.Enum):
    VK = "vk"
    INSTAGRAM = "io"
    YOUTUBE = "gg"
    PINTEREST = "pi"


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    social = Column(Enum(SocialNetwork), nullable=False)
    account_id = Column(String, nullable=False)  # ID аккаунта в соцсети
    account_type = Column(String, nullable=False)  # user, group, page
    name = Column(String, nullable=True)
    photo = Column(String, nullable=True)
    smmbox_group_id = Column(String, nullable=True)  # ID группы в SmmBox
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Связь с постами
    posts = relationship("Post", back_populates="account")


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    video_url = Column(String, nullable=False)  # URL видео в S3
    smmbox_post_id = Column(Integer, nullable=True)  # ID поста в SmmBox
    status = Column(String, default="pending")  # pending, published, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    published_at = Column(DateTime(timezone=True), nullable=True)

    # Связь с аккаунтом
    account = relationship("Account", back_populates="posts")
