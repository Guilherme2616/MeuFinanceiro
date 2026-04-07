from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Usuario, Movimentacao, FormaPagamento, Categoria, Subcategoria, Orcamento, Investimento
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

# Motor de Projeção Real de Cartões Brasileiros
def calcular_data_cobranca(data_compra, dia_fechamento, dia_vencimento):
    mes = data_compra.month
    ano = data_compra.year
    
    # Se passou do fechamento, vira o ciclo para o próximo mês
    if data_compra.day >= dia_fechamento:
        mes += 1
        if mes > 12:
            mes = 1
            ano += 1
            
    # Define se o vencimento é no mesmo mês do ciclo ou no mês seguinte
    mes_vencimento = mes
    ano_vencimento = ano
    if dia_vencimento < dia_fechamento:
        mes_vencimento += 1
        if mes_vencimento > 12:
            mes_vencimento = 1
            ano_vencimento += 1
            
    ultimo_dia = calendar.monthrange(ano_vencimento, mes_vencimento)[1]
    dia_real = min(dia_vencimento, ultimo_dia)
    return date(ano_vencimento, mes_vencimento, dia_real)

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        senha_criptografada = generate_password_hash(request.form.get('senha'), method='pbkdf2:sha256')
        novo_usuario = Usuario(nome_completo=request.form.get('nome'), telefone=request.form.get('telefone'), cpf=request.form.get('cpf'), senha=senha_criptografada)
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
                db.session.add(FormaPagamento(nome='Pix', icone='bi-phone', cor='#20c997', is_credito=False, usuario_id=user.id))
                db.session.add(FormaPagamento(nome='Dinheiro', icone='bi-cash-stack', cor='#198754', is_credito=False, usuario_id=user.id))
                db.session.add(FormaPagamento(nome='Cartão de Crédito', icone='bi-credit-card', cor='#ffc107', is_credito=True, dia_fechamento=5, dia_vencimento=12, usuario_id=user.id))
            
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
    
    # SALDO GERAL: Usa a Data de Cobrança (Caixa Real)
    t_entrada_caixa = sum(m.valor for m in todas_movs if m.tipo_movimentacao == 'Entrada' and m.data_cobranca <= data_fim_obj)
    t_saida_caixa = sum(m.valor for m in todas_movs if m.tipo_movimentacao == 'Saída' and m.data_cobranca <= data_fim_obj)
    caixa_atual = t_entrada_caixa - t_saida_caixa

    t_investimento_geral = sum(m.valor for m in todas_movs if m.tipo_movimentacao == 'Investimento')
    t_saida_futura = sum(m.valor for m in todas_movs if m.tipo_movimentacao == 'Saída' and m.data_cobranca > data_fim_obj)

    patrimonio_total = caixa_atual + t_investimento_geral

    # GRÁFICOS: Mostram as Categorias (Opção B), mas baseadas no mês que vão afetar a conta (Data de Cobrança)
    movs_periodo = [m for m in todas_movs if datetime.strptime(data_inicio, '%Y-%m-%d').date() <= m.data_cobranca <= data_fim_obj]
    
    t_entrada_periodo = sum(m.valor for m in movs_periodo if m.tipo_movimentacao == 'Entrada')
    t_saida_periodo = sum(m.valor for m in movs_periodo if m.tipo_movimentacao == 'Saída')

    categorias_db = Categoria.query.filter_by(usuario_id=current_user.id).all()
    mapa_cores_cat = {c.nome: c.cor for c in categorias_db}
    
    pagamentos_db = FormaPagamento.query.filter_by(usuario_id=current_user.id).all()
    mapa_cores_pagto = {p.nome: p.cor for p in pagamentos_db}

    gastos_cat_sub = {}
    gastos_pagto = {}
    
    for m in movs_periodo:
        if m.tipo_movimentacao == 'Saída':
            nome_cat = f"{m.categoria} - {m.subcategoria}" if m.subcategoria else m.categoria
            gastos_cat_sub[nome_cat] = gastos_cat_sub.get(nome_cat, 0) + m.valor
            gastos_pagto[m.forma_pagto] = gastos_pagto.get(m.forma_pagto, 0) + m.valor

    cores_grafico_cat = [mapa_cores_cat.get(cat.split(' - ')[0], '#5F7254') for cat in gastos_cat_sub.keys()]
    cores_grafico_pagto = [mapa_cores_pagto.get(pag, '#6c757d') for pag in gastos_pagto.keys()]

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
        mes_ano = m.data_cobranca.strftime('%m/%Y')
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

    gastos_cat_limpos = {}
    for m in movs_periodo:
        if m.tipo_movimentacao == 'Saída':
            gastos_cat_limpos[m.categoria] = gastos_cat_limpos.get(m.categoria, 0) + m.valor

    return render_template('dashboard.html', 
                           t_entrada=t_entrada_periodo, t_saida=t_saida_periodo, t_saida_futura=t_saida_futura,
                           t_investimento=t_investimento_geral, caixa=caixa_atual, patrimonio_total=patrimonio_total,
                           labels_cat=list(gastos_cat_sub.keys()), valores_cat=list(gastos_cat_sub.values()), cores_cat=cores_grafico_cat,
                           labels_pagto=list(gastos_pagto.keys()), valores_pagto=list(gastos_pagto.values()), cores_pagto=cores_grafico_pagto,
                           gastos_cat=gastos_cat_limpos, orcamentos=orcamentos,
                           labels_meses=labels_meses, dados_entradas_mes=dados_entradas_mes, 
                           dados_saidas_mes=dados_saidas_mes, dados_investimentos_mes=dados_investimentos_mes, 
                           dados_orcamento_mes=dados_orcamento_mes,
                           data_inicio=data_inicio, data_fim=data_fim)

# --- ROTA: CONTA CORRENTE (Lançamentos Padrão) ---
@app.route('/lancamentos', methods=['GET', 'POST'])
@login_required
def lancamentos():
    if request.method == 'POST':
        valor_raw = request.form.get('valor').replace('.', '').replace(',', '.')
        parcelas = int(request.form.get('parcelas', 1))
        valor_total = float(valor_raw)
        data_base = datetime.strptime(request.form.get('data'), '%Y-%m-%d').date()
        nome_forma = request.form.get('forma_pagto')
        
        valor_parcela = round(valor_total / parcelas, 2)
        diferenca_centavos = round(valor_total - (valor_parcela * parcelas), 2)

        for i in range(parcelas):
            data_lanc = adicionar_meses(data_base, i) 
            desc = f"{request.form.get('descricao')} ({i+1}/{parcelas})" if parcelas > 1 else request.form.get('descricao')
            valor_final = valor_parcela + diferenca_centavos if i == 0 else valor_parcela
            
            nova = Movimentacao(
                descricao=desc, valor=valor_final,
                forma_pagto=nome_forma, categoria=request.form.get('categoria'),
                subcategoria=request.form.get('subcategoria', ''), tipo_movimentacao=request.form.get('tipo_movimentacao'),
                data=data_lanc, data_cobranca=data_lanc, usuario_id=current_user.id
            )
            db.session.add(nova)
        db.session.commit()
        return redirect(request.referrer or url_for('lancamentos'))

    hoje = datetime.today()
    data_inicio_str = request.args.get('data_inicio', hoje.replace(day=1).strftime('%Y-%m-%d'))
    data_fim_str = request.args.get('data_fim', hoje.replace(day=calendar.monthrange(hoje.year, hoje.month)[1]).strftime('%Y-%m-%d'))
    filtro_pagto = request.args.get('filtro_pagto', '')
    filtro_cat = request.args.get('filtro_cat', '')
    filtro_subcat = request.args.get('filtro_subcat', '')

    data_inicio_obj = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
    data_fim_obj = datetime.strptime(data_fim_str, '%Y-%m-%d').date()

    todas = Movimentacao.query.filter_by(usuario_id=current_user.id).all()
    t_entrada_caixa = sum(m.valor for m in todas if m.tipo_movimentacao == 'Entrada' and m.data_cobranca <= data_fim_obj)
    t_saida_caixa = sum(m.valor for m in todas if m.tipo_movimentacao == 'Saída' and m.data_cobranca <= data_fim_obj)
    caixa_atual = t_entrada_caixa - t_saida_caixa
    invest_geral = sum(m.valor for m in todas if m.tipo_movimentacao == 'Investimento')
    t_saida_futura = sum(m.valor for m in todas if m.tipo_movimentacao == 'Saída' and m.data_cobranca > data_fim_obj)
    patrimonio_total = caixa_atual + invest_geral

    cartoes = FormaPagamento.query.filter_by(usuario_id=current_user.id, is_credito=True).all()
    nomes_cartoes = [c.nome for c in cartoes]

    # Busca as operações da conta corrente (Ignora as linhas brutas de cartão)
    query_compras = Movimentacao.query.filter(
        Movimentacao.usuario_id == current_user.id,
        Movimentacao.data_cobranca >= data_inicio_obj,
        Movimentacao.data_cobranca <= data_fim_obj,
        ~Movimentacao.forma_pagto.in_(nomes_cartoes)
    )
    if filtro_pagto: query_compras = query_compras.filter(Movimentacao.forma_pagto == filtro_pagto)
    if filtro_cat: query_compras = query_compras.filter(Movimentacao.categoria == filtro_cat)
    if filtro_subcat: query_compras = query_compras.filter(Movimentacao.subcategoria == filtro_subcat)
    movs_compras = query_compras.all()
    
    for m in movs_compras: m.is_fatura = False 
    
    t_ent_per = sum(m.valor for m in movs_compras if m.tipo_movimentacao == 'Entrada')
    t_sai_per = sum(m.valor for m in movs_compras if m.tipo_movimentacao == 'Saída')

    # A LINHA MÁGICA: Agrupa a fatura do cartão
    linhas_virtuais = []
    if not filtro_cat and not filtro_subcat: # Só exibe se não tiver filtrando por categoria
        query_faturas = Movimentacao.query.filter(
            Movimentacao.usuario_id == current_user.id,
            Movimentacao.forma_pagto.in_(nomes_cartoes),
            Movimentacao.data_cobranca >= data_inicio_obj,
            Movimentacao.data_cobranca <= data_fim_obj,
            Movimentacao.tipo_movimentacao == 'Saída'
        )
        if filtro_pagto: query_faturas = query_faturas.filter(Movimentacao.forma_pagto == filtro_pagto)
        
        faturas_agrupadas = {}
        for m in query_faturas.all():
            chave = (m.forma_pagto, m.data_cobranca)
            if chave not in faturas_agrupadas: faturas_agrupadas[chave] = 0
            faturas_agrupadas[chave] += m.valor

        for (cartao, dt_cob), total in faturas_agrupadas.items():
            linhas_virtuais.append({
                'is_fatura': True, 'data': dt_cob, 'data_cobranca': dt_cob, 'descricao': f'💳 Fatura Consolidada - {cartao}',
                'forma_pagto': cartao, 'categoria': 'Múltiplas Categorias', 'valor': total, 'tipo_movimentacao': 'Saída'
            })
            t_sai_per += total

    itens_tabela = list(movs_compras) + linhas_virtuais
    itens_tabela.sort(key=lambda item: item['data_cobranca'] if isinstance(item, dict) else item.data_cobranca, reverse=True)

    formas_padrao = FormaPagamento.query.filter_by(usuario_id=current_user.id, is_credito=False).all()
    formas_todas = FormaPagamento.query.filter_by(usuario_id=current_user.id).all()
    categorias = Categoria.query.filter_by(usuario_id=current_user.id).all()
    subcategorias = Subcategoria.query.filter_by(usuario_id=current_user.id).all()

    return render_template('lancamentos.html', movimentacoes=itens_tabela, 
                           t_entrada=t_ent_per, t_saida=t_sai_per, t_saida_futura=t_saida_futura,
                           t_investimento=invest_geral, caixa=caixa_atual, patrimonio_total=patrimonio_total,
                           data_inicio=data_inicio_str, data_fim=data_fim_str,
                           filtro_pagto=filtro_pagto, filtro_cat=filtro_cat, filtro_subcat=filtro_subcat,
                           formas=formas_padrao, formas_todas=formas_todas, categorias=categorias, subcategorias=subcategorias)

# --- NOVA ROTA: EXCLUSIVA PARA CARTÕES DE CRÉDITO ---
@app.route('/cartoes', methods=['GET', 'POST'])
@login_required
def cartoes():
    if request.method == 'POST':
        valor_raw = request.form.get('valor').replace('.', '').replace(',', '.')
        parcelas = int(request.form.get('parcelas', 1))
        valor_total = float(valor_raw)
        data_base = datetime.strptime(request.form.get('data'), '%Y-%m-%d').date()
        nome_forma = request.form.get('forma_pagto')
        
        forma_obj = FormaPagamento.query.filter_by(nome=nome_forma, usuario_id=current_user.id).first()
        
        valor_parcela = round(valor_total / parcelas, 2)
        diferenca_centavos = round(valor_total - (valor_parcela * parcelas), 2)
        
        # A MÁGICA DA PROJEÇÃO: Calcula a data da PRIMEIRA cobrança com base no fechamento
        data_cob_inicial = calcular_data_cobranca(data_base, forma_obj.dia_fechamento, forma_obj.dia_vencimento)

        for i in range(parcelas):
            data_lanc = adicionar_meses(data_base, i) # Apenas visual da compra
            data_cob = adicionar_meses(data_cob_inicial, i) # Quando cai na fatura
            
            desc = f"{request.form.get('descricao')} ({i+1}/{parcelas})" if parcelas > 1 else request.form.get('descricao')
            valor_final = valor_parcela + diferenca_centavos if i == 0 else valor_parcela
            
            nova = Movimentacao(
                descricao=desc, valor=valor_final,
                forma_pagto=nome_forma, categoria=request.form.get('categoria'),
                subcategoria=request.form.get('subcategoria', ''), tipo_movimentacao='Saída',
                data=data_lanc, data_cobranca=data_cob, usuario_id=current_user.id
            )
            db.session.add(nova)
        db.session.commit()
        return redirect(request.referrer or url_for('cartoes'))

    hoje = datetime.today()
    data_inicio_str = request.args.get('data_inicio', hoje.replace(day=1).strftime('%Y-%m-%d'))
    data_fim_str = request.args.get('data_fim', hoje.replace(day=calendar.monthrange(hoje.year, hoje.month)[1]).strftime('%Y-%m-%d'))
    filtro_pagto = request.args.get('filtro_pagto', '')

    data_inicio_obj = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
    data_fim_obj = datetime.strptime(data_fim_str, '%Y-%m-%d').date()

    formas_credito = FormaPagamento.query.filter_by(usuario_id=current_user.id, is_credito=True).all()
    nomes_cartoes = [c.nome for c in formas_credito]

    # Na aba de cartão, filtramos pela data que cai na FATURA (data_cobranca)
    query = Movimentacao.query.filter(
        Movimentacao.usuario_id == current_user.id,
        Movimentacao.forma_pagto.in_(nomes_cartoes),
        Movimentacao.data_cobranca >= data_inicio_obj,
        Movimentacao.data_cobranca <= data_fim_obj
    )
    if filtro_pagto: query = query.filter(Movimentacao.forma_pagto == filtro_pagto)
    
    movs = query.order_by(Movimentacao.data_cobranca.desc()).all()
    total_fatura = sum(m.valor for m in movs)

    categorias = Categoria.query.filter_by(usuario_id=current_user.id).all()
    subcategorias = Subcategoria.query.filter_by(usuario_id=current_user.id).all()

    return render_template('cartoes.html', movimentacoes=movs, total_fatura=total_fatura,
                           data_inicio=data_inicio_str, data_fim=data_fim_str, filtro_pagto=filtro_pagto,
                           formas_credito=formas_credito, categorias=categorias, subcategorias=subcategorias)

@app.route('/investimentos', methods=['GET', 'POST'])
@login_required
def investimentos():
    if request.method == 'POST':
        qtd_raw = float(request.form.get('quantidade').replace(',', '.'))
        valor_raw = float(request.form.get('valor').replace('.', '').replace(',', '.'))
        novo_inv = Investimento(operacao=request.form.get('operacao'),categoria=request.form.get('categoria'),subcategoria=request.form.get('subcategoria'),ativo=request.form.get('ativo').upper(),quantidade=qtd_raw,valor=valor_raw,data=datetime.strptime(request.form.get('data'), '%Y-%m-%d').date(),usuario_id=current_user.id)
        db.session.add(novo_inv)
        db.session.commit()
        return redirect(request.referrer or url_for('investimentos'))
    
    hoje = datetime.today()
    data_inicio_str = request.args.get('data_inicio', hoje.replace(day=1).strftime('%Y-%m-%d'))
    data_fim_str = request.args.get('data_fim', hoje.replace(day=calendar.monthrange(hoje.year, hoje.month)[1]).strftime('%Y-%m-%d'))
    filtro_cat = request.args.get('filtro_cat', '')
    filtro_subcat = request.args.get('filtro_subcat', '')
    
    data_inicio_obj = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
    data_fim_obj = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
    
    todas_movs = Movimentacao.query.filter_by(usuario_id=current_user.id).all()
    total_transferido = sum(m.valor for m in todas_movs if m.tipo_movimentacao == 'Investimento')
    todos_invs = Investimento.query.filter_by(usuario_id=current_user.id).all()
    total_compras = sum((i.quantidade * i.valor) for i in todos_invs if i.operacao == 'Compra')
    total_vendas = sum((i.quantidade * i.valor) for i in todos_invs if i.operacao == 'Venda')
    total_recebimentos = sum((i.quantidade * i.valor) for i in todos_invs if i.operacao == 'Recebimento')
    valor_investido = total_compras - total_vendas
    saldo_corretora = total_transferido - total_compras + total_vendas + total_recebimentos
    
    query = Investimento.query.filter_by(usuario_id=current_user.id).filter(Investimento.data >= data_inicio_obj, Investimento.data <= data_fim_obj)
    if filtro_cat: query = query.filter(Investimento.categoria == filtro_cat)
    if filtro_subcat: query = query.filter(Investimento.subcategoria == filtro_subcat)
    invs_filtrados = query.order_by(Investimento.data.desc()).all()
    
    return render_template('investimentos.html', investimentos=invs_filtrados, total_transferido=total_transferido, valor_investido=valor_investido, saldo_corretora=saldo_corretora,data_inicio=data_inicio_str, data_fim=data_fim_str,filtro_cat=filtro_cat, filtro_subcat=filtro_subcat)

@app.route('/editar_investimento/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_investimento(id):
    inv = Investimento.query.get_or_404(id)
    if inv.usuario_id != current_user.id: return redirect(url_for('investimentos'))
    if request.method == 'POST':
        inv.operacao = request.form.get('operacao')
        inv.categoria = request.form.get('categoria')
        inv.subcategoria = request.form.get('subcategoria')
        inv.ativo = request.form.get('ativo').upper()
        inv.quantidade = float(request.form.get('quantidade').replace(',', '.'))
        inv.valor = float(request.form.get('valor').replace('.', '').replace(',', '.'))
        inv.data = datetime.strptime(request.form.get('data'), '%Y-%m-%d').date()
        db.session.commit()
        return redirect(url_for('investimentos'))
    return render_template('editar_investimento.html', inv=inv)

@app.route('/excluir_investimento/<int:id>')
@login_required
def excluir_investimento(id):
    inv = Investimento.query.get_or_404(id)
    if inv.usuario_id == current_user.id:
        db.session.delete(inv)
        db.session.commit()
    return redirect(request.referrer or url_for('investimentos'))

@app.route('/excluir_mov_massa', methods=['POST'])
@login_required
def excluir_mov_massa():
    ids_para_excluir = request.form.getlist('mov_ids')
    if ids_para_excluir:
        Movimentacao.query.filter(Movimentacao.id.in_(ids_para_excluir), Movimentacao.usuario_id == current_user.id).delete(synchronize_session=False)
        db.session.commit()
    return redirect(request.referrer or url_for('lancamentos'))

@app.route('/editar_mov/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_mov(id):
    mov = Movimentacao.query.get_or_404(id)
    if mov.usuario_id != current_user.id: return redirect(url_for('lancamentos'))
    if request.method == 'POST':
        mov.valor = float(request.form.get('valor').replace('.', '').replace(',', '.'))
        mov.descricao = request.form.get('descricao')
        mov.categoria = request.form.get('categoria')
        mov.subcategoria = request.form.get('subcategoria', '')
        
        # Só recalcula se for alterada a data no painel de cartões
        nova_data = datetime.strptime(request.form.get('data'), '%Y-%m-%d').date()
        mov.data = nova_data
        
        forma_obj = FormaPagamento.query.filter_by(nome=mov.forma_pagto, usuario_id=current_user.id).first()
        if forma_obj and forma_obj.is_credito:
            mov.data_cobranca = calcular_data_cobranca(nova_data, forma_obj.dia_fechamento, forma_obj.dia_vencimento)
        else:
            mov.data_cobranca = nova_data
            
        db.session.commit()
        return redirect(request.referrer or url_for('lancamentos'))
        
    return render_template('editar_lancamento.html', mov=mov, formas=FormaPagamento.query.filter_by(usuario_id=current_user.id).all(), categorias=Categoria.query.filter_by(usuario_id=current_user.id).all(), subcategorias=Subcategoria.query.filter_by(usuario_id=current_user.id).all())

@app.route('/excluir_mov/<int:id>')
@login_required
def excluir_mov(id):
    mov = Movimentacao.query.get_or_404(id)
    if mov.usuario_id == current_user.id:
        db.session.delete(mov)
        db.session.commit()
    return redirect(request.referrer or url_for('lancamentos'))

@app.route('/orcamentos', methods=['GET', 'POST'])
@login_required
def orcamentos():
    if request.method == 'POST':
        categoria = request.form.get('categoria')
        valor_raw = request.form.get('valor_limite').replace('.', '').replace(',', '.')
        orc = Orcamento.query.filter_by(usuario_id=current_user.id, categoria=categoria).first()
        if orc: orc.valor_limite = float(valor_raw)
        else: db.session.add(Orcamento(categoria=categoria, valor_limite=float(valor_raw), usuario_id=current_user.id))
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
        is_cred = True if request.form.get('is_credito') == 'on' else False
        dia_f = int(request.form.get('dia_fechamento')) if is_cred else None
        dia_v = int(request.form.get('dia_vencimento')) if is_cred else None
        
        db.session.add(FormaPagamento(nome=request.form.get('nome'), icone=request.form.get('icone'), cor=request.form.get('cor'), is_credito=is_cred, dia_fechamento=dia_f, dia_vencimento=dia_v, usuario_id=current_user.id))
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

@app.route('/excluir_subcategoria/<int:id>')
@login_required
def excluir_subcategoria(id):
    sub = Subcategoria.query.get_or_404(id)
    if sub.usuario_id == current_user.id:
        db.session.delete(sub)
        db.session.commit()
    return redirect(url_for('gerenciar_categorias'))

@app.route('/editar_subcategoria/<int:id>', methods=['POST'])
@login_required
def editar_subcategoria(id):
    sub = Subcategoria.query.get_or_404(id)
    if sub.usuario_id == current_user.id:
        novo_nome = request.form.get('novo_nome')
        if novo_nome:
            sub.nome = novo_nome
            db.session.commit()
    return redirect(url_for('gerenciar_categorias'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)