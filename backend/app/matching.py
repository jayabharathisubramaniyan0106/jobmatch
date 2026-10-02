"""Rule-based, explainable matching (no ML). Role match is mandatory; the rest adds score.
Weights: role 40, skills 25, experience 10, location 10, pay 5, job/internship preference 10."""
EXP = ["fresher", "1-2 years", "3-5 years", "5+ years"]
def split(s): return {x.strip().lower() for x in (s or "").split(",") if x.strip()}
def score(u, o):
    if o.role.strip().lower() not in split(u.roles): return None  # role not selected -> never shown
    s = 40
    req = split(o.skills)
    s += 25 if not req else round(25 * len(req & split(u.skills)) / len(req))
    ue = EXP.index(u.experience.lower()) if u.experience.lower() in EXP else 0
    oe = EXP.index(o.experience.lower()) if o.experience.lower() in EXP else 0
    s += 10 if ue >= oe else (5 if ue == oe - 1 else 0)
    if o.work_mode == "Remote" or not u.location or u.location.strip().lower() == o.location.strip().lower(): s += 10
    if (o.pay or 0) >= (u.expected_pay or 0): s += 5
    if u.preference in ("Both", o.kind): s += 10
    return min(s, 100)
