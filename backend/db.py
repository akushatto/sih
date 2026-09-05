import os
from collections import Counter
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, JSON
from sqlalchemy.orm import declarative_base, sessionmaker

URL = os.getenv("DATABASE_URL", "sqlite:///./labelguard.db")
engine = create_engine(URL, connect_args={"check_same_thread": False} if URL.startswith("sqlite") else {})
Session = sessionmaker(bind=engine)
Base = declarative_base()


class Inspection(Base):
    __tablename__ = "inspections"
    id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    product_name = Column(String)
    category = Column(String)
    lang = Column(String)
    score = Column(Float)
    status = Column(String, index=True)
    violations = Column(Integer)
    timing_ms = Column(Integer)
    checks = Column(JSON)
    fields = Column(JSON)
    scale = Column(JSON)
    image_path = Column(String)
    sha256 = Column(String)


def init_db():
    Base.metadata.create_all(engine)


def to_dict(r: Inspection, light=False):
    d = {"id": r.id, "created_at": r.created_at.isoformat() + "Z", "product_name": r.product_name,
         "category": r.category, "score": r.score, "status": r.status, "violations": r.violations, "timing_ms": r.timing_ms,
         "image_url": f"/evidence/{r.id}.jpg", "annotated_url": f"/evidence/{r.id}_annotated.jpg",
         "pdf_url": f"/api/report/{r.id}.pdf"}
    if not light:
        d.update(checks=r.checks, fields=r.fields, scale=r.scale, image_path=r.image_path, sha256=r.sha256, lang=r.lang)
    return d


def save_inspection(res: dict, image_path: str):
    with Session() as s:
        s.add(Inspection(id=res["id"], product_name=res.get("product_name"), category=res.get("category"),
                         lang=res.get("lang"), score=res["score"], status=res["status"], violations=res["violations"],
                         timing_ms=res.get("timing_ms"), checks=res["checks"], fields=res["fields"],
                         scale=res.get("scale"), image_path=image_path, sha256=res.get("sha256")))
        s.commit()


def list_inspections(limit=50, status: str | None = None):
    with Session() as s:
        q = s.query(Inspection).order_by(Inspection.created_at.desc())
        if status:
            q = q.filter(Inspection.status == status)
        return [to_dict(r, light=True) for r in q.limit(limit)]


def get_inspection(iid: str):
    with Session() as s:
        r = s.get(Inspection, iid)
        return to_dict(r) if r else None


def stats(days=30):
    since = datetime.utcnow() - timedelta(days=days)
    with Session() as s:
        rows = s.query(Inspection).filter(Inspection.created_at >= since).all()
    total = len(rows)
    compliant = sum(r.status == "Compliant" for r in rows)
    by_rule = Counter()
    for r in rows:
        for c in (r.checks or []):
            if c.get("s") == "bad":
                by_rule[c["ref"].split("—")[0].strip()] += 1
    daily = Counter(r.created_at.strftime("%Y-%m-%d") for r in rows)
    days14 = [(datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(13, -1, -1)]
    repeat = Counter(r.product_name for r in rows if r.status != "Compliant" and r.product_name)
    return {
        "window_days": days, "total": total,
        "compliance_rate": round(100 * compliant / total) if total else 0,
        "open_violations": sum((r.violations or 0) for r in rows if r.status != "Compliant"),
        "avg_ms": round(sum((r.timing_ms or 0) for r in rows) / total) if total else None,
        "by_rule": by_rule.most_common(5),
        "daily": [[d, daily.get(d, 0)] for d in days14],
        "by_category": dict(Counter(r.category for r in rows)),
        "repeat_offenders": [{"product": p, "violations": n} for p, n in repeat.most_common(5) if n >= 2],
        "recent": [to_dict(r, light=True) for r in sorted(rows, key=lambda r: r.created_at, reverse=True)[:8]],
    }