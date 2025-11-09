import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import json
from Main import create_app
from config import TestingConfig
from Modules.models import db, User, Transaction
from Modules.auth import AuthService

@pytest.fixture
def app():
    """Configura la app para pruebas con la DB en memoria."""
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        # Crear un usuario de prueba para las transacciones
        AuthService.register_user('user@finance.com', 'securepass')
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
        user = User.query.filter_by(email='user@finance.com').first()
        return user.id

def test_record_income_success(client, test_user_id):
    """Prueba el registro exitoso de un ingreso."""
    response = client.post(
        '/api/v1/transactions',
        data=json.dumps(dict(
            user_id=test_user_id,
            amount=500.00,
            type='Ingreso',
            description='Salario mensual'
        )),
        content_type='application/json'
    )
    # Crítico 2: Verificar transacción exitosa (código 201)
    assert response.status_code == 201
    with client.application.app_context():
        assert Transaction.query.count() == 1

def test_record_expense_success(client, test_user_id):
    """Prueba el registro exitoso de un gasto."""
    response = client.post(
        '/api/v1/transactions',
        data=json.dumps(dict(
            user_id=test_user_id,
            amount=50.50,
            type='Gasto',
            description='Compra en supermercado'
        )),
        content_type='application/json'
    )
    # Crítico 2: Verificar transacción exitosa (código 201)
    assert response.status_code == 201
    with client.application.app_context():
        assert Transaction.query.count() == 1

def test_transaction_validation_negative_amount(client, test_user_id):
    """Prueba la validación para montos negativos o cero."""
    response = client.post(
        '/api/v1/transactions',
        data=json.dumps(dict(
            user_id=test_user_id,
            amount=-100.00,
            type='Ingreso',
            description='Monto negativo'
        )),
        content_type='application/json'
    )
    # Crítico 2: Verificar fallo por validación (código 400)
    assert response.status_code == 400
    with client.application.app_context():
        assert Transaction.query.count() == 0 # No se debe guardar

def test_balance_calculation(client, test_user_id):
    """Prueba el cálculo correcto del balance consolidado."""
    # 1. Registrar transacciones de prueba
    transactions_to_add = [
        {'amount': 1000.00, 'type': 'Ingreso'},
        {'amount': 500.00, 'type': 'Ingreso'},
        {'amount': 200.00, 'type': 'Gasto'},
        {'amount': 150.00, 'type': 'Gasto'}
    ]
    
    for t in transactions_to_add:
        client.post(
            '/api/v1/transactions',
            data=json.dumps(dict(
                user_id=test_user_id,
                amount=t['amount'],
                type=t['type'],
                description='Test'
            )),
            content_type='application/json'
        )

    # 2. Obtener el balance
    response = client.get(f'/api/v1/balance/{test_user_id}')
    
    # Crítico 2: Verificar cálculo de balance
    assert response.status_code == 200
    balance_data = response.get_json()  # Corregido aquí
    
    # Ingresos Totales: 1000 + 500 = 1500.00
    # Gastos Totales: 200 + 150 = 350.00
    # Balance Consolidado: 1500 - 350 = 1150.00
    
    assert balance_data['total_income'] == 1500.00
    assert balance_data['total_expense'] == 350.00
    assert balance_data['consolidated_balance'] == 1150.00
