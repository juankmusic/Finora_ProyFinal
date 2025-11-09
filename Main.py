import os
from flask import Flask
from Modules.models import db
from Modules.api import api_bp
from config import DevelopmentConfig, TestingConfig

def create_app(config_class=DevelopmentConfig):
    """Función de factoría para crear y configurar la aplicación Flask."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Inicialización de extensiones
    db.init_app(app)

    # Registro de Blueprints (rutas)
    app.register_blueprint(api_bp)

    # Crea las tablas de la DB si no existen (solo se debe correr en desarrollo)
    with app.app_context():
        # db.drop_all() # Descomentar para resetear la base de datos
        db.create_all()

    return app

if __name__ == '__main__':
    # Usar el ambiente de desarrollo por defecto
    app = create_app(DevelopmentConfig)
    # Se asegura que la carpeta 'uploads' exista (si fuera necesario para archivos)
    # os.makedirs('uploads', exist_ok=True)
    app.run(host='0.0.0.0', port=5000)