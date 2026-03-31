from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, Usuario, Movimentacao, FormaPagamento, Categoria, Subcategoria
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///financeiro.db'
app.config['SECRET_KEY'] = 'chave_mestre_financeira_2024'

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

@app.template_filter('formato_moeda')
def formato_moeda(valor):
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        novo_usuario = Usuario(
            nome_completo=request.form.get('nome'),
            telefone=request.form.get('telefone'),
            cpf=request.form.get('cpf'),
            senha=request.form.get('senha')
        )
        try:
            db.session.add(novo_usuario)
            db.session.commit()
            return redirect(url_for('login'))
        except:
            db.session.rollback()
            flash('Erro: CPF já cadastrado.', 'danger')
    return render_template('cadastro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = Usuario.query.filter_by(cpf=request.form.get('cpf')).first()
        if user and user.senha == request.form.get('senha'):
            login_user(user)
            
            if not FormaPagamento.query.filter_by(usuario_id=user.id).first():
                pagamentos_padrao = [
                    ('Pix', 'bi-phone'), 
                    ('Dinheiro Físico', 'bi-cash-stack'), 
                    ('Cartão de Crédito', 'bi-credit-card'), 
                    ('Cartão de Débito', 'bi-credit-card-2-front')
                ]
                for nome, icone in pagamentos_padrao:
                    db.session.add(FormaPagamento(nome=nome, icone=icone, usuario_id=user.id))
            
            if not Categoria.query.filter_by(usuario_id=user.id).first():
                cats_padrao = [
                    ('Moradia', 'bi-house-door'), ('Alimentação', 'bi-cart'),
                    ('Transporte', 'bi-car-front'), ('Lazer', 'bi-balloon'),
                    ('Saúde', 'bi-heart-pulse'), ('Salário', 'bi-cash-coin'),
                    ('Investimentos', 'bi-graph-up-arrow')
                ]
                for nome, icone in cats_padrao:
                    db.session.add(Categoria(nome=nome, icone=icone, usuario_id=user.id))
            
            db.session.commit()
            return redirect(url_for('dashboard'))
        flash('CPF ou Senha incorretos.', 'danger')
    return render_template('login.html')

# --- ROTA: DASHBOARD (COM FILTRO DE DATAS) ---
@app.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')

    query = Movimentacao.query.filter_by(usuario_id=current_user.id)
    
    # Aplicando os filtros se o usuário selecionou as datas
    if data_inicio:
        query = query.filter(Movimentacao.data >= datetime.strptime(data_inicio, '%Y-%m-%d').date())
    if data_fim:
        query = query.filter(Movimentacao.data <= datetime.strptime(data_fim, '%Y-%m-%d').date())

    movs = query.all()
    
    t_entrada = sum(m.valor for m in movs if m.tipo_movimentacao == 'Entrada')
    t_saida = sum(m.valor for m in movs if m.tipo_movimentacao == 'Saída')
    t_investimento = sum(m.valor for m in movs if m.tipo_movimentacao == 'Investimento')
    caixa = t_entrada - t_saida - t_investimento

    # Gráfico
    gastos_cat = {}
    for m in movs:
        if m.tipo_movimentacao == 'Saída':
            gastos_cat[m.categoria] = gastos_cat.get(m.categoria, 0) + m.valor

    return render_template('dashboard.html', t_entrada=t_entrada, t_saida=t_saida, 
                           t_investimento=t_investimento, caixa=caixa,
                           labels_cat=list(gastos_cat.keys()), 
                           valores_cat=list(gastos_cat.values()),
                           data_inicio=data_inicio, data_fim=data_fim)

# --- ROTA: LANÇAMENTOS ---
@app.route('/lancamentos', methods=['GET', 'POST'])
@login_required
def lancamentos():
    if request.method == 'POST':
        valor_raw = request.form.get('valor').replace('.', '').replace(',', '.')
        nova = Movimentacao(
            descricao=request.form.get('descricao'),
            valor=float(valor_raw),
            forma_pagto=request.form.get('forma_pagto'),
            categoria=request.form.get('categoria'),
            subcategoria=request.form.get('subcategoria', ''),
            tipo_movimentacao=request.form.get('tipo_movimentacao'),
            data=datetime.strptime(request.form.get('data'), '%Y-%m-%d').date(),
            usuario_id=current_user.id
        )
        db.session.add(nova)
        db.session.commit()
        return redirect(url_for('lancamentos'))

    movs = Movimentacao.query.filter_by(usuario_id=current_user.id).order_by(Movimentacao.data.desc()).all()
    formas = FormaPagamento.query.filter_by(usuario_id=current_user.id).all()
    categorias = Categoria.query.filter_by(usuario_id=current_user.id).all()
    subcategorias = Subcategoria.query.filter_by(usuario_id=current_user.id).all()
    
    # Reativando os cálculos para a tela de Lançamentos
    t_entrada = sum(m.valor for m in movs if m.tipo_movimentacao == 'Entrada')
    t_saida = sum(m.valor for m in movs if m.tipo_movimentacao == 'Saída')
    t_investimento = sum(m.valor for m in movs if m.tipo_movimentacao == 'Investimento')
    caixa = t_entrada - t_saida - t_investimento

    return render_template('lancamentos.html', movimentacoes=movs, formas=formas, 
                           categorias=categorias, subcategorias=subcategorias,
                           t_entrada=t_entrada, t_saida=t_saida, 
                           t_investimento=t_investimento, caixa=caixa)

@app.route('/config/formas', methods=['GET', 'POST'])
@login_required
def gerenciar_formas():
    if request.method == 'POST':
        nome = request.form.get('nome')
        icone = request.form.get('icone')
        db.session.add(FormaPagamento(nome=nome, icone=icone, usuario_id=current_user.id))
        db.session.commit()
        return redirect(url_for('gerenciar_formas'))
    formas = FormaPagamento.query.filter_by(usuario_id=current_user.id).all()
    return render_template('formas_pagamento.html', formas=formas)

@app.route('/excluir_forma/<int:id>')
@login_required
def excluir_forma(id):
    forma = FormaPagamento.query.get_or_404(id)
    if forma.usuario_id == current_user.id:
        db.session.delete(forma)
        db.session.commit()
    return redirect(url_for('gerenciar_formas'))

@app.route('/config/categorias', methods=['GET', 'POST'])
@login_required
def gerenciar_categorias():
    if request.method == 'POST':
        tipo = request.form.get('tipo_form')
        if tipo == 'categoria':
            db.session.add(Categoria(nome=request.form.get('nome'), icone=request.form.get('icone'), usuario_id=current_user.id))
        elif tipo == 'subcategoria':
            db.session.add(Subcategoria(nome=request.form.get('nome'), categoria_id=request.form.get('categoria_id'), usuario_id=current_user.id))
        db.session.commit()
        return redirect(url_for('gerenciar_categorias'))
    categorias = Categoria.query.filter_by(usuario_id=current_user.id).all()
    return render_template('categorias.html', categorias=categorias)

@app.route('/excluir_categoria/<int:id>')
@login_required
def excluir_categoria(id):
    cat = Categoria.query.get_or_404(id)
    if cat.usuario_id == current_user.id:
        Subcategoria.query.filter_by(categoria_id=cat.id).delete()
        db.session.delete(cat)
        db.session.commit()
    return redirect(url_for('gerenciar_categorias'))

@app.route('/excluir_mov/<int:id>')
@login_required
def excluir_mov(id):
    mov = Movimentacao.query.get_or_404(id)
    if mov.usuario_id == current_user.id:
        db.session.delete(mov)
        db.session.commit()
    return redirect(url_for('lancamentos'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)