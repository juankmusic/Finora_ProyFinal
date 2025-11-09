import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import json
import allure
from Main import create_app
from config import TestingConfig
from Modules.models import db, User, Goal
from Modules.auth import AuthService
from datetime import datetime, timedelta
import pytz


@pytest.fixture
def app():
    """Configura la app para pruebas con la DB en memoria."""
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        AuthService.register_user('goal_user@finance.com', 'securepass')
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
        user = User.query.filter_by(email='goal_user@finance.com').first()
        return user.id if user else 999


def get_future_date_iso(days=30):
    """Genera una fecha futura en formato ISO 8601 (UTC)."""
    return (datetime.now(pytz.utc) + timedelta(days=days)).isoformat()


def create_temp_goal(client, user_id, name, target, due_date):
    """Crea una meta temporal y devuelve su ID."""
    response = client.post(
        '/api/v1/goals/create',
        data=json.dumps(dict(user_id=user_id, name=name, target_amount=target, due_date=due_date)),
        content_type='application/json'
    )

    if response.status_code != 201:
        raise Exception(f"Fallo en create_temp_goal con status {response.status_code}: {response.get_json()}")
    
    return response.get_json()['id']


# ------------------------
# PRUEBAS CON ALLURE
# ------------------------

@allure.feature("Metas Financieras")
@allure.story("Creación de metas")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("Verifica que una meta pueda crearse correctamente con un monto y fecha válida.")
def test_create_goal_success(client, test_user_id):
    with allure.step("Generar una fecha futura válida"):
        future_date = get_future_date_iso(30)

    with allure.step("Enviar solicitud POST a /api/v1/goals/create"):
        response = client.post(
            '/api/v1/goals/create',
            data=json.dumps(dict(
                user_id=test_user_id,
                name='Vacaciones Europa',
                target_amount=5000.00,
                due_date=future_date
            )),
            content_type='application/json'
        )
        allure.attach(response.get_data(as_text=True), name="Respuesta de creación", attachment_type=allure.attachment_type.TEXT)

    with allure.step("Validar respuesta y datos almacenados"):
        assert response.status_code == 201
        data = response.get_json()
        assert 'Meta creada con éxito.' in data['message']

        with client.application.app_context():
            goal = db.session.get(Goal, data['id'])
            assert float(goal.target_amount) == 5000.00
            assert float(goal.current_amount) == 0.00


@allure.feature("Metas Financieras")
@allure.story("Validación de datos")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("Verifica que no se permita crear una meta con un monto objetivo no positivo.")
def test_create_goal_invalid_target(client, test_user_id):
    with allure.step("Generar fecha futura válida"):
        future_date = get_future_date_iso(30)

    with allure.step("Intentar crear meta con monto 0"):
        response = client.post(
            '/api/v1/goals/create',
            data=json.dumps(dict(
                user_id=test_user_id,
                name='Meta Inválida',
                target_amount=0,
                due_date=future_date
            )),
            content_type='application/json'
        )
        allure.attach(response.get_data(as_text=True), name="Respuesta inválida", attachment_type=allure.attachment_type.TEXT)

    with allure.step("Validar que la creación falle con 400"):
        assert response.status_code == 400
        assert 'El monto objetivo debe ser positivo.' in response.get_json()['message']


@allure.feature("Metas Financieras")
@allure.story("Contribución a metas")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("Prueba la contribución exitosa a una meta y la actualización del monto acumulado.")
def test_contribute_to_goal(client, test_user_id):
    with allure.step("Crear meta temporal válida"):
        future_date = get_future_date_iso(30)
        goal_id = create_temp_goal(client, test_user_id, 'Ahorro Inicial', 1000.00, future_date)

    with allure.step("Realizar contribución a la meta"):
        response = client.post(
            '/api/v1/goals/contribute',
            data=json.dumps(dict(goal_id=goal_id, amount=250.00)),
            content_type='application/json'
        )
        allure.attach(response.get_data(as_text=True), name="Respuesta contribución", attachment_type=allure.attachment_type.TEXT)

    with allure.step("Verificar resultado y base de datos"):
        assert response.status_code == 200
        data = response.get_json()
        assert 'Contribución registrada.' in data['message']
        assert data['new_current_amount'] == 250.00
        assert data['is_completed'] is False

        with client.application.app_context():
            goal = db.session.get(Goal, goal_id)
            assert float(goal.current_amount) == 250.00


@allure.feature("Metas Financieras")
@allure.story("Completado de metas")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("Verifica que una meta se marque como completada al alcanzar el monto objetivo.")
def test_goal_completion(client, test_user_id):
    with allure.step("Crear meta de 500.00"):
        future_date = get_future_date_iso(30)
        goal_id = create_temp_goal(client, test_user_id, 'Ahorro Corto', 500.00, future_date)

    with allure.step("Hacer contribución parcial de 400.00"):
        client.post(
            '/api/v1/goals/contribute',
            data=json.dumps(dict(goal_id=goal_id, amount=400.00)),
            content_type='application/json'
        )

    with allure.step("Hacer contribución final de 100.00"):
        response = client.post(
            '/api/v1/goals/contribute',
            data=json.dumps(dict(goal_id=goal_id, amount=100.00)),
            content_type='application/json'
        )
        allure.attach(response.get_data(as_text=True), name="Respuesta final", attachment_type=allure.attachment_type.TEXT)

    with allure.step("Verificar meta completada"):
        assert response.status_code == 200
        data = response.get_json()
        assert data['new_current_amount'] == 500.00
        assert data['is_completed'] is True


@allure.feature("Metas Financieras")
@allure.story("Listado de metas con progreso")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("Verifica que el listado de metas incluya el progreso y se ordene correctamente.")
def test_get_user_goals_with_progress(client, test_user_id):
    with allure.step("Crear metas con diferentes montos y fechas"):
        goal1_id = create_temp_goal(client, test_user_id, 'Meta 100%', 200.00, get_future_date_iso(60))
        goal2_id = create_temp_goal(client, test_user_id, 'Meta 50%', 1000.00, get_future_date_iso(30))

    with allure.step("Contribuir a ambas metas"):
        client.post('/api/v1/goals/contribute', data=json.dumps(dict(goal_id=goal1_id, amount=200.00)), content_type='application/json')
        client.post('/api/v1/goals/contribute', data=json.dumps(dict(goal_id=goal2_id, amount=500.00)), content_type='application/json')

    with allure.step("Obtener listado de metas del usuario"):
        response = client.get(f'/api/v1/goals/{test_user_id}')
        allure.attach(response.get_data(as_text=True), name="Listado de metas", attachment_type=allure.attachment_type.JSON)
        assert response.status_code == 200

    with allure.step("Validar orden y progreso"):
        goals = response.get_json()
        assert goals[0]['name'] == 'Meta 50%'
        assert goals[0]['progress_percent'] == 50.00
        assert goals[0]['is_completed'] is False

        assert goals[1]['name'] == 'Meta 100%'
        assert goals[1]['progress_percent'] == 100.00
        assert goals[1]['is_completed'] is True
