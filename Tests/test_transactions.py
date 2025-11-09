import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import json
import allure
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
        # Crear un usuario de prueba
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


# --------------------------
# PRUEBAS CON ALLURE
# --------------------------

@allure.feature("Transacciones")
@allure.story("Registro de ingresos")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("Verifica que el usuario pueda registrar exitosamente una transacción de tipo 'Ingreso'.")
def test_record_income_success(client, test_user_id):
    with allure.step("Enviar solicitud POST para registrar un ingreso"):
        payload = dict(user_id=test_user_id, amount=500.00, type='Ingreso', description='Salario mensual')
        response = client.post('/api/v1/transactions', data=json.dumps(payload), content_type='application/json')
        allure.attach(json.dumps(payload, indent=2), name="Payload de ingreso", attachment_type=allure.attachment_type.JSON)
        assert response.status_code == 201

    with allure.step("Verificar que la transacción fue registrada en la base de datos"):
        with client.application.app_context():
            count = Transaction.query.count()
            allure.attach(str(count), name="Cantidad de transacciones", attachment_type=allure.attachment_type.TEXT)
            assert count == 1


@allure.feature("Transacciones")
@allure.story("Registro de gastos")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("Verifica que el usuario pueda registrar exitosamente una transacción de tipo 'Gasto'.")
def test_record_expense_success(client, test_user_id):
    with allure.step("Enviar solicitud POST para registrar un gasto"):
        payload = dict(user_id=test_user_id, amount=50.50, type='Gasto', description='Compra en supermercado')
        response = client.post('/api/v1/transactions', data=json.dumps(payload), content_type='application/json')
        allure.attach(json.dumps(payload, indent=2), name="Payload de gasto", attachment_type=allure.attachment_type.JSON)
        assert response.status_code == 201

    with allure.step("Verificar que la transacción fue registrada correctamente"):
        with client.application.app_context():
            count = Transaction.query.count()
            assert count == 1


@allure.feature("Transacciones")
@allure.story("Validación de montos")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("Verifica que el sistema rechace transacciones con montos negativos o cero.")
def test_transaction_validation_negative_amount(client, test_user_id):
    with allure.step("Enviar solicitud con monto negativo"):
        payload = dict(user_id=test_user_id, amount=-100.00, type='Ingreso', description='Monto negativo')
        response = client.post('/api/v1/transactions', data=json.dumps(payload), content_type='application/json')
        allure.attach(json.dumps(payload, indent=2), name="Payload inválido", attachment_type=allure.attachment_type.JSON)
        assert response.status_code == 400

    with allure.step("Verificar que no se haya registrado ninguna transacción en la base de datos"):
        with client.application.app_context():
            count = Transaction.query.count()
            allure.attach(str(count), name="Cantidad de transacciones", attachment_type=allure.attachment_type.TEXT)
            assert count == 0


@allure.feature("Transacciones")
@allure.story("Cálculo de balance consolidado")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("Verifica que el cálculo del balance consolidado sea correcto al combinar ingresos y gastos.")
def test_balance_calculation(client, test_user_id):
    with allure.step("Registrar múltiples transacciones de prueba"):
        transactions_to_add = [
            {'amount': 1000.00, 'type': 'Ingreso'},
            {'amount': 500.00, 'type': 'Ingreso'},
            {'amount': 200.00, 'type': 'Gasto'},
            {'amount': 150.00, 'type': 'Gasto'}
        ]
        for t in transactions_to_add:
            payload = dict(user_id=test_user_id, amount=t['amount'], type=t['type'], description='Test')
            client.post('/api/v1/transactions', data=json.dumps(payload), content_type='application/json')
        allure.attach(json.dumps(transactions_to_add, indent=2), name="Transacciones registradas", attachment_type=allure.attachment_type.JSON)

    with allure.step("Obtener el balance consolidado del usuario"):
        response = client.get(f'/api/v1/balance/{test_user_id}')
        allure.attach(response.get_data(as_text=True), name="Respuesta de balance", attachment_type=allure.attachment_type.JSON)
        assert response.status_code == 200
        balance_data = response.get_json()

    with allure.step("Verificar los valores del balance"):
        assert balance_data['total_income'] == 1500.00
        assert balance_data['total_expense'] == 350.00
        assert balance_data['consolidated_balance'] == 1150.00
