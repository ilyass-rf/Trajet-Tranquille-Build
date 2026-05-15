import math
from fastapi import Depends, HTTPException, Request    
from sqlalchemy.orm import Session
from main import app, get_db, BusLocation, limiter

VITESSE_DEFAUT_KMH = 30.0  

def calculer_distance(lat1, lon1, lat2, lon2) -> float:
    """Formule de Haversine — retourne la distance en mètres."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi   = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

@app.get("/get-bus-analysis/{bus_id}")
@limiter.limit("30/minute")
async def get_bus_analysis(
    request : Request,
    bus_id  : str,
    user_lat: float,
    user_lon: float,
    db      : Session = Depends(get_db),
):
    if not (-90 <= user_lat <= 90) or not (-180 <= user_lon <= 180):
        raise HTTPException(status_code=422, detail="Coordonnées utilisateur invalides")
    bus_pos = (
        db.query(BusLocation)
        .filter(BusLocation.bus_id == bus_id)
        .order_by(BusLocation.timestamp.desc())
        .first()
    )
    if not bus_pos:
        raise HTTPException(status_code=404, detail="Bus non trouvé")
    distance = calculer_distance(
        bus_pos.latitude, bus_pos.longitude,
        user_lat, user_lon,
    )
    vitesse_kmh = bus_pos.speed_kmh if (bus_pos.speed_kmh and bus_pos.speed_kmh > 1) \
                  else VITESSE_DEFAUT_KMH
    vitesse_ms  = vitesse_kmh / 3.6
    temps_sec   = distance / vitesse_ms

    if distance < 100:
        statut = "À l'arrêt / très proche"
    elif distance < 500:
        statut = "Proche"
    elif distance < 2000:
        statut = "En approche"
    else:
        statut = "En route"

    return {
        "bus_id"               : bus_id,
        "distance_metres"      : round(distance, 1),
        "temps_arrivee_minutes": round(temps_sec / 60, 1),
        "vitesse_utilisee_kmh" : round(vitesse_kmh, 1),   
        "status"               : statut,
    }