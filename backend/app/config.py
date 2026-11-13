import os
from pydantic import BaseModel

class Settings(BaseModel):
    PORT: int = int(os.getenv("PORT", "8000"))
    DATAPIPELINE_DB: str = os.getenv("DATAPIPELINE_DB", "datapipeline.db")

settings = Settings()
