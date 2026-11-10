"""Seed da organização de demonstração com os dados do protótipo (docs/ESPECIFICACAO.md, seção 3).

    cd backend && uv run python -m app.seed            # aplica as migrations e semeia o banco do DATABASE_URL (só dev)
    uv run python -m app.seed --organizacao acme       # popula UMA organização (modo um banco por organização);
                                                       # qualquer ambiente; em prod só com --forcar

Idempotente: `base` só cria o que falta (identidade, perfis, config de e-mail); `demo` só roda se o funil
"Serviços B2B" ainda não existe (tudo numa transação: ou entra inteiro, ou nada). Usuários são criados se faltarem.
Datas relativas a HOJE (nunca fixas). Só em AMBIENTE=dev: em hml/prod a senha de demonstração é recusada.

Usuários (senha de demonstração SENHA_DEMO, documentada no CLAUDE.md):
  francine (Gestor) · marina e lucas (Comercial) · fin (Financeiro)
"""

import os
import sys
from datetime import date, time, timedelta
from decimal import Decimal as D

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import perfis
from app.core.config import settings
from app.core.db import hoje as hoje_de_negocio
from app.core.models import ConfigEmail, Identidade, Usuario
from app.core.security import hash_senha
from app.domain.dinheiro import somar_meses
from app.domain.recorrencia import competencia_de

SENHA_DEMO = os.environ.get("SEED_SENHA") or "Flic@2026"  # só dev (ver _so_dev)
NOME_ORGANIZACAO = "FlicSales Demo"
FUNIL_DEMO = "Serviços B2B"

USUARIOS = [
    ("francine", "Francine Alves", "francine@flicsales.demo", "Gestor"),
    ("marina", "Marina Costa", "marina@flicsales.demo", "Comercial"),
    ("lucas", "Lucas Ribeiro", "lucas@flicsales.demo", "Comercial"),
    ("fin", "Fernanda Souza", "fin@flicsales.demo", "Financeiro"),
]


def _so_dev() -> None:
    if settings.ambiente != "dev":
        sys.exit("O seed de demonstração só roda com AMBIENTE=dev (usa senha conhecida).")


def base(db: Session, *, nome: str = NOME_ORGANIZACAO) -> None:
    """Identidade, perfis padrão e config de e-mail, se faltarem. Não altera o que já foi editado."""
    if db.get(Identidade, 1) is None:
        db.add(Identidade(id=1, nome_exibicao=nome))
    perfis.garantir_padrao(db)
    if db.get(ConfigEmail, 1) is None:
        db.add(ConfigEmail(id=1, remetente_nome=nome, copia_padrao=[]))
    db.flush()


def usuarios(db: Session, senha: str = SENHA_DEMO) -> dict[str, Usuario]:
    p = perfis.garantir_padrao(db)
    out = {}
    for login, nome, email, perfil in USUARIOS:
        u = db.scalar(select(Usuario).where(Usuario.login == login))
        if u is None:
            u = Usuario(nome=nome, email=email, login=login, perfil_acesso_id=p[perfil].id, senha_hash=hash_senha(senha))
            db.add(u)
        out[login] = u
    db.flush()
    return out


def demo(db: Session, hoje: date) -> bool:
    """Dados de demonstração. False se já existiam (nada é duplicado)."""
    from app.modules.comercial.models import Atividade, Comunicacao, Etapa, Funil, Oportunidade, OportunidadeEvento
    from app.modules.financeiro.models import Recorrencia, Titulo
    from app.modules.nucleo.models import CampoCustom, Categoria, CentroCusto, ContaFinanceira, Empresa, Pessoa, Produto

    if db.scalar(select(Funil.id).where(Funil.nome == FUNIL_DEMO)):
        return False
    u = usuarios(db)
    francine, marina, lucas, fin = u["francine"], u["marina"], u["lucas"], u["fin"]

    # ---------------------------------------------------------------- cadastros de apoio
    receita = Categoria(nome="Serviços prestados", natureza="receita")
    estrutura = Categoria(nome="Estrutura", natureza="despesa")
    operacao = CentroCusto(nome="Operação", codigo="OP", responsavel_id=francine.id)
    conta = ContaFinanceira(nome="Conta operacional", instituicao="Banco demonstração", saldo_inicial=D("25000.00"),
                            data_base=hoje - timedelta(days=30))
    produto = Produto(nome="Consultoria estratégica", tipo="servico", codigo="CONS-EST", unidade="projeto",
                      preco_referencia=D("24000.00"), descricao="Projeto de consultoria estratégica.")
    db.add_all([receita, estrutura, operacao, conta, produto])
    db.flush()

    # ---------------------------------------------------------------- funil
    funil = Funil(nome=FUNIL_DEMO)
    db.add(funil)
    db.flush()
    etapas = {}
    for ordem, (nome, prob, limite, criterio) in enumerate([
        ("Entrada", 10, 2, "Contato identificado e interesse inicial."),
        ("Discovery", 25, 7, "Necessidade, decisor e prazo mapeados."),
        ("Proposta", 50, 10, "Proposta enviada e validada com o decisor."),
        ("Negociação", 75, 14, "Condições em negociação; próximos passos combinados."),
    ], start=1):
        etapas[nome] = Etapa(funil_id=funil.id, nome=nome, ordem=ordem, probabilidade=prob, limite_dias=limite,
                             criterios=criterio)
    db.add_all(etapas.values())
    db.flush()

    # ---------------------------------------------------------------- campos personalizados
    db.add_all([
        CampoCustom(nome="Interesse", slug="interesse", tipo="lista", objeto="oportunidade",
                    opcoes=["Baixo", "Médio", "Alto"], ordem=1),
        CampoCustom(nome="Origem", slug="origem", tipo="lista", objeto="empresa",
                    opcoes=["Indicação", "Site", "Evento", "Prospecção ativa"], ordem=1),
    ])

    # ---------------------------------------------------------------- empresas e pessoas
    def empresa(nome, *papeis, **kw):
        e = Empresa(nome=nome, responsavel_id=kw.pop("responsavel_id", francine.id), **kw)
        e.papeis = list(papeis)
        db.add(e)
        return e

    aurora = empresa("Aurora Consultoria", "cliente", segmento="Consultoria", responsavel_id=marina.id,
                     campos_custom={"origem": "Indicação"}, origem="Indicação")
    vertice = empresa("Vértice Serviços", "prospect", segmento="Serviços", responsavel_id=lucas.id,
                      campos_custom={"origem": "Site"}, origem="Site")
    horizonte = empresa("Horizonte Gestão", "prospect", segmento="Gestão", responsavel_id=marina.id,
                        campos_custom={"origem": "Evento"}, origem="Evento")
    atlas = empresa("Atlas Tecnologia", "prospect", segmento="Tecnologia", responsavel_id=lucas.id,
                    campos_custom={"origem": "Prospecção ativa"}, origem="Prospecção ativa")
    ponto_norte = empresa("Ponto Norte", "cliente", email_financeiro="financeiro@pontonorte.demo")
    estudio_base = empresa("Estúdio Base", "cliente", email_financeiro="contas@estudiobase.demo")
    lume = empresa("Lume Serviços", "cliente")
    espaco = empresa("Espaço Compartilhado", "fornecedor", condicao_habitual="Boleto todo dia 5")
    nuvem = empresa("Nuvem Digital", "fornecedor", condicao_habitual="Cartão corporativo")
    db.flush()
    espaco.categoria_padrao_id = nuvem.categoria_padrao_id = estrutura.id

    contatos = {}
    for emp, nome, cargo, canal in [(aurora, "Paula Mendes", "Diretora de operações (decisora)", "email"),
                                    (vertice, "Rafael Torres", "Gerente de projetos", "ligacao"),
                                    (horizonte, "Camila Rocha", "Sócia", "whatsapp"),
                                    (atlas, "Diego Martins", "CTO", "email")]:
        contatos[emp.nome] = Pessoa(nome=nome, empresa_id=emp.id, cargo=cargo, canal_preferido=canal,
                                    responsavel_id=emp.responsavel_id)
    db.add_all(contatos.values())
    db.flush()

    # ---------------------------------------------------------------- oportunidades
    def oportunidade(titulo, emp, valor, etapa, resp, interesse, dias_na_etapa, proxima, prazo, **kw):
        o = Oportunidade(titulo=titulo, funil_id=funil.id, etapa_id=etapas[etapa].id, empresa_id=emp.id,
                         contato_id=contatos[emp.nome].id, responsavel_id=resp.id, valor_unico=D(valor),
                         entrou_etapa_em=hoje - timedelta(days=dias_na_etapa), proxima_acao=proxima,
                         proxima_acao_prazo=prazo, campos_custom={"interesse": interesse}, **kw)
        db.add(o)
        return o

    op_aurora = oportunidade("Projeto de consultoria", aurora, "24000", "Negociação", marina, "Alto", 4,
                             "Confirmar escopo com Aurora", hoje, previsao_fechamento=hoje + timedelta(days=10),
                             necessidade="Reorganizar a operação comercial e financeira.", decisor="Paula Mendes",
                             origem="Indicação")
    op_vertice = oportunidade("Expansão de operação", vertice, "18000", "Proposta", lucas, "Alto", 6,
                              "Retomar proposta da Vértice", hoje - timedelta(days=1),
                              previsao_fechamento=hoje + timedelta(days=20), origem="Site")
    op_horizonte = oportunidade("Diagnóstico estratégico", horizonte, "12000", "Discovery", marina, "Médio", 9,
                                "Preparar discovery da Horizonte", hoje + timedelta(days=1), origem="Evento")
    op_atlas = oportunidade("Consultoria recorrente", atlas, "9600", "Entrada", lucas, "Médio", 1, None, None,
                            valor_recorrente_mensal=D("800.00"), origem="Prospecção ativa")
    db.flush()
    for o, etapa in ((op_aurora, "Negociação"), (op_vertice, "Proposta"), (op_horizonte, "Discovery"),
                     (op_atlas, "Entrada")):
        db.add(OportunidadeEvento(oportunidade_id=o.id, tipo="etapa", texto=f"Entrou em {etapa}",
                                  usuario_id=o.responsavel_id))

    # ---------------------------------------------------------------- atividades e comunicações
    db.add_all([
        Atividade(assunto="Confirmar escopo com Aurora", tipo="reuniao", responsavel_id=marina.id,
                  empresa_id=aurora.id, oportunidade_id=op_aurora.id, prazo=hoje, hora_inicio=time(15, 0),
                  hora_fim=time(15, 45), canal="Videochamada", objetivo="Fechar escopo e condição comercial."),
        Atividade(assunto="Retomar proposta da Vértice", tipo="ligacao", responsavel_id=lucas.id,
                  empresa_id=vertice.id, oportunidade_id=op_vertice.id, prazo=hoje - timedelta(days=1),
                  objetivo="Entender objeções da proposta."),
        Atividade(assunto="Preparar discovery da Horizonte", tipo="tarefa", responsavel_id=marina.id,
                  empresa_id=horizonte.id, oportunidade_id=op_horizonte.id, prazo=hoje + timedelta(days=1)),
        Comunicacao(canal="notas", titulo="Discovery Aurora", data=hoje - timedelta(days=5), empresa_id=aurora.id,
                    oportunidade_id=op_aurora.id,
                    conteudo="Paula quer reorganizar a operação até o fim do trimestre. Orçamento aprovado; "
                             "preocupação com o prazo de implantação. Combinamos revisar o escopo nesta semana."),
        Comunicacao(canal="email", titulo="Proposta Vértice", data=hoje - timedelta(days=6), empresa_id=vertice.id,
                    oportunidade_id=op_vertice.id,
                    conteudo="Rafael recebeu a proposta e pediu para comparar com a solução atual antes de decidir."),
        Comunicacao(canal="whatsapp", titulo="Próximo encontro Horizonte", data=hoje - timedelta(days=2),
                    empresa_id=horizonte.id, oportunidade_id=op_horizonte.id,
                    conteudo="Camila confirmou disponibilidade para o discovery na próxima semana."),
    ])

    # ---------------------------------------------------------------- recorrência e títulos
    inicio_rec = somar_meses(hoje.replace(day=12), -2)
    rec = Recorrencia(descricao="Mensalidade", direcao="receber", empresa_id=estudio_base.id, valor_ciclo=D("4800.00"),
                      frequencia="mensal", inicio=inicio_rec, fim=somar_meses(inicio_rec, 11),
                      dia_vencimento=12, categoria_id=receita.id, centro_custo_id=operacao.id,
                      responsavel_id=fin.id)
    db.add(rec)
    db.flush()
    competencia = competencia_de(hoje)

    def titulo(direcao, emp, descricao, valor, vencimento, **kw):
        t = Titulo(direcao=direcao, empresa_id=emp.id, descricao=descricao, valor_original=D(valor), saldo=D(valor),
                   vencimento=vencimento, emissao=hoje - timedelta(days=20), responsavel_id=fin.id, status="aberto",
                   categoria_id=(receita if direcao == "receber" else estrutura).id, centro_custo_id=operacao.id,
                   conta_prevista_id=conta.id, forma=kw.pop("forma", "pix"), competencia=kw.pop("competencia", competencia),
                   **kw)
        db.add(t)
        return t

    titulo("receber", ponto_norte, "Consultoria • parcela 1/2", "6000", hoje - timedelta(days=7), parcela=1,
           parcelas_total=2)
    venc_mensalidade = date(hoje.year, hoje.month, 12)
    if venc_mensalidade <= hoje:  # a mensalidade da demonstração ainda vai vencer (só a Ponto Norte está vencida)
        venc_mensalidade = somar_meses(venc_mensalidade, 1)
    titulo("receber", estudio_base, f"Mensalidade • {_mes_extenso(venc_mensalidade)}", "4800", venc_mensalidade,
           origem_recorrencia_id=rec.id, competencia=competencia_de(venc_mensalidade))
    titulo("receber", lume, "Implantação • parcela única", "8500", hoje + timedelta(days=13), parcela=1,
           parcelas_total=1, forma="boleto")
    titulo("pagar", espaco, "Aluguel", "4200", hoje + timedelta(days=5), aprovacao="pendente", forma="boleto")
    titulo("pagar", nuvem, "Serviços de tecnologia", "3000", hoje + timedelta(days=8), aprovacao="aprovado",
           forma="cartao", aprovado_por_id=francine.id)
    db.flush()
    return True


_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
          "novembro", "dezembro"]


def _mes_extenso(d: date) -> str:
    return _MESES[d.month - 1]


def semear(db: Session, hoje: date | None = None) -> bool:
    base(db)
    usuarios(db)
    criado = demo(db, hoje or hoje_de_negocio())
    db.commit()
    return criado


class SeedRecusado(RuntimeError):
    """Pedido de seed fora das regras (organização inexistente, prod sem --forcar…)."""


def popular_organizacao(slug: str, *, forcar: bool = False, hoje: date | None = None) -> bool:
    """Popula UMA organização (um banco por organização) com os dados do protótipo e os usuários de demonstração
    (francine/marina/lucas/fin, senha SENHA_DEMO). Qualquer ambiente; em prod só com `forcar`. Idempotente
    (False se já estava populada). Não cria outros usuários nem mexe no Gestor da organização."""
    from app.controle import service
    from app.core import tenancy
    from app.core.db import SessionLocal

    if settings.ambiente == "prod" and not forcar:
        raise SeedRecusado("Em produção o seed de demonstração exige --forcar (cria usuários com senha conhecida).")
    if not tenancy.multi():
        raise SeedRecusado(f"Sem o banco de controle {tenancy.banco_controle()}: rode `python -m app.seed` "
                           "(um banco só) ou ative o modo multi com `python -m app.controle.cli ativar`.")
    import app.controle.sincronia  # noqa: F401  (logins de demo entram no catálogo do controle)

    org = service.por_slug(slug)
    if org is None:
        raise SeedRecusado(f"Organização {slug} não existe ou está inativa. Confira com `python -m app.controle.cli listar`.")
    with tenancy.usando(org), SessionLocal() as db:
        return semear(db, hoje)


def main(argv: list[str] | None = None) -> None:
    import argparse

    ap = argparse.ArgumentParser(prog="python -m app.seed", description="Dados de demonstração do protótipo.")
    ap.add_argument("--organizacao", metavar="SLUG",
                    help="popula esta organização (modo um banco por organização); qualquer ambiente exceto prod")
    ap.add_argument("--forcar", action="store_true", help="permite --organizacao em produção")
    a = ap.parse_args(argv)
    if a.organizacao:
        try:
            criado = popular_organizacao(a.organizacao, forcar=a.forcar)
        except SeedRecusado as e:
            sys.exit(str(e))
        print(f"Organização {a.organizacao}: dados de demonstração " + ("criados." if criado else "já existiam (nada duplicado)."))
        print("Logins: francine (Gestor), marina e lucas (Comercial), fin (Financeiro). Senha de demonstração no CLAUDE.md.")
        return
    _so_dev()
    from pathlib import Path

    from app.main import migrar

    if settings.database_url.startswith("sqlite"):
        Path(settings.database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)

    migrar()
    from app.core.db import SessionLocal

    with SessionLocal() as db:
        criado = semear(db)
    print("Organização de demonstração " + ("criada." if criado else "já existia (nada duplicado)."))
    print("Logins: francine (Gestor), marina e lucas (Comercial), fin (Financeiro). Senha de demonstração no CLAUDE.md.")


if __name__ == "__main__":
    main()
