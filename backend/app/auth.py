import os, hashlib, secrets, jwt
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from .database import get_db
from .models import User
SECRET = os.getenv("SECRET_KEY", "change-me-in-production")
bearer = HTTPBearer(auto_error=False)
def hash_pw(p, salt=None):
    salt = salt or secrets.token_hex(8)
    return salt + "$" + hashlib.pbkdf2_hmac("sha256", p.encode(), salt.encode(), 100000).hex()
def check_pw(p, stored):
    return hash_pw(p, stored.split("$")[0]) == stored
def make_token(uid):
    return jwt.encode({"sub": str(uid), "exp": datetime.utcnow() + timedelta(days=2)}, SECRET, "HS256")
def current_user(c: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)):
    if not c: raise HTTPException(401, "Not authenticated")
    try: uid = int(jwt.decode(c.credentials, SECRET, ["HS256"])["sub"])
    except Exception: raise HTTPException(401, "Invalid or expired token")
    u = db.get(User, uid)
    if not u: raise HTTPException(401, "User not found")
    return u
def seeker(u: User = Depends(current_user)):
    if u.role != "seeker": raise HTTPException(403, "Job seekers only")
    return u
def recruiter(u: User = Depends(current_user)):
    if u.role != "recruiter": raise HTTPException(403, "Recruiters only")
    return u
