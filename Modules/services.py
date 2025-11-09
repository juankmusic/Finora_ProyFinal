from Modules.models import db, Transaction, Category, Goal
from datetime import datetime, date, timedelta
import pytz
from sqlalchemy import or_
from decimal import Decimal

class FinanceService:
    """Servicio para manejar la lógica de negocio de las finanzas personales."""

    # ... (Otras funciones se mantienen sin cambios)

    @staticmethod
    def record_transaction(user_id, amount, type, description, category_id=None, date=None):
        """Registra una nueva transacción (Ingreso o Gasto)."""
        # ... (Función record_transaction)
        try:
            if amount <= 0:
                print("ERROR: El monto debe ser un valor positivo.")
                return False

            if type not in ['Ingreso', 'Gasto']:
                print("ERROR: Tipo de transacción inválido.")
                return False

            new_transaction = Transaction(
                user_id=user_id,
                amount=amount,
                type=type,
                description=description,
                category_id=category_id,
                date=date if date else datetime.now(pytz.utc)
            )

            db.session.add(new_transaction)
            db.session.commit()
            return new_transaction
        except Exception as e:
            db.session.rollback()
            print(f"ERROR al registrar transacción: {e}")
            return False

    @staticmethod
    def calculate_balance(user_id, start_date=None, end_date=None):
        """Calcula el balance consolidado del usuario en un período dado."""
        # ... (Función calculate_balance)
        query = Transaction.query.filter_by(user_id=user_id)
        
        if start_date:
            query = query.filter(Transaction.date >= start_date)
        if end_date:
            query = query.filter(Transaction.date <= end_date)

        transactions = query.all()

        # Usar float() para la suma, aunque los montos estén en Decimal
        total_income = sum(float(t.amount) for t in transactions if t.type == 'Ingreso')
        total_expense = sum(float(t.amount) for t in transactions if t.type == 'Gasto')
        
        consolidated_balance = total_income - total_expense
        
        return {
            'total_income': round(total_income, 2),
            'total_expense': round(total_expense, 2),
            'consolidated_balance': round(consolidated_balance, 2)
        }

    @staticmethod
    def generate_report_data(user_id, period='monthly'):
        """Genera los datos para un reporte financiero (simulación)."""
        # ... (Función generate_report_data)
        balance = FinanceService.calculate_balance(user_id)
        transactions = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.date.desc()).limit(10).all()

        report_data = {
            'period': period,
            'user_id': user_id,
            'summary': balance,
            'recent_transactions': [{
                'date': t.date.isoformat(),
                'type': t.type,
                'amount': float(t.amount),
                'description': t.description,
                'category_name': t.category.name if t.category else 'Sin Categoría'
            } for t in transactions]
        }
        return report_data

    @staticmethod
    def get_categories(user_id, category_type=None):
        """Obtiene categorías globales y personalizadas del usuario."""
        # ... (Función get_categories)
        query = Category.query.filter(or_(Category.user_id == None, Category.user_id == user_id))
        
        if category_type and category_type in ['Ingreso', 'Gasto']:
            query = query.filter_by(type=category_type)
            
        categories = query.all()
        
        return [{
            'id': c.id,
            'name': c.name,
            'type': c.type,
            'is_custom': c.user_id is not None
        } for c in categories]

    @staticmethod
    def create_custom_category(user_id, name, type):
        """Permite a un usuario crear su propia categoría (personalizada)."""
        # ... (Función create_custom_category)
        if type not in ['Ingreso', 'Gasto']:
            return "Tipo inválido", 400

        existing = Category.query.filter_by(user_id=user_id, name=name).first()
        if existing:
            return "Categoría ya existe", 409

        try:
            new_category = Category(
                name=name,
                type=type,
                user_id=user_id 
            )
            db.session.add(new_category)
            db.session.commit()
            return new_category, 201
        except Exception as e:
            db.session.rollback()
            print(f"ERROR al crear categoría personalizada: {e}")
            return "Error de servidor", 500

    # --- Lógica de Metas Financieras (Corregida) ---

    @staticmethod
    def create_goal(user_id, name, target_amount, due_date_str=None):
        """Crea una nueva meta de ahorro/inversión."""
        try:
            target = Decimal(str(target_amount))
            if target <= 0:
                return "El monto objetivo debe ser positivo.", 400

            due_date = None
            if due_date_str:
                # ¡CORRECCIÓN CLAVE AQUÍ!
                # Aseguramos que el argumento es una cadena, ya que si es None fallará en fromisoformat.
                if not isinstance(due_date_str, str):
                    # Si el controlador pasa algo que no es str, retornamos 400 explícitamente.
                    return "Formato de fecha de vencimiento inválido.", 400

                # 1. Parsear la cadena (viene con formato ISO 8601 con o sin tz)
                due_date = datetime.fromisoformat(due_date_str) 

                # 2. Asegurarse de que la fecha sea aware (si es naive, asumimos UTC)
                if due_date.tzinfo is None or due_date.tzinfo.utcoffset(due_date) is None:
                    due_date = pytz.utc.localize(due_date)

                # 3. Comparación: la fecha límite debe ser estrictamente posterior a la hora actual (aware)
                if due_date <= datetime.now(pytz.utc):
                    return "La fecha límite debe ser posterior al día de hoy.", 400

            new_goal = Goal(
                user_id=user_id,
                name=name,
                target_amount=target,
                current_amount=Decimal('0.00'), # Inicia en cero
                due_date=due_date
            )
            
            db.session.add(new_goal)
            db.session.commit()
            return new_goal, 201
        except ValueError:
            db.session.rollback()
            # Esto captura errores de formato si due_date_str no es ISO 8601 válido o si target_amount no es convertible a Decimal
            return "Formato de monto o fecha inválido.", 400
        except Exception as e:
            db.session.rollback()
            print(f"ERROR al crear meta: {e}") 
            return "Error de servidor.", 500

    @staticmethod
    def get_user_goals(user_id):
        """Obtiene todas las metas del usuario con el progreso calculado."""
        # ... (Función get_user_goals)
        goals = Goal.query.filter_by(user_id=user_id).order_by(Goal.due_date.asc()).all()
        
        result = []
        for goal in goals:
            target = float(goal.target_amount)
            current = float(goal.current_amount)
            
            progress = (current / target) * 100 if target > 0 else 0
            
            result.append({
                'id': goal.id,
                'name': goal.name,
                'target_amount': target,
                'current_amount': current,
                'progress_percent': round(progress, 2),
                'due_date': goal.due_date.isoformat() if goal.due_date else None, # Usar isoformat para consistencia
                'is_completed': goal.is_completed
            })
        return result

    @staticmethod
    def contribute_to_goal(goal_id, amount):
        """Añade una contribución a una meta existente."""
        
        # CORRECCIÓN DE WARNING: Usar db.session.get() en lugar de Goal.query.get()
        goal = db.session.get(Goal, goal_id) 
        
        if not goal:
            return "Meta no encontrada.", 404

        try:
            contribution = Decimal(str(amount))
            if contribution <= 0:
                return "La contribución debe ser positiva.", 400
            
            goal.current_amount += contribution
            
            # Verificar si la meta se completó
            if goal.current_amount >= goal.target_amount:
                goal.current_amount = goal.target_amount # Asegurar que no se exceda visualmente
                goal.is_completed = True
            
            db.session.commit()
            return goal, 200
        except Exception as e:
            db.session.rollback()
            print(f"ERROR al contribuir a meta: {e}")
            return "Error al actualizar la meta.", 500