import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import json
import allure
from Main import create_app
from config import TestingConfig
from Modules.models import db, User, Category
from Modules.auth import AuthService


@pytest.fixture
def app():
    """Configura la app para pruebas con la DB en memoria."""
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        # Crear usuario de prueba
        AuthService.register_user('cat_user@finance.com', 'securepass')
        # Insertar algunas categorías globales (simulando carga inicial)
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


# ------------------------
# PRUEBAS CON ALLURE
# ------------------------

@allure.feature("Categorías")
@allure.story("Listar categorías (globales + personalizadas)")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("Verifica que se listen correctamente las categorías globales y personalizadas de un usuario.")
def test_list_all_categories(client, test_user_id):
    with allure.step("Crear una categoría personalizada para el usuario"):
        client.post(
            '/api/v1/categories/add',
            data=json.dumps(dict(user_id=test_user_id, name='Regalos Recibidos', type='Ingreso')),
            content_type='application/json'
        )

    with allure.step("Solicitar la lista de categorías del usuario"):
        response = client.get(f'/api/v1/categories/{test_user_id}')
        assert response.status_code == 200
        categories = response.get_json()
        allure.attach(json.dumps(categories, indent=2), name="Listado de categorías", attachment_type=allure.attachment_type.JSON)

    with allure.step("Validar cantidad de categorías (3 globales + 1 personalizada)"):
        assert len(categories) == 4

    with allure.step("Validar que la categoría personalizada se marque como 'custom'"):
        custom_cat = next(c for c in categories if c['name'] == 'Regalos Recibidos')
        assert custom_cat['is_custom'] is True

    with allure.step("Validar que una categoría global no sea 'custom'"):
        global_cat = next(c for c in categories if c['name'] == 'Comida')
        assert global_cat['is_custom'] is False


@allure.feature("Categorías")
@allure.story("Filtrar categorías por tipo")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("Verifica que se puedan filtrar correctamente las categorías por tipo (Ingreso o Gasto).")
def test_list_categories_filter_type(client, test_user_id):
    with allure.step("Crear una categoría personalizada tipo 'Gasto'"):
        client.post(
            '/api/v1/categories/add',
            data=json.dumps(dict(user_id=test_user_id, name='Ropa Nueva', type='Gasto')),
            content_type='application/json'
        )

    with allure.step("Solicitar las categorías filtradas por tipo Gasto"):
        response = client.get(f'/api/v1/categories/{test_user_id}?type=Gasto')
        assert response.status_code == 200
        categories = response.get_json()
        allure.attach(json.dumps(categories, indent=2), name="Categorías de tipo Gasto", attachment_type=allure.attachment_type.JSON)

    with allure.step("Validar que solo existan categorías de tipo 'Gasto'"):
        assert len(categories) == 3
        for cat in categories:
            assert cat['type'] == 'Gasto'


@allure.feature("Categorías")
@allure.story("Crear categoría personalizada")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("Verifica que se pueda crear una categoría personalizada correctamente.")
def test_create_custom_category_success(client, test_user_id):
    with allure.step("Enviar solicitud para crear categoría personalizada"):
        response = client.post(
            '/api/v1/categories/add',
            data=json.dumps(dict(user_id=test_user_id, name='Cafetería', type='Gasto')),
            content_type='application/json'
        )
        allure.attach(response.get_data(as_text=True), name="Respuesta del servidor", attachment_type=allure.attachment_type.TEXT)

    with allure.step("Verificar que la respuesta sea exitosa (201)"):
        assert response.status_code == 201
        data = response.get_json()
        assert 'Cafetería' in data['name']

    with allure.step("Verificar que la categoría se haya guardado correctamente en la base de datos"):
        with client.application.app_context():
            new_cat = Category.query.filter_by(name='Cafetería').first()
            assert new_cat is not None
            assert new_cat.user_id == test_user_id


@allure.feature("Categorías")
@allure.story("Evitar duplicados")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("Verifica que no se permita crear una categoría duplicada para el mismo usuario.")
def test_create_custom_category_duplicate(client, test_user_id):
    with allure.step("Crear primera categoría personalizada"):
        client.post(
            '/api/v1/categories/add',
            data=json.dumps(dict(user_id=test_user_id, name='Viajes', type='Gasto')),
            content_type='application/json'
        )

    with allure.step("Intentar crear la misma categoría nuevamente"):
        response = client.post(
            '/api/v1/categories/add',
            data=json.dumps(dict(user_id=test_user_id, name='Viajes', type='Gasto')),
            content_type='application/json'
        )
        allure.attach(response.get_data(as_text=True), name="Respuesta duplicada", attachment_type=allure.attachment_type.TEXT)

    with allure.step("Verificar que el código sea 409 y el mensaje de error correcto"):
        assert response.status_code == 409
        assert 'Categoría ya existe' in response.get_json()['message']
