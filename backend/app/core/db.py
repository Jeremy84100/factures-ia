from sqlmodel import Session, create_engine, select

from app import crud
from app.core.config import settings
from app.models import User, UserCreate

engine = create_engine(str(settings.DATABASE_URL), pool_pre_ping=True)


def create_superuser(session: Session, email: str, password: str) -> User:
    user = session.exec(select(User).where(User.email == email)).first()
    if user:
        return user
    user_in = UserCreate(email=email, password=password, is_superuser=True)
    return crud.create_user(session=session, user_create=user_in)
