from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Usuario, Movimentacao, FormaPagamento, Categoria, Subcategoria, Orcamento
from datetime import datetime, date
import calendar

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

def adicionar_meses(data_original, meses_a_adicionar):
    mes = data_original.month - 1 + meses_a_adicionar
    ano = data_original.year + mes // 12
    mes = mes % 12 + 1
    dia = min(data_original.day, calendar.monthrange(ano, mes)[1])
    return date(ano, mes, dia)

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        senha_criptografada = generate_password_hash(request.form.get('senha'), method='pbkdf2:sha256')
        novo_usuario = Usuario(
            nome_completo=request.form.get('nome'),
            telefone=request.form.get('telefone'),
            cpf=request.form.get('cpf'),
            senha=senha_criptografada
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
        if user and check_password_hash(user.senha, request.form.get('senha')):
            login_user(user)
            
            if not FormaPagamento.query.filter_by(usuario_id=user.id).first():
                for nome, icone, cor in [('Pix', 'bi-phone', '#20c997'), ('Dinheiro', 'bi-cash-stack', '#198754'), ('Cartão de Crédito', 'bi-credit-card', '#ffc107')]:
                    db.session.add(FormaPagamento(nome=nome, icone=icone, cor=cor, usuario_id=user.id))
            
            if not Categoria.query.filter_by(usuario_id=user.id).first():
                cats = [('Moradia', 'bi-house-door', '#5F7254'), ('Alimentação', 'bi-cart', '#783E19'), ('Transporte', 'bi-car-front', '#8E8D8A'), ('Salário', 'bi-cash-coin', '#198754'), ('Investimentos', 'bi-graph-up-arrow', '#0dcaf0')]
                for nome, icone, cor in cats:
                    db.session.add(Categoria(nome=nome, icone=icone, cor=cor, usuario_id=user.id))
            
            db.session.commit()
            return redirect(url_for('dashboard'))
        flash('CPF ou Senha incorretos.', 'danger')
    return render_template('login.html')

@app.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    hoje = datetime.today()
    data_inicio = request.args.get('data_inicio', hoje.replace(day=1).strftime('%Y-%m-%d'))
    data_fim = request.args.get('data_fim', hoje.replace(day=calendar.monthrange(hoje.year, hoje.month)[1]).strftime('%Y-%m-%d'))

    data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
    todas_movs = Movimentacao.query.filter_by(usuario_id=current_user.id).all()
    orcamentos = Orcamento.query.filter_by(usuario_id=current_user.id).all()
    
    t_entrada_caixa = sum(m.valor for m in todas_movs if m.tipo_movimentacao == 'Entrada' and m.data <= data_fim_obj)
    t_saida_caixa = sum(m.valor for m in todas_movs if m.tipo_movimentacao == 'Saída' and m.data <= data_fim_obj)
    caixa_atual = t_entrada_caixa - t_saida_caixa

    t_investimento_geral = sum(m.valor for m in todas_movs if m.tipo_movimentacao == 'Investimento')
    t_saida_futura = sum(m.valor for m in todas_movs if m.tipo_movimentacao == 'Saída' and m.data > data_fim_obj)

    movs_periodo = [m for m in todas_movs if datetime.strptime(data_inicio, '%Y-%m-%d').date() <= m.data <= data_fim_obj]
    
    t_entrada_periodo = sum(m.valor for m in movs_periodo if m.tipo_movimentacao == 'Entrada')
    t_saida_periodo = sum(m.valor for m in movs_periodo if m.tipo_movimentacao == 'Saída')

    categorias_db = Categoria.query.filter_by(usuario_id=current_user.id).all()
    mapa_cores = {c.nome: c.cor for c in categorias_db}

    gastos_cat = {}
    for m in movs_periodo:
        if m.tipo_movimentacao == 'Saída':
            gastos_cat[m.categoria] = gastos_cat.get(m.categoria, 0) + m.valor

    cores_grafico = [mapa_cores.get(cat, '#5F7254') for cat in gastos_cat.keys()]

    # --- LÓGICA DO GRÁFICO MENSAL (LINHAS E BARRAS) ---
    dt_atual = datetime.strptime(data_inicio, '%Y-%m-%d').date().replace(day=1)
    dt_fim_mes = data_fim_obj.replace(day=1)

    meses_dict = {}
    while dt_atual <= dt_fim_mes:
        mes_ano = dt_atual.strftime('%m/%Y')
        meses_dict[mes_ano] = {'Entrada': 0, 'Saída': 0, 'Investimento': 0}
        ano = dt_atual.year + (dt_atual.month // 12)
        mes = (dt_atual.month % 12) + 1
        dt_atual = date(ano, mes, 1)

    for m in movs_periodo:
        mes_ano = m.data.strftime('%m/%Y')
        if mes_ano in meses_dict:
            if m.tipo_movimentacao in meses_dict[mes_ano]:
                meses_dict[mes_ano][m.tipo_movimentacao] += m.valor

    total_orcamento_mensal = sum(o.valor_limite for o in orcamentos)

    labels_meses = []
    dados_entradas_mes = []
    dados_saidas_mes = []
    dados_investimentos_mes = []
    dados_orcamento_mes = []

    for mes_ano, valores in meses_dict.items():
        labels_meses.append(mes_ano)
        dados_entradas_mes.append(valores['Entrada'])
        dados_saidas_mes.append(valores['Saída'])
        dados_investimentos_mes.append(valores['Investimento'])
        dados_orcamento_mes.append(total_orcamento_mensal)

    return render_template('dashboard.html', 
                           t_entrada=t_entrada_periodo, t_saida=t_saida_periodo, t_saida_futura=t_saida_futura,
                           t_investimento=t_investimento_geral, caixa=caixa_atual,
                           labels_cat=list(gastos_cat.keys()), valores_cat=list(gastos_cat.values()), cores_cat=cores_grafico,
                           gastos_cat=gastos_cat, orcamentos=orcamentos,
                           labels_meses=labels_meses, dados_entradas_mes=dados_entradas_mes, 
                           dados_saidas_mes=dados_saidas_mes, dados_investimentos_mes=dados_investimentos_mes, 
                           dados_orcamento_mes=dados_orcamento_mes,
                           data_inicio=data_inicio, data_fim=data_fim)

@app.route('/lancamentos', methods=['GET', 'POST'])
@login_required
def lancamentos():
    if request.method == 'POST':
        valor_raw = request.form.get('valor').replace('.', '').replace(',', '.')
        parcelas = int(request.form.get('parcelas', 1))
        valor_parcela = float(valor_raw) / parcelas
        data_base = datetime.strptime(request.form.get('data'), '%Y-%m-%d').date()

        for i in range(parcelas):
            data_lanc = adicionar_meses(data_base, i)
            desc = f"{request.form.get('descricao')} ({i+1}/{parcelas})" if parcelas > 1 else request.form.get('descricao')
            nova = Movimentacao(
                descricao=desc, valor=valor_parcela,
                forma_pagto=request.form.get('forma_pagto'), categoria=request.form.get('categoria'),
                subcategoria=request.form.get('subcategoria', ''), tipo_movimentacao=request.form.get('tipo_movimentacao'),
                data=data_lanc, usuario_id=current_user.id
            )
            db.session.add(nova)
        db.session.commit()
        return redirect(request.referrer or url_for('lancamentos'))

    hoje = datetime.today()
    data_inicio_str = request.args.get('data_inicio', hoje.replace(day=1).strftime('%Y-%m-%d'))
    data_fim_str = request.args.get('data_fim', hoje.replace(day=calendar.monthrange(hoje.year, hoje.month)[1]).strftime('%Y-%m-%d'))

    data_inicio_obj = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
    data_fim_obj = datetime.strptime(data_fim_str, '%Y-%m-%d').date()

    todas = Movimentacao.query.filter_by(usuario_id=current_user.id).all()
    
    t_entrada_caixa = sum(m.valor for m in todas if m.tipo_movimentacao == 'Entrada' and m.data <= data_fim_obj)
    t_saida_caixa = sum(m.valor for m in todas if m.tipo_movimentacao == 'Saída' and m.data <= data_fim_obj)
    caixa_atual = t_entrada_caixa - t_saida_caixa
    
    invest_geral = sum(m.valor for m in todas if m.tipo_movimentacao == 'Investimento')
    t_saida_futura = sum(m.valor for m in todas if m.tipo_movimentacao == 'Saída' and m.data > data_fim_obj)

    movs = Movimentacao.query.filter_by(usuario_id=current_user.id).filter(
        Movimentacao.data >= data_inicio_obj, Movimentacao.data <= data_fim_obj
    ).order_by(Movimentacao.data.desc()).all()

    t_ent_per = sum(m.valor for m in movs if m.tipo_movimentacao == 'Entrada')
    t_sai_per = sum(m.valor for m in movs if m.tipo_movimentacao == 'Saída')

    formas = FormaPagamento.query.filter_by(usuario_id=current_user.id).all()
    categorias = Categoria.query.filter_by(usuario_id=current_user.id).all()
    subcategorias = Subcategoria.query.filter_by(usuario_id=current_user.id).all()

    return render_template('lancamentos.html', movimentacoes=movs, 
                           t_entrada=t_ent_per, t_saida=t_sai_per, t_saida_futura=t_saida_futura,
                           t_investimento=invest_geral, caixa=caixa_atual,
                           data_inicio=data_inicio_str, data_fim=data_fim_str,
                           formas=formas, categorias=categorias, subcategorias=subcategorias)

@app.route('/editar_mov/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_mov(id):
    mov = Movimentacao.query.get_or_404(id)
    if mov.usuario_id != current_user.id:
        return redirect(url_for('lancamentos'))
    
    if request.method == 'POST':
        mov.valor = float(request.form.get('valor').replace('.', '').replace(',', '.'))
        mov.descricao = request.form.get('descricao')
        mov.forma_pagto = request.form.get('forma_pagto')
        mov.categoria = request.form.get('categoria')
        mov.subcategoria = request.form.get('subcategoria', '')
        mov.tipo_movimentacao = request.form.get('tipo_movimentacao')
        mov.data = datetime.strptime(request.form.get('data'), '%Y-%m-%d').date()
        db.session.commit()
        return redirect(url_for('lancamentos'))

    return render_template('editar_lancamento.html', mov=mov, 
                           formas=FormaPagamento.query.filter_by(usuario_id=current_user.id).all(), 
                           categorias=Categoria.query.filter_by(usuario_id=current_user.id).all(), 
                           subcategorias=Subcategoria.query.filter_by(usuario_id=current_user.id).all())

@app.route('/orcamentos', methods=['GET', 'POST'])
@login_required
def orcamentos():
    if request.method == 'POST':
        categoria = request.form.get('categoria')
        valor_raw = request.form.get('valor_limite').replace('.', '').replace(',', '.')
        orc = Orcamento.query.filter_by(usuario_id=current_user.id, categoria=categoria).first()
        if orc:
            orc.valor_limite = float(valor_raw)
        else:
            db.session.add(Orcamento(categoria=categoria, valor_limite=float(valor_raw), usuario_id=current_user.id))
        db.session.commit()
        return redirect(url_for('orcamentos'))
    return render_template('orcamentos.html', orcamentos=Orcamento.query.filter_by(usuario_id=current_user.id).all(), categorias=Categoria.query.filter_by(usuario_id=current_user.id).all())

@app.route('/excluir_orcamento/<int:id>')
@login_required
def excluir_orcamento(id):
    orc = Orcamento.query.get_or_404(id)
    if orc.usuario_id == current_user.id:
        db.session.delete(orc)
        db.session.commit()
    return redirect(url_for('orcamentos'))

@app.route('/config/formas', methods=['GET', 'POST'])
@login_required
def gerenciar_formas():
    if request.method == 'POST':
        db.session.add(FormaPagamento(nome=request.form.get('nome'), icone=request.form.get('icone'), cor=request.form.get('cor'), usuario_id=current_user.id))
        db.session.commit()
        return redirect(url_for('gerenciar_formas'))
    return render_template('formas_pagamento.html', formas=FormaPagamento.query.filter_by(usuario_id=current_user.id).all())

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
            db.session.add(Categoria(nome=request.form.get('nome'), icone=request.form.get('icone'), cor=request.form.get('cor'), usuario_id=current_user.id))
        elif tipo == 'subcategoria':
            db.session.add(Subcategoria(nome=request.form.get('nome'), categoria_id=request.form.get('categoria_id'), usuario_id=current_user.id))
        db.session.commit()
        return redirect(url_for('gerenciar_categorias'))
    return render_template('categorias.html', categorias=Categoria.query.filter_by(usuario_id=current_user.id).all())

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
    return redirect(request.referrer or url_for('lancamentos'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)