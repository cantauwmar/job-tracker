from enum import Enum
from sqlalchemy import Column, Integer, String, Float, Text, Date, Enum as SQLEnum, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./applications.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class JobType(str, Enum):
    IT_STUDENT = "IT-Werkstudent"
    MINIJOB = "Standard-Minijob"
    NON_IT_STUDENT = "Werkstudent (Non-IT)"
    OTHER = "Sonstige"
    NA = "Nicht angegeben"

class ApplicationStatus(str, Enum):
    DRAFT = "Entwurf"
    APPLIED = "Beworben"
    FIRST_ROUND = "Erstgespräch"
    TECH_INTERVIEW = "Tech-Interview"
    OFFER = "Zusage"
    REJECTED = "Absage"

class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    company = Column(String(30), nullable=False)
    position = Column(String(40), nullable=False)
    job_type = Column(SQLEnum(JobType), default=JobType.IT_STUDENT, nullable=False)
    status = Column(SQLEnum(ApplicationStatus), default=ApplicationStatus.DRAFT, nullable=False)
    #NULLwerte hier teilweise Erlaubt, da info nicht vorhanden bei vielen Stellenbeschreibungen
    hourly_wage = Column(Float)
    hours_per_week = Column(Integer)
    location = Column(String(30))
    distance = Column(String(50))
    contact = Column(String(50))
    job_url = Column(String(100))
    applied_date = Column(Date )
    notes = Column(String)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

