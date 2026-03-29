from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import rasterio
import numpy as np
from pyproj import Transformer
import os

app = FastAPI()

# =========================
# CORS (REQUIRED FOR FRONTEND)
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# BASE DIRECTORY (IMPORTANT FOR DEPLOYMENT)
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# =========================
# LOAD RASTERS (SAFE PATH)
# =========================
def load_raster(filename):
    path = os.path.join(BASE_DIR, filename)
    return rasterio.open(path)

rasters = {
    "wheat": load_raster("energy_wheat.tif"),
    "chickpea": load_raster("energy_Chickpea.tif"),
    "mustard": load_raster("energy_Mustard.tif"),
    "lentils": load_raster("energy_lentils.tif"),
    "coriander": load_raster("energy_Coriander.tif"),
}

# =========================
# COORDINATE TRANSFORMER
# =========================
transformer = Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)

# =========================
# FAST VALUE SAMPLING (OPTIMIZED)
# =========================
def get_value(src, lat, lon):
    try:
        # Convert lat/lon → UTM
        x, y = transformer.transform(lon, lat)

        # Sample directly (faster than read entire raster)
        for val in src.sample([(x, y)]):
            value = val[0]

        # Handle NoData
        if src.nodata is not None and value == src.nodata:
            return None

        if np.isnan(value):
            return None

        return float(value)

    except Exception:
        return None

# =========================
# ROOT ENDPOINT
# =========================
@app.get("/")
def home():
    return {
        "message": "Irrigation Energy API is running",
        "usage": "/calculate?lat=23&lon=77&crop=wheat&area=2&price=6",
        "inputs": {
            "lat": "Latitude (decimal degrees)",
            "lon": "Longitude (decimal degrees)",
            "crop": ["wheat", "chickpea", "mustard", "lentils", "coriander"],
            "area": "Land area in hectares",
            "price": "Electricity price (₹ per kWh)"
        }
    }

# =========================
# MAIN API
# =========================
@app.get("/calculate")
def calculate(lat: float, lon: float, crop: str, area: float, price: float):

    crop = crop.lower()

    # Validate crop
    if crop not in rasters:
        return {
            "error": "Invalid crop",
            "allowed_crops": list(rasters.keys())
        }

    # Get energy per hectare
    energy_per_ha = get_value(rasters[crop], lat, lon)

    if energy_per_ha is None:
        return {
            "error": "Location outside Madhya Pradesh or no data available"
        }

    # =========================
    # CALCULATIONS
    # =========================
    total_energy = energy_per_ha * area
    total_cost = total_energy * price

    # =========================
    # RESPONSE
    # =========================
    return {
        "crop": crop,
        "location": {
            "latitude": lat,
            "longitude": lon
        },
        "inputs": {
            "land_area_hectare": area,
            "electricity_price_rs_per_kwh": price
        },
        "results": {
            "energy_per_hectare_kwh": round(energy_per_ha, 2),
            "total_energy_kwh": round(total_energy, 2),
            "total_cost_rs": round(total_cost, 2)
        }
    }