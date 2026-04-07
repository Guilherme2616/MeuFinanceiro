from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuario'
    id = db.Column(db.Integer, primary_key=True)
    nome_completo = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(20), nullable=False)
    cpf = db.Column(db.String(14), unique=True, nullable=False)
    senha = db.Column(db.String(255), nullable=False)
    
    movimentacoes = db.relationship('Movimentacao', backref='dono', lazy=True)
    formas_pagamento = db.relationship('FormaPagamento', backref='dono_forma', lazy=True)
    categorias = db.relationship('Categoria', backref='dono_categoria', lazy=True)
    subcategorias = db.relationship('Subcategoria', backref='dono_sub', lazy=True)
    orcamentos = db.relationship('Orcamento', backref='dono_orc', lazy=True)
    investimentos = db.relationship('Investimento', backref='dono_inv', lazy=True)

class Investimento(db.Model):
    __tablename__ = 'investimento'
    id = db.Column(db.Integer, primary_key=True)
    operacao = db.Column(db.String(20), nullable=False) 
    categoria = db.Column(db.String(50), nullable=False) 
    subcategoria = db.Column(db.String(50), nullable=False) 
    ativo = db.Column(db.String(50), nullable=False)    
    quantidade = db.Column(db.Float, nullable=False)
    valor = db.Column(db.Float, nullable=False)         
    data = db.Column(db.Date, nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

class Orcamento(db.Model):
    __tablename__ = 'orcamento'
    id = db.Column(db.Integer, primary_key=True)
    categoria = db.Column(db.String(50), nullable=False)
    valor_limite = db.Column(db.Float, nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

class Categoria(db.Model):
    __tablename__ = 'categoria'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False)
    icone = db.Column(db.String(255), nullable=False)
    cor = db.Column(db.String(20), nullable=False, default='#5F7254')
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    subcategorias = db.relationship('Subcategoria', backref='categoria_pai', lazy=True)

class Subcategoria(db.Model):
    __tablename__ = 'subcategoria'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

# O Motor de Inteligência precisa saber se é crédito e quais as datas
class FormaPagamento(db.Model):
    __tablename__ = 'forma_pagamento'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False)
    icone = db.Column(db.String(255), nullable=False) 
    cor = db.Column(db.String(20), nullable=False, default='#6c757d')
    is_credito = db.Column(db.Boolean, default=False)
    dia_fechamento = db.Column(db.Integer, nullable=True)
    dia_vencimento = db.Column(db.Integer, nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

# Separamos a Data da Compra da Data de Cobrança (Caixa)
class Movimentacao(db.Model):
    __tablename__ = 'movimentacao'
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(200), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data = db.Column(db.Date, nullable=False) # Data da Compra
    data_cobranca = db.Column(db.Date, nullable=False) # Quando afeta o bolso
    tipo_gasto = db.Column(db.String(50))
    forma_pagto = db.Column(db.String(50))
    categoria = db.Column(db.String(50))
    subcategoria = db.Column(db.String(50))
    tipo_movimentacao = db.Column(db.String(20), nullable=False) 
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)