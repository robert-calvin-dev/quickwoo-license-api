from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, EmailStr
from starlette.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from datetime import datetime, date
import os
import uuid
from dotenv import load_dotenv

from database import get_db
from models import License

load_dotenv()

app = FastAPI()

# CORS (optional, but helpful for JS testing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ENV VARS
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")

# ----------------------
# SCHEMAS
# ----------------------
class LicenseVerifyRequest(BaseModel):
    license_key: str
    email: EmailStr
    plugin: str

# ----------------------
# ROUTES
# ----------------------
@app.post("/verify-license")
async def verify_license(data: LicenseVerifyRequest):
    db = get_db()
    license = db.query(License).filter_by(
        license_key=data.license_key,
        email=data.email,
        plugin=data.plugin
    ).first()

    if not license:
        return JSONResponse(status_code=403, content={"valid": False, "reason": 
"not_found"})

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

    # Optional: log validation event
    license.validated_at = datetime.utcnow()
    db.commit()

    return {"valid": True, "plugin": license.plugin, "plan": license.plan, 
"expires_at": license.expires_at}

@app.get("/")
def root():
    return {"status": "OK", "message": "QuickWoo License API live."}

