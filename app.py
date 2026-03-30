from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, Usuario, Movimentacao, FormaPagamento
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

# Filtro para formatar moeda brasileira
@app.template_filter('formato_moeda')
def formato_moeda(valor):
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

with app.app_context():
    db.create_all()

# --- ROTA INICIAL ---
@app.route('/')
def index():
    return redirect(url_for('login'))

# --- ROTA DE CADASTRO ---
@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form.get('nome')
        telefone = request.form.get('telefone')
        cpf = request.form.get('cpf')
        senha = request.form.get('senha')
        
        novo_usuario = Usuario(nome_completo=nome, telefone=telefone, cpf=cpf, senha=senha)
        
        try:
            db.session.add(novo_usuario)
            db.session.commit()
            flash('Conta criada com sucesso!', 'success')
            return redirect(url_for('login'))
        except:
            db.session.rollback()
            flash('Erro: Este CPF já está cadastrado.', 'danger')
            
    return render_template('cadastro.html')

# --- ROTA DE LOGIN ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = Usuario.query.filter_by(cpf=request.form.get('cpf')).first()
        if user and user.senha == request.form.get('senha'):
            login_user(user)
            
            # Criar formas padrão se o usuário não tiver nenhuma
            if not FormaPagamento.query.filter_by(usuario_id=user.id).first():
                padroes = ['Pix', 'Dinheiro Físico', 'Cartão 1', 'Cartão 2']
                for p in padroes:
                    db.session.add(FormaPagamento(nome=p, usuario_id=user.id))
                db.session.commit()
                
            return redirect(url_for('dashboard'))
        flash('CPF ou Senha incorretos.', 'danger')
    return render_template('login.html')

# --- DASHBOARD ---
@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if request.method == 'POST':
        valor_raw = request.form.get('valor').replace('.', '').replace(',', '.')
        nova = Movimentacao(
            descricao=request.form.get('descricao'),
            valor=float(valor_raw),
            forma_pagto=request.form.get('forma_pagto'),
            tipo_movimentacao=request.form.get('tipo_movimentacao'),
            data=datetime.strptime(request.form.get('data'), '%Y-%m-%d').date(),
            usuario_id=current_user.id
        )
        db.session.add(nova)
        db.session.commit()
        return redirect(url_for('dashboard'))

    movs = Movimentacao.query.filter_by(usuario_id=current_user.id).order_by(Movimentacao.data.desc()).all()
    formas = FormaPagamento.query.filter_by(usuario_id=current_user.id).all()
    
    t_entrada = sum(m.valor for m in movs if m.tipo_movimentacao == 'Entrada')
    t_saida = sum(m.valor for m in movs if m.tipo_movimentacao == 'Saída')
    
    return render_template('dashboard.html', movimentacoes=movs, t_entrada=t_entrada, 
                           t_saida=t_saida, caixa=t_entrada - t_saida, formas=formas)

# --- GERENCIAR FORMAS DE PAGTO ---
@app.route('/config/formas', methods=['GET', 'POST'])
@login_required
def gerenciar_formas():
    if request.method == 'POST':
        nome = request.form.get('nome')
        db.session.add(FormaPagamento(nome=nome, usuario_id=current_user.id))
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

@app.route('/excluir_mov/<int:id>')
@login_required
def excluir_mov(id):
    mov = Movimentacao.query.get_or_404(id)
    if mov.usuario_id == current_user.id:
        db.session.delete(mov)
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)