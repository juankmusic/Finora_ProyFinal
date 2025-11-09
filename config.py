import os
from dotenv import load_dotenv

# Carga las variables de entorno del archivo .env
load_dotenv()

class Config:
    """Clase base de configuración, aplica para todos los ambientes."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'una_clave_secreta_fuerte')
    
    # Configuración de la Base de Datos PostgreSQL
    # Usaremos una base de datos local temporal para pruebas (sqlite) y PostgreSQL para desarrollo
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'postgresql://postgres:pgadmin4@localhost:5432/finora_db' # Reemplazar con credenciales reales
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(Config):
    """Configuración para el ambiente de desarrollo."""
    DEBUG = True

class TestingConfig(Config):
    """Configuración para el ambiente de pruebas (usaremos SQLite en memoria)."""
    TESTING = True
    # Usar una base de datos SQLite en memoria para que las pruebas sean rápidas y aisladas
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'