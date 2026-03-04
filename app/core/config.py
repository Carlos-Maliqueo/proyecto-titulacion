import os
from dotenv import load_dotenv, find_dotenv
from pydantic import BaseModel

# Cargar variables desde .env en la raíz del proyecto
# find_dotenv() localiza el archivo aun si cambias el directorio de trabajo
# override=False => no pisa variables ya presentes en el entorno (comportamiento estándar)
load_dotenv(find_dotenv(), override=False)

class Settings(BaseModel):
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-key")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")

    # XSD
    #carpeta donde se ponen los XSD
    SII_XSD_DIR: str = os.getenv("SII_XSD_DIR", "app/xsd")
    #nombres de archivo
    SII_XSD_DTE: str = os.getenv("SII_XSD_DTE", "EnvioDTE_v10.xsd")
    SII_XSD_BOLETA: str = os.getenv("SII_XSD_BOLETA", "EnvioBOLETA_v11.xsd")

    # max reintentos y backoff
    ETL_MAX_RETRIES: int = 2
    ETL_BACKOFF_SEC: int = 5
    ETL_ADVISORY_LOCK_KEY: int = 424242

    # Notificaciones / monitoreo
    SLACK_WEBHOOK_URL: str | None = None  
    APP_BASE_URL: str | None = None

    # --- Scheduler ---
    SCHEDULER_ENABLED: bool = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"
    SCHEDULER_TIMEZONE: str = os.getenv("SCHEDULER_TIMEZONE", "America/Santiago")
    # CRON “min hora día mes día_semana” (5 campos). Para pruebas: "*/1 * * * *"
    SCHEDULER_CRON: str = os.getenv("SCHEDULER_CRON", "0 3 * * *")      

settings = Settings()
