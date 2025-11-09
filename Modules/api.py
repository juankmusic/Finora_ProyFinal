from flask import Blueprint, request, jsonify
from Modules.auth import AuthService
from Modules.services import FinanceService
from datetime import datetime

# Crea un Blueprint para organizar las rutas de la API
api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

# --- Rutas de Autenticación (Sin Cambios) ---

@api_bp.route('/register', methods=['POST'])
def register():
    """Ruta para el registro de nuevos usuarios."""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"message": "Faltan email o contraseña."}), 400

    user = AuthService.register_user(email, password)
    
    if user:
        return jsonify({"message": "Registro exitoso.", "user_id": user.id}), 201
    else:
        return jsonify({"message": "El email ya está registrado."}), 409

@api_bp.route('/login', methods=['POST'])
def login():
    """Ruta para el inicio de sesión."""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = AuthService.login_user(email, password)
    
    if user:
        # En un MVP, solo retornamos éxito, pero en un sistema real retornaría un token
        return jsonify({"message": "Login exitoso.", "user_id": user.id}), 200
    else:
        return jsonify({"message": "Credenciales inválidas."}), 401

# --- Rutas de Transacciones y Finanzas (Sin Cambios Relevantes) ---

@api_bp.route('/transactions', methods=['POST'])
def add_transaction():
    """Ruta para agregar una nueva transacción."""
    data = request.get_json()
    user_id = data.get('user_id') 
    amount = data.get('amount')
    type = data.get('type')
    description = data.get('description')
    category_id = data.get('category_id') # Nuevo campo para enlazar la categoría

    if not all([user_id, amount, type]):
        return jsonify({"message": "Datos de transacción incompletos."}), 400

    transaction = FinanceService.record_transaction(user_id, amount, type, description, category_id)
    
    if transaction:
        return jsonify({"message": "Transacción registrada con éxito.", "transaction_id": transaction.id}), 201
    else:
        return jsonify({"message": "Error al registrar la transacción. Verifique el monto."}), 400

@api_bp.route('/balance/<int:user_id>', methods=['GET'])
def get_balance(user_id):
    """Ruta para obtener el balance financiero consolidado."""
    balance = FinanceService.calculate_balance(user_id)
    return jsonify(balance), 200

@api_bp.route('/reports/export/<int:user_id>', methods=['GET'])
def export_report(user_id):
    """Ruta para generar y exportar un reporte (simulado a JSON)."""
    report_data = FinanceService.generate_report_data(user_id)
    
    return jsonify({
        "message": "Datos de reporte listos para exportación.",
        "data": report_data
    }), 200

# --- Rutas de Categorías (Nuevo) ---

@api_bp.route('/categories/<int:user_id>', methods=['GET'])
def list_categories(user_id):
    """
    Ruta para obtener todas las categorías disponibles para el usuario 
    (globales + personalizadas).
    Acepta un parámetro de consulta 'type' (Ingreso/Gasto) para filtrar.
    Ejemplo: /api/v1/categories/1?type=Gasto
    """
    category_type = request.args.get('type')
    categories = FinanceService.get_categories(user_id, category_type)
    
    return jsonify(categories), 200

@api_bp.route('/categories/add', methods=['POST'])
def add_custom_category():
    """Ruta para que un usuario cree una categoría personalizada."""
    data = request.get_json()
    user_id = data.get('user_id') 
    name = data.get('name')
    category_type = data.get('type')

    if not all([user_id, name, category_type]):
        return jsonify({"message": "Faltan datos (user_id, name, type)."}), 400

    result, status_code = FinanceService.create_custom_category(user_id, name, category_type)
    
    if status_code == 201:
        return jsonify({
            "message": "Categoría personalizada creada.",
            "id": result.id,
            "name": result.name
        }), 201
    else:
        return jsonify({"message": result}), status_code
    
# --- Rutas de Metas Financieras (Corregidas) ---

@api_bp.route('/goals/<int:user_id>', methods=['GET'])
def list_goals(user_id):
    """Ruta para obtener todas las metas de un usuario."""
    goals = FinanceService.get_user_goals(user_id)
    return jsonify(goals), 200

@api_bp.route('/goals/create', methods=['POST'])
def create_goal():
    """Ruta para crear una nueva meta financiera."""
    data = request.get_json()
    
    user_id = data.get('user_id') 
    name = data.get('name')
    target_amount = data.get('target_amount')
    # due_date es una cadena (str) ISO 8601
    due_date_str = data.get('due_date') 

    # Validación de datos obligatorios
    if user_id is None or name is None or target_amount is None:
        return jsonify({"message": "Faltan datos obligatorios (user_id, name, target_amount)."}), 400
    
    # Validación de target_amount (debe ser mayor que 0)
    try:
        # Se convierte a float/decimal aquí para la VALIDACIÓN inicial en el controlador
        target_amount = float(target_amount)
        if target_amount <= 0:
            return jsonify({"message": "El monto objetivo debe ser positivo."}), 400
    except (ValueError, TypeError):
        return jsonify({"message": "Formato de monto inválido."}), 400

    # ----------------------------------------------------
    # SE ELIMINÓ LA CONVERSIÓN DE FECHA DE AQUÍ.
    # Ahora pasamos el due_date_str original al servicio.
    # ----------------------------------------------------

    # Llamada al servicio para crear la meta financiera
    # Se pasa la cadena (due_date_str) sin convertir
    goal, status_code = FinanceService.create_goal(user_id, name, target_amount, due_date_str)

    if status_code == 201:
        return jsonify({
            "message": "Meta creada con éxito.",
            "id": goal.id,
            "name": goal.name
        }), 201
    else:
        # El servicio devuelve el mensaje de error y el código de estado (400 o 500)
        return jsonify({"message": goal}), status_code

@api_bp.route('/goals/contribute', methods=['POST'])
def contribute_to_goal_route():
    """Ruta para añadir una contribución a una meta específica."""
    data = request.get_json()
    goal_id = data.get('goal_id') 
    amount = data.get('amount')

    if goal_id is None or amount is None:
        return jsonify({"message": "Faltan datos (goal_id, amount)."}), 400

    goal, status_code = FinanceService.contribute_to_goal(goal_id, amount)
    
    if status_code == 200:
        return jsonify({
            "message": "Contribución registrada.",
            "goal_id": goal.id,
            "new_current_amount": float(goal.current_amount),
            "is_completed": goal.is_completed
        }), 200
    else:
        return jsonify({"message": goal}), status_code