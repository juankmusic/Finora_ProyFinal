import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import json
from Main import create_app
from config import TestingConfig
from Modules.models import db, User, Goal
from Modules.auth import AuthService
from datetime import datetime, timedelta
import pytz # Necesario para manejar fechas aware

@pytest.fixture
def app():
    """Configura la app para pruebas con la DB en memoria."""
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        # Crear usuario de prueba
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
        # Si el usuario no existe (fallo en setup), retornar un ID falso para forzar el fallo de la prueba.
        return user.id if user else 999 

def get_future_date_iso(days=30):
    """Genera una fecha futura consciente de zona horaria (UTC) en formato ISO 8601 string."""
    return (datetime.now(pytz.utc) + timedelta(days=days)).isoformat()

def create_temp_goal(client, user_id, name, target, due_date):
    """
    Función de ayuda para crear una meta y retornar su ID.
    due_date DEBE ser un string en formato ISO 8601 (producido por get_future_date_iso).
    """
    # NO es necesario convertir aquí, ya que la fecha se generará como string ISO 8601 en las llamadas a esta función.
    
    response = client.post(
        '/api/v1/goals/create',
        data=json.dumps(dict(user_id=user_id, name=name, target_amount=target, due_date=due_date)),
        content_type='application/json'
    )

    if response.status_code != 201:
        # Esto permite que la prueba que llama a esta función falle limpiamente
        # Si ves este error, el servicio está devolviendo 500 o 400.
        raise Exception(f"Fallo en create_temp_goal con status {response.status_code}: {response.get_json()}")
    
    # Si todo es correcto, devuelve el ID de la meta
    return response.get_json()['id']



def test_create_goal_success(client, test_user_id):
    """Prueba la creación exitosa de una meta con fecha futura."""
    # Se usa la función auxiliar para generar la fecha consistente
    future_date = get_future_date_iso(30) 
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
    assert response.status_code == 201
    data = response.get_json()
    assert 'Meta creada con éxito.' in data['message']

    with client.application.app_context():
        goal = db.session.get(Goal, data['id'])
        assert float(goal.target_amount) == 5000.00
        assert float(goal.current_amount) == 0.00



def test_create_goal_invalid_target(client, test_user_id):
    """Prueba que la creación falle con un monto objetivo no positivo."""
    # Usamos la función auxiliar para una fecha válida
    future_date = get_future_date_iso(30)
    
    response = client.post(
        '/api/v1/goals/create',
        data=json.dumps(dict(
            user_id=test_user_id, 
            name='Meta Inválida', 
            target_amount=0, # Monto inválido
            due_date=future_date
        )),
        content_type='application/json'
    )
    
    # El test debe esperar que el servicio falle con el mensaje de negocio
    assert response.status_code == 400
    assert 'El monto objetivo debe ser positivo.' in response.get_json()['message']


def test_contribute_to_goal(client, test_user_id):
    """Prueba la contribución exitosa a una meta."""
    # Usamos la función auxiliar para una fecha válida
    future_date = get_future_date_iso(30)
    # create_temp_goal ahora es robusto
    goal_id = create_temp_goal(client, test_user_id, 'Ahorro Inicial', 1000.00, future_date)

    response = client.post(
        '/api/v1/goals/contribute',
        data=json.dumps(dict(goal_id=goal_id, amount=250.00)),
        content_type='application/json'
    )

    assert response.status_code == 200
    data = response.get_json()
    assert 'Contribución registrada.' in data['message']
    assert data['new_current_amount'] == 250.00
    assert data['is_completed'] is False

    # Verificar en la base de datos
    with client.application.app_context():
        goal = db.session.get(Goal, goal_id)
        assert float(goal.current_amount) == 250.00


def test_goal_completion(client, test_user_id):
    """Prueba que la meta se marque como completada al alcanzar el monto objetivo."""
    # Usamos la función auxiliar para una fecha válida
    future_date = get_future_date_iso(30)
    goal_id = create_temp_goal(client, test_user_id, 'Ahorro Corto', 500.00, future_date)

    # 1. Contribución parcial
    client.post(
        '/api/v1/goals/contribute',
        data=json.dumps(dict(goal_id=goal_id, amount=400.00)),
        content_type='application/json'
    )

    # 2. Contribución final que completa la meta
    response = client.post(
        '/api/v1/goals/contribute',
        data=json.dumps(dict(goal_id=goal_id, amount=100.00)),
        content_type='application/json'
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data['new_current_amount'] == 500.00
    assert data['is_completed'] is True


def test_get_user_goals_with_progress(client, test_user_id):
    """Prueba que el listado de metas incluya el cálculo de progreso correcto."""
    # Usamos la función auxiliar para fechas válidas
    future_date_1 = get_future_date_iso(60)
    future_date_2 = get_future_date_iso(30)

    goal1_id = create_temp_goal(client, test_user_id, 'Meta 100%', 200.00, future_date_1)
    goal2_id = create_temp_goal(client, test_user_id, 'Meta 50%', 1000.00, future_date_2)

    # Contribuir a Meta 1 (100%)
    client.post(
        '/api/v1/goals/contribute',
        data=json.dumps(dict(goal_id=goal1_id, amount=200.00)),
        content_type='application/json'
    )

    # Contribuir a Meta 2 (50%)
    client.post(
        '/api/v1/goals/contribute',
        data=json.dumps(dict(goal_id=goal2_id, amount=500.00)),
        content_type='application/json'
    )

    response = client.get(f'/api/v1/goals/{test_user_id}')
    assert response.status_code == 200
    goals = response.get_json()
    
    # El orden debe ser por fecha de vencimiento (Meta 50% primero)
    assert goals[0]['name'] == 'Meta 50%'
    assert goals[0]['progress_percent'] == 50.00
    assert goals[0]['is_completed'] is False
    
    assert goals[1]['name'] == 'Meta 100%'
    assert goals[1]['progress_percent'] == 100.00
    assert goals[1]['is_completed'] is True