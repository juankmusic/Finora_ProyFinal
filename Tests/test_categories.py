import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
import json
from Main import create_app
from config import TestingConfig
from Modules.models import db, User, Category
from Modules.auth import AuthService

# Nota: El script SQL ya inserta algunas categorías globales. 
# Para las pruebas unitarias, confiamos en la inicialización de la DB por SQLAlchemy.

@pytest.fixture
def app():
    """Configura la app para pruebas con la DB en memoria."""
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        # Crear usuario de prueba
        AuthService.register_user('cat_user@finance.com', 'securepass')
        # Insertar algunas categorías globales para las pruebas (simulando la carga inicial)
        db.session.add_all([
            Category(name='Salario', type='Ingreso', user_id=None),
            Category(name='Comida', type='Gasto', user_id=None),
            Category(name='Transporte', type='Gasto', user_id=None),
        ])
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """Crea un cliente de prueba para hacer solicitudes HTTP."""
    return app.test_client()

@pytest.fixture
def test_user_id(app):
    """Retorna el ID del usuario de prueba."""
    with app.app_context():
        user = User.query.filter_by(email='cat_user@finance.com').first()
        return user.id

def test_list_all_categories(client, test_user_id):
    """Prueba listar todas las categorías (globales + personalizadas)."""
    # 1. Crear una categoría personalizada
    client.post(
        '/api/v1/categories/add',
        data=json.dumps(dict(user_id=test_user_id, name='Regalos Recibidos', type='Ingreso')),
        content_type='application/json'
    )
    
    # 2. Obtener todas las categorías para el usuario
    response = client.get(f'/api/v1/categories/{test_user_id}')
    
    assert response.status_code == 200
    categories = response.get_json()  # Cambiar de json.get_json() a response.get_json()
    
    # Debe tener 3 globales + 1 personalizada = 4
    assert len(categories) == 4 
    
    # Verificar que la personalizada se reporte como custom
    custom_cat = next(c for c in categories if c['name'] == 'Regalos Recibidos')
    assert custom_cat['is_custom'] is True
    
    # Verificar que una global no se reporte como custom
    global_cat = next(c for c in categories if c['name'] == 'Comida')
    assert global_cat['is_custom'] is False


def test_list_categories_filter_type(client, test_user_id):
    """Prueba filtrar las categorías por tipo (Ingreso o Gasto)."""
    # 1. Crear una categoría personalizada
    client.post(
        '/api/v1/categories/add',
        data=json.dumps(dict(user_id=test_user_id, name='Ropa Nueva', type='Gasto')),
        content_type='application/json'
    )
    
    # 2. Obtener solo categorías de Gasto
    response = client.get(f'/api/v1/categories/{test_user_id}?type=Gasto')
    
    assert response.status_code == 200
    categories = response.get_json()  # Cambiar de json.get_json() a response.get_json()
    
    # Debe tener 'Comida' (global), 'Transporte' (global) y 'Ropa Nueva' (personalizada) = 3
    assert len(categories) == 3
    for cat in categories:
        assert cat['type'] == 'Gasto'


def test_create_custom_category_success(client, test_user_id):
    """Prueba la creación exitosa de una categoría personalizada."""
    response = client.post(
        '/api/v1/categories/add',
        data=json.dumps(dict(user_id=test_user_id, name='Cafetería', type='Gasto')),
        content_type='application/json'
    )
    
    assert response.status_code == 201
    data = response.get_json()  # Cambiar de json.get_json() a response.get_json()
    assert 'Cafetería' in data['name']

    # Verificar que se haya guardado en la DB con el user_id correcto
    with client.application.app_context():
        new_cat = Category.query.filter_by(name='Cafetería').first()
        assert new_cat is not None
        assert new_cat.user_id == test_user_id


def test_create_custom_category_duplicate(client, test_user_id):
    """Prueba que no se pueda crear una categoría duplicada para el mismo usuario."""
    # Primer intento (éxito)
    client.post(
        '/api/v1/categories/add',
        data=json.dumps(dict(user_id=test_user_id, name='Viajes', type='Gasto')),
        content_type='application/json'
    )
    
    # Segundo intento con el mismo nombre y usuario (falla)
    response = client.post(
        '/api/v1/categories/add',
        data=json.dumps(dict(user_id=test_user_id, name='Viajes', type='Gasto')),
        content_type='application/json'
    )
    
    assert response.status_code == 409
    assert 'Categoría ya existe' in response.get_json()['message']  # Cambiar de json.get_json() a response.get_json()
