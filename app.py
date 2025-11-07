import os
import psycopg2
import psycopg2.extras
import json
import io
import csv
from flask import Flask, request, jsonify, g, Response
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt
from datetime import datetime, timedelta
from flask_jwt_extended import JWTManager


# --- Configuración de la Aplicación ---

app = Flask(__name__)
CORS(app)



# Configuración de la base de datos (PostgreSQL)
# Asegúrate de tener esta variable de entorno. Ej:
# export DATABASE_URL="postgresql://user:password@localhost:5432/finora_db"
app.config['DATABASE_URL'] = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgre@localhost:5432/finora_db')

# Configuración de JWT (Tokens)
# CAMBIA ESTO por una clave secreta y segura en producción
app.config['JWT_SECRET_KEY'] = '8ca358b6d5dc69d6b68427dc6ffd09d720ff9c4127ca68f93a7a3eb90dcccf2f'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1) # Duración del token
app.config['JWT_HEADER_TYPE'] = 'Bearer' # Usar 'Bearer' en el header Authorization


# Inicializar extensiones
bcrypt = Bcrypt(app)
jwt = JWTManager(app)

# --- Base de Datos (PostgreSQL) ---

def get_db():
    """Conecta a la base de datos. Se reutiliza la conexión si ya existe en el contexto 'g'."""
    if 'db' not in g:
        try:
            g.db = psycopg2.connect(app.config['DATABASE_URL'])
        except psycopg2.OperationalError as e:
            # Esto es útil si la base de datos no está lista al iniciar
            print(f"Error conectando a la base de datos: {e}")
            return None
    return g.db

@app.teardown_appcontext
def close_connection(exception):
    """Cierra la conexión a la base de datos al finalizar la solicitud."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False, commit=False):
    """Función auxiliar para ejecutar consultas con 'RealDictCursor'."""
    db = get_db()
    if db is None:
        raise ConnectionError("No se pudo conectar a la base de datos.")
        
    # Usamos RealDictCursor para obtener resultados como diccionarios
    with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute(query, args)
        
        if commit:
            db.commit()
            return # No hay resultados que devolver en un commit puro (ej. INSERT, UPDATE)

        # Si no es commit, es una consulta SELECT
        if one:
            rv = cursor.fetchone()
        else:
            rv = cursor.fetchall()
        
        return rv

# --- 1. Autenticación y Autorización ---

@app.route('/register', methods=['POST'])
def register():
    """Registra un nuevo usuario."""
    try:
        data = request.json
        username = data['username']
        password = data['password']

        if not username or not password:
            return jsonify({"error": "Usuario y contraseña requeridos"}), 400

        # Hashear la contraseña
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        
        # 'user' es el rol por defecto
        query = "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)"
        
        query_db(query, (username, hashed_password, 'user'), commit=True)
        
        return jsonify({"message": f"Usuario {username} registrado exitosamente"}), 201

    except psycopg2.IntegrityError:
        return jsonify({"error": "El nombre de usuario ya existe"}), 409
    except Exception as e:
        return jsonify({"error": f"Error al procesar la solicitud: {str(e)}"}), 400

@app.route('/login', methods=['POST'])
def login():
    """Inicia sesión y devuelve un token JWT."""
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({"error": "Usuario y contraseña requeridos"}), 400

        user = query_db("SELECT * FROM users WHERE username = %s", (username,), one=True)

        if user and bcrypt.check_password_hash(user['password_hash'], password):
            # Contraseña correcta. Crear token.
            # Guardamos el 'rol' en las "claims" adicionales del token
            additional_claims = {"role": user['role']}
            access_token = create_access_token(
                identity=str(user['id']),
                additional_claims=additional_claims
            )
            return jsonify(access_token=access_token), 200
        else:
            # Usuario o contraseña incorrectos
            return jsonify({"error": "Credenciales inválidas"}), 401

    except Exception as e:
        return jsonify({"error": f"Error al procesar la solicitud: {str(e)}"}), 500

# --- 2. Registro de Transacciones y Cálculo de Balance (Núcleo) ---

@app.route('/transaction', methods=['POST'])
@jwt_required() # Proteger la ruta
def add_transaction():
    """Registra una nueva transacción (ingreso o gasto) para el usuario autenticado."""
    try:
        user_id = int(get_jwt_identity())# Obtener el ID del usuario desde el token
        data = request.json
        
        type_ = data['type']
        amount = float(data['amount'])
        category = data['category']
        description = data.get('description', '')

        if type_ not in ['income', 'expense']:
            return jsonify({"error": "El tipo debe ser 'income' o 'expense'"}), 400
        if amount <= 0:
            return jsonify({"error": "El monto debe ser positivo"}), 400

        query = """
        INSERT INTO transactions (user_id, type, amount, category, description, date)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        args = (user_id, type_, amount, category, description, datetime.now())
        
        query_db(query, args, commit=True)
        
        return jsonify({"message": "Transacción registrada exitosamente"}), 201

    except Exception as e:
        return jsonify({"error": f"Error al procesar la solicitud: {str(e)}"}), 400

@app.route('/transaction/<int:transaction_id>', methods=['PUT'])
@jwt_required()
def update_transaction(transaction_id):
    """Actualiza una transacción existente del usuario."""
    user_id = int(get_jwt_identity())
    try:
        data = request.json
        # Validar los datos de entrada (monto, tipo, etc.)
        amount = float(data['amount'])
        category = data['category']
        description = data.get('description', '')

        if amount <= 0:
            return jsonify({"error": "El monto debe ser positivo"}), 400

        query = """
        UPDATE transactions
        SET amount = %s, category = %s, description = %s
        WHERE id = %s AND user_id = %s
        RETURNING id; 
        """
        # (RETURNING id) nos permite saber si algo fue actualizado
        args = (amount, category, description, transaction_id, user_id)
        
        # Usamos query_db sin 'commit=True' para poder leer el 'RETURNING'
        result = query_db(query, args, one=True)
        get_db().commit() # Hacemos commit manualmente después de verificar

        if result:
            return jsonify({"message": "Transacción actualizada exitosamente"}), 200
        else:
            return jsonify({"error": "Transacción no encontrada o no pertenece al usuario"}), 404

    except Exception as e:
        get_db().rollback() # Revertir cambios si hay error
        return jsonify({"error": f"Error al procesar la solicitud: {str(e)}"}), 400


@app.route('/transaction/<int:transaction_id>', methods=['DELETE'])
@jwt_required()
def delete_transaction(transaction_id):
    """Elimina una transacción del usuario."""
    user_id = int(get_jwt_identity())
    try:
        # Usamos RETURNING id para saber si la fila existía y se borró
        query = "DELETE FROM transactions WHERE id = %s AND user_id = %s RETURNING id"
        args = (transaction_id, user_id)
        
        result = query_db(query, args, one=True)
        get_db().commit() # Commit manual

        if result:
            return jsonify({"message": "Transacción eliminada exitosamente"}), 200
        else:
            return jsonify({"error": "Transacción no encontrada o no pertenece al usuario"}), 404

    except Exception as e:
        get_db().rollback()
        return jsonify({"error": f"Error al procesar la solicitud: {str(e)}"}), 500

@app.route('/transactions', methods=['GET'])
@jwt_required()
def get_transactions():
    """Obtiene todas las transacciones del usuario, con filtros opcionales."""
    user_id = int(get_jwt_identity())
    
    # Filtros por fecha (ej. /transactions?start_date=2023-01-01&end_date=2023-01-31)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    base_query = "SELECT * FROM transactions WHERE user_id = %s"
    args = [user_id]
    
    if start_date:
        base_query += " AND date >= %s"
        args.append(start_date)
    if end_date:
        base_query += " AND date <= %s"
        args.append(end_date)
        
    base_query += " ORDER BY date DESC"
    
    try:
        transactions = query_db(base_query, tuple(args))
        return jsonify(transactions), 200
    except Exception as e:
        return jsonify({"error": f"Error al obtener transacciones: {str(e)}"}), 500

@app.route('/balance', methods=['GET'])
@jwt_required()
def get_balance():
    """Calcula el balance consolidado del usuario."""
    user_id = int(get_jwt_identity())
    try:
        query_income = "SELECT SUM(amount) as total FROM transactions WHERE type = 'income' AND user_id = %s"
        income_result = query_db(query_income, (user_id,), one=True)
        total_income = (income_result['total'] if income_result['total'] is not None else 0)

        query_expense = "SELECT SUM(amount) as total FROM transactions WHERE type = 'expense' AND user_id = %s"
        expense_result = query_db(query_expense, (user_id,), one=True)
        total_expense = (expense_result['total'] if expense_result['total'] is not None else 0)

        balance = total_income - total_expense

        return jsonify({
            "total_income": total_income,
            "total_expense": total_expense,
            "balance": balance
        }), 200

    except Exception as e:
        return jsonify({"error": f"Error al calcular el balance: {str(e)}"}), 500

# --- 3. Exportación / Integración y Reportes ---

@app.route('/export/csv', methods=['GET'])
@jwt_required()
def export_csv():
    """Exporta todas las transacciones del usuario como un archivo CSV."""
    user_id = int(get_jwt_identity())
    
    try:
        # 1. Obtener los datos
        transactions = query_db("SELECT * FROM transactions WHERE user_id = %s ORDER BY date DESC", (user_id,))
        
        if not transactions:
            return jsonify({"message": "No hay transacciones para exportar"}), 404

        # 2. Generar el CSV en memoria
        si = io.StringIO()
        # Definir los encabezados (columnas)
        fieldnames = ['id', 'type', 'amount', 'category', 'description', 'date', 'user_id']
        writer = csv.DictWriter(si, fieldnames=fieldnames, extrasaction='ignore')

        writer.writeheader()
        for trans in transactions:
            # Convertir 'datetime' a string si es necesario (psycopg2 suele devolverlo)
            trans['date'] = str(trans['date']) 
            writer.writerow(trans)
        
        output = si.getvalue()
        si.close()

        # 3. Devolver el CSV como un archivo
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-disposition":
                     f"attachment; filename=finora_export_{datetime.now().date()}.csv"}
        )

    except Exception as e:
        return jsonify({"error": f"Error al exportar CSV: {str(e)}"}), 500

# Endpoint de ejemplo para Roles (Premium)
@app.route('/premium_report', methods=['GET'])
@jwt_required()
def premium_report():
    """Un endpoint de ejemplo que solo usuarios 'premium' pueden acceder."""
    
    # Obtenemos las "claims" (incluyendo el rol) del token
    claims = get_jwt()
    role = claims.get('role', 'user') # Por defecto es 'user' si no existe

    if role != 'premium':
        return jsonify({"error": "Acceso denegado. Se requiere suscripción Premium."}), 403
    
    # Lógica del reporte premium (ej. análisis predictivo)
    return jsonify({
        "message": "Bienvenido a tu reporte premium de Finora!",
        "analysis": "Predicción: A este paso, cumplirás tu meta de ahorro en 3 meses."
    }), 200


# --- Ejecución ---

def init_db_command():
    """
Aviso: Esta función es para inicializar la BD desde la línea de comandos.
Ejecuta: 'flask --app app init-db'
"""
    db = get_db()
    if db is None:
        print("Error: No se pudo conectar a la base de datos. Verifica tu DATABASE_URL.")
        return
        
    with db.cursor() as cursor:
        with open('schema.sql', 'r', encoding='utf-8') as f:
            cursor.execute(f.read())
    db.commit()
    print("Base de datos inicializada con 'schema.sql'.")

# Registrar el comando 'init-db' con Flask
@app.cli.command('init-db')
def init_db_cli():
    init_db_command()

if __name__ == '__main__':
    # Nota: Para correr en producción, usa un servidor WSGI como Gunicorn.
    # gunicorn -w 4 app:app
    # Para desarrollo:
    # 1. export FLASK_APP=app
    # 2. export FLASK_DEBUG=1
    # 3. flask run --port 5001
    app.run(debug=True, port=5001)