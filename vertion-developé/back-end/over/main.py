import math
import datetime
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Index
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from pydantic import BaseModel, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# --- CONFIGURATION ---
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:PooTiiCaaTee21082006@localhost:5432/trajet_tranquille"
VITESSE_DEFAUT_KMH = 30.0   

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Trajet Tranquille API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- CORRECTION CORS (Indispensable pour test.html) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- BASE DE DONNÉES ---
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

# --- MODÈLES ---
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

# --- LOGIQUE DE CALCUL ---
def calculer_distance(lat1, lon1, lat2, lon2) -> float:
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi    = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def calculer_statut(distance: float) -> str:
    if distance < 100:
        return "À l'arrêt / très proche"
    elif distance < 500:
        return "Proche"
    elif distance < 2000:
        return "En approche"
    return "En route"

# --- ENDPOINTS ---

@app.get("/")
async def root():
    return {"message": "Serveur Trajet Tranquille opérationnel"}

@app.post("/update-location")
@limiter.limit("5/second")
async def update_location(request: Request, data: LocationUpdate, db: Session = Depends(get_db)):
    """Reçoit la position GPS envoyée par le bus (SimCom A7670G)."""
    db.add(BusLocation(
        bus_id    = data.bus_id,
        latitude  = data.latitude,
        longitude = data.longitude,
        speed_kmh = data.speed_kmh,
    ))
    db.commit()
    return {"status": "success"}

@app.get("/get-bus/{bus_id}")
@limiter.limit("60/minute")
async def get_bus(request: Request, bus_id: str, db: Session = Depends(get_db)):
    """Retourne la dernière position pour Leaflet."""
    location = (
        db.query(BusLocation)
        .filter(BusLocation.bus_id == bus_id)
        .order_by(BusLocation.timestamp.desc())
        .first()
    )
    if not location:
        raise HTTPException(status_code=404, detail="Bus introuvable")
    return {
        "bus_id"    : location.bus_id,
        "lat"       : location.latitude,
        "lon"       : location.longitude,
        "speed_kmh" : location.speed_kmh,
        "timestamp" : location.timestamp.isoformat(),
    }

@app.get("/get-bus-analysis/{bus_id}") #li ka yssta9bel les donné partagé par js dyal localisation d'utilisateur 
@limiter.limit("60/minute")
async def get_bus_analysis(
    request : Request,
    bus_id  : str,
    user_lat: float,
    user_lon: float,
    db      : Session = Depends(get_db),
):
    """Calcule distance et ETA pour l'interface utilisateur."""
    bus_pos = (
        db.query(BusLocation)
        .filter(BusLocation.bus_id == bus_id)
        .order_by(BusLocation.timestamp.desc())
        .first()
    )
    if not bus_pos:
        raise HTTPException(status_code=404, detail="Bus non trouvé")

    distance    = calculer_distance(bus_pos.latitude, bus_pos.longitude, user_lat, user_lon)
    vitesse_kmh = bus_pos.speed_kmh if (bus_pos.speed_kmh and bus_pos.speed_kmh > 1) else VITESSE_DEFAUT_KMH
    temps_sec   = distance / (vitesse_kmh / 3.6)

    return {
        "bus_id"                : bus_id,
        "distance_metres"       : round(distance, 1),
        "temps_arrivee_minutes" : round(temps_sec / 60, 1),
        "status"                : calculer_statut(distance),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)