from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

import database as db
import schemas

from fastapi import Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

app = FastAPI(title="Job Tracker API")

# Erstellt Tabellen beim Serverstart, falls noch nicht vorhanden
db.init_db()

@app.post("/api/applications", response_model=schemas.ApplicationOut, status_code=status.HTTP_201_CREATED)
def create_application(app_in: schemas.ApplicationCreate, session: Session = Depends(db.get_db)):
    # Daten aus dem Pydantic-Schema in ein SQLAlchemy-Model umwandeln:
    db_app = db.Application(**app_in.model_dump())
    session.add(db_app)
    session.commit()
    session.refresh(db_app)
    return db_app

@app.get("/api/applications", response_model=List[schemas.ApplicationOut])
def get_all_applications(session: Session = Depends(db.get_db)):
    applications = session.query(db.Application).all()
    return applications

@app.get("/api/applications/{app_id}", response_model=schemas.ApplicationOut)
def get_application(app_id: int, session: Session = Depends(db.get_db)):
    db_app = session.query(db.Application).filter(db.Application.id == app_id).first()

    if not db_app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bewerbung mit ID {app_id} nicht gefunden")

    return db_app

@app.delete("/api/applications/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(app_id: int, session: Session = Depends(db.get_db)):
    db_app = session.query(db.Application).filter(db.Application.id == app_id).first()
    

    if not db_app:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bewerbung mit ID {app_id} nicht gefunden")

    session.delete(db_app)
    session.commit()

    return None

@app.patch("/api/applications/{app_id}", response_model=schemas.ApplicationOut)
def patch_application(app_id: int, app_update: schemas.ApplicationUpdate ,session: Session = Depends(db.get_db)):
    db_app = session.query(db.Application).filter(db.Application.id == app_id).first()
    
    if not db_app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bewerbung mit ID {app_id} nicht gefunden")
    
    update_data = app_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(db_app, field, value)


    session.commit()
    session.refresh(db_app)
    return db_app

@app.get("/", response_class=HTMLResponse)
def get_dashboard(request: Request, session: Session = Depends(db.get_db)):
    # 1. Alle Bewerbungen holen
    applications = session.query(db.Application).order_by(db.Application.id.desc()).all()

    # 2. Statistiken berechnen
    total_count = len(applications)
    applied_count = session.query(db.Application).filter(db.Application.status != db.ApplicationStatus.DRAFT).count()
    avg_wage = session.query(func.avg(db.Application.hourly_wage)).scalar()

    stats = {
        "total": total_count,
        "applied": applied_count,
        "avg_wage": f"{avg_wage:.2f} €" if avg_wage else "–"
    }

    # 3. HTML-Template mit Daten füttern
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "applications": applications,
            "stats": stats,
            "job_types": [t.value for t in db.JobType],
            "statuses": [s.value for s in db.ApplicationStatus]

        }
    )

@app.post("/applications/add")
def add_application_form(
    company: str = Form(...),
    position: str = Form(...),
    job_type: str = Form(...),
    hourly_wage: Optional[float] = Form(None),
    hours_per_week: Optional[float] = Form(None),
    location: Optional[str] = Form(None),
    session: Session = Depends(db.get_db)
):
    # Den String aus dem Dropdown wieder dem passenden Enum zuordnen
    type_enum = next((t for t in db.JobType if t.value == job_type), db.JobType.NA)

    new_app = db.Application(
        company=company.strip(),
        position=position.strip(),
        job_type=type_enum,
        hourly_wage=hourly_wage,
        hours_per_week = hours_per_week,
        location=location.strip() if location else None
    )
    session.add(new_app)
    session.commit()

    # Nach dem Speichern Browser neu laden (HTTP 303 See Other)
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/applications/{app_id}/delete")
def delete_application_form(app_id: int, session: Session = Depends(db.get_db)):
    db_app = session.query(db.Application).filter(db.Application.id == app_id).first()
    if db_app:
        session.delete(db_app)
        session.commit()
    # Leitet den Browser wieder zurück zum Dashboard:
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/applications/{app_id}/update-status")
def update_status_form(app_id: int, new_status: str = Form(...), session: Session = Depends(db.get_db)):
    db_app = session.query(db.Application).filter(db.Application.id == app_id).first()
    if db_app:
        db_app.status = db.ApplicationStatus(new_status)
        session.commit()
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/applications/{app_id}/edit")
def edit_application_form(
    app_id: int,
    location: Optional[str] = Form(None),
    distance: Optional[str] = Form(None),
    contact: Optional[str] = Form(None),
    job_url: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    session: Session = Depends(db.get_db)
):
    db_app = session.query(db.Application).filter(db.Application.id == app_id).first()
    if db_app:
        db_app.location = location.strip() if location else None
        db_app.distance = distance.strip() if distance else None
        db_app.contact = contact.strip() if contact else None
        db_app.job_url = job_url.strip() if job_url else None
        db_app.notes = notes.strip() if notes else None
        session.commit()
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)