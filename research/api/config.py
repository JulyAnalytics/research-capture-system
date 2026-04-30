from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    db_path: str = str(Path(__file__).parent.parent / "data" / "research.db")
    image_root: str = str(Path(__file__).parent.parent / "data" / "images")
    library_db_path: str = ""
    # Empty string disables canvas source documents feature
    # and makes get_library_db() raise RuntimeError.

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
