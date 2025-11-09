from Modules.models import User, db
from werkzeug.security import generate_password_hash, check_password_hash

class AuthService:
    """Servicio para manejar la lógica de autenticación y autorización."""

    @staticmethod
    def register_user(email, password):
        """
        Registra un nuevo usuario en la base de datos.
        Retorna el objeto User si es exitoso, False si el email ya existe.
        """
        # 1. Validación: Verificar si el usuario ya existe
        if User.query.filter_by(email=email).first():
            print(f"ERROR: El usuario con email {email} ya existe.")
            return False

        # 2. Hashing de Contraseña (Seguridad Crítica)
        password_hash = generate_password_hash(password)
        
        # 3. Creación del usuario
        new_user = User(
            email=email,
            password_hash=password_hash
        )
        
        # 4. Guardar en DB
        try:
            db.session.add(new_user)
            db.session.commit()
            return new_user
        except Exception as e:
            db.session.rollback()
            print(f"ERROR al guardar usuario en DB: {e}")
            return False

    @staticmethod
    def login_user(email, password):
        """
        Verifica las credenciales del usuario.
        Retorna el objeto User si las credenciales son correctas, None en caso contrario.
        """
        user = User.query.filter_by(email=email).first()
        
        # 1. Validación de usuario y contraseña
        if user and check_password_hash(user.password_hash, password):
            # En un sistema real, aquí se generaría un token JWT o se crearía una sesión
            return user
        
        return None

    @staticmethod
    def is_premium(user_id):
        """Verifica el estado Premium de un usuario (para autorización)."""
        user = User.query.get(user_id)
        if user:
            return user.is_premium
        return False