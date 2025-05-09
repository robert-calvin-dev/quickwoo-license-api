from fastapi import FastAPI, Request, HTTPException, Header
from pydantic import BaseModel, EmailStr
from starlette.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from datetime import datetime, date, timedelta
import os
import uuid
import hmac
import hashlib
import json
import stripe
import smtplib
from email.mime.text import MIMEText
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
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")

stripe.api_key = STRIPE_SECRET_KEY

PRICE_MAP = {
    "price_1RMtLxRsUBtHLZvd9xEhquGH": {"plugin": "quick-add", "plan": "year"},
    "price_1RMtMURsUBtHLZvdHZxqBaVX": {"plugin": "quick-add", "plan": "life"},
    "price_1RMtN7RsUBtHLZvdINpQTk9o": {"plugin": "quick-edit", "plan": "year"},
    "price_1RMtO8RsUBtHLZvdoiAxc3sk": {"plugin": "quick-edit", "plan": "life"},
    "price_1RMtOgRsUBtHLZvd3PcrTf80": {"plugin": "quick-seo", "plan": "year"},
    "price_1RMtPHRsUBtHLZvdwZ6BhH3g": {"plugin": "quick-seo", "plan": "life"},
    "price_1RMtQSRsUBtHLZvdErOh33fh": {"plugin": "quickwoo-bundle", "plan": "year"},
    "price_1RMtR9RsUBtHLZvdJCE0UquK": {"plugin": "quickwoo-bundle", "plan": "life"}
}

def send_license_email(to_email, plugin, license_key):
    subject = f"Your QuickWoo License for {plugin}"
    body = f"""
Thank you for your purchase of {plugin}!

Your license key:
{license_key}

You can now activate your plugin by entering this key in your WordPress dashboard.

Download your plugin here:
https://www.quickwoo.pro/downloads/{plugin}.zip

Enjoy,
The QuickWoo Team
    """
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_HOST_USER
    msg['To'] = to_email

    try:
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
            server.sendmail(EMAIL_HOST_USER, to_email, msg.as_string())
            print(f"Sent license to {to_email}")
    except Exception as e:
        print("Failed to send email:", e)

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

    send_license_email(data.email, data.plugin, license_key)

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

            send_license_email(email, info['plugin'], license_key)

    return {"status": "success"}

@app.get("/")
def root():
    return {"status": "OK", "message": "QuickWoo License API live."}
