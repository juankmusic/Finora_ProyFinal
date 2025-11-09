import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import json
from Main import create_app
from config import TestingConfig
from Modules.models import db, User

# Fixture para configurar la aplicación de pruebas con SQLite en memoria
@pytest.fixture
def app():
    """Configura la app para pruebas usando la clase TestingConfig."""
    app = create_app(TestingConfig)
    # Con el contexto de la aplicación, inicializa la DB y crea las tablas
    with app.app_context():
        db.create_all()
        # Se asegura que el estado de la DB esté limpio antes de cada prueba
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """Crea un cliente de prueba para hacer solicitudes HTTP."""
    return app.test_client()

def test_user_registration_success(client):
    """Prueba el registro exitoso de un nuevo usuario."""
    response = client.post(
        '/api/v1/register',
        data=json.dumps(dict(email='test1@example.com', password='password123')),
        content_type='application/json'
    )
    # Crítico 1: Verificar el código de estado 201 (Creado) y el mensaje de éxito
    assert response.status_code == 201
    data = response.get_json()  # Corregido: usar get_json() del objeto response
    assert 'Registro exitoso.' in data['message']
    assert User.query.filter_by(email='test1@example.com').first() is not None

def test_user_registration_duplicate(client):
    """Prueba que no se pueda registrar un email ya existente."""
    # Primer registro (debería ser exitoso)
    client.post(
        '/api/v1/register',
        data=json.dumps(dict(email='test2@example.com', password='password123')),
        content_type='application/json'
    )
    # Segundo registro con el mismo email (debería fallar)
    response = client.post(
        '/api/v1/register',
        data=json.dumps(dict(email='test2@example.com', password='password456')),
        content_type='application/json'
    )
    # Crítico 1: Verificar el código de estado 409 (Conflicto)
    assert response.status_code == 409
    data = response.get_json()  # Corregido: usar get_json() del objeto response
    assert 'El email ya está registrado.' in data['message']

def test_user_login_success(client):
    """Prueba el inicio de sesión con credenciales correctas."""
    # Registrar un usuario primero
    client.post('/api/v1/register', data=json.dumps(dict(email='loginok@test.com', password='securepass')), content_type='application/json')
    
    # Intentar iniciar sesión
    response = client.post(
        '/api/v1/login',
        data=json.dumps(dict(email='loginok@test.com', password='securepass')),
        content_type='application/json'
    )
    # Crítico 1: Verificar login exitoso (código 200)
    assert response.status_code == 200
    data = response.get_json()  # Corregido: usar get_json() del objeto response
    assert 'Login exitoso.' in data['message']

def test_user_login_invalid_password(client):
    """Prueba el inicio de sesión con contraseña incorrecta."""
    # Registrar un usuario
    client.post('/api/v1/register', data=json.dumps(dict(email='loginfail@test.com', password='correctpass')), content_type='application/json')
    
    # Intentar iniciar sesión con contraseña incorrecta
    response = client.post(
        '/api/v1/login',
        data=json.dumps(dict(email='loginfail@test.com', password='wrongpass')),
        content_type='application/json'
    )
    # Crítico 1: Verificar fallo de autenticación (código 401)
    assert response.status_code == 401
    data = response.get_json()  # Corregido: usar get_json() del objeto response
    assert 'Credenciales inválidas.' in data['message']

def test_user_login_nonexistent_user(client):
    """Prueba el inicio de sesión con un usuario que no existe."""
    response = client.post(
        '/api/v1/login',
        data=json.dumps(dict(email='nosuchuser@test.com', password='anypass')),
        content_type='application/json'
    )
    # Crítico 1: Verificar fallo de autenticación (código 401)
    assert response.status_code == 401
    data = response.get_json()  # Corregido: usar get_json() del objeto response
    assert 'Credenciales inválidas.' in data['message']  # Este mensaje es el que se retorna cuando el usuario no existe o la contraseña es incorrecta
