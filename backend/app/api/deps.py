import uuid
from collections.abc import Generator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlmodel import Session

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.models import TokenPayload, User
from app.services.extraction import DocumentExtractor, GeminiExtractor

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


def get_db() -> Generator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


def get_current_user(session: SessionDep, token: TokenDep) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        if payload.get("purpose", "access") != "access":
            raise InvalidTokenError("Wrong token purpose")
        token_data = TokenPayload(**payload)
        user_id = uuid.UUID(token_data.sub or "")
    except InvalidTokenError, ValidationError, ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session invalide, reconnectez-vous",
        )
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Compte désactivé")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Droits insuffisants")
    return current_user


def get_extractor() -> DocumentExtractor:
    return GeminiExtractor(api_key=settings.GEMINI_API_KEY, model=settings.GEMINI_MODEL)


def get_engine() -> Engine:
    return engine


ExtractorDep = Annotated[DocumentExtractor, Depends(get_extractor)]
EngineDep = Annotated[Engine, Depends(get_engine)]
