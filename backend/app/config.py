from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "BeFriend FundAsset"
    database_url: str = "sqlite:///./data/fundasset.db"

    class Config:
        env_file = ".env"


settings = Settings()
