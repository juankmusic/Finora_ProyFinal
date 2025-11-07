/* Este es el esquema SQL para PostgreSQL.

Crea tu base de datos en PostgreSQL (ej. 'CREATE DATABASE finora_db;')

Configura tu DATABASE_URL

Corre 'flask --app app init-db' para crear estas tablas.
*/

-- Borra las tablas si existen para una inicialización limpia
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS users;

-- Tabla de Usuarios (para Autenticación y Roles)
CREATE TABLE users (
id SERIAL PRIMARY KEY,
username VARCHAR(80) UNIQUE NOT NULL,
password_hash TEXT NOT NULL,
role VARCHAR(20) NOT NULL DEFAULT 'user', -- 'user' o 'premium'
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de Transacciones (Vinculada al usuario)
CREATE TABLE transactions (
id SERIAL PRIMARY KEY,
user_id INTEGER NOT NULL,
type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
amount REAL NOT NULL CHECK(amount > 0),
category TEXT NOT NULL,
description TEXT,
date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

-- Clave foránea que enlaza con la tabla 'users'
CONSTRAINT fk_user
    FOREIGN KEY(user_id) 
    REFERENCES users(id)
    ON DELETE CASCADE -- Si se borra un usuario, se borran sus transacciones


);

-- Índices para mejorar la velocidad de las consultas comunes
CREATE INDEX idx_transactions_user_id ON transactions(user_id);
CREATE INDEX idx_transactions_date ON transactions(date);