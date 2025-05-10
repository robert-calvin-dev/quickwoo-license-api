from fastapi import FastAPI, Request, HTTPException, Header, Query
from pydantic import BaseModel, EmailStr
from starlette.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from datetime import datetime, date, timedelta
from typing import List
import os
import uuid
import stripe
import json
from dotenv import load_dotenv

from database import get_db
from models import License
from utils import generate_license_key

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")

stripe.api_key = STRIPE_SECRET_KEY

PRICE_MAP = {
    "price_1RN2RfRoUkoV66d2Ouyhudyi": {"plugin": "quick-add", "plan": "year"},
    "price_1RN3gCRoUkoV66d2oMhAAkWT": {"plugin": "quick-add", "plan": "life"},
    "price_1RMxJdRoUkoV66d2Gdid1PeH": {"plugin": "quick-edit", "plan": "year"},
    "price_1RMxK6RoUkoV66d2d6yN3dmW": {"plugin": "quick-edit", "plan": "life"},
    "price_1RMxKhRoUkoV66d20o1WH0RB": {"plugin": "quick-seo", "plan": "year"},
    "price_1RMxLCRoUkoV66d2ClvZ0akg": {"plugin": "quick-seo", "plan": "life"},
    "price_1RMxLsRoUkoV66d2YJEvgwoF": {"plugin": "quickwoo-bundle", "plan": "year"},
    "price_1RMxMORoUkoV66d2YSeyssqq": {"plugin": "quickwoo-bundle", "plan": "life"}
}

class LicenseVerifyRequest(BaseModel):
    license_key: str
    email: EmailStr
    plugin: str

class LicenseGenerateRequest(BaseModel):
    email: EmailStr
    plugin: str
    plan: str

class LicenseRevokeRequest(BaseModel):
    license_key: str
    email: EmailStr
    reason: str

@app.post("/verify-license")
async def verify_license(data: LicenseVerifyRequest):
    db = next(get_db())
    license = db.query(License).filter_by(
        license_key=data.license_key,
        email=data.email,
        plugin=data.plugin
    ).first()

    if not license:
        return JSONResponse(status_code=403, content={"valid": False, "reason": "not_found"})

    if license.revoked:
        return JSONResponse(status_code=403, content={
            "valid": False,
            "reason": "revoked",
            "revoke_reason": license.revoke_reason
        })

    if license.plan == 'year' and license.expires_at < date.today():
        return JSONResponse(status_code=403, content={
            "valid": False,
            "reason": "expired",
            "expired_at": str(license.expires_at)
        })

    license.validated_at = datetime.utcnow()
    db.commit()

    return {
        "valid": True,
        "plugin": license.plugin,
        "plan": license.plan,
        "expires_at": license.expires_at
    }

@app.post("/generate-license")
async def generate_license(data: LicenseGenerateRequest, x_api_key: str = Header(...)):
    if x_api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    db = next(get_db())
    issued_at = date.today()
    expires_at = issued_at + timedelta(days=365) if data.plan == "year" else None

    license_key = generate_license_key(data.plugin, data.plan, issued_at)

    new_license = License(
        license_key=license_key,
        email=data.email,
        plugin=data.plugin,
        plan=data.plan,
        issued_at=issued_at,
        expires_at=expires_at
    )

    db.add(new_license)
    db.commit()
    db.refresh(new_license)

    return {
        "license_key": new_license.license_key,
        "email": new_license.email,
        "plugin": new_license.plugin,
        "plan": new_license.plan,
        "expires_at": new_license.expires_at
    }

@app.post("/revoke-license")
async def revoke_license(data: LicenseRevokeRequest, x_api_key: str = Header(...)):
    if x_api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    db = next(get_db())
    license = db.query(License).filter_by(
        license_key=data.license_key,
        email=data.email
    ).first()

    if not license:
        raise HTTPException(status_code=404, detail="License not found")

    license.revoked = True
    license.revoke_reason = data.reason
    license.revoked_at = datetime.utcnow()
    db.commit()

    return {"status": "revoked", "license_key": data.license_key, "reason": data.reason}

@app.post("/stripe-webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    print("Received raw payload:", payload.decode())
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        print("Webhook signature error:", str(e))
        raise HTTPException(status_code=400, detail=f"Invalid webhook signature: {str(e)}")

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        email = session.get('customer_details', {}).get('email')
        session_id = session['id']

        try:
            line_items = stripe.checkout.Session.list_line_items(session_id, limit=1)
            price_id = line_items['data'][0]['price']['id'] if line_items['data'] else None
        except Exception as e:
            print("Failed to fetch line items:", str(e))
            raise HTTPException(status_code=500, detail=f"Failed to fetch line items: {str(e)}")
        
        print("Parsed email:", email)
        print("Parsed price_id:", price_id)
        print("PRICE_MAP keys:", list(PRICE_MAP.keys()))


        if email and price_id and price_id in PRICE_MAP:
            info = PRICE_MAP[price_id]
            issued_at = date.today()
            expires_at = issued_at + timedelta(days=365) if info['plan'] == "year" else None
            license_key = generate_license_key(info['plugin'], info['plan'], issued_at)

            db = next(get_db())
            new_license = License(
                license_key=license_key,
                email=email,
                plugin=info['plugin'],
                plan=info['plan'],
                issued_at=issued_at,
                expires_at=expires_at
            )
            db.add(new_license)
            db.commit()

    return {"status": "success"}

@app.get("/license-lookup")
def license_lookup(email: EmailStr = Query(...), x_api_key: str = Header(...)):
    if x_api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    db = next(get_db())
    licenses = db.query(License).filter_by(email=email).all()

    if not licenses:
        raise HTTPException(status_code=404, detail="No licenses found")

    return [
        {
            "license_key": l.license_key,
            "plugin": l.plugin,
            "plan": l.plan,
            "issued_at": str(l.issued_at),
            "expires_at": str(l.expires_at) if l.expires_at else None,
            "revoked": l.revoked
        }
        for l in licenses
    ]

@app.get("/")
def root():
    return {"status": "OK", "message": "QuickWoo License API live."}

from fastapi.staticfiles import StaticFiles
import os

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

