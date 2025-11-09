import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import json
import allure
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
        # Añadir transacciones de prueba
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


# ------------------------
# PRUEBAS CON ALLURE
# ------------------------

@allure.feature("Reportes Financieros")
@allure.story("Estructura de datos del reporte")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("Verifica que la estructura del reporte contenga los campos esperados antes de la exportación final (CSV/PDF).")
def test_report_generation_structure(client, test_user_id):
    with allure.step("Solicitar los datos del reporte para el usuario"):
        response = client.get(f'/api/v1/reports/export/{test_user_id}')
        assert response.status_code == 200
        report_response = response.get_json()
        allure.attach(json.dumps(report_response, indent=2), name="Respuesta JSON", attachment_type=allure.attachment_type.JSON)

    with allure.step("Verificar mensaje de éxito en la respuesta"):
        assert "Datos de reporte listos para exportación." in report_response['message']

    with allure.step("Validar estructura de los datos del reporte"):
        report_data = report_response['data']
        assert 'summary' in report_data
        assert 'recent_transactions' in report_data
        assert isinstance(report_data['recent_transactions'], list)

    with allure.step("Verificar que los totales del summary sean correctos"):
        summary = report_data['summary']
        assert summary['total_income'] == 2000.00
        assert summary['total_expense'] == 500.00
        assert summary['consolidated_balance'] == 1500.00


@allure.feature("Reportes Financieros")
@allure.story("Formato de transacciones en el reporte")
@allure.severity(allure.severity_level.NORMAL)
@allure.description("Verifica que las transacciones recientes tengan el formato correcto para su exportación.")
def test_report_transaction_data_format(client, test_user_id):
    with allure.step("Solicitar los datos del reporte para el usuario"):
        response = client.get(f'/api/v1/reports/export/{test_user_id}')
        assert response.status_code == 200
        report_response = response.get_json()
        report_data = report_response['data']
        allure.attach(json.dumps(report_data, indent=2), name="Datos del reporte", attachment_type=allure.attachment_type.JSON)

    with allure.step("Extraer transacciones y validar cantidad mínima"):
        transactions = report_data['recent_transactions']
        assert len(transactions) >= 2

    with allure.step("Validar formato de campos en la primera transacción"):
        first_transaction = transactions[0]
        assert 'date' in first_transaction
        assert 'type' in first_transaction
        assert 'amount' in first_transaction
        assert 'description' in first_transaction

    with allure.step("Verificar tipos de datos y valores esperados"):
        assert isinstance(first_transaction['amount'], float)
        assert first_transaction['amount'] in [2000.0, 500.0]
        assert first_transaction['type'] in ['Ingreso', 'Gasto']
