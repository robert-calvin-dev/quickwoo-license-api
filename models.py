from sqlalchemy import Column, String, Boolean, Date, DateTime
from sqlalchemy.ext.declarative import declarative_base
import uuid
from datetime import datetime

Base = declarative_base()

class License(Base):
    __tablename__ = "licenses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    license_key = Column(String, unique=True, nullable=False)
    email = Column(String, nullable=False)
    plugin = Column(String, nullable=False)
    plan = Column(String, nullable=False)  # 'year' or 'life'
    issued_at = Column(Date, default=datetime.utcnow)
    expires_at = Column(Date, nullable=True)  # null = lifetime
    validated_at = Column(DateTime, nullable=True)
    revoked = Column(Boolean, default=False)
    revoke_reason = Column(String, nullable=True)
    revoked_at = Column(DateTime, nullable=True)

