from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuario' # Forçando o nome da tabela
    id = db.Column(db.Integer, primary_key=True)
    nome_completo = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(20), nullable=False)
    cpf = db.Column(db.String(14), unique=True, nullable=False)
    senha = db.Column(db.String(100), nullable=False)
    
    # Relacionamentos
    movimentacoes = db.relationship('Movimentacao', backref='dono', lazy=True)
    formas_pagamento = db.relationship('FormaPagamento', backref='dono_forma', lazy=True)

class Movimentacao(db.Model):
    __tablename__ = 'movimentacao' # Forçando o nome da tabela
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(200), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data = db.Column(db.Date, nullable=False)
    tipo_gasto = db.Column(db.String(50))
    forma_pagto = db.Column(db.String(50))
    tipo_movimentacao = db.Column(db.String(10), nullable=False) 
    
    # Chave estrangeira ligada ao nome exato da tabela
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

class FormaPagamento(db.Model):
    __tablename__ = 'forma_pagamento' # Forçando o nome da tabela
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False)
    
    # Chave estrangeira ligada ao nome exato da tabela
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)