from datetime import date
from typing import Optional
from pydantic import BaseModel
from database import JobType, ApplicationStatus

# Gemeinsame Basis-Felder
class ApplicationBase(BaseModel):
    company: str
    position: str
    job_type: JobType = JobType.NA
    status: ApplicationStatus = ApplicationStatus.DRAFT
    hourly_wage: Optional[float] = None
    hours_per_week: Optional[int] = None
    location: Optional[str] = None
    distance: Optional[str] = None
    contact: Optional[str] = None
    job_url: Optional[str] = None
    applied_date: Optional[date] = None
    notes: Optional[str] = None

class ApplicationUpdate(BaseModel):
    company: Optional[str] = None
    position: Optional[str] = None
    job_type: Optional[JobType] = None
    status: Optional[ApplicationStatus] = None
    hourly_wage: Optional[float] = None
    hours_per_week: Optional[int] = None
    location: Optional[str] = None
    distance: Optional[str] = None
    contact: Optional[str] = None
    job_url: Optional[str] = None
    applied_date: Optional[date] = None
    notes: Optional[str] = None

class ApplicationCreate(ApplicationBase):
    pass

class ApplicationOut(ApplicationBase):
    id: int

    class Config:
        from_attributes = True  # Erlaubt Pydantic, Daten direkt aus SQLAlchemy-Objekten zu lesen