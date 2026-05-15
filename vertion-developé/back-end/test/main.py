from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Index
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase   
from pydantic import BaseModel, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import datetime

SQLALCHEMY_DATABASE_URL = "postgresql://postgres:password@localhost:5432/trajet_tranquille"
limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],         
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):      
    pass

class BusLocation(Base):
    __tablename__ = "bus_locations"
    id        = Column(Integer, primary_key=True, index=True)
    bus_id    = Column(String, nullable=False)
    latitude  = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    speed_kmh = Column(Float, nullable=True)     
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))  
    __table_args__ = (Index("ix_bus_id_timestamp", "bus_id", "timestamp"),)

Base.metadata.create_all(bind=engine)

class LocationUpdate(BaseModel):
    bus_id    : str
    latitude  : float
    longitude : float
    speed_kmh : float | None = None    

    @field_validator("latitude")
    @classmethod
    def check_latitude(cls, v):
        if not -90 <= v <= 90:
            raise ValueError(f"Latitude invalide : {v}")
        return v

    @field_validator("longitude")
    @classmethod
    def check_longitude(cls, v):
        if not -180 <= v <= 180:
            raise ValueError(f"Longitude invalide : {v}")
        return v

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/update-location")
@limiter.limit("2/second")
async def update_location(request: Request, data: LocationUpdate, db: Session = Depends(get_db)):
    new_point = BusLocation(
        bus_id    = data.bus_id,
        latitude  = data.latitude,
        longitude = data.longitude,
        speed_kmh = data.speed_kmh,
    )
    db.add(new_point)
    db.commit()
    return {"status": "success"}

@app.get("/get-bus/{bus_id}")
@limiter.limit("30/minute")         # ✅ rate limit aussi sur la lecture
async def get_bus(request: Request, bus_id: str, db: Session = Depends(get_db)):
    location = (
        db.query(BusLocation)
        .filter(BusLocation.bus_id == bus_id)
        .order_by(BusLocation.timestamp.desc())
        .first()
    )
    if not location:
        raise HTTPException(status_code=404, detail="Bus introuvable")   # ✅ 404 propre
    return {
        "bus_id"    : location.bus_id,
        "lat"       : location.latitude,
        "lon"       : location.longitude,
        "speed_kmh" : location.speed_kmh,
        "timestamp" : location.timestamp.isoformat(),
    }