from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from pydantic import EmailStr
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static directory for HTML file serving
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

# Hardcoded license keys per product
STATIC_LICENSE_KEYS = {
    "quick-add": "QW-QUICKADD-STATIC-KEY",
    "quick-edit": "QW-QUICKEDIT-STATIC-KEY",
    "quick-seo": "QW-QUICKSEO-STATIC-KEY",
    "quick-blog": "QW-QUICKBLOG-STATIC-KEY",
    "quickwoo-bundle": [
        "QW-QUICKADD-STATIC-KEY",
        "QW-QUICKEDIT-STATIC-KEY",
        "QW-QUICKSEO-STATIC-KEY",
        "QW-QUICKBLOG-STATIC-KEY"
    ]
}

@app.get("/static-license")
def get_static_license(email: EmailStr, product: str):
    key = STATIC_LICENSE_KEYS.get(product)
    if not key:
        raise HTTPException(status_code=404, detail="Product not recognized")

    return {
        "email": email,
        "product": product,
        "license_keys": key if isinstance(key, list) else [key]
    }

@app.get("/")
def root():
    return {"status": "OK", "message": "QuickWoo Static License API ready."}
