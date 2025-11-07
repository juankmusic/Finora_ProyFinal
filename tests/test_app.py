import pytest
import os
import json
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
from app import app, init_db_command, get_db

# --- Configuración del Entorno de Pruebas ---

@pytest.fixture(scope='module')
def client():
    """
    Fixture de Pytest (scope de módulo) para configurar la app para pruebas.
    Usa una base de datos de PRUEBA de PostgreSQL.
    """
    
    # --- IMPORTANTE ---
    # Define la URL de la base de datos de PRUEBA
    # Esta base de datos DEBE existir y ser accesible.
    # Generalmente se llama 'finora_test_db' o similar.
    TEST_DATABASE_URL = "postgresql://postgres:postgre@localhost:5432/finora_test_db"

    app.config['TESTING'] = True
    app.config['DATABASE_URL'] = TEST_DATABASE_URL
    
    # Usar una clave JWT fija para pruebas
    with app.app_context():
        # Limpia e inicializa la BD de prueba
        try:
            init_db_command()
        except ConnectionError as e:
            print(f"\n--- ERROR DE PRUEBA: No se pudo conectar a la BD de prueba: {TEST_DATABASE_URL} ---")
            print("--- Asegúrate de que PostgreSQL esté corriendo y la BD 'finora_test_db' exista ---")
            pytest.skip("No se pudo conectar a la base de datos de prueba.")
            return

    with app.test_client() as client:
        yield client # El cliente de prueba se usa aquí

    # Limpieza (Opcional, pero init_db_command ya limpia)
    with app.app_context():
        db = get_db()
        with db.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS transactions; DROP TABLE IF EXISTS users;")
        db.commit()
        db.close()


# --- Funciones Auxiliares de Prueba ---

def register_and_login(client, username, password):
    """Auxiliar para registrar y loguear un usuario, devuelve el token."""
    client.post('/register', json={"username": username, "password": password})
    rv = client.post('/login', json={"username": username, "password": password})
    assert rv.status_code == 200
    json_data = rv.get_json()
    return json_data['access_token']

def auth_headers(token):
    """Auxiliar para crear los headers de autorización."""
    return {'Authorization': f'Bearer {token}'}


# --- 1. Pruebas de Autenticación y Autorización ---

def test_auth_flow(client):
    """Prueba el flujo completo de registro y login."""
    # Registro
    rv_reg = client.post('/register', json={"username": "testuser", "password": "password123"})
    assert rv_reg.status_code == 201
    assert "Usuario testuser registrado" in rv_reg.get_json()['message']

    # Registro duplicado (debe fallar)
    rv_reg_fail = client.post('/register', json={"username": "testuser", "password": "password123"})
    assert rv_reg_fail.status_code == 409 # Conflict
    assert "ya existe" in rv_reg_fail.get_json()['error']

    # Login exitoso
    rv_login = client.post('/login', json={"username": "testuser", "password": "password123"})
    assert rv_login.status_code == 200
    assert 'access_token' in rv_login.get_json()

    # Login fallido (contraseña incorrecta)
    rv_login_fail = client.post('/login', json={"username": "testuser", "password": "wrongpassword"})
    assert rv_login_fail.status_code == 401
    assert "Credenciales inválidas" in rv_login_fail.get_json()['error']

def test_premium_endpoint_security(client):
    """Prueba que un usuario 'user' no puede acceder a rutas 'premium'."""
    token = register_and_login(client, "normaluser", "pass")
    
    rv = client.get('/premium_report', headers=auth_headers(token))
    
    assert rv.status_code == 403 # Forbidden
    assert "Acceso denegado" in rv.get_json()['error']

# --- 2. Pruebas de Transacciones y Balance (Núcleo) ---

def test_transaction_flow_with_auth(client):
    """Prueba el flujo CRUD completo de transacciones con autenticación."""
    # Usuario 1
    token1 = register_and_login(client, "user_flow_1", "pass1")
    headers1 = auth_headers(token1)

    # Usuario 2 (para probar aislamiento)
    token2 = register_and_login(client, "user_flow_2", "pass2")
    headers2 = auth_headers(token2)

    # 1. POST (Crear)
    rv_post = client.post('/transaction', json={
        "type": "income", "amount": 1000, "category": "Salario"
    }, headers=headers1)
    assert rv_post.status_code == 201

    # POST (Gasto)
    client.post('/transaction', json={
        "type": "expense", "amount": 50, "category": "Café"
    }, headers=headers1)

    # 2. GET (Leer)
    rv_get = client.get('/transactions', headers=headers1)
    assert rv_get.status_code == 200
    transactions = rv_get.get_json()
    assert len(transactions) == 2
    assert transactions[0]['category'] == 'Café'
    assert transactions[1]['amount'] == 1000
    
    transaction_id_to_edit = transactions[0]['id'] # El ID del café

    # Usuario 2 no debe ver transacciones de Usuario 1
    rv_get_user2 = client.get('/transactions', headers=headers2)
    assert rv_get_user2.status_code == 200
    assert len(rv_get_user2.get_json()) == 0

    # 3. PUT (Actualizar)
    rv_put = client.put(f'/transaction/{transaction_id_to_edit}', json={
        "amount": 75, "category": "Comida", "description": "Café y croissant"
    }, headers=headers1)
    assert rv_put.status_code == 200
    
    # Verificar actualización
    rv_get_updated = client.get('/transactions', headers=headers1)
    updated_transactions = rv_get_updated.get_json()
    assert updated_transactions[0]['amount'] == 75
    assert updated_transactions[0]['description'] == "Café y croissant"

    # Usuario 2 no puede actualizar transacción de Usuario 1
    rv_put_fail = client.put(f'/transaction/{transaction_id_to_edit}', json={
        "amount": 999, "category": "Hack",
    }, headers=headers2)
    assert rv_put_fail.status_code == 404 # No encontrada (para ese usuario)

    # 4. DELETE (Borrar)
    rv_del = client.delete(f'/transaction/{transaction_id_to_edit}', headers=headers1)
    assert rv_del.status_code == 200

    # Verificar borrado
    rv_get_deleted = client.get('/transactions', headers=headers1)
    transactions_after_del = rv_get_deleted.get_json()
    assert len(transactions_after_del) == 1 # Solo queda el Salario
    assert transactions_after_del[0]['category'] == 'Salario'

def test_balance_with_auth(client):
    """Prueba el cálculo del balance por usuario."""
    token = register_and_login(client, "user_balance", "pass")
    headers = auth_headers(token)

    client.post('/transaction', json={"type": "income", "amount": 2000, "category": "Salario"}, headers=headers)
    client.post('/transaction', json={"type": "income", "amount": 500, "category": "Freelance"}, headers=headers)
    client.post('/transaction', json={"type": "expense", "amount": 300, "category": "Comida"}, headers=headers)
    
    rv = client.get('/balance', headers=headers)
    assert rv.status_code == 200
    balance_data = rv.get_json()
    
    assert balance_data['total_income'] == 2500
    assert balance_data['total_expense'] == 300
    assert balance_data['balance'] == 2200

# --- 3. Pruebas de Exportación / Reportes ---

def test_export_csv(client):
    """Prueba que la exportación a CSV funcione y contenga los datos correctos."""
    token = register_and_login(client, "user_export", "pass")
    headers = auth_headers(token)

    # Añadir datos para exportar
    client.post('/transaction', json={"type": "income", "amount": 5000, "category": "ExportTest"}, headers=headers)
    client.post('/transaction', json={"type": "expense", "amount": 123, "category": "CSV"}, headers=headers)
    
    rv = client.get('/export/csv', headers=headers)
    
    assert rv.status_code == 200
    assert rv.mimetype == 'text/csv'
    assert 'attachment; filename=' in rv.headers['Content-disposition']
    
    # Verificar el contenido
    content = rv.data.decode('utf-8')
    assert 'id,type,amount,category,description,date,user_id' in content
    assert '5000' in content
    assert 'ExportTest' in content
    assert '123' in content
    assert 'CSV' in content