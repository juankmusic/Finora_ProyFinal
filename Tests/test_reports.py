import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import json
from Main import create_app
from config import TestingConfig
from Modules.models import db, User
from Modules.auth import AuthService
from Modules.services import FinanceService



@pytest.fixture
def app():
    """Configura la app para pruebas con la DB en memoria."""
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        # Crear usuario de prueba
        AuthService.register_user('report_user@finance.com', 'securepass')
        user = User.query.filter_by(email='report_user@finance.com').first()
        # Añadir transacciones de prueba para el reporte
        FinanceService.record_transaction(user.id, 2000.00, 'Ingreso', 'Sueldo')
        FinanceService.record_transaction(user.id, 500.00, 'Gasto', 'Arriendo')
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
        user = User.query.filter_by(email='report_user@finance.com').first()
        return user.id

def test_report_generation_structure(client, test_user_id):
    """
    Prueba que la función de reporte retorne la estructura de datos esperada
    antes de la exportación final (CSV/PDF).
    """
    response = client.get(f'/api/v1/reports/export/{test_user_id}')
    
    # Crítico 3: Verificar respuesta exitosa (código 200)
    assert response.status_code == 200
    report_response = response.get_json()  # Corregido aquí
    
    # Verificar el mensaje de éxito
    assert "Datos de reporte listos para exportación." in report_response['message']
    
    report_data = report_response['data']
    
    # Crítico 3: Verificar la estructura mínima del reporte
    assert 'summary' in report_data
    assert 'recent_transactions' in report_data
    assert isinstance(report_data['recent_transactions'], list)
    
    # Verificar que los datos del summary sean correctos (Ingreso: 2000, Gasto: 500, Balance: 1500)
    assert report_data['summary']['total_income'] == 2000.00
    assert report_data['summary']['total_expense'] == 500.00
    assert report_data['summary']['consolidated_balance'] == 1500.00

def test_report_transaction_data_format(client, test_user_id):
    """
    Prueba que los datos de las transacciones recientes tengan el formato correcto
    para ser exportados.
    """
    response = client.get(f'/api/v1/reports/export/{test_user_id}')
    report_response = response.get_json()  # Corregido aquí
    report_data = report_response['data']
    
    transactions = report_data['recent_transactions']
    
    # Asume que hay 2 transacciones (creadas en el fixture)
    assert len(transactions) >= 2
    
    # Crítico 3: Verificar el formato de los campos de la transacción
    first_transaction = transactions[0]
    assert 'date' in first_transaction
    assert 'type' in first_transaction
    assert 'amount' in first_transaction
    assert 'description' in first_transaction
    
    # Verificar que el tipo de dato sea el esperado (float para amount)
    assert isinstance(first_transaction['amount'], float)
    assert first_transaction['amount'] in [2000.0, 500.0] # Valores esperados
    assert first_transaction['type'] in ['Ingreso', 'Gasto']
