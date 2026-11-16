from getpass import getpass

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlmodel import Session

from app.core.db import create_superuser, engine


def main() -> None:
    try:
        email = TypeAdapter(EmailStr).validate_python(input("E-mail : ").strip())
    except ValidationError:
        raise SystemExit("Adresse e-mail invalide")
    password = getpass("Mot de passe : ")
    if len(password) < 8:
        raise SystemExit("8 caractères minimum")
    if getpass("Confirmez : ") != password:
        raise SystemExit("Les mots de passe ne correspondent pas")
    with Session(engine) as session:
        user = create_superuser(session, email, password)
    print(f"Administrateur prêt : {user.email}")


if __name__ == "__main__":
    main()
