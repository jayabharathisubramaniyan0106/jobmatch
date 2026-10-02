from typing import List, Optional
from pydantic import BaseModel, Field
class RegisterIn(BaseModel):
    name: str = Field(min_length=2)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=6)
    role: str = Field(pattern="^(seeker|recruiter)$")
    phone: str = ""
    roles: List[str] = []
    skills: List[str] = []
    experience: str = "Fresher"
    location: str = ""
    expected_pay: int = 0
    preference: str = "Both"
    company_name: str = ""
class LoginIn(BaseModel):
    email: str
    password: str
class ProfileIn(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    roles: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    experience: Optional[str] = None
    location: Optional[str] = None
    expected_pay: Optional[int] = None
    preference: Optional[str] = None
    company_name: Optional[str] = None
    company_desc: Optional[str] = None
    website: Optional[str] = None
class OppIn(BaseModel):
    title: str = Field(min_length=2)
    role: str = Field(min_length=2)
    skills: List[str] = []
    experience: str = "Fresher"
    location: str = ""
    pay: int = 0
    job_type: str = "Full-time"
    work_mode: str = "On-site"
    description: str = ""
class AppIn(BaseModel):
    opportunity_id: int
    resume_name: str = ""
    resume_data: str = ""  # base64 file content
class StatusIn(BaseModel):
    status: str
class SavedIn(BaseModel):
    opportunity_id: int
