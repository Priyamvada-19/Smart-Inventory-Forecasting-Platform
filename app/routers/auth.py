from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

from app import models, schemas, security
from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=schemas.UserOut, status_code=201)
def register(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")
    if db.query(models.User).filter(models.User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = models.User(
        username=payload.username,
        email=payload.email,
        hashed_password=security.hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/google", response_model=schemas.Token)
def login_with_google(payload: schemas.GoogleLoginRequest, db: Session = Depends(get_db)):
    """
    Verifies a Google Identity Services ID token and issues our own JWT.

    Frontend flow this pairs with:
      1. Load https://accounts.google.com/gsi/client
      2. google.accounts.id.initialize({ client_id: YOUR_CLIENT_ID, callback: onGoogleResponse })
      3. onGoogleResponse receives { credential } -- POST { id_token: credential } here.

    Requires GOOGLE_CLIENT_ID to be set in the environment, matching a Client ID
    registered in Google Cloud Console with your frontend's exact origin listed
    under "Authorized JavaScript origins".
    """
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in is not configured on this server (GOOGLE_CLIENT_ID is unset).",
        )

    try:
        info = google_id_token.verify_oauth2_token(
            payload.id_token, google_requests.Request(), settings.google_client_id
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google token")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach Google to verify the token. Try again.",
        )

    email = info.get("email")
    if not email or not info.get("email_verified", False):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google account email not verified")

    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        base_username = email.split("@")[0]
        username = base_username
        suffix = 1
        while db.query(models.User).filter(models.User.username == username).first():
            username = f"{base_username}{suffix}"
            suffix += 1
        user = models.User(
            username=username,
            email=email,
            hashed_password=security.hash_password(security.create_access_token(email, "viewer")),  # unusable random hash, login is Google-only
            role=models.UserRole.viewer,
            auth_provider="google",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token = security.create_access_token(subject=user.username, role=user.role.value)
    return schemas.Token(access_token=token, role=user.role)


@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    identifier = form_data.username
    user = (
        db.query(models.User)
        .filter((models.User.username == identifier) | (models.User.email == identifier))
        .first()
    )
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = security.create_access_token(subject=user.username, role=user.role.value)
    return schemas.Token(access_token=token, role=user.role)


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(security.get_current_user)):
    return current_user
