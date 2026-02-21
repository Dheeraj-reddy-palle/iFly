from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # App Settings
    app_name: str = "iFly Flight Price Intelligence"
    env: str = "development"
    log_level: str = "INFO"
    
    # Database
    database_url: str
    db_pool_size: int = 5
    db_max_overflow: int = 10
    
    # Third Party: Amadeus
    amadeus_base_url: str = "https://test.api.amadeus.com"
    amadeus_api_key: str = ""  # Optional for prediction-only deployments
    amadeus_api_secret: str = ""  # Optional for prediction-only deployments
    
    # CORS
    cors_origins: str = ""  # Comma-separated production origins
    
    # Machine Learning (Future)
    ml_model_path: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
