from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./webclip.db"
    static_dir: Path = Path(__file__).resolve().parent.parent / "static"
    # WEBCLIP_API_TOKEN と組み合わせて /api/* に Bearer を要求する
    api_token: str | None = Field(default=None, validation_alias="WEBCLIP_API_TOKEN")
    # 起動時に false にすると、トークンがあっても Bearer 認証をかけない
    bearer_auth_enabled: bool = Field(default=True, validation_alias="WEBCLIP_BEARER_AUTH_ENABLED")

    @property
    def bearer_auth_active(self) -> bool:
        return self.bearer_auth_enabled and bool(self.api_token and self.api_token.strip())

    # ゴミ箱に入れてから完全削除までの日数
    trash_retention_days: int = Field(default=30, ge=1, le=3650, validation_alias="WEBCLIP_TRASH_RETENTION_DAYS")

    @property
    def data_dir(self) -> Path:
        if self.database_url.startswith("sqlite:///"):
            return Path(self.database_url.replace("sqlite:///", "")).resolve().parent
        return Path("./data").resolve()

    @property
    def images_dir(self) -> Path:
        return self.data_dir / "images"


settings = Settings()
