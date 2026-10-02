import base64, uuid
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from .database import Base, engine, get_db
from .models import User, Opportunity, Application, Saved, Notification
from .schemas import *
from .auth import hash_pw, check_pw, make_token, current_user, seeker, recruiter
from .matching import score, split

Base.metadata.create_all(engine)
app = FastAPI(title="JobMatch API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
UPLOADS = Path(__file__).resolve().parents[1] / "uploads"
UPLOADS.mkdir(exist_ok=True)
STATUSES = ["Applied", "Under Review", "Shortlisted", "Rejected", "Selected"]
CSV = ("roles", "skills")

def user_out(u):
    return dict(id=u.id, name=u.name, email=u.email, role=u.role, phone=u.phone,
                roles=[x for x in u.roles.split(",") if x], skills=[x for x in u.skills.split(",") if x],
                experience=u.experience, location=u.location, expected_pay=u.expected_pay, preference=u.preference,
                company_name=u.company_name, company_desc=u.company_desc, website=u.website)
def opp_out(o, db, u=None):
    r = db.get(User, o.recruiter_id)
    d = dict(id=o.id, kind=o.kind, title=o.title, role=o.role, skills=[x for x in o.skills.split(",") if x],
             experience=o.experience, location=o.location, pay=o.pay, job_type=o.job_type, work_mode=o.work_mode,
             description=o.description, active=o.active, created_at=o.created_at.isoformat(),
             company=r.company_name or r.name)
    if u and u.role == "seeker":
        d["match"] = score(u, o)
        d["applied"] = db.query(Application).filter_by(user_id=u.id, opportunity_id=o.id).first() is not None
        d["saved"] = db.query(Saved).filter_by(user_id=u.id, opportunity_id=o.id).first() is not None
    return d
def notify(db, uid, msg): db.add(Notification(user_id=uid, message=msg))

# ---------- auth ----------
@app.post("/auth/register")
def register(d: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter_by(email=d.email.lower()).first(): raise HTTPException(400, "Email already registered")
    if d.role == "seeker" and not d.roles: raise HTTPException(400, "Select at least one interested role")
    if d.role == "recruiter" and not d.company_name: raise HTTPException(400, "Company name is required")
    u = User(name=d.name, email=d.email.lower(), password_hash=hash_pw(d.password), role=d.role, phone=d.phone,
             roles=",".join(d.roles), skills=",".join(d.skills), experience=d.experience, location=d.location,
             expected_pay=d.expected_pay, preference=d.preference, company_name=d.company_name)
    db.add(u); db.commit()
    return {"token": make_token(u.id), "user": user_out(u)}
@app.post("/auth/login")
def login(d: LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter_by(email=d.email.lower()).first()
    if not u or not check_pw(d.password, u.password_hash): raise HTTPException(401, "Invalid email or password")
    return {"token": make_token(u.id), "user": user_out(u)}
@app.get("/auth/me")
def me(u: User = Depends(current_user)): return user_out(u)
@app.get("/profile")
def get_profile(u: User = Depends(current_user)): return user_out(u)
@app.put("/profile")
def put_profile(d: ProfileIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    for k, v in d.model_dump(exclude_unset=True).items():
        if v is None: continue
        setattr(u, k, ",".join(v) if k in CSV else v)
    db.commit(); return user_out(u)

# ---------- opportunities (jobs & internships) ----------
def query(db, kind, q="", location="", job_type="", work_mode="", min_pay=0, skill="", experience=""):
    qs = db.query(Opportunity).filter(Opportunity.kind == kind, Opportunity.active == True)
    if q: qs = qs.filter(Opportunity.title.ilike(f"%{q}%") | Opportunity.role.ilike(f"%{q}%"))
    if location: qs = qs.filter(Opportunity.location.ilike(f"%{location}%"))
    if job_type: qs = qs.filter(Opportunity.job_type == job_type)
    if work_mode: qs = qs.filter(Opportunity.work_mode == work_mode)
    if experience: qs = qs.filter(Opportunity.experience == experience)
    if skill: qs = qs.filter(Opportunity.skills.ilike(f"%{skill}%"))
    if min_pay: qs = qs.filter(Opportunity.pay >= min_pay)
    return qs.order_by(Opportunity.created_at.desc()).all()

def crud(kind, prefix):
    r = APIRouter(prefix=prefix)
    @r.post("")
    def create(d: OppIn, u: User = Depends(recruiter), db: Session = Depends(get_db)):
        o = Opportunity(recruiter_id=u.id, kind=kind, **{**d.model_dump(), "skills": ",".join(d.skills)})
        db.add(o); db.commit()
        for s in db.query(User).filter_by(role="seeker").all():
            if score(s, o) is not None: notify(db, s.id, f"New {kind.lower()} matches your interests: {o.title}")
        db.commit(); return opp_out(o, db)
    @r.get("")
    def list_(q: str = "", location: str = "", job_type: str = "", work_mode: str = "", min_pay: int = 0,
              skill: str = "", experience: str = "", u: User = Depends(current_user), db: Session = Depends(get_db)):
        return [opp_out(o, db, u) for o in query(db, kind, q, location, job_type, work_mode, min_pay, skill, experience)]
    @r.get("/mine")
    def mine(u: User = Depends(recruiter), db: Session = Depends(get_db)):
        return [opp_out(o, db) for o in db.query(Opportunity).filter_by(recruiter_id=u.id, kind=kind).order_by(Opportunity.created_at.desc())]
    def own(id, u, db):
        o = db.get(Opportunity, id)
        if not o or o.kind != kind: raise HTTPException(404, "Not found")
        if u.role == "recruiter" and o.recruiter_id != u.id: raise HTTPException(403, "Not your post")
        return o
    @r.get("/{id}")
    def one(id: int, u: User = Depends(current_user), db: Session = Depends(get_db)): return opp_out(own(id, u, db), db, u)
    @r.put("/{id}")
    def upd(id: int, d: OppIn, u: User = Depends(recruiter), db: Session = Depends(get_db)):
        o = own(id, u, db)
        for k, v in d.model_dump().items(): setattr(o, k, ",".join(v) if k == "skills" else v)
        db.commit(); return opp_out(o, db)
    @r.delete("/{id}")
    def delete(id: int, u: User = Depends(recruiter), db: Session = Depends(get_db)):
        o = own(id, u, db)
        db.query(Application).filter_by(opportunity_id=id).delete(); db.query(Saved).filter_by(opportunity_id=id).delete()
        db.delete(o); db.commit(); return {"ok": True}
    return r
app.include_router(crud("Job", "/jobs")); app.include_router(crud("Internship", "/internships"))

# ---------- recommendations ----------
def recs(db, u, kind, **f):
    out = [opp_out(o, db, u) for o in query(db, kind, **f)]
    return sorted([o for o in out if o["match"] is not None], key=lambda o: -o["match"])
@app.get("/recommendations/jobs")
def rec_jobs(q: str = "", location: str = "", job_type: str = "", work_mode: str = "", min_pay: int = 0, skill: str = "",
             experience: str = "", u: User = Depends(seeker), db: Session = Depends(get_db)):
    return recs(db, u, "Job", q=q, location=location, job_type=job_type, work_mode=work_mode, min_pay=min_pay, skill=skill, experience=experience)
@app.get("/recommendations/internships")
def rec_int(q: str = "", location: str = "", job_type: str = "", work_mode: str = "", min_pay: int = 0, skill: str = "",
            experience: str = "", u: User = Depends(seeker), db: Session = Depends(get_db)):
    return recs(db, u, "Internship", q=q, location=location, job_type=job_type, work_mode=work_mode, min_pay=min_pay, skill=skill, experience=experience)
@app.get("/recommendations")
def rec_all(u: User = Depends(seeker), db: Session = Depends(get_db)):
    return sorted(recs(db, u, "Job") + recs(db, u, "Internship"), key=lambda o: -o["match"])

# ---------- applications ----------
@app.post("/applications")
def apply(d: AppIn, u: User = Depends(seeker), db: Session = Depends(get_db)):
    o = db.get(Opportunity, d.opportunity_id)
    if not o: raise HTTPException(404, "Opportunity not found")
    if db.query(Application).filter_by(user_id=u.id, opportunity_id=o.id).first(): raise HTTPException(400, "Already applied")
    ext = Path(d.resume_name).suffix.lower()
    if ext not in (".pdf", ".doc", ".docx"): raise HTTPException(400, "Resume must be a PDF, DOC or DOCX file")
    try: raw = base64.b64decode(d.resume_data, validate=True)
    except Exception: raise HTTPException(400, "Invalid resume file")
    if not raw or len(raw) > 2 * 1024 * 1024: raise HTTPException(400, "Resume must be under 2 MB")
    fname = uuid.uuid4().hex + ext
    (UPLOADS / fname).write_bytes(raw)
    db.add(Application(user_id=u.id, opportunity_id=o.id, resume=fname + "|" + Path(d.resume_name).name))
    notify(db, o.recruiter_id, f"{u.name} applied for {o.title}"); db.commit(); return {"ok": True}
@app.get("/applications")
def apps(u: User = Depends(current_user), db: Session = Depends(get_db)):
    if u.role == "seeker":
        rows = db.query(Application).filter_by(user_id=u.id).order_by(Application.created_at.desc()).all()
    else:
        ids = [o.id for o in db.query(Opportunity).filter_by(recruiter_id=u.id)]
        rows = db.query(Application).filter(Application.opportunity_id.in_(ids)).order_by(Application.created_at.desc()).all() if ids else []
    out = []
    for a in rows:
        o, s = db.get(Opportunity, a.opportunity_id), db.get(User, a.user_id)
        out.append(dict(id=a.id, status=a.status, resume=a.resume.split("|")[-1], applied_at=a.created_at.isoformat(), title=o.title, kind=o.kind,
                        company=opp_out(o, db)["company"], applicant=s.name, applicant_email=s.email, match=score(s, o)))
    return out
@app.put("/applications/{id}/status")
def set_status(id: int, d: StatusIn, u: User = Depends(recruiter), db: Session = Depends(get_db)):
    if d.status not in STATUSES: raise HTTPException(400, "Invalid status")
    a = db.get(Application, id); o = a and db.get(Opportunity, a.opportunity_id)
    if not a or o.recruiter_id != u.id: raise HTTPException(404, "Application not found")
    a.status = d.status; notify(db, a.user_id, f"Your application for {o.title} is now: {d.status}"); db.commit(); return {"ok": True}

@app.get("/applications/{id}/resume")
def get_resume(id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    a = db.get(Application, id); o = a and db.get(Opportunity, a.opportunity_id)
    if not a or u.id not in (a.user_id, o.recruiter_id): raise HTTPException(404, "Not found")
    stored, _, name = a.resume.partition("|")
    p = UPLOADS / stored
    if not name or not p.exists(): raise HTTPException(404, "No resume file")
    return FileResponse(p, filename=name)

# ---------- saved ----------
@app.post("/saved")
def save(d: SavedIn, u: User = Depends(seeker), db: Session = Depends(get_db)):
    if not db.get(Opportunity, d.opportunity_id): raise HTTPException(404, "Not found")
    if not db.query(Saved).filter_by(user_id=u.id, opportunity_id=d.opportunity_id).first():
        db.add(Saved(user_id=u.id, opportunity_id=d.opportunity_id)); db.commit()
    return {"ok": True}
@app.get("/saved")
def saved(u: User = Depends(seeker), db: Session = Depends(get_db)):
    return [opp_out(db.get(Opportunity, s.opportunity_id), db, u) for s in db.query(Saved).filter_by(user_id=u.id)]
@app.delete("/saved/{opportunity_id}")
def unsave(opportunity_id: int, u: User = Depends(seeker), db: Session = Depends(get_db)):
    db.query(Saved).filter_by(user_id=u.id, opportunity_id=opportunity_id).delete(); db.commit(); return {"ok": True}

# ---------- recruiter extras ----------
@app.get("/matched-candidates")
def matched(u: User = Depends(recruiter), db: Session = Depends(get_db)):
    out = []
    seekers = db.query(User).filter_by(role="seeker").all()
    for o in db.query(Opportunity).filter_by(recruiter_id=u.id):
        for s in seekers:
            m = score(s, o)
            if m is not None: out.append(dict(post=o.title, kind=o.kind, name=s.name, email=s.email, skills=s.skills, experience=s.experience, location=s.location, match=m))
    return sorted(out, key=lambda x: -x["match"])
@app.get("/recruiter/stats")
def stats(u: User = Depends(recruiter), db: Session = Depends(get_db)):
    posts = db.query(Opportunity).filter_by(recruiter_id=u.id).all()
    return dict(total_posts=len(posts), active_posts=sum(p.active for p in posts), applications=len(apps(u, db)),
                matched_candidates=len({m["email"] for m in matched(u, db)}))
@app.put("/opportunities/{id}/toggle")
def toggle(id: int, u: User = Depends(recruiter), db: Session = Depends(get_db)):
    o = db.get(Opportunity, id)
    if not o or o.recruiter_id != u.id: raise HTTPException(404, "Not found")
    o.active = not o.active; db.commit(); return {"active": o.active}
@app.get("/notifications")
def notifs(u: User = Depends(current_user), db: Session = Depends(get_db)):
    return [dict(id=n.id, message=n.message, created_at=n.created_at.isoformat()) for n in db.query(Notification).filter_by(user_id=u.id).order_by(Notification.id.desc()).limit(50)]

FRONT = Path(__file__).resolve().parents[2] / "frontend"
if FRONT.exists(): app.mount("/", StaticFiles(directory=FRONT, html=True), name="frontend")
