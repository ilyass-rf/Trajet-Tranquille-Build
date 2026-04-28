from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from database import SessionLocal, BusLocation
from pydantic import BaseModel

app = FastAPI()

# Modèle de données pour la réception (Pydantic)
class LocationUpdate(BaseModel):
    bus_id: str
    latitude: float
    longitude: float

# Dépendance pour la base de données
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ROUTE 1 : Recevoir les données de l'Arduino
@app.post("/update-location")
async def update_location(data: LocationUpdate, db: Session = Depends(get_db)):
    new_point = BusLocation(
        bus_id=data.bus_id,
        latitude=data.latitude,
        longitude=data.longitude
    )
    db.add(new_point)
    db.commit()
    return {"status": "success", "message": "Position enregistrée"}

# ROUTE 2 : Envoyer la dernière position au Site Web
@app.get("/get-bus/{bus_id}")
async def get_bus(bus_id: str, db: Session = Depends(get_db)):
    location = db.query(BusLocation).filter(BusLocation.bus_id == bus_id).order_by(BusLocation.timestamp.desc()).first()
    if location:
        return {
            "bus_id": location.bus_id,
            "lat": location.latitude,
            "lon": location.longitude,
            "time": location.timestamp
        }
    return {"error": "Bus non trouvé"}