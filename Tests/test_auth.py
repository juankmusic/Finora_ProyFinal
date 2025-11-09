import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import json
import allure
from Main import create_app
from config import TestingConfig
from Modules.models import db, User

@pytest.fixture
def app():
    """Configura la app para pruebas usando la clase TestingConfig."""
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """Crea un cliente de prueba para hacer solicitudes HTTP."""
    return app.test_client()

# ------------------------
# PRUEBAS CON ALLURE
# ------------------------

@allure.feature("Registro de usuario")
@allure.story("Registro exitoso")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("Verifica que un nuevo usuario pueda registrarse correctamente.")
def test_user_registration_success(client):
    with allure.step("Enviar solicitud POST a /api/v1/register"):
        response = client.post(
            '/api/v1/register',
            data=json.dumps(dict(email='test1@example.com', password='password123')),
            content_type='application/json'
        )

    with allure.step("Verificar código de estado 201 y mensaje de éxito"):
        assert response.status_code == 201
        data = response.get_json()
        assert 'Registro exitoso.' in data['message']
        assert User.query.filter_by(email='test1@example.com').first() is not None


@allure.feature("Registro de usuario")
@allure.story("Registro duplicado")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("Prueba que no se pueda registrar un email ya existente.")
def test_user_registration_duplicate(client):
    client.post(
        '/api/v1/register',
        data=json.dumps(dict(email='test2@example.com', password='password123')),
        content_type='application/json'
    )
    response = client.post(
        '/api/v1/register',
        data=json.dumps(dict(email='test2@example.com', password='password456')),
        content_type='application/json'
    )

    with allure.step("Verificar código 409 y mensaje de conflicto"):
        assert response.status_code == 409
        data = response.get_json()
        assert 'El email ya está registrado.' in data['message']


@allure.feature("Inicio de sesión")
@allure.story("Login exitoso")
@allure.severity(allure.severity_level.CRITICAL)
def test_user_login_success(client):
    client.post('/api/v1/register',
        data=json.dumps(dict(email='loginok@test.com', password='securepass')),
        content_type='application/json'
    )

    response = client.post(
        '/api/v1/login',
        data=json.dumps(dict(email='loginok@test.com', password='securepass')),
        content_type='application/json'
    )

    with allure.step("Verificar login exitoso (código 200)"):
        assert response.status_code == 200
        data = response.get_json()
        assert 'Login exitoso.' in data['message']


@allure.feature("Inicio de sesión")
@allure.story("Contraseña incorrecta")
@allure.severity(allure.severity_level.NORMAL)
def test_user_login_invalid_password(client):
    client.post('/api/v1/register',
        data=json.dumps(dict(email='loginfail@test.com', password='correctpass')),
        content_type='application/json'
    )

    response = client.post(
        '/api/v1/login',
        data=json.dumps(dict(email='loginfail@test.com', password='wrongpass')),
        content_type='application/json'
    )

    with allure.step("Verificar fallo de autenticación (401)"):
        assert response.status_code == 401
        data = response.get_json()
        assert 'Credenciales inválidas.' in data['message']


@allure.feature("Inicio de sesión")
@allure.story("Usuario inexistente")
@allure.severity(allure.severity_level.MINOR)
def test_user_login_nonexistent_user(client):
    response = client.post(
        '/api/v1/login',
        data=json.dumps(dict(email='nosuchuser@test.com', password='anypass')),
        content_type='application/json'
    )

    with allure.step("Verificar fallo de autenticación (401) para usuario inexistente"):
        assert response.status_code == 401
        data = response.get_json()
        assert 'Credenciales inválidas.' in data['message']
