from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, UniqueConstraint
from .database import Base
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)  # seeker | recruiter
    phone = Column(String, default="")
    roles = Column(Text, default="")       # interested roles (comma separated)
    skills = Column(Text, default="")
    experience = Column(String, default="Fresher")
    location = Column(String, default="")
    expected_pay = Column(Integer, default=0)
    preference = Column(String, default="Both")  # Job | Internship | Both
    company_name = Column(String, default="")
    company_desc = Column(Text, default="")
    website = Column(String, default="")
class Opportunity(Base):  # jobs and internships (kind = Job | Internship)
    __tablename__ = "opportunities"
    id = Column(Integer, primary_key=True)
    recruiter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    kind = Column(String, nullable=False)
    title = Column(String, nullable=False)
    role = Column(String, nullable=False)
    skills = Column(Text, default="")
    experience = Column(String, default="Fresher")
    location = Column(String, default="")
    pay = Column(Integer, default=0)
    job_type = Column(String, default="Full-time")
    work_mode = Column(String, default="On-site")
    description = Column(Text, default="")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("user_id", "opportunity_id"),)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"))
    resume = Column(Text, default="")
    status = Column(String, default="Applied")
    created_at = Column(DateTime, default=datetime.utcnow)
class Saved(Base):
    __tablename__ = "saved"
    __table_args__ = (UniqueConstraint("user_id", "opportunity_id"),)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"))
class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    message = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
