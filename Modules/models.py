from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

# Inicializa SQLAlchemy. Se inicializará con la app en Main.py
db = SQLAlchemy()

class User(db.Model):
    """Modelo de Usuario para la autenticación."""
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_premium = db.Column(db.Boolean, default=False)
    
    # Relación con Transacciones y Metas
    transactions = db.relationship('Transaction', backref='owner', lazy=True)
    custom_categories = db.relationship('Category', backref='creator', lazy=True, foreign_keys='Category.user_id')
    goals = db.relationship('Goal', backref='user_goal', lazy=True) # Nueva relación

class Category(db.Model):
    """Modelo de Categoría para organizar ingresos y gastos."""
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    type = db.Column(db.String(10), nullable=False) # 'Ingreso' o 'Gasto'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) # Puede ser categoría global (NULL) o de usuario
    
class Transaction(db.Model):
    """Modelo para registrar Ingresos o Gastos."""
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False) # Monto de la transacción
    type = db.Column(db.String(10), nullable=False) # 'Ingreso' o 'Gasto'
    description = db.Column(db.String(255), nullable=True)
    date = db.Column(db.DateTime, default=datetime.now(timezone.utc), nullable=False)
    
    # Relación con Categoría
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    category = db.relationship('Category', backref='transactions', lazy=True)
    
# --- NUEVO MODELO: Goal ---
class Goal(db.Model):
    """Modelo para metas financieras (ahorro o inversión)."""
    __tablename__ = 'goals'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    target_amount = db.Column(db.Numeric(10, 2), nullable=False) # Monto total a alcanzar
    current_amount = db.Column(db.Numeric(10, 2), default=0.00, nullable=False) # Monto actual ahorrado
    due_date = db.Column(db.DateTime, nullable=True) # Fecha límite para la meta
    is_completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))