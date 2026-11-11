"""Serviços do Comercial: carregar com escopo, empresa nascendo na oportunidade, histórico, serialização e cálculos.

Outros módulos podem chamar `registrar_evento` e `oportunidades_abertas_resumo` (assinaturas estáveis).
"""

from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import hoje as hoje_de_negocio
from app.core.deps import Contexto
from app.core.models import Usuario
from app.domain import RegraViolada
from app.domain.atividade import atrasada
from app.domain.cadastro import chave_de_nome, validar_nome
from app.domain.dinheiro import ZERO
from app.domain.funil import alem_do_limite, dias_na_etapa
from app.domain.modelos_comunicacao import CONTEXTOS
from app.modules.comercial import regras
from app.modules.comercial.models import (
    Atividade,
    Comunicacao,
    Etapa,
    Funil,
    ModeloComunicacao,
    ModeloProposta,
    Oportunidade,
    OportunidadeEvento,
    Proposta,
)
from app.modules.comercial.schemas import AtividadeOut, OportunidadeOut
from app.modules.nucleo.models import CampoCustom, Empresa, Pessoa, Produto

NAO_ENCONTRADA = "Oportunidade não encontrada."


def hoje() -> date:
    return hoje_de_negocio()


# ------------------------------------------------------------------------------------------------ carregar com escopo
def obter(ctx: Contexto, modelo, id_: int, mensagem: str, *, responsavel: str | None = "responsavel_id"):
    """Carrega ou 404. Com escopo "só meus registros", registro de outro responsável também é 404 (não revela)."""
    obj = ctx.db.get(modelo, id_)
    if obj is None:
        raise HTTPException(404, mensagem)
    if responsavel and not ctx.pode_acessar(getattr(obj, responsavel)):
        raise HTTPException(404, mensagem)
    return obj


def obter_oportunidade(ctx: Contexto, id_: int) -> Oportunidade:
    return obter(ctx, Oportunidade, id_, NAO_ENCONTRADA)


def comunicacao_visivel(ctx: Contexto, com: Comunicacao) -> bool:
    """Regra ÚNICA de acesso a uma comunicação (tela Comercial e IA): com "só meus registros", a conversa herda o
    responsável da oportunidade vinculada — sem oportunidade, ou de oportunidade de outro, não é visível."""
    if not ctx.somente_meus_registros():
        return True
    op = ctx.db.get(Oportunidade, com.oportunidade_id) if com.oportunidade_id else None
    return op is not None and op.responsavel_id == ctx.usuario.id


def responsavel_efetivo(ctx: Contexto, responsavel_id: int | None) -> int:
    """Quem tem escopo "só meus registros" só cria registros para si (senão deixaria de enxergá-los)."""
    if ctx.somente_meus_registros():
        return ctx.usuario.id
    if responsavel_id is None:
        return ctx.usuario.id
    u = ctx.db.get(Usuario, responsavel_id)
    if u is None or not u.ativo:
        raise RegraViolada("Responsável não encontrado ou inativo.")
    return responsavel_id


def conferir_empresa(db: Session, empresa_id: int | None) -> None:
    if empresa_id is not None and db.get(Empresa, empresa_id) is None:
        raise RegraViolada("Empresa não encontrada.")


def conferir_oportunidade_vinculo(ctx: Contexto, oportunidade_id: int | None) -> Oportunidade | None:
    if oportunidade_id is None:
        return None
    op = ctx.db.get(Oportunidade, oportunidade_id)
    if op is None or not ctx.pode_acessar(op.responsavel_id):
        raise RegraViolada("Oportunidade não encontrada.")
    return op


def conferir_modelo(db: Session, modelo_id: int | None, contexto: str) -> ModeloComunicacao | None:
    """Modelo usado num envio: precisa existir e ser da área (`contexto` comercial|financeiro → a sua + geral)."""
    if modelo_id is None:
        return None
    m = db.get(ModeloComunicacao, modelo_id)
    if m is None or m.classificacao not in CONTEXTOS[contexto]:
        raise RegraViolada("Modelo de comunicação não encontrado. Escolha outro modelo ou escreva a mensagem.")
    return m


def conferir_modelo_comercial(db: Session, modelo_id: int | None) -> ModeloComunicacao | None:
    return conferir_modelo(db, modelo_id, "comercial")


def resolver_empresa(ctx: Contexto, *, empresa_id: int | None, empresa_nome: str | None,
                     responsavel_id: int) -> Empresa | None:
    """Empresa pelo id, ou pelo NOME (nasce dentro da oportunidade como prospect se ainda não existe).
    Mesmo nome normalizado = mesma empresa (cadastro único)."""
    if empresa_id is not None:
        e = ctx.db.get(Empresa, empresa_id)
        if e is None:
            raise RegraViolada("Empresa não encontrada.")
        return e
    if empresa_nome is None or not empresa_nome.strip():
        return None
    nome = validar_nome(empresa_nome, o_que="o nome da empresa")
    e = ctx.db.scalar(select(Empresa).where(Empresa.nome_chave == chave_de_nome(nome)))
    if e is not None:
        return e
    e = Empresa(nome=nome, responsavel_id=responsavel_id, papel_prospect=True, campos_custom={},
                origem="Oportunidade")
    ctx.db.add(e)
    ctx.db.flush()
    ctx.auditar("empresa.criar", "empresa", e.id, descricao=f"Empresa criada na oportunidade: {nome}",
                depois={"nome": nome, "papeis": ["prospect"]})
    return e


def registrar_evento(db: Session, oportunidade_id: int, tipo: str, texto: str, usuario_id: int | None) -> None:
    """Histórico compartilhado (o motor de automações lê esta tabela). `tipo` ∈ regras.TIPOS_EVENTO."""
    db.add(OportunidadeEvento(oportunidade_id=oportunidade_id, tipo=regras.validar_tipo_evento(tipo),
                              texto=texto[:4000], usuario_id=usuario_id))


def etapas_do_funil(db: Session, funil_id: int) -> list[Etapa]:
    return list(db.scalars(select(Etapa).where(Etapa.funil_id == funil_id).order_by(Etapa.ordem, Etapa.id)))


def primeira_etapa(db: Session, funil_id: int) -> Etapa:
    etapas = etapas_do_funil(db, funil_id)
    if not etapas:
        raise RegraViolada("O funil não tem etapas. Configure as etapas antes de criar oportunidades.")
    return etapas[0]


def conferir_campos_exigidos(db: Session, op: Oportunidade, etapa: Etapa) -> None:
    """Campo personalizado exigido na etapa precisa estar preenchido antes de entrar nela."""
    exigidos = db.scalars(select(CampoCustom).where(
        CampoCustom.objeto == "oportunidade", CampoCustom.exigido_na_etapa_id == etapa.id,
        CampoCustom.arquivado.is_(False)))
    for c in exigidos:
        if (op.campos_custom or {}).get(c.slug) in (None, ""):
            raise RegraViolada(f"Preencha {c.nome} antes de mover para {etapa.nome}.")


# ------------------------------------------------------------------------------------------------ nomes em lote
def _nomes(db: Session, modelo, ids: Iterable[int | None], campo: str = "nome") -> dict[int, str]:
    ids = {i for i in ids if i is not None}
    if not ids:
        return {}
    col = getattr(modelo, campo)
    return dict(db.execute(select(modelo.id, col).where(modelo.id.in_(ids))).all())


def serializar_oportunidades(db: Session, ops: list[Oportunidade], ref: date | None = None) -> list[OportunidadeOut]:
    ref = ref or hoje()
    empresas = _nomes(db, Empresa, (o.empresa_id for o in ops))
    pessoas = _nomes(db, Pessoa, (o.contato_id for o in ops))
    usuarios = _nomes(db, Usuario, (o.responsavel_id for o in ops))
    funis = _nomes(db, Funil, (o.funil_id for o in ops))
    etapa_ids = {o.etapa_id for o in ops if o.etapa_id}
    etapas = {e.id: e for e in db.scalars(select(Etapa).where(Etapa.id.in_(etapa_ids)))} if etapa_ids else {}
    out = []
    for o in ops:
        e = etapas.get(o.etapa_id)
        aberta = o.resultado == "aberta"
        out.append(OportunidadeOut.model_validate(o).model_copy(update={
            "funil_nome": funis.get(o.funil_id),
            "etapa_nome": e.nome if e else None,
            "etapa_probabilidade": e.probabilidade if e else None,
            "empresa_nome": empresas.get(o.empresa_id),
            "contato_nome": pessoas.get(o.contato_id),
            "responsavel_nome": usuarios.get(o.responsavel_id),
            "dias_na_etapa": dias_na_etapa(o.entrou_etapa_em, ref) if aberta else 0,
            "alem_do_limite": aberta and e is not None and alem_do_limite(o.entrou_etapa_em, e.limite_dias, ref),
            "interesse": (o.campos_custom or {}).get("interesse"),
            "campos_custom": o.campos_custom or {},
        }))
    return out


def serializar_atividades(db: Session, ats: list[Atividade], ref: date | None = None) -> list[AtividadeOut]:
    ref = ref or hoje()
    empresas = _nomes(db, Empresa, (a.empresa_id for a in ats))
    usuarios = _nomes(db, Usuario, (a.responsavel_id for a in ats))
    ops = _nomes(db, Oportunidade, (a.oportunidade_id for a in ats), "titulo")
    return [AtividadeOut.model_validate(a).model_copy(update={
        "empresa_nome": empresas.get(a.empresa_id),
        "responsavel_nome": usuarios.get(a.responsavel_id),
        "oportunidade_titulo": ops.get(a.oportunidade_id),
        "atrasada": atrasada(prazo=a.prazo, status=a.status, hoje=ref),
    }) for a in ats]


def nomes_empresas(db: Session, ids: Iterable[int | None]) -> dict[int, str]:
    return _nomes(db, Empresa, ids)


def nomes_usuarios(db: Session, ids: Iterable[int | None]) -> dict[int, str]:
    return _nomes(db, Usuario, ids)


def nomes_oportunidades(db: Session, ids: Iterable[int | None]) -> dict[int, str]:
    return _nomes(db, Oportunidade, ids, "titulo")


def nomes_produtos(db: Session, ids: Iterable[int | None]) -> dict[int, str]:
    return _nomes(db, Produto, ids)


def nomes_funis(db: Session, ids: Iterable[int | None]) -> dict[int, str]:
    return _nomes(db, Funil, ids)


def nomes_etapas(db: Session, ids: Iterable[int | None]) -> dict[int, str]:
    return _nomes(db, Etapa, ids)


# ------------------------------------------------------------------------------------------------ contexto da negociação
def contexto_negociacao(db: Session, op: Oportunidade) -> dict[str, Any]:
    """Contexto determinístico para o drawer: última comunicação vinculada (análise, se houver) + próxima ação.
    Sem probabilidade preditiva."""
    limite = "Leitura dos registros vinculados; hipótese de fechamento, sem probabilidade preditiva."
    c = db.scalar(select(Comunicacao).where(Comunicacao.oportunidade_id == op.id)
                  .order_by(Comunicacao.data.desc().nullslast(), Comunicacao.id.desc()).limit(1))
    if c is None:
        texto = (f"Próxima ação registrada: {op.proxima_acao}." if op.proxima_acao
                 else "Sem comunicações vinculadas e sem próxima ação registrada.")
        return {"texto": texto, "fonte": None, "limite": limite + " Importe notas ou mensagens para enriquecer."}
    a = c.analise or {}
    partes = []
    if a.get("objecoes"):
        partes.append(f"Objeção: {a['objecoes'][0]}")
    if a.get("compromissos"):
        partes.append(f"Compromisso: {a['compromissos'][0]}")
    if not partes:
        trecho = c.conteudo.strip().replace("\n", " ")
        partes.append(trecho[:280] + ("…" if len(trecho) > 280 else ""))
    if op.proxima_acao:
        partes.append(f"Próxima ação: {op.proxima_acao}")
    canal = {"reuniao": "reunião", "email": "e-mail", "whatsapp": "WhatsApp", "notas": "notas"}.get(c.canal, c.canal)
    data_txt = c.data.strftime("%d/%m/%Y") if c.data else "sem data"
    return {"texto": " · ".join(partes), "fonte": f"{canal} · {c.titulo or 'Comunicação'} · {data_txt}",
            "limite": limite}


def contagens_oportunidade(db: Session, op_id: int) -> dict[str, int]:
    return {
        "atividades_pendentes": db.scalar(select(func.count()).select_from(Atividade).where(
            Atividade.oportunidade_id == op_id, Atividade.status == "pendente")) or 0,
        "comunicacoes": db.scalar(select(func.count()).select_from(Comunicacao).where(
            Comunicacao.oportunidade_id == op_id)) or 0,
        "propostas": db.scalar(select(func.count()).select_from(Proposta).where(
            Proposta.oportunidade_id == op_id)) or 0,
    }


# ------------------------------------------------------------------------------------------------ cálculos
def soma(valores: Iterable[Decimal | None]) -> Decimal:
    return sum((v or ZERO for v in valores), ZERO)


def no_periodo(d: date | datetime | None, inicio: date, fim: date) -> bool:
    if d is None:
        return False
    if isinstance(d, datetime):
        d = d.date()
    return inicio <= d <= fim


def oportunidades_abertas_resumo(db: Session, funil_id: int | None = None) -> list[Oportunidade]:
    q = select(Oportunidade).where(Oportunidade.resultado == "aberta")
    if funil_id:
        q = q.where(Oportunidade.funil_id == funil_id)
    return list(db.scalars(q))


# ------------------------------------------------------------------------------------------------ proposta: documento
def modelo_proposta_padrao(db: Session) -> ModeloProposta | None:
    return db.scalar(select(ModeloProposta).where(ModeloProposta.padrao.is_(True), ModeloProposta.ativo.is_(True))
                     .order_by(ModeloProposta.id).limit(1))


def garantir_modelo_proposta(db: Session) -> None:
    """Sem nenhum modelo de proposta, cria "Proposta comercial padrão" (só `flush`: quem chama faz o commit)."""
    from app.domain.modelo_proposta import MODELO_INICIAL

    if db.scalar(select(func.count()).select_from(ModeloProposta)):
        return
    db.add(ModeloProposta(**MODELO_INICIAL, ativo=True))
    db.flush()


def modelo_da_proposta(db: Session, proposta: Proposta):
    """Modelo usado no documento: o da proposta; senão o padrão; senão os textos iniciais (sem gravar nada)."""
    from app.domain.modelo_proposta import MODELO_INICIAL

    m = db.get(ModeloProposta, proposta.modelo_proposta_id) if proposta.modelo_proposta_id else None
    return m or modelo_proposta_padrao(db) or ModeloProposta(**MODELO_INICIAL, ativo=True)


def variaveis_da_proposta(db: Session, proposta: Proposta, ref: date | None = None) -> dict[str, str | None]:
    from app.domain.modelo_proposta import valores_variaveis

    op = db.get(Oportunidade, proposta.oportunidade_id)
    emp = db.get(Empresa, proposta.empresa_id)
    contato = db.get(Pessoa, op.contato_id) if op is not None and op.contato_id else None
    resp = db.get(Usuario, proposta.responsavel_id)
    return valores_variaveis(
        empresa_nome=emp.nome if emp else None, empresa_cnpj=emp.documento if emp else None,
        contato_nome=contato.nome if contato else None, oportunidade_titulo=op.titulo if op else None,
        proposta_titulo=proposta.titulo, total=proposta.total, validade=proposta.validade,
        condicao=proposta.condicao, responsavel_nome=resp.nome if resp else None, hoje=ref or hoje())


def _endereco_texto(e: Empresa) -> str | None:
    linha1 = ", ".join(x for x in (e.logradouro, e.numero, e.complemento) if x)
    linha2 = " - ".join(x for x in (e.bairro, e.cidade, e.uf) if x)
    partes = [x for x in (linha1, linha2, f"CEP {e.cep}" if e.cep else None) if x]
    return " · ".join(partes) if partes else (e.endereco or None)


def gerar_pdf_proposta(db: Session, proposta: Proposta) -> bytes:
    """PDF da proposta (bytes). Não grava nada no banco. Assinatura estável: a frente WhatsApp anexa este PDF."""
    from app.core import storage
    from app.core.models import Identidade
    from app.domain.modelo_proposta import linha_item, mostra_faixa_rascunho
    from app.modules.comercial.pdf_proposta import DocumentoProposta, desenhar

    ref = hoje()
    ident = db.get(Identidade, 1) or db.scalar(select(Identidade).order_by(Identidade.id).limit(1))
    logo = None
    if ident is not None and storage.existe(ident.logo_path):
        try:
            logo = storage.ler(ident.logo_path)
        except (OSError, storage.ArquivoInvalido):
            logo = None
    modelo = modelo_da_proposta(db, proposta)
    valores = variaveis_da_proposta(db, proposta, ref)
    op = db.get(Oportunidade, proposta.oportunidade_id)
    emp = db.get(Empresa, proposta.empresa_id)
    contato = db.get(Pessoa, op.contato_id) if op is not None and op.contato_id else None
    resp = db.get(Usuario, proposta.responsavel_id)
    produto = db.get(Produto, proposta.produto_id) if proposta.produto_id else None
    item = linha_item(quantidade=proposta.quantidade, preco_unitario=proposta.preco_unitario,
                      desconto_pct=proposta.desconto_pct)
    doc = DocumentoProposta(
        organizacao=(ident.nome_exibicao if ident else None) or "FlicSales OS",
        cor=ident.cor_destaque if ident else None, logo=logo,
        titulo=proposta.titulo, versao=proposta.versao, emissao=ref, validade=proposta.validade,
        status=proposta.status, rascunho=mostra_faixa_rascunho(proposta.status, proposta.desconto_pct),
        empresa_nome=emp.nome if emp else "-", empresa_cnpj=emp.documento if emp else None,
        empresa_endereco=_endereco_texto(emp) if emp else None,
        contato_nome=contato.nome if contato else None, contato_email=contato.email if contato else None,
        introducao=regras.renderizar_modelo(modelo.introducao, valores)[0],
        escopo=proposta.escopo,
        item_nome=produto.nome if produto else proposta.titulo,
        quantidade=item["quantidade"], preco_unitario=item["preco_unitario"], desconto_pct=item["desconto_pct"],
        total=proposta.total, mensalidade_adicional=proposta.mensalidade_adicional or ZERO,
        condicao=proposta.condicao, termos=regras.renderizar_modelo(modelo.termos, valores)[0],
        responsavel_nome=resp.nome if resp else None, responsavel_email=resp.email if resp else None,
        rodape=regras.renderizar_modelo(modelo.rodape, valores)[0],
    )
    return desenhar(doc)
