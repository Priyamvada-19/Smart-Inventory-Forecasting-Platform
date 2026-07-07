from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    database_url: str = "mysql+pymysql://chainmind_app:chainmind_app_pw@localhost:3306/chainmind"
    secret_key: str = "dev-secret-do-not-use-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    seed_on_startup: bool = True
    google_client_id: str = ""  # from Google Cloud Console; required for POST /auth/google

    artifacts_dir: Path = Path(__file__).resolve().parent.parent / "artifacts"

    class Config:
        env_file = ".env"


settings = Settings()
settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
