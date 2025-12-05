from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.models import SocialNetwork


class AccountBase(BaseModel):
    social: SocialNetwork
    account_id: str
    account_type: str
    name: Optional[str] = None
    photo: Optional[str] = None
    smmbox_group_id: Optional[str] = None


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    account_id: Optional[str] = None
    account_type: Optional[str] = None
    name: Optional[str] = None
    photo: Optional[str] = None
    smmbox_group_id: Optional[str] = None


class AccountResponse(AccountBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class VideoUploadResponse(BaseModel):
    message: str
    video_path: str


class UniquizationStatus(BaseModel):
    total_videos: int
    target_count: int = 100
    video_urls: List[str] = []


class PostCreate(BaseModel):
    video_url: str
    account_id: int


class PostResponse(BaseModel):
    id: int
    account_id: int
    video_url: str
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class GroupInfo(BaseModel):
    id: str
    social: str
    type: str
    name: Optional[str] = None
    photo: Optional[str] = None
    index: Optional[int] = None


class GroupsBySocialResponse(BaseModel):
    social: str
    count: int
    groups: List[GroupInfo]


class PublishRequest(BaseModel):
    selected_accounts: List[dict]  # [{"id": "123", "social": "vk", "type": "user"}, ...]
    publish_date: str  # ISO format datetime string
    video_file: Optional[str] = None  # Will be sent as multipart


class PublishResponse(BaseModel):
    message: str
    total_accounts: int
    total_videos: int
    published: int
    errors: List[dict]
