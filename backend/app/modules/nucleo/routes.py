"""API do Núcleo (`/api/nucleo`): cadastros compartilhados (empresas, pessoas, produtos), cadastros financeiros
(fornecedores, categorias, centros de custo, contas), campos personalizados, busca global e qualidade dos dados.

Permissões (app/core/permissoes.py + as regras abaixo):
  empresas | pessoas | produtos            → nucleo.cadastros.(ver|editar)
  fornecedores | categorias | centros-custo | contas → financeiro.cadastros.(ver|editar)
  campos                                    → nucleo.campos.(ver|editar)
  duplicidades, empresas/{id}/mesclar       → nucleo.administracao.(ver|editar)  (Qualidade dos dados)
  busca                                     → qualquer logado; cada grupo respeita a permissão do recurso
  consultas/cnpj|cep                        → nucleo.cadastros.ver  (consulta pública no servidor; nada é gravado)
  empresas/{id}/(socios|anexos|cnpj/aplicar) → nucleo.cadastros.(ver|editar)
  planilhas/(empresas|pessoas|produtos)     → nucleo.cadastros.(ver modelo | editar importar)
  planilhas/(fornecedores|categorias|centros-custo|contas) → financeiro.cadastros.(ver | editar)
  campos/sugeridos                          → nucleo.campos.(ver|editar)
  campos/padroes                            → GET livre para logados (os formulários usam); PATCH nucleo.campos.editar
  listas/{segmento|porte|motivo_perda}      → GET livre para logados (alimenta selects); o resto
                                              nucleo.administracao.editar (Governança de ajustes)
Nada é excluído: DELETE inativa (ou arquiva). Toda mudança é auditada.
"""

import mimetypes
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import String, case, cast, func, or_, select
from sqlalchemy.exc import IntegrityError

from app.core import audit, storage
from app.core.config import settings
from app.core.db import hoje
from app.core.deps import Ctx
from app.core.models import Usuario
from app.core.permissoes import adicionar_regras
from app.core.schemas import Pagina
from app.domain import RegraViolada
from app.domain import campos_padrao as dom_padrao
from app.domain import campos_sugeridos as dom_sugeridos
from app.domain import listas as dom_listas
from app.domain.cadastro import (
    CAMPOS_ENDERECO,
    CAMPOS_PREENCHIVEIS_CNPJ,
    chave_de_nome,
    cnpj_valido,
    endereco_de,
    formas_do_documento,
    normalizar_endereco,
    preencher_vazios,
    resolver_endereco_pessoa,
    validar_base_legal,
    validar_documento_cadastro,
    validar_documento_livre,
    validar_nome,
    validar_papeis,
    validar_permissoes_comunicacao,
)
from app.domain.caixa import validar_edicao_conta
from app.domain.campos_exibicao import EtapaRef, validar_exibicao
from app.domain.contatos import principal_de, validar_emails, validar_telefones
from app.domain.produto import descrever_recorrencia, validar_desconto, validar_recorrencia
from app.modules.comercial.models import Etapa, Funil, Oportunidade
from app.modules.financeiro.models import Baixa, Titulo, Transferencia
from app.modules.nucleo import consultas, planilhas, regras, servico
from app.modules.nucleo.comprovante import gerar_comprovante_cnpj
from app.modules.nucleo.models import (
    CampoCustom,
    CampoPadraoConfig,
    Categoria,
    CentroCusto,
    ContaFinanceira,
    Empresa,
    EmpresaAnexo,
    EmpresaSocio,
    OpcaoLista,
    Pessoa,
    Produto,
)
from app.modules.nucleo.schemas import (
    AnexoSaida,
    ArquivarIn,
    BuscaSaida,
    CampoAtualizar,
    CampoCriar,
    CampoPadraoAtualizar,
    CampoPadraoSaida,
    CampoSaida,
    CampoSugeridoSaida,
    CategoriaAtualizar,
    CategoriaCriar,
    CategoriaSaida,
    CentroAtualizar,
    CentroCriar,
    CentroSaida,
    ConsultaCepSaida,
    ConsultaCnpjSaida,
    ContaAtualizar,
    ContaCriar,
    ContaSaida,
    ContatoResumo,
    Dependencia,
    DependenciasSaida,
    Duplicidade,
    EmpresaAtualizar,
    EmpresaCriar,
    EmpresaCurta,
    EmpresaDetalhe,
    EmpresaSaida,
    EtapaOpcao,
    FornecedorAtualizar,
    FornecedorCriar,
    FornecedorSaida,
    GrupoBusca,
    ImportacaoSaida,
    ItemBusca,
    MesclarIn,
    MesclaSaida,
    OpcaoListaAtualizar,
    OpcaoListaCriar,
    OpcaoListaSaida,
    Papel,
    PessoaAtualizar,
    PessoaCriar,
    PessoaSaida,
    ProdutoAtualizar,
    ProdutoCriar,
    ProdutoSaida,
    ReordenarIn,
    SocioSaida,
    TipoAnexo,
    _ReceitaSaida,
)

adicionar_regras([
    ("GET", r"/nucleo/busca$", None),  # livre para logados; cada grupo confere a permissão do recurso
    ("GET", r"/nucleo/campos/padroes$", None),  # metadado dos formulários: livre para logados
    ("GET", r"/nucleo/listas/[^/]+$", None),  # segmento/porte/motivo de perda: alimenta selects de todos
    ("*", r"/nucleo/listas/", "nucleo.administracao.*e"),  # Governança de ajustes
    ("POST", r"/nucleo/empresas/\d+/mesclar$", "nucleo.administracao.editar"),
    ("*", r"/nucleo/(fornecedores|categorias|centros-custo|contas)", "financeiro.cadastros.*e"),
    ("GET", r"/nucleo/consultas/(cnpj|cep)/[^/]+$", "nucleo.cadastros.ver"),
    ("*", r"/nucleo/planilhas/(fornecedores|categorias|centros-custo|contas)/", "financeiro.cadastros.*e"),
    # empresas, pessoas, produtos — e objeto desconhecido (a rota responde 404 depois do login)
    ("*", r"/nucleo/planilhas/[^/]+/", "nucleo.cadastros.*e"),
])

router = APIRouter(prefix="/nucleo", tags=["núcleo"])

Situacao = Literal["ativos", "inativos", "todos"]
CATEGORIA_ANEXOS = "empresas_anexos"
ZERO = Decimal("0.00")


# ================================================================================================= utilitários
def _ou_404(obj, o_que: str):
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{o_que} não encontrado(a).")
    return obj


def _commit(ctx: Ctx, duplicado: str = "Já existe um registro com estes dados.") -> None:
    """Commit que traduz violação de UNIQUE (corrida entre duas telas) em 400 com mensagem clara."""
    try:
        ctx.db.commit()
    except IntegrityError:
        ctx.db.rollback()
        raise RegraViolada(duplicado) from None


def _usuario_existe(ctx: Ctx, uid: int | None) -> None:
    if uid is not None and ctx.db.get(Usuario, uid) is None:
        raise RegraViolada("Responsável não encontrado.")


def _situacao(q, coluna, situacao: Situacao):
    if situacao == "ativos":
        return q.where(coluna.is_(True))
    if situacao == "inativos":
        return q.where(coluna.is_(False))
    return q


def _paginar(ctx: Ctx, q, pagina: int, por_pagina: int):
    total = ctx.db.scalar(select(func.count()).select_from(q.order_by(None).subquery())) or 0
    linhas = ctx.db.execute(q.limit(por_pagina).offset((pagina - 1) * por_pagina)).all()
    return linhas, total


def _nomes_usuarios(ctx: Ctx, ids) -> dict[int, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return dict(ctx.db.execute(select(Usuario.id, Usuario.nome).where(Usuario.id.in_(ids))).all())


def _dinheiro(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(Decimal("0.01"))


def _alterar(ctx: Ctx, obj, dados: dict, acao: str, entidade: str, duplicado: str):
    """Aplica `dados` (já validados), audita o diff e confirma."""
    antes = audit.snapshot(obj)
    for k, v in dados.items():
        setattr(obj, k, v)
    ctx.db.flush()
    a, d = audit.diff(antes, audit.snapshot(obj))
    if a or d:
        ctx.auditar(acao, entidade, obj.id, antes=a, depois=d)
    _commit(ctx, duplicado)


def _propagar_endereco(ctx: Ctx, e: Empresa) -> None:
    """Endereço da empresa mudou: as pessoas com "usar endereço da empresa" recebem o novo (auditado)."""
    for p, a, d in servico.propagar_endereco_empresa(ctx.db, e):
        ctx.auditar("pessoa.endereco_da_empresa", "pessoa", p.id,
                    descricao=f"{p.nome}: endereço atualizado com o de {e.nome}", antes=a, depois=d)


def _inativar(ctx: Ctx, obj, entidade: str, rotulo: str) -> None:
    if obj.ativo:
        obj.ativo = False
        ctx.auditar(f"{entidade}.inativar", entidade, obj.id, descricao=rotulo, antes={"ativo": True},
                    depois={"ativo": False})
        ctx.db.commit()


# ================================================================================================= empresas
def _subq_contagens(ctx: Ctx | None = None):
    """Contagens por empresa. Com `ctx`, respeita o escopo "só meus registros" (sem ctx: visão administrativa,
    usada na detecção de duplicidades)."""
    opp_q = (select(Oportunidade.empresa_id.label("eid"), func.count().label("n"))
             .where(Oportunidade.empresa_id.is_not(None)))
    tit_q = (select(Titulo.empresa_id.label("eid"), func.count().label("n"),
                    func.coalesce(func.sum(case((Titulo.status.in_(("aberto", "parcial")), Titulo.saldo), else_=0)), 0)
                    .label("saldo"))
             .where(Titulo.direcao == "receber", Titulo.status != "cancelado"))
    if ctx is not None:
        opp_q = ctx.filtrar_meus(opp_q, Oportunidade.responsavel_id)
        tit_q = ctx.filtrar_meus(tit_q, Titulo.responsavel_id)
    return (opp_q.group_by(Oportunidade.empresa_id).subquery(), tit_q.group_by(Titulo.empresa_id).subquery())


def _ve_contagens(ctx: Ctx) -> tuple[bool, bool]:
    """(vê oportunidades, vê títulos a receber): cadastro é compartilhado, os números de cada módulo não."""
    return ctx.pode("comercial.oportunidades.ver"), ctx.pode("financeiro.titulos.ver")


def _empresa_saida(e: Empresa, *, opp: int = 0, tit: int = 0, saldo=0, resp: str | None = None,
                   categoria: str | None = None, modelo=EmpresaSaida, ve: tuple[bool, bool] = (True, True)):
    ve_opp, ve_tit = ve
    base = {c: getattr(e, c) for c in EmpresaSaida.model_fields if hasattr(e, c)}
    base.update(responsavel_nome=resp, categoria_padrao_nome=categoria, cnaes_secundarios=e.cnaes_secundarios or [],
                oportunidades=(opp or 0) if ve_opp else None, titulos_receber=(tit or 0) if ve_tit else None,
                saldo_receber=_dinheiro(saldo) if ve_tit else None, campos_custom=e.campos_custom or {})
    return modelo(**base)


def _empresa_completa(ctx: Ctx, e: Empresa, modelo=EmpresaSaida):
    opp, tit = _subq_contagens(ctx)
    n_opp = ctx.db.scalar(select(opp.c.n).where(opp.c.eid == e.id)) or 0
    linha = ctx.db.execute(select(tit.c.n, tit.c.saldo).where(tit.c.eid == e.id)).first()
    resp = ctx.db.get(Usuario, e.responsavel_id).nome if e.responsavel_id else None
    cat = ctx.db.get(Categoria, e.categoria_padrao_id).nome if e.categoria_padrao_id else None
    saida = _empresa_saida(e, opp=n_opp, tit=linha.n if linha else 0, saldo=linha.saldo if linha else 0, resp=resp,
                           categoria=cat, modelo=modelo, ve=_ve_contagens(ctx))
    if modelo is EmpresaDetalhe:
        contatos = ctx.db.scalars(select(Pessoa).where(Pessoa.empresa_id == e.id, Pessoa.ativo.is_(True))
                                  .order_by(Pessoa.nome))
        saida.contatos = [ContatoResumo.model_validate(p) for p in contatos]
    return saida


def _validar_documento(ctx: Ctx, e: Empresa | None, dados: dict) -> None:
    """Só quando o payload traz `documento`: CNPJ/CPF válido (com máscara) e não usado por outra empresa ativa.
    Documento antigo inválido não é tocado se a tela não mandar o campo."""
    if "documento" not in dados:
        return
    doc = dados["documento"] = validar_documento_cadastro(dados["documento"])
    if doc is None:
        return
    q = select(Empresa.id, Empresa.nome, Empresa.documento).where(
        Empresa.ativo.is_(True), Empresa.documento.in_(formas_do_documento(doc)))
    if e is not None:
        q = q.where(Empresa.id != e.id)
    validar_documento_livre(doc, [tuple(linha) for linha in ctx.db.execute(q).all()])


def _validar_empresa(ctx: Ctx, e: Empresa | None, dados: dict) -> dict:
    """Valida o que veio (criar: e=None) e devolve os atributos prontos para gravar."""
    if "nome" in dados:
        if dados["nome"] is None and e is not None:
            raise RegraViolada("Informe o nome da empresa.")
        dados["nome"] = servico.garantir_nome_livre(ctx.db, dados["nome"], exceto_id=e.id if e else None)
    _validar_documento(ctx, e, dados)
    if "responsavel_id" in dados:
        _usuario_existe(ctx, dados["responsavel_id"])
    if dados.get("categoria_padrao_id") is not None and ctx.db.get(Categoria, dados["categoria_padrao_id"]) is None:
        raise RegraViolada("Categoria padrão não encontrada.")
    if "papeis" in dados:
        dados["papeis"] = validar_papeis(dados["papeis"] or [])
    if "campos_custom" in dados or e is None:
        dados["campos_custom"] = servico.validar_campos_custom(
            ctx.db, "empresa", dados.get("campos_custom") or {}, e.campos_custom if e else None)
    dados = normalizar_endereco(dados)
    servico.validar_campos_padrao(ctx.db, "empresa", dados, criando=e is None)
    return dados


@router.get("/empresas", response_model=Pagina[EmpresaSaida])
def listar_empresas(ctx: Ctx, q: str | None = None, papel: Papel | None = None,
                    situacao: Situacao = "ativos", pagina: int = Query(1, ge=1),
                    por_pagina: int = Query(50, ge=1, le=200)):
    opp, tit = _subq_contagens(ctx)
    ve = _ve_contagens(ctx)
    consulta = (select(Empresa, opp.c.n, tit.c.n, tit.c.saldo, Usuario.nome)
                .outerjoin(opp, opp.c.eid == Empresa.id).outerjoin(tit, tit.c.eid == Empresa.id)
                .outerjoin(Usuario, Usuario.id == Empresa.responsavel_id))
    consulta = _situacao(consulta, Empresa.ativo, situacao)
    if q and q.strip():
        termo = q.strip()
        consulta = consulta.where(or_(Empresa.nome_chave.contains(chave_de_nome(termo)),
                                      Empresa.nome_fantasia.ilike(f"%{termo}%"),
                                      Empresa.documento.contains(termo), Empresa.segmento.ilike(f"%{termo}%")))
    if papel:
        consulta = consulta.where(getattr(Empresa, f"papel_{papel}").is_(True))
    linhas, total = _paginar(ctx, consulta.order_by(Empresa.nome_chave), pagina, por_pagina)
    itens = [_empresa_saida(e, opp=n_opp, tit=n_tit, saldo=saldo, resp=resp, ve=ve)
             for e, n_opp, n_tit, saldo, resp in linhas]
    return Pagina[EmpresaSaida](itens=itens, total=total, pagina=pagina, por_pagina=por_pagina)


@router.post("/empresas", response_model=EmpresaDetalhe, status_code=201)
def criar_empresa(dados: EmpresaCriar, ctx: Ctx):
    valores = _validar_empresa(ctx, None, dados.model_dump(exclude_unset=True))
    papeis = valores.pop("papeis", None) or ["prospect"]
    valores.setdefault("responsavel_id", ctx.usuario.id)
    e = Empresa(**valores)
    e.papeis = papeis
    ctx.db.add(e)
    ctx.db.flush()
    ctx.auditar("empresa.criar", "empresa", e.id, descricao=e.nome, depois=audit.snapshot(e))
    _commit(ctx, "Já existe empresa com este nome")
    return _empresa_completa(ctx, e, EmpresaDetalhe)


@router.get("/empresas/{empresa_id}", response_model=EmpresaDetalhe)
def ver_empresa(empresa_id: int, ctx: Ctx):
    e = _ou_404(ctx.db.get(Empresa, empresa_id), "Empresa")
    return _empresa_completa(ctx, e, EmpresaDetalhe)


@router.patch("/empresas/{empresa_id}", response_model=EmpresaDetalhe)
def atualizar_empresa(empresa_id: int, dados: EmpresaAtualizar, ctx: Ctx):
    e = _ou_404(ctx.db.get(Empresa, empresa_id), "Empresa")
    valores = _validar_empresa(ctx, e, dados.model_dump(exclude_unset=True))
    papeis = valores.pop("papeis", None)
    antes = audit.snapshot(e)
    for k, v in valores.items():
        setattr(e, k, v)
    if papeis is not None:
        e.papeis = papeis
    ctx.db.flush()
    a, d = audit.diff(antes, audit.snapshot(e))
    if a or d:
        descricao = f"{antes['nome']} → {e.nome}" if "nome" in d else e.nome
        ctx.auditar("empresa.alterar", "empresa", e.id, descricao=descricao, antes=a, depois=d)
    if any(k in d for k in CAMPOS_ENDERECO):
        _propagar_endereco(ctx, e)
    _commit(ctx, "Já existe empresa com este nome")
    return _empresa_completa(ctx, e, EmpresaDetalhe)


@router.delete("/empresas/{empresa_id}", response_model=EmpresaDetalhe)
def inativar_empresa(empresa_id: int, ctx: Ctx):
    e = _ou_404(ctx.db.get(Empresa, empresa_id), "Empresa")
    _inativar(ctx, e, "empresa", e.nome)
    return _empresa_completa(ctx, e, EmpresaDetalhe)


@router.post("/empresas/{empresa_id}/mesclar", response_model=MesclaSaida)
def mesclar_empresa(empresa_id: int, dados: MesclarIn, ctx: Ctx):
    """`empresa_id` é a que FICA; `duplicada_id` tem os vínculos movidos para ela e é inativada."""
    destino = _ou_404(ctx.db.get(Empresa, empresa_id), "Empresa")
    origem = _ou_404(ctx.db.get(Empresa, dados.duplicada_id), "Empresa duplicada")
    antes_destino, antes_origem = audit.snapshot(destino), audit.snapshot(origem)
    movidos = servico.mesclar_empresas(ctx.db, destino=destino, origem=origem, hoje=hoje())
    resumo = ", ".join(f"{k}: {v}" for k, v in movidos.items()) or "nenhum vínculo"
    a, d = audit.diff(antes_destino, audit.snapshot(destino))
    ctx.auditar("empresa.mesclar", "empresa", destino.id,
                descricao=f"“{origem.nome}” mesclada em “{destino.nome}” ({resumo})",
                antes=a, depois={**d, "vinculos_movidos": movidos, "duplicada_id": origem.id})
    a, d = audit.diff(antes_origem, audit.snapshot(origem))
    ctx.auditar("empresa.inativar", "empresa", origem.id, descricao=f"Mesclada em “{destino.nome}”", antes=a, depois=d)
    _propagar_endereco(ctx, destino)  # contatos que vieram da duplicada passam a usar o endereço da que fica
    ctx.db.commit()
    total = sum(movidos.values())
    return MesclaSaida(empresa=_empresa_completa(ctx, destino), movidos=movidos,
                       mensagem=f"Empresas mescladas: {total} vínculo(s) movido(s) para “{destino.nome}”.")


@router.get("/duplicidades", response_model=list[Duplicidade])
def duplicidades(ctx: Ctx):
    empresas = ctx.db.scalars(select(Empresa).where(Empresa.ativo.is_(True))).all()
    pares = regras.encontrar_duplicidades(
        [regras.EmpresaComparavel(e.id, e.nome, e.documento) for e in empresas])
    if not pares:
        return []
    por_id = {e.id: e for e in empresas}
    opp, tit = _subq_contagens()
    n_opp = dict(ctx.db.execute(select(opp.c.eid, opp.c.n)).all())
    n_tit = dict(ctx.db.execute(select(tit.c.eid, tit.c.n)).all())

    def curta(i: int) -> EmpresaCurta:
        e = por_id[i]
        return EmpresaCurta(id=e.id, nome=e.nome, documento=e.documento, ativo=e.ativo, oportunidades=n_opp.get(i, 0),
                            titulos=n_tit.get(i, 0))

    return [Duplicidade(a=curta(p.a), b=curta(p.b), motivo=p.motivo, semelhanca=p.semelhanca) for p in pares]


# ================================================================================================= pessoas
def _pessoa_saida(p: Pessoa, empresa: str | None, resp: str | None) -> PessoaSaida:
    s = PessoaSaida.model_validate(p)
    s.empresa_nome, s.responsavel_nome, s.campos_custom = empresa, resp, p.campos_custom or {}
    s.permissoes_comunicacao = list(p.permissoes_comunicacao or [])
    return s


def _pessoa_completa(ctx: Ctx, p: Pessoa) -> PessoaSaida:
    emp = ctx.db.get(Empresa, p.empresa_id).nome if p.empresa_id else None
    resp = ctx.db.get(Usuario, p.responsavel_id).nome if p.responsavel_id else None
    return _pessoa_saida(p, emp, resp)


def _validar_pessoa(ctx: Ctx, p: Pessoa | None, dados: dict) -> dict:
    if "nome" in dados or p is None:
        dados["nome"] = validar_nome(dados.get("nome"), o_que="o nome da pessoa")
    if dados.get("empresa_id") is not None and ctx.db.get(Empresa, dados["empresa_id"]) is None:
        raise RegraViolada("Empresa não encontrada.")
    if "responsavel_id" in dados:
        _usuario_existe(ctx, dados["responsavel_id"])
    # vários contatos: a lista manda e o campo antigo espelha o principal (sem lista, o antigo troca o principal)
    if "telefones" in dados:
        dados["telefones"] = validar_telefones(dados["telefones"])
        dados["telefone"] = principal_de(dados["telefones"], "numero")
    if "emails" in dados:
        dados["emails"] = validar_emails(dados["emails"])
        dados["email"] = principal_de(dados["emails"], "email")
    elif dados.get("email") and "@" not in dados["email"]:
        raise RegraViolada("Informe um e-mail válido.")
    servico.validar_campos_padrao(ctx.db, "pessoa", dados, criando=p is None)
    if "base_legal" in dados:
        dados["base_legal"] = validar_base_legal(dados["base_legal"])
    if "permissoes_comunicacao" in dados or p is None:
        dados["permissoes_comunicacao"] = validar_permissoes_comunicacao(dados.get("permissoes_comunicacao"))
    if "campos_custom" in dados or p is None:
        dados["campos_custom"] = servico.validar_campos_custom(
            ctx.db, "pessoa", dados.get("campos_custom") or {}, p.campos_custom if p else None)
    dados = normalizar_endereco(dados)
    # endereço e a marca "usar o da empresa" (regra pura: app.domain.cadastro.resolver_endereco_pessoa)
    marca = dados.pop("usa_endereco_da_empresa", None)
    enviado = {k: dados.pop(k) for k in CAMPOS_ENDERECO if k in dados}
    if p is None or enviado or marca is not None or "empresa_id" in dados:
        empresa_id = dados["empresa_id"] if "empresa_id" in dados else (p.empresa_id if p else None)
        empresa = ctx.db.get(Empresa, empresa_id) if empresa_id else None
        m, endereco = resolver_endereco_pessoa(
            marca_atual=p.usa_endereco_da_empresa if p else True, endereco_atual=endereco_de(p) if p else {},
            enviado=enviado, marca_enviada=marca, endereco_empresa=endereco_de(empresa) if empresa else None)
        dados.update(endereco, usa_endereco_da_empresa=m)
    return dados


@router.get("/pessoas", response_model=Pagina[PessoaSaida])
def listar_pessoas(ctx: Ctx, q: str | None = None, empresa_id: int | None = None, situacao: Situacao = "ativos",
                   base_legal: str | None = None, pagina: int = Query(1, ge=1),
                   por_pagina: int = Query(50, ge=1, le=200)):
    consulta = (select(Pessoa, Empresa.nome, Usuario.nome).outerjoin(Empresa, Empresa.id == Pessoa.empresa_id)
                .outerjoin(Usuario, Usuario.id == Pessoa.responsavel_id))
    consulta = _situacao(consulta, Pessoa.ativo, situacao)
    if base_legal:  # "sem" = pessoas sem base legal registrada
        consulta = consulta.where(Pessoa.base_legal.is_(None) if base_legal == "sem"
                                  else Pessoa.base_legal == validar_base_legal(base_legal))
    if empresa_id is not None:
        consulta = consulta.where(Pessoa.empresa_id == empresa_id)
    if q and q.strip():
        t = f"%{q.strip()}%"
        consulta = consulta.where(or_(Pessoa.nome.ilike(t), Pessoa.email.ilike(t), Pessoa.cargo.ilike(t),
                                      Pessoa.telefone.ilike(t), cast(Pessoa.emails, String).ilike(t),
                                      cast(Pessoa.telefones, String).ilike(t),
                                      Empresa.nome_chave.contains(chave_de_nome(q))))
    linhas, total = _paginar(ctx, consulta.order_by(Pessoa.nome), pagina, por_pagina)
    return Pagina[PessoaSaida](itens=[_pessoa_saida(p, emp, resp) for p, emp, resp in linhas], total=total,
                               pagina=pagina, por_pagina=por_pagina)


@router.post("/pessoas", response_model=PessoaSaida, status_code=201)
def criar_pessoa(dados: PessoaCriar, ctx: Ctx):
    valores = _validar_pessoa(ctx, None, dados.model_dump(exclude_unset=True))
    valores.setdefault("responsavel_id", ctx.usuario.id)
    p = Pessoa(**valores)
    ctx.db.add(p)
    ctx.db.flush()
    ctx.auditar("pessoa.criar", "pessoa", p.id, descricao=p.nome, depois=audit.snapshot(p))
    _commit(ctx)
    return _pessoa_completa(ctx, p)


@router.get("/pessoas/{pessoa_id}", response_model=PessoaSaida)
def ver_pessoa(pessoa_id: int, ctx: Ctx):
    return _pessoa_completa(ctx, _ou_404(ctx.db.get(Pessoa, pessoa_id), "Pessoa"))


@router.patch("/pessoas/{pessoa_id}", response_model=PessoaSaida)
def atualizar_pessoa(pessoa_id: int, dados: PessoaAtualizar, ctx: Ctx):
    p = _ou_404(ctx.db.get(Pessoa, pessoa_id), "Pessoa")
    _alterar(ctx, p, _validar_pessoa(ctx, p, dados.model_dump(exclude_unset=True)), "pessoa.alterar", "pessoa",
             "Não foi possível salvar a pessoa.")
    return _pessoa_completa(ctx, p)


@router.delete("/pessoas/{pessoa_id}", response_model=PessoaSaida)
def inativar_pessoa(pessoa_id: int, ctx: Ctx):
    p = _ou_404(ctx.db.get(Pessoa, pessoa_id), "Pessoa")
    _inativar(ctx, p, "pessoa", p.nome)
    return _pessoa_completa(ctx, p)


# ================================================================================================= produtos
def _validar_produto(ctx: Ctx, p: Produto | None, dados: dict) -> dict:
    if "nome" in dados or p is None:
        dados["nome"] = validar_nome(dados.get("nome"), o_que="o nome do produto ou serviço")
        q = select(Produto.id).where(func.lower(Produto.nome) == dados["nome"].lower())
        if p is not None:
            q = q.where(Produto.id != p.id)
        if ctx.db.scalar(q):
            raise RegraViolada("Já existe produto ou serviço com este nome.")
    if dados.get("codigo"):
        dados["codigo"] = dados["codigo"].strip()
        q = select(Produto.id).where(Produto.codigo == dados["codigo"])
        if p is not None:
            q = q.where(Produto.id != p.id)
        if ctx.db.scalar(q):
            raise RegraViolada("Já existe produto ou serviço com este código.")
    if dados.get("preco_referencia") is not None:
        dados["preco_referencia"] = _dinheiro(dados["preco_referencia"])
    if "recorrente" in dados and dados["recorrente"] is None:
        dados["recorrente"] = False
    if "tipo" in dados and dados["tipo"] is None:
        raise RegraViolada("Informe o tipo (serviço ou produto).")

    def final(campo: str, padrao=None):
        return dados[campo] if campo in dados else (getattr(p, campo) if p is not None else padrao)

    # desconto e recorrência valem sobre o estado final (o que veio + o que já estava): regras em app.domain.produto
    if p is None or {"desconto_tipo", "desconto_valor", "preco_referencia"} & dados.keys():
        dados["desconto_tipo"], dados["desconto_valor"] = validar_desconto(
            final("desconto_tipo"), final("desconto_valor"), final("preco_referencia"))
    if p is None or {"recorrente", "frequencia", "intervalo", "dias_semana"} & dados.keys():
        r = validar_recorrencia(bool(final("recorrente", False)), final("frequencia"), final("intervalo"),
                                final("dias_semana"))
        dados.update(frequencia=r.frequencia, intervalo=r.intervalo, dias_semana=r.dias_semana)
    if "campos_custom" in dados or p is None:
        dados["campos_custom"] = servico.validar_campos_custom(
            ctx.db, "produto", dados.get("campos_custom") or {}, p.campos_custom if p else None)
    servico.validar_campos_padrao(ctx.db, "produto", dados, criando=p is None)
    return dados


def _produto_saida(p: Produto) -> ProdutoSaida:
    s = ProdutoSaida.model_validate(p)
    s.dias_semana, s.campos_custom = list(p.dias_semana or []), dict(p.campos_custom or {})
    s.recorrencia_texto = descrever_recorrencia(p.recorrente, p.frequencia, p.intervalo, p.dias_semana)
    return s


@router.get("/produtos", response_model=Pagina[ProdutoSaida])
def listar_produtos(ctx: Ctx, q: str | None = None, tipo: Literal["servico", "produto"] | None = None,
                    situacao: Situacao = "ativos", pagina: int = Query(1, ge=1),
                    por_pagina: int = Query(50, ge=1, le=200)):
    consulta = _situacao(select(Produto), Produto.ativo, situacao)
    if tipo:
        consulta = consulta.where(Produto.tipo == tipo)
    if q and q.strip():
        t = f"%{q.strip()}%"
        consulta = consulta.where(or_(Produto.nome.ilike(t), Produto.codigo.ilike(t), Produto.descricao.ilike(t)))
    linhas, total = _paginar(ctx, consulta.order_by(Produto.nome), pagina, por_pagina)
    return Pagina[ProdutoSaida](itens=[_produto_saida(p) for (p,) in linhas], total=total, pagina=pagina,
                                por_pagina=por_pagina)


@router.post("/produtos", response_model=ProdutoSaida, status_code=201)
def criar_produto(dados: ProdutoCriar, ctx: Ctx):
    p = Produto(**_validar_produto(ctx, None, dados.model_dump(exclude_unset=True)))
    ctx.db.add(p)
    ctx.db.flush()
    ctx.auditar("produto.criar", "produto", p.id, descricao=p.nome, depois=audit.snapshot(p))
    _commit(ctx, "Já existe produto ou serviço com este nome ou código.")
    return _produto_saida(p)


@router.get("/produtos/{produto_id}", response_model=ProdutoSaida)
def ver_produto(produto_id: int, ctx: Ctx):
    return _produto_saida(_ou_404(ctx.db.get(Produto, produto_id), "Produto"))


@router.patch("/produtos/{produto_id}", response_model=ProdutoSaida)
def atualizar_produto(produto_id: int, dados: ProdutoAtualizar, ctx: Ctx):
    p = _ou_404(ctx.db.get(Produto, produto_id), "Produto")
    _alterar(ctx, p, _validar_produto(ctx, p, dados.model_dump(exclude_unset=True)), "produto.alterar", "produto",
             "Já existe produto ou serviço com este nome ou código.")
    return _produto_saida(p)


@router.delete("/produtos/{produto_id}", response_model=ProdutoSaida)
def inativar_produto(produto_id: int, ctx: Ctx):
    p = _ou_404(ctx.db.get(Produto, produto_id), "Produto")
    _inativar(ctx, p, "produto", p.nome)
    return _produto_saida(p)


# ================================================================================================= fornecedores
def _fornecedor_saida(ctx: Ctx, e: Empresa) -> FornecedorSaida:
    contato = ctx.db.scalar(select(Pessoa.nome).where(Pessoa.empresa_id == e.id, Pessoa.ativo.is_(True))
                            .order_by(Pessoa.id).limit(1))
    cat = ctx.db.get(Categoria, e.categoria_padrao_id).nome if e.categoria_padrao_id else None
    n = ctx.db.scalar(select(func.count()).select_from(Titulo).where(Titulo.empresa_id == e.id,
                                                                      Titulo.direcao == "pagar")) or 0
    return FornecedorSaida(id=e.id, nome=e.nome, documento=e.documento, contato=contato, email=e.email_financeiro,
                           telefone=e.telefone, categoria_padrao_id=e.categoria_padrao_id, categoria_padrao_nome=cat,
                           condicao_habitual=e.condicao_habitual, observacoes=e.observacoes, papeis=e.papeis,
                           ativo=e.ativo, titulos_pagar=n, **endereco_de(e),
                           **{c: getattr(e, c) for c in _ReceitaSaida.model_fields})


def _fornecedor(ctx: Ctx, fid: int) -> Empresa:
    e = ctx.db.get(Empresa, fid)
    if e is None or not e.papel_fornecedor:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fornecedor não encontrado.")
    return e


def _dados_fornecedor(ctx: Ctx, e: Empresa | None, dados: dict) -> tuple[dict, str | None]:
    """Traduz o formulário de fornecedor para colunas da empresa. Devolve (atributos, contato)."""
    contato = dados.pop("contato", None)
    mapa = {"email": "email_financeiro"}
    valores = {mapa.get(k, k): v for k, v in dados.items() if k not in ("empresa_id",)}
    if "nome" in valores:
        if valores["nome"] is None:
            raise RegraViolada("Informe o nome do fornecedor.")
        valores["nome"] = servico.garantir_nome_livre(ctx.db, valores["nome"], exceto_id=e.id if e else None)
    _validar_documento(ctx, e, valores)
    if valores.get("categoria_padrao_id") is not None:
        cat = ctx.db.get(Categoria, valores["categoria_padrao_id"])
        if cat is None:
            raise RegraViolada("Categoria padrão não encontrada.")
        if cat.natureza != "despesa":
            raise RegraViolada("A categoria padrão do fornecedor deve ser de despesa.")
    return normalizar_endereco(valores), contato


def _garantir_contato(ctx: Ctx, e: Empresa, contato: str | None, email: str | None, telefone: str | None) -> None:
    if not contato:
        return
    nome = validar_nome(contato, o_que="o contato")
    ja = ctx.db.scalar(select(Pessoa).where(Pessoa.empresa_id == e.id, func.lower(Pessoa.nome) == nome.lower()))
    if ja is None:
        p = Pessoa(nome=nome, empresa_id=e.id, email=email, telefone=telefone, responsavel_id=ctx.usuario.id,
                   campos_custom={}, usa_endereco_da_empresa=True, **endereco_de(e))
        ctx.db.add(p)
        ctx.db.flush()
        ctx.auditar("pessoa.criar", "pessoa", p.id, descricao=f"{nome} (contato do fornecedor {e.nome})")


@router.get("/fornecedores", response_model=Pagina[FornecedorSaida])
def listar_fornecedores(ctx: Ctx, q: str | None = None, situacao: Situacao = "ativos", pagina: int = Query(1, ge=1),
                        por_pagina: int = Query(50, ge=1, le=200)):
    consulta = _situacao(select(Empresa).where(Empresa.papel_fornecedor.is_(True)), Empresa.ativo, situacao)
    if q and q.strip():
        consulta = consulta.where(or_(Empresa.nome_chave.contains(chave_de_nome(q)),
                                      Empresa.documento.contains(q.strip())))
    linhas, total = _paginar(ctx, consulta.order_by(Empresa.nome_chave), pagina, por_pagina)
    return Pagina[FornecedorSaida](itens=[_fornecedor_saida(ctx, e) for (e,) in linhas], total=total, pagina=pagina,
                                   por_pagina=por_pagina)


@router.post("/fornecedores", response_model=FornecedorSaida, status_code=201)
def criar_fornecedor(dados: FornecedorCriar, ctx: Ctx):
    corpo = dados.model_dump(exclude_unset=True)
    if dados.empresa_id is not None:  # empresa que já existe passa a ser também fornecedor (sem duplicar cadastro)
        e = _ou_404(ctx.db.get(Empresa, dados.empresa_id), "Empresa")
        corpo.pop("nome", None)
        valores, contato = _dados_fornecedor(ctx, e, corpo)
        antes = audit.snapshot(e)
        for k, v in valores.items():
            setattr(e, k, v)
        e.papel_fornecedor = True
        ctx.db.flush()
        a, d = audit.diff(antes, audit.snapshot(e))
        ctx.auditar("empresa.alterar", "empresa", e.id, descricao=f"{e.nome} marcada como fornecedor", antes=a, depois=d)
        if any(k in d for k in CAMPOS_ENDERECO):
            _propagar_endereco(ctx, e)
    else:
        if not dados.nome:
            raise RegraViolada("Informe o nome do fornecedor.")
        valores, contato = _dados_fornecedor(ctx, None, corpo)
        e = Empresa(responsavel_id=ctx.usuario.id, campos_custom={}, **valores)
        e.papeis = ["fornecedor"]
        ctx.db.add(e)
        ctx.db.flush()
        ctx.auditar("empresa.criar", "empresa", e.id, descricao=f"{e.nome} (fornecedor)", depois=audit.snapshot(e))
    _garantir_contato(ctx, e, contato, dados.email, dados.telefone)
    _commit(ctx, "Já existe empresa com este nome")
    return _fornecedor_saida(ctx, e)


@router.get("/fornecedores/{fornecedor_id}", response_model=FornecedorSaida)
def ver_fornecedor(fornecedor_id: int, ctx: Ctx):
    return _fornecedor_saida(ctx, _fornecedor(ctx, fornecedor_id))


@router.patch("/fornecedores/{fornecedor_id}", response_model=FornecedorSaida)
def atualizar_fornecedor(fornecedor_id: int, dados: FornecedorAtualizar, ctx: Ctx):
    e = _fornecedor(ctx, fornecedor_id)
    valores, contato = _dados_fornecedor(ctx, e, dados.model_dump(exclude_unset=True))
    antes = audit.snapshot(e)
    for k, v in valores.items():
        setattr(e, k, v)
    ctx.db.flush()
    a, d = audit.diff(antes, audit.snapshot(e))
    if a or d:
        ctx.auditar("empresa.alterar", "empresa", e.id, descricao=e.nome, antes=a, depois=d)
    if any(k in d for k in CAMPOS_ENDERECO):
        _propagar_endereco(ctx, e)
    _garantir_contato(ctx, e, contato, dados.email, dados.telefone)
    _commit(ctx, "Já existe empresa com este nome")
    return _fornecedor_saida(ctx, e)


@router.delete("/fornecedores/{fornecedor_id}", response_model=FornecedorSaida)
def inativar_fornecedor(fornecedor_id: int, ctx: Ctx):
    e = _fornecedor(ctx, fornecedor_id)
    _inativar(ctx, e, "empresa", e.nome)
    return _fornecedor_saida(ctx, e)


# ================================================================================================= categorias
def _categoria_saida(ctx: Ctx, c: Categoria) -> CategoriaSaida:
    s = CategoriaSaida.model_validate(c)
    if c.superior_id:
        s.superior_nome = ctx.db.get(Categoria, c.superior_id).nome
    return s


def _validar_categoria(ctx: Ctx, c: Categoria | None, dados: dict) -> dict:
    nome = dados["nome"] = validar_nome(dados["nome"], o_que="o nome da categoria") if "nome" in dados else c.nome
    natureza = dados.get("natureza") or (c.natureza if c else None)
    if "natureza" in dados and dados["natureza"] is None:
        raise RegraViolada("Informe a natureza (receita ou despesa).")
    superior_id = dados["superior_id"] if "superior_id" in dados else (c.superior_id if c else None)
    if superior_id is not None:
        sup = ctx.db.get(Categoria, superior_id)
        if sup is None:
            raise RegraViolada("Categoria superior não encontrada.")
        if sup.natureza != natureza:
            raise RegraViolada("A categoria superior precisa ter a mesma natureza.")
        atual, vistos = sup, set()
        while atual is not None and atual.id not in vistos:  # sem ciclo: a superior não pode descender desta
            if c is not None and atual.id == c.id:
                raise RegraViolada("Uma categoria não pode ficar abaixo dela mesma.")
            vistos.add(atual.id)
            atual = ctx.db.get(Categoria, atual.superior_id) if atual.superior_id else None
    if c is not None and natureza != c.natureza and ctx.db.scalar(
            select(Categoria.id).where(Categoria.superior_id == c.id).limit(1)):
        raise RegraViolada("Categoria com subcategorias: altere a natureza delas antes.")
    q = select(Categoria.id).where(Categoria.natureza == natureza, func.lower(Categoria.nome) == nome.lower(),
                                   Categoria.superior_id.is_(None) if superior_id is None
                                   else Categoria.superior_id == superior_id)
    if c is not None:
        q = q.where(Categoria.id != c.id)
    if ctx.db.scalar(q):
        raise RegraViolada("Já existe categoria com este nome neste nível.")
    return dados


@router.get("/categorias", response_model=list[CategoriaSaida])
def listar_categorias(ctx: Ctx, q: str | None = None, natureza: Literal["receita", "despesa"] | None = None,
                      situacao: Situacao = "ativos"):
    consulta = _situacao(select(Categoria), Categoria.ativo, situacao)
    if natureza:
        consulta = consulta.where(Categoria.natureza == natureza)
    if q and q.strip():
        consulta = consulta.where(Categoria.nome.ilike(f"%{q.strip()}%"))
    cats = ctx.db.scalars(consulta.order_by(Categoria.natureza.desc(), Categoria.nome)).all()
    return [_categoria_saida(ctx, c) for c in cats]


@router.post("/categorias", response_model=CategoriaSaida, status_code=201)
def criar_categoria(dados: CategoriaCriar, ctx: Ctx):
    c = Categoria(**_validar_categoria(ctx, None, dados.model_dump(exclude_unset=True)))
    ctx.db.add(c)
    ctx.db.flush()
    ctx.auditar("categoria.criar", "categoria", c.id, descricao=c.nome, depois=audit.snapshot(c))
    _commit(ctx, "Já existe categoria com este nome neste nível.")
    return _categoria_saida(ctx, c)


@router.get("/categorias/{categoria_id}", response_model=CategoriaSaida)
def ver_categoria(categoria_id: int, ctx: Ctx):
    return _categoria_saida(ctx, _ou_404(ctx.db.get(Categoria, categoria_id), "Categoria"))


@router.patch("/categorias/{categoria_id}", response_model=CategoriaSaida)
def atualizar_categoria(categoria_id: int, dados: CategoriaAtualizar, ctx: Ctx):
    c = _ou_404(ctx.db.get(Categoria, categoria_id), "Categoria")
    _alterar(ctx, c, _validar_categoria(ctx, c, dados.model_dump(exclude_unset=True)), "categoria.alterar",
             "categoria", "Já existe categoria com este nome neste nível.")
    return _categoria_saida(ctx, c)


@router.delete("/categorias/{categoria_id}", response_model=CategoriaSaida)
def inativar_categoria(categoria_id: int, ctx: Ctx):
    c = _ou_404(ctx.db.get(Categoria, categoria_id), "Categoria")
    _inativar(ctx, c, "categoria", c.nome)
    return _categoria_saida(ctx, c)


# ================================================================================================= centros de custo
def _centro_saida(ctx: Ctx, c: CentroCusto) -> CentroSaida:
    s = CentroSaida.model_validate(c)
    if c.responsavel_id:
        s.responsavel_nome = ctx.db.get(Usuario, c.responsavel_id).nome
    return s


def _validar_centro(ctx: Ctx, c: CentroCusto | None, dados: dict) -> dict:
    if "nome" in dados or c is None:
        dados["nome"] = validar_nome(dados.get("nome"), o_que="o nome do centro de custo")
    if "codigo" in dados or c is None:
        codigo = (dados.get("codigo") or "").strip().upper()
        if not codigo:
            raise RegraViolada("Informe o código do centro de custo.")
        q = select(CentroCusto.id).where(func.upper(CentroCusto.codigo) == codigo)
        if c is not None:
            q = q.where(CentroCusto.id != c.id)
        if ctx.db.scalar(q):
            raise RegraViolada("Já existe centro de custo com este código.")
        dados["codigo"] = codigo
    if "responsavel_id" in dados:
        _usuario_existe(ctx, dados["responsavel_id"])
    return dados


@router.get("/centros-custo", response_model=list[CentroSaida])
def listar_centros(ctx: Ctx, q: str | None = None, situacao: Situacao = "ativos"):
    consulta = _situacao(select(CentroCusto), CentroCusto.ativo, situacao)
    if q and q.strip():
        t = f"%{q.strip()}%"
        consulta = consulta.where(or_(CentroCusto.nome.ilike(t), CentroCusto.codigo.ilike(t)))
    return [_centro_saida(ctx, c) for c in ctx.db.scalars(consulta.order_by(CentroCusto.codigo))]


@router.post("/centros-custo", response_model=CentroSaida, status_code=201)
def criar_centro(dados: CentroCriar, ctx: Ctx):
    c = CentroCusto(**_validar_centro(ctx, None, dados.model_dump(exclude_unset=True)))
    ctx.db.add(c)
    ctx.db.flush()
    ctx.auditar("centro_custo.criar", "centro_custo", c.id, descricao=f"{c.codigo} · {c.nome}",
                depois=audit.snapshot(c))
    _commit(ctx, "Já existe centro de custo com este código.")
    return _centro_saida(ctx, c)


@router.get("/centros-custo/{centro_id}", response_model=CentroSaida)
def ver_centro(centro_id: int, ctx: Ctx):
    return _centro_saida(ctx, _ou_404(ctx.db.get(CentroCusto, centro_id), "Centro de custo"))


@router.patch("/centros-custo/{centro_id}", response_model=CentroSaida)
def atualizar_centro(centro_id: int, dados: CentroAtualizar, ctx: Ctx):
    c = _ou_404(ctx.db.get(CentroCusto, centro_id), "Centro de custo")
    _alterar(ctx, c, _validar_centro(ctx, c, dados.model_dump(exclude_unset=True)), "centro_custo.alterar",
             "centro_custo", "Já existe centro de custo com este código.")
    return _centro_saida(ctx, c)


@router.delete("/centros-custo/{centro_id}", response_model=CentroSaida)
def inativar_centro(centro_id: int, ctx: Ctx):
    c = _ou_404(ctx.db.get(CentroCusto, centro_id), "Centro de custo")
    _inativar(ctx, c, "centro_custo", c.nome)
    return _centro_saida(ctx, c)


# ================================================================================================= contas financeiras
def _tem_movimento(ctx: Ctx, conta_id: int) -> bool:
    baixa = ctx.db.scalar(select(Baixa.id).where(Baixa.conta_id == conta_id, Baixa.estornada.is_(False)).limit(1))
    if baixa:
        return True
    return bool(ctx.db.scalar(select(Transferencia.id).where(
        or_(Transferencia.conta_origem_id == conta_id, Transferencia.conta_destino_id == conta_id)).limit(1)))


def _conta_saida(ctx: Ctx, c: ContaFinanceira) -> ContaSaida:
    s = ContaSaida.model_validate(c)
    s.tem_movimento = _tem_movimento(ctx, c.id)
    return s


def _validar_conta(ctx: Ctx, c: ContaFinanceira | None, dados: dict) -> dict:
    if "nome" in dados or c is None:
        dados["nome"] = validar_nome(dados.get("nome"), o_que="o nome da conta")
        q = select(ContaFinanceira.id).where(func.lower(ContaFinanceira.nome) == dados["nome"].lower())
        if c is not None:
            q = q.where(ContaFinanceira.id != c.id)
        if ctx.db.scalar(q):
            raise RegraViolada("Já existe conta com este nome.")
    for campo, rotulo in (("saldo_inicial", "o saldo inicial"), ("data_base", "a data-base do saldo")):
        if campo in dados and dados[campo] is None:
            raise RegraViolada(f"Informe {rotulo}.")
    if "saldo_inicial" in dados:
        dados["saldo_inicial"] = _dinheiro(dados["saldo_inicial"])
    if c is not None:
        muda_saldo = "saldo_inicial" in dados and Decimal(dados["saldo_inicial"]) != c.saldo_inicial
        muda_data = "data_base" in dados and dados["data_base"] != c.data_base
        if muda_saldo or muda_data:
            validar_edicao_conta(tem_movimento=_tem_movimento(ctx, c.id), muda_saldo_inicial=muda_saldo,
                                 muda_data_base=muda_data)
    return dados


@router.get("/contas", response_model=list[ContaSaida])
def listar_contas(ctx: Ctx, q: str | None = None, situacao: Situacao = "ativos"):
    consulta = _situacao(select(ContaFinanceira), ContaFinanceira.ativo, situacao)
    if q and q.strip():
        t = f"%{q.strip()}%"
        consulta = consulta.where(or_(ContaFinanceira.nome.ilike(t), ContaFinanceira.instituicao.ilike(t)))
    return [_conta_saida(ctx, c) for c in ctx.db.scalars(consulta.order_by(ContaFinanceira.nome))]


@router.post("/contas", response_model=ContaSaida, status_code=201)
def criar_conta(dados: ContaCriar, ctx: Ctx):
    c = ContaFinanceira(**_validar_conta(ctx, None, dados.model_dump(exclude_unset=True)))
    ctx.db.add(c)
    ctx.db.flush()
    ctx.auditar("conta_financeira.criar", "conta_financeira", c.id, descricao=c.nome, depois=audit.snapshot(c))
    _commit(ctx, "Já existe conta com este nome.")
    return _conta_saida(ctx, c)


@router.get("/contas/{conta_id}", response_model=ContaSaida)
def ver_conta(conta_id: int, ctx: Ctx):
    return _conta_saida(ctx, _ou_404(ctx.db.get(ContaFinanceira, conta_id), "Conta"))


@router.patch("/contas/{conta_id}", response_model=ContaSaida)
def atualizar_conta(conta_id: int, dados: ContaAtualizar, ctx: Ctx):
    c = _ou_404(ctx.db.get(ContaFinanceira, conta_id), "Conta")
    _alterar(ctx, c, _validar_conta(ctx, c, dados.model_dump(exclude_unset=True)), "conta_financeira.alterar",
             "conta_financeira", "Já existe conta com este nome.")
    return _conta_saida(ctx, c)


@router.delete("/contas/{conta_id}", response_model=ContaSaida)
def inativar_conta(conta_id: int, ctx: Ctx):
    c = _ou_404(ctx.db.get(ContaFinanceira, conta_id), "Conta")
    _inativar(ctx, c, "conta_financeira", c.nome)
    return _conta_saida(ctx, c)


# ================================================================================================= campos personalizados
def _campo_saida(ctx: Ctx, c: CampoCustom, preenchidos: dict | None = None) -> CampoSaida:
    s = CampoSaida.model_validate(c)
    s.opcoes = list(c.opcoes or [])
    if c.exigido_na_etapa_id:
        etapa = ctx.db.get(Etapa, c.exigido_na_etapa_id)
        s.etapa_nome = etapa.nome if etapa else None
        funil = ctx.db.get(Funil, etapa.funil_id) if etapa else None
        s.funil_id, s.funil_nome = (funil.id, funil.nome) if funil else (None, None)
    if c.exibir_funil_id:
        funil = ctx.db.get(Funil, c.exibir_funil_id)
        s.exibir_funil_nome = funil.nome if funil else None
    if c.exibir_etapa_id:
        etapa = ctx.db.get(Etapa, c.exibir_etapa_id)
        s.exibir_etapa_nome, s.exibir_etapa_ordem = (etapa.nome, etapa.ordem) if etapa else (None, None)
    s.tipo_rotulo = regras.ROTULO_TIPO.get(c.tipo, c.tipo)
    cont = preenchidos if preenchidos is not None else servico.preenchimentos(ctx.db, c.objeto)
    s.registros_preenchidos = cont.get(c.slug, 0)
    s.dependencias_ativas = sum(1 for u in servico.dependencias_do_campo(ctx.db, c, preenchidos=s.registros_preenchidos)
                                if u.ativa)
    return s


def _validar_etapa(ctx: Ctx, objeto: str, etapa_id: int | None) -> None:
    if etapa_id is None:
        return
    if objeto != "oportunidade":
        raise RegraViolada("Só campos de oportunidade podem ser exigidos por etapa.")
    etapa = ctx.db.get(Etapa, etapa_id)
    if etapa is None:
        raise RegraViolada("Etapa não encontrada. Escolha o funil e depois uma etapa dele.")
    funil = ctx.db.get(Funil, etapa.funil_id)
    if funil is None or not funil.ativo:
        raise RegraViolada("O funil desta etapa está inativo. Escolha uma etapa de um funil ativo.")


def _etapa_ref(ctx: Ctx, etapa_id: int | None, o_que: str) -> EtapaRef | None:
    if etapa_id is None:
        return None
    etapa = ctx.db.get(Etapa, etapa_id)
    if etapa is None:
        raise RegraViolada(f"Etapa {o_que} não encontrada. Escolha o funil e depois uma etapa dele.")
    return EtapaRef(etapa.id, etapa.funil_id, etapa.ordem)


def _validar_exibicao(ctx: Ctx, objeto: str, funil_id: int | None, etapa_id: int | None,
                      exigido_id: int | None) -> int | None:
    """Exibir na etapa (regra em app.domain.campos_exibicao). Devolve o funil de exibição."""
    if funil_id is not None:
        funil = ctx.db.get(Funil, funil_id)
        if funil is None or not funil.ativo:
            raise RegraViolada("Funil de exibição não encontrado ou inativo. Escolha um funil ativo.")
    return validar_exibicao(objeto=objeto, exibir_funil_id=funil_id,
                            exibir_etapa=_etapa_ref(ctx, etapa_id, "de exibição"),
                            exigido_etapa=_etapa_ref(ctx, exigido_id, "exigida"))


ObjetoCampoQuery = Literal["empresa", "pessoa", "oportunidade", "produto"]


@router.get("/campos", response_model=list[CampoSaida])
def listar_campos(ctx: Ctx, objeto: ObjetoCampoQuery | None = None, arquivados: bool = False):
    consulta = select(CampoCustom)
    if objeto:
        consulta = consulta.where(CampoCustom.objeto == objeto)
    if not arquivados:
        consulta = consulta.where(CampoCustom.arquivado.is_(False))
    campos = ctx.db.scalars(consulta.order_by(CampoCustom.objeto, CampoCustom.ordem, CampoCustom.id)).all()
    contagens = {o: servico.preenchimentos(ctx.db, o) for o in {c.objeto for c in campos}}
    return [_campo_saida(ctx, c, contagens[c.objeto]) for c in campos]


@router.get("/campos/etapas", response_model=list[EtapaOpcao])
def etapas_para_campos(ctx: Ctx):
    """Etapas de todos os funis ativos (para "exigir na etapa"). Só leitura no modelo do Comercial."""
    linhas = ctx.db.execute(select(Etapa.id, Etapa.nome, Funil.id, Funil.nome, Etapa.ordem)
                            .join(Funil, Funil.id == Etapa.funil_id)
                            .where(Funil.ativo.is_(True)).order_by(Funil.nome, Etapa.ordem)).all()
    return [EtapaOpcao(id=i, nome=n, funil_id=fid, funil_nome=f, ordem=o) for i, n, fid, f, o in linhas]


# ------------------------------------------------------------------------------- sugestão de campos e campos padrões
def _slugs(ctx: Ctx, objeto: str) -> set[str]:
    return set(ctx.db.scalars(select(CampoCustom.slug).where(CampoCustom.objeto == objeto)))


def _sugestao_saida(objeto: str, s: dom_sugeridos.Sugestao) -> CampoSugeridoSaida:
    return CampoSugeridoSaida(objeto=objeto, chave=s.chave, nome=s.nome, tipo=s.tipo,
                              tipo_rotulo=regras.ROTULO_TIPO.get(s.tipo, s.tipo), descricao=s.descricao,
                              opcoes=list(s.opcoes))


@router.get("/campos/sugestoes", response_model=list[CampoSugeridoSaida])
@router.get("/campos/sugeridos", response_model=list[CampoSugeridoSaida])
def campos_sugeridos(ctx: Ctx, objeto: ObjetoCampoQuery | None = None):
    """Modelos prontos de campo ainda não criados (sem objeto: todos os objetos)."""
    objetos = [objeto] if objeto else list(dom_sugeridos.OBJETOS)
    return [_sugestao_saida(o, s) for o in objetos for s in dom_sugeridos.disponiveis(o, _slugs(ctx, o))]


@router.post("/campos/sugeridos/{objeto}/{chave}", response_model=CampoSaida, status_code=201)
def adicionar_campo_sugerido(objeto: str, chave: str, ctx: Ctx):
    """“+ Adicionar campo”: cria o campo personalizado já configurado (vai para o fim da lista)."""
    if objeto not in dom_sugeridos.OBJETOS:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "Objeto não encontrado. Use oportunidade, empresa, pessoa ou produto.")
    if not any(s.chave == chave for s in dom_sugeridos.CATALOGO[objeto]):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sugestão de campo não encontrada.")
    s = dom_sugeridos.obter(objeto, chave, _slugs(ctx, objeto))
    opcoes = regras.validar_definicao_campo(nome=s.nome, tipo=s.tipo, objeto=objeto, opcoes=list(s.opcoes))
    ordem = (ctx.db.scalar(select(func.max(CampoCustom.ordem)).where(CampoCustom.objeto == objeto)) or 0) + 1
    c = CampoCustom(nome=s.nome, slug=s.chave, tipo=s.tipo, objeto=objeto, opcoes=opcoes, obrigatorio=False,
                    ordem=ordem)
    ctx.db.add(c)
    ctx.db.flush()
    ctx.auditar("campo_custom.criar", "campo_custom", c.id, descricao=f"{c.nome} · {c.tipo} · {c.objeto} (sugestão)",
                depois=audit.snapshot(c))
    _commit(ctx, "Já existe campo com este nome neste objeto.")
    return _campo_saida(ctx, c)


def _padrao_saida(objeto: str, e: dom_padrao.CampoEfetivo) -> CampoPadraoSaida:
    return CampoPadraoSaida(objeto=objeto, campo=e.campo, nome=e.nome, tipo=e.tipo, fixo=e.fixo,
                            obrigatorio=e.obrigatorio, visivel=e.visivel, ordem=e.ordem)


@router.get("/campos/padroes", response_model=list[CampoPadraoSaida])
def campos_padroes(ctx: Ctx, objeto: ObjetoCampoQuery | None = None):
    """Campos fixos do sistema com obrigatoriedade/visibilidade (sem objeto: todos). Livre para logados: os
    formulários escondem o invisível e exigem o obrigatório (o servidor também exige)."""
    objetos = [objeto] if objeto else list(dom_padrao.OBJETOS)
    return [_padrao_saida(o, e) for o in objetos for e in servico.campos_padrao(ctx.db, o)]


@router.patch("/campos/padroes/{objeto}/{campo}", response_model=CampoPadraoSaida)
def configurar_campo_padrao(objeto: str, campo: str, dados: CampoPadraoAtualizar, ctx: Ctx):
    if objeto not in dom_padrao.OBJETOS or not any(c.campo == campo for c in dom_padrao.CATALOGO[objeto]):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campo padrão não encontrado.")
    atual = next(e for e in servico.campos_padrao(ctx.db, objeto) if e.campo == campo)
    valores = {k: v for k, v in dados.model_dump(exclude_unset=True).items() if v is not None}
    obrigatorio = valores.get("obrigatorio", atual.obrigatorio)
    visivel = valores.get("visivel", atual.visivel)
    cat = dom_padrao.validar_alteracao(objeto, campo, obrigatorio=obrigatorio, visivel=visivel)
    cfg = ctx.db.scalar(select(CampoPadraoConfig).where(CampoPadraoConfig.objeto == objeto,
                                                        CampoPadraoConfig.campo == campo))
    chaves = ("obrigatorio", "visivel", "ordem")
    antes = ({k: getattr(cfg, k) for k in chaves} if cfg is not None
             else {"obrigatorio": atual.obrigatorio, "visivel": atual.visivel, "ordem": 0})
    if cfg is None:
        cfg = CampoPadraoConfig(objeto=objeto, campo=campo, ordem=0)
        ctx.db.add(cfg)
    cfg.obrigatorio, cfg.visivel = obrigatorio, visivel
    if "ordem" in valores:
        cfg.ordem = valores["ordem"]
    ctx.db.flush()
    a, d = audit.diff(antes, {k: getattr(cfg, k) for k in chaves})
    if a or d:
        ctx.auditar("campo_padrao.alterar", "campo_padrao_config", cfg.id, descricao=f"{cat.nome} · {objeto}",
                    antes=a, depois=d)
    _commit(ctx, "Outra pessoa alterou este campo ao mesmo tempo. Atualize a tela.")
    return _padrao_saida(objeto, next(e for e in servico.campos_padrao(ctx.db, objeto) if e.campo == campo))


@router.post("/campos", response_model=CampoSaida, status_code=201)
def criar_campo(dados: CampoCriar, ctx: Ctx):
    opcoes = regras.validar_definicao_campo(nome=dados.nome, tipo=dados.tipo, objeto=dados.objeto, opcoes=dados.opcoes)
    _validar_etapa(ctx, dados.objeto, dados.exigido_na_etapa_id)
    exibir_funil_id = _validar_exibicao(ctx, dados.objeto, dados.exibir_funil_id, dados.exibir_etapa_id,
                                        dados.exigido_na_etapa_id)
    nome = validar_nome(dados.nome, o_que="o nome do campo")
    slug = regras.slug_de(nome)
    if ctx.db.scalar(select(CampoCustom.id).where(CampoCustom.objeto == dados.objeto, CampoCustom.slug == slug)):
        raise RegraViolada("Já existe campo com este nome neste objeto.")
    c = CampoCustom(nome=nome, slug=slug, tipo=dados.tipo, objeto=dados.objeto, opcoes=opcoes,
                    obrigatorio=dados.obrigatorio, exigido_na_etapa_id=dados.exigido_na_etapa_id, ordem=dados.ordem,
                    exibir_funil_id=exibir_funil_id, exibir_etapa_id=dados.exibir_etapa_id, visivel=dados.visivel)
    ctx.db.add(c)
    ctx.db.flush()
    ctx.auditar("campo_custom.criar", "campo_custom", c.id, descricao=f"{c.nome} · {c.tipo} · {c.objeto}",
                depois=audit.snapshot(c))
    _commit(ctx, "Já existe campo com este nome neste objeto.")
    return _campo_saida(ctx, c)


@router.get("/campos/{campo_id}", response_model=CampoSaida)
def ver_campo(campo_id: int, ctx: Ctx):
    return _campo_saida(ctx, _ou_404(ctx.db.get(CampoCustom, campo_id), "Campo"))


@router.patch("/campos/{campo_id}", response_model=CampoSaida)
def atualizar_campo(campo_id: int, dados: CampoAtualizar, ctx: Ctx):
    c = _ou_404(ctx.db.get(CampoCustom, campo_id), "Campo")
    valores = dados.model_dump(exclude_unset=True)
    if "nome" in valores:
        valores["nome"] = validar_nome(valores["nome"], o_que="o nome do campo")  # o slug não muda: valores gravados
    if "opcoes" in valores:
        valores["opcoes"] = regras.validar_definicao_campo(nome=c.nome, tipo=c.tipo, objeto=c.objeto,
                                                           opcoes=valores["opcoes"])
        if c.tipo in regras.TIPOS_COM_OPCOES:
            em_uso = servico.valores_em_uso(ctx.db, c.objeto, c.slug)
            removidas = [o for o in em_uso if o not in valores["opcoes"]]
            if removidas:
                raise RegraViolada(f"A opção “{removidas[0]}” está em uso em {em_uso[removidas[0]]} registro(s). "
                                   "Altere esses registros antes de removê-la.")
    if "obrigatorio" in valores and valores["obrigatorio"] is None:
        valores["obrigatorio"] = False
    if "ordem" in valores and valores["ordem"] is None:
        valores["ordem"] = 0
    if "visivel" in valores and valores["visivel"] is None:
        valores["visivel"] = True
    if "exigido_na_etapa_id" in valores and valores["exigido_na_etapa_id"] != c.exigido_na_etapa_id:
        _validar_etapa(ctx, c.objeto, valores["exigido_na_etapa_id"])
    if "exibir_funil_id" in valores and valores["exibir_funil_id"] is None and "exibir_etapa_id" not in valores:
        valores["exibir_etapa_id"] = None  # tirou o funil: deixa de exibir por etapa
    if {"exibir_funil_id", "exibir_etapa_id", "exigido_na_etapa_id"} & valores.keys():
        final = {k: valores[k] if k in valores else getattr(c, k)
                 for k in ("exibir_funil_id", "exibir_etapa_id", "exigido_na_etapa_id")}
        valores["exibir_funil_id"] = _validar_exibicao(ctx, c.objeto, final["exibir_funil_id"],
                                                       final["exibir_etapa_id"], final["exigido_na_etapa_id"])
        valores["exibir_etapa_id"] = final["exibir_etapa_id"]
    _alterar(ctx, c, valores, "campo_custom.alterar", "campo_custom", "Já existe campo com este nome neste objeto.")
    return _campo_saida(ctx, c)


def _deps_saida(ctx: Ctx, c: CampoCustom) -> DependenciasSaida:
    usos = servico.dependencias_do_campo(ctx.db, c)
    ativas = [u for u in usos if u.ativa]
    if ativas:
        msg = (f"{len(ativas)} dependência(s) ativa(s). Revise antes de arquivar — ou confirme para arquivar mesmo "
               "assim.")
    else:
        msg = "Nenhuma dependência ativa: o campo pode ser arquivado. Os valores gravados são preservados."
    return DependenciasSaida(campo=_campo_saida(ctx, c),
                             dependencias=[Dependencia(**u.__dict__) for u in usos],
                             pode_arquivar=not ativas, mensagem=msg)


@router.get("/campos/{campo_id}/dependencias", response_model=DependenciasSaida)
def dependencias_campo(campo_id: int, ctx: Ctx):
    return _deps_saida(ctx, _ou_404(ctx.db.get(CampoCustom, campo_id), "Campo"))


@router.post("/campos/{campo_id}/arquivar", response_model=CampoSaida)
def arquivar_campo(campo_id: int, dados: ArquivarIn, ctx: Ctx):
    c = _ou_404(ctx.db.get(CampoCustom, campo_id), "Campo")
    if c.arquivado:
        raise RegraViolada("Este campo já está arquivado.")
    ativas = [u for u in servico.dependencias_do_campo(ctx.db, c) if u.ativa]
    if ativas and not dados.confirmar:
        lista = "; ".join(f"{ROTULO_USO[u.tipo]} “{u.nome}”" for u in ativas)
        raise RegraViolada(f"Campo em uso: {lista}. Revise essas dependências ou confirme o arquivamento.")
    c.arquivado = True
    descricao = c.nome + (f" (confirmado com dependências: {', '.join(u.nome for u in ativas)})" if ativas else "")
    ctx.auditar("campo_custom.arquivar", "campo_custom", c.id, descricao=descricao, antes={"arquivado": False},
                depois={"arquivado": True})
    ctx.db.commit()
    return _campo_saida(ctx, c)


@router.post("/campos/{campo_id}/restaurar", response_model=CampoSaida)
def restaurar_campo(campo_id: int, ctx: Ctx):
    c = _ou_404(ctx.db.get(CampoCustom, campo_id), "Campo")
    if c.arquivado:
        c.arquivado = False
        ctx.auditar("campo_custom.restaurar", "campo_custom", c.id, descricao=c.nome, antes={"arquivado": True},
                    depois={"arquivado": False})
        ctx.db.commit()
    return _campo_saida(ctx, c)


ROTULO_USO = {"dashboard": "Dashboard", "automacao": "Automação", "etapa": "Etapa", "registros": "Registros"}


# ================================================================================================= listas (governança)
def _tipo_lista(tipo: str) -> str:
    if tipo not in dom_listas.TIPOS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lista não encontrada. Use segmento, porte ou motivo_perda.")
    return tipo


def _opcao(ctx: Ctx, tipo: str, opcao_id: int) -> OpcaoLista:
    o = ctx.db.get(OpcaoLista, opcao_id)
    if o is None or o.tipo != _tipo_lista(tipo):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Opção não encontrada nesta lista.")
    return o


def _outros_nomes(ctx: Ctx, tipo: str, exceto_id: int | None = None) -> list[str]:
    q = select(OpcaoLista.nome).where(OpcaoLista.tipo == tipo)
    if exceto_id is not None:
        q = q.where(OpcaoLista.id != exceto_id)
    return list(ctx.db.scalars(q))


@router.get("/listas/{tipo}", response_model=list[OpcaoListaSaida])
def listar_opcoes(tipo: str, ctx: Ctx, incluir_inativos: bool = False):
    """Opções na ordem. Sem `incluir_inativos`, só as ativas (selects); com ele, todas (Governança de ajustes)."""
    return servico.opcoes_da_lista(ctx.db, _tipo_lista(tipo), so_ativas=not incluir_inativos)


@router.post("/listas/{tipo}", response_model=OpcaoListaSaida, status_code=201)
def criar_opcao(tipo: str, dados: OpcaoListaCriar, ctx: Ctx):
    tipo = _tipo_lista(tipo)
    nome = dom_listas.validar_nome_opcao(tipo, dados.nome, _outros_nomes(ctx, tipo))
    ordem = dados.ordem if dados.ordem is not None else (
        ctx.db.scalar(select(func.max(OpcaoLista.ordem)).where(OpcaoLista.tipo == tipo)) or 0) + 1
    o = OpcaoLista(tipo=tipo, nome=nome, ordem=ordem, ativo=True)
    ctx.db.add(o)
    ctx.db.flush()
    ctx.auditar("opcao_lista.criar", "opcao_lista", o.id, descricao=f"{dom_listas.ROTULO[tipo]}: {nome}",
                depois=audit.snapshot(o))
    _commit(ctx, "Já existe esta opção na lista.")
    return o


@router.post("/listas/{tipo}/reordenar", response_model=list[OpcaoListaSaida])
def reordenar_opcoes(tipo: str, dados: ReordenarIn, ctx: Ctx):
    """`ids` = todos os itens da lista (ativos e inativos), na ordem nova."""
    tipo = _tipo_lista(tipo)
    itens = {o.id: o for o in servico.opcoes_da_lista(ctx.db, tipo, so_ativas=False)}
    ids = dom_listas.validar_reordenacao(list(itens), dados.ids)
    antes = {str(o.id): o.ordem for o in itens.values()}
    for ordem, i in enumerate(ids, 1):
        itens[i].ordem = ordem
    depois = {str(o.id): o.ordem for o in itens.values()}
    if antes != depois:
        ctx.auditar("opcao_lista.reordenar", "opcao_lista", None, descricao=f"Nova ordem da lista {tipo}",
                    antes={"ordem": antes}, depois={"ordem": depois})
    ctx.db.commit()
    return servico.opcoes_da_lista(ctx.db, tipo, so_ativas=False)


@router.patch("/listas/{tipo}/{opcao_id}", response_model=OpcaoListaSaida)
def atualizar_opcao(tipo: str, opcao_id: int, dados: OpcaoListaAtualizar, ctx: Ctx):
    """Renomear não muda os cadastros que já usam o texto antigo (segmento, porte e motivo continuam texto)."""
    o = _opcao(ctx, tipo, opcao_id)
    valores = dados.model_dump(exclude_unset=True)
    if "nome" in valores:
        valores["nome"] = dom_listas.validar_nome_opcao(o.tipo, valores["nome"], _outros_nomes(ctx, o.tipo, o.id))
    for campo in ("ordem", "ativo"):
        if campo in valores and valores[campo] is None:
            raise RegraViolada(f"Informe {'a ordem' if campo == 'ordem' else 'se a opção está ativa'}.")
    _alterar(ctx, o, valores, "opcao_lista.alterar", "opcao_lista", "Já existe esta opção na lista.")
    return o


@router.delete("/listas/{tipo}/{opcao_id}", response_model=OpcaoListaSaida)
def inativar_opcao(tipo: str, opcao_id: int, ctx: Ctx):
    """Nada se exclui: a opção some dos selects e continua nos cadastros que a usam."""
    o = _opcao(ctx, tipo, opcao_id)
    _inativar(ctx, o, "opcao_lista", f"{dom_listas.ROTULO[o.tipo]}: {o.nome}")
    return o


# ================================================================================================= consultas públicas
def _consulta(funcao, *args):
    """Erros da consulta externa → 404 (não existe) / 502 (provedores fora). Inválido → RegraViolada (400)."""
    try:
        return funcao(*args)
    except consultas.ConsultaNaoEncontrada as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, e.mensagem) from None
    except consultas.ConsultaIndisponivel as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, e.mensagem) from None


@router.get("/consultas/cnpj/{cnpj}", response_model=ConsultaCnpjSaida)
def consultar_cnpj(cnpj: str, ctx: Ctx):
    """Dados públicos do CNPJ (BrasilAPI → CNPJá). Nada é gravado; `empresa_existente` avisa de duplicidade."""
    return _consulta(consultas.consultar_cnpj, cnpj, ctx.db)


@router.get("/consultas/cep/{cep}", response_model=ConsultaCepSaida)
def consultar_cep(cep: str, ctx: Ctx):
    return _consulta(consultas.consultar_cep, cep)


# ================================================================================================= sócios e anexos
storage.registrar_categoria(CATEGORIA_ANEXOS, "nucleo.cadastros.ver", storage.DOCUMENTOS, 10)


def _anexo_saida(a: EmpresaAnexo, nomes: dict[int, str]) -> AnexoSaida:
    return AnexoSaida(id=a.id, empresa_id=a.empresa_id, nome=a.nome, tipo=a.tipo, mime=a.mime, tamanho=a.tamanho,
                      enviado_por_nome=nomes.get(a.enviado_por_id), criado_em=a.criado_em, ativo=a.ativo,
                      url=f"/nucleo/empresas/{a.empresa_id}/anexos/{a.id}/arquivo")


def _anexo(ctx: Ctx, empresa_id: int, anexo_id: int) -> EmpresaAnexo:
    a = ctx.db.get(EmpresaAnexo, anexo_id)
    if a is None or a.empresa_id != empresa_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Anexo não encontrado.")
    return a


def _salvar_anexo(ctx: Ctx, e: Empresa, nome: str, conteudo: bytes, tipo: str, mime: str | None) -> EmpresaAnexo:
    try:
        caminho = storage.salvar(CATEGORIA_ANEXOS, nome, conteudo, subpasta=f"empresa_{e.id}")
    except storage.ArquivoInvalido as erro:
        raise RegraViolada(str(erro)) from None
    a = EmpresaAnexo(empresa_id=e.id, nome=nome[:200], tipo=tipo, tamanho=len(conteudo), caminho=caminho,
                     mime=(mime or mimetypes.guess_type(nome)[0] or "application/octet-stream")[:100],
                     enviado_por_id=ctx.usuario.id)
    ctx.db.add(a)
    ctx.db.flush()
    ctx.auditar("empresa_anexo.criar", "empresa", e.id, descricao=f"Anexo “{a.nome}” ({tipo}) em {e.nome}",
                depois={"anexo_id": a.id, "nome": a.nome, "tipo": tipo, "tamanho": a.tamanho})
    return a


@router.get("/empresas/{empresa_id}/socios", response_model=list[SocioSaida])
def listar_socios(empresa_id: int, ctx: Ctx):
    _ou_404(ctx.db.get(Empresa, empresa_id), "Empresa")
    return ctx.db.scalars(select(EmpresaSocio).where(EmpresaSocio.empresa_id == empresa_id)
                          .order_by(EmpresaSocio.id)).all()


@router.get("/empresas/{empresa_id}/anexos", response_model=list[AnexoSaida])
def listar_anexos(empresa_id: int, ctx: Ctx, arquivados: bool = False):
    _ou_404(ctx.db.get(Empresa, empresa_id), "Empresa")
    q = select(EmpresaAnexo).where(EmpresaAnexo.empresa_id == empresa_id)
    if not arquivados:
        q = q.where(EmpresaAnexo.ativo.is_(True))
    anexos = ctx.db.scalars(q.order_by(EmpresaAnexo.id.desc())).all()
    nomes = _nomes_usuarios(ctx, (a.enviado_por_id for a in anexos))
    return [_anexo_saida(a, nomes) for a in anexos]


@router.post("/empresas/{empresa_id}/anexos", response_model=AnexoSaida, status_code=201)
def enviar_anexo(empresa_id: int, ctx: Ctx, arquivo: UploadFile = File(...), tipo: TipoAnexo = Form("documento")):
    """PDF, imagem, .docx ou .xlsx até 10 MB (conteúdo conferido pela assinatura do arquivo)."""
    e = _ou_404(ctx.db.get(Empresa, empresa_id), "Empresa")
    conteudo = arquivo.file.read(10 * 1024 * 1024 + 1)
    a = _salvar_anexo(ctx, e, arquivo.filename or "arquivo", conteudo, tipo, arquivo.content_type)
    ctx.db.commit()
    return _anexo_saida(a, _nomes_usuarios(ctx, [a.enviado_por_id]))


@router.get("/empresas/{empresa_id}/anexos/{anexo_id}/arquivo")
def baixar_anexo(empresa_id: int, anexo_id: int, ctx: Ctx):
    a = _anexo(ctx, empresa_id, anexo_id)
    try:
        conteudo = storage.ler(a.caminho)
    except (FileNotFoundError, storage.ArquivoInvalido):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Arquivo do anexo não encontrado no armazenamento.") from None
    return Response(conteudo, media_type=a.mime or "application/octet-stream", headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(a.nome)}", "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "sandbox", "Cache-Control": "private, no-store"})


@router.delete("/empresas/{empresa_id}/anexos/{anexo_id}", response_model=AnexoSaida)
def arquivar_anexo(empresa_id: int, anexo_id: int, ctx: Ctx):
    """Nada se apaga: o anexo é arquivado (some da lista; o arquivo fica guardado)."""
    a = _anexo(ctx, empresa_id, anexo_id)
    if a.ativo:
        a.ativo = False
        ctx.auditar("empresa_anexo.arquivar", "empresa", empresa_id, descricao=f"Anexo “{a.nome}” arquivado",
                    antes={"anexo_id": a.id, "ativo": True}, depois={"anexo_id": a.id, "ativo": False})
        ctx.db.commit()
    return _anexo_saida(a, _nomes_usuarios(ctx, [a.enviado_por_id]))


def _socio_dict(s: EmpresaSocio) -> dict:
    return {"nome": s.nome, "qualificacao": s.qualificacao, "documento": s.documento,
            "data_entrada": s.data_entrada.isoformat() if s.data_entrada else None, "faixa_etaria": s.faixa_etaria}


def _dados_receita(dados: dict) -> dict:
    """Campos da Receita gravados na empresa a partir da consulta (sempre sobrescreve)."""
    abertura = dados.get("abertura")
    try:
        data_abertura = date.fromisoformat(str(abertura)[:10]) if abertura else None
    except ValueError:
        data_abertura = None
    capital = dados.get("capital_social")
    return {
        "cnae_principal": (dados.get("cnae_principal") or None) and str(dados["cnae_principal"])[:300],
        "cnaes_secundarios": [str(c) for c in dados.get("cnaes_secundarios") or [] if c],
        "natureza_juridica": (dados.get("natureza_juridica") or None) and str(dados["natureza_juridica"])[:200],
        "capital_social": _dinheiro(capital) if capital not in (None, "") else None,
        "situacao_cadastral": (dados.get("situacao") or None) and str(dados["situacao"])[:40],
        "data_abertura": data_abertura,
    }


@router.post("/empresas/{empresa_id}/cnpj/aplicar", response_model=EmpresaDetalhe)
def aplicar_cnpj(empresa_id: int, ctx: Ctx):
    """Consulta o CNPJ da empresa, substitui o quadro societário, preenche só os campos vazios (o endereço novo
    propaga para as pessoas) e anexa o PDF "Comprovante de consulta CNPJ"."""
    e = _ou_404(ctx.db.get(Empresa, empresa_id), "Empresa")
    if not cnpj_valido(e.documento):
        raise RegraViolada("Informe um CNPJ válido no cadastro da empresa antes de buscar os dados.")
    dados = _consulta(consultas.consultar_cnpj, e.documento)
    agora_br = datetime.now(ZoneInfo(settings.fuso))

    antes = audit.snapshot(e)
    for k, v in preencher_vazios({c: getattr(e, c) for c in CAMPOS_PREENCHIVEIS_CNPJ}, dados).items():
        setattr(e, k, normalizar_endereco({k: v})[k] if k in CAMPOS_ENDERECO else v)
    e.documento = dados["documento"]
    for k, v in _dados_receita(dados).items():  # dados da Receita: sempre sobrescreve
        setattr(e, k, v)
    e.receita_consultada_em = agora_br
    ctx.db.flush()
    a, d = audit.diff(antes, audit.snapshot(e))
    if a or d:
        ctx.auditar("empresa.alterar", "empresa", e.id, descricao=f"{e.nome}: dados completados pelo CNPJ "
                    f"({dados['fonte']})", antes=a, depois=d)
    if any(k in d for k in CAMPOS_ENDERECO):
        _propagar_endereco(ctx, e)

    velhos = ctx.db.scalars(select(EmpresaSocio).where(EmpresaSocio.empresa_id == e.id).order_by(EmpresaSocio.id)).all()
    socios_antes = [_socio_dict(s) for s in velhos]
    for s in velhos:
        ctx.db.delete(s)
    novos = []
    for s in dados.get("socios") or []:
        entrada = s.get("data_entrada")
        novos.append(EmpresaSocio(empresa_id=e.id, nome=(s.get("nome") or "Sócio sem nome")[:200],
                                  qualificacao=(s.get("qualificacao") or None) and s["qualificacao"][:120],
                                  documento=(s.get("documento") or None) and s["documento"][:18],
                                  data_entrada=date.fromisoformat(entrada) if entrada else None,
                                  faixa_etaria=(s.get("faixa_etaria") or None) and s["faixa_etaria"][:40]))
    ctx.db.add_all(novos)
    ctx.db.flush()
    socios_depois = [_socio_dict(s) for s in novos]
    if socios_antes != socios_depois:
        ctx.auditar("empresa.socios", "empresa", e.id, descricao=f"Quadro societário de {e.nome} pelo CNPJ "
                    f"({len(novos)} sócio(s))", antes={"socios": socios_antes}, depois={"socios": socios_depois})

    pdf = gerar_comprovante_cnpj(dados, agora_br)
    _salvar_anexo(ctx, e, f"Comprovante CNPJ {agora_br:%d-%m-%Y}.pdf", pdf, "cartao_cnpj", "application/pdf")
    _commit(ctx, "Não foi possível salvar os dados do CNPJ.")
    return _empresa_completa(ctx, e, EmpresaDetalhe)


# ================================================================================================= planilhas de migração
def _objeto_planilha(objeto: str) -> str:
    if objeto not in planilhas.OBJETOS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Planilha não encontrada. Use: " +
                            ", ".join(planilhas.OBJETOS) + ".")
    return objeto


@router.get("/planilhas/{objeto}/modelo")
def baixar_modelo_planilha(objeto: str, ctx: Ctx):
    """Modelo .xlsx: aba "Dados" (cabeçalho + linha EXEMPLO + listas de opção) e aba "Instruções"."""
    objeto = _objeto_planilha(objeto)
    return Response(planilhas.gerar_modelo(ctx.db, objeto), media_type=planilhas.TIPO_XLSX,
                    headers={"Content-Disposition": f'attachment; filename="modelo-{objeto}.xlsx"',
                             "Cache-Control": "no-store"})


@router.post("/planilhas/{objeto}/importar", response_model=ImportacaoSaida)
def importar_planilha(objeto: str, ctx: Ctx, arquivo: UploadFile = File(...), simular: bool = True):
    """`simular=true` (padrão) não grava. `simular=false` é tudo ou nada: com qualquer erro, 400 com a mesma lista e
    nada gravado."""
    objeto = _objeto_planilha(objeto)
    conteudo = arquivo.file.read(planilhas.LIMITE_BYTES + 1)
    rel = planilhas.importar(ctx.db, objeto, arquivo.filename, conteudo, usuario_id=ctx.usuario.id,
                             auditar=ctx.auditar)
    corpo = rel.como_dict()
    if simular or rel.erros:
        ctx.db.rollback()
        if rel.erros and not simular:
            return JSONResponse(status_code=400, content={
                "detail": f"A planilha tem {len(rel.erros)} erro(s). Corrija e envie de novo: nada foi gravado.",
                **corpo})
        return corpo
    ctx.auditar(f"importacao.{objeto}", "importacao", None,
                descricao=f"Planilha “{arquivo.filename or objeto}”: {rel.criar} criado(s), {rel.atualizar} "
                          f"atualizado(s), {rel.ignorar} sem mudança",
                depois={"total": rel.total, "criar": rel.criar, "atualizar": rel.atualizar, "ignorar": rel.ignorar})
    _commit(ctx, "Outra pessoa gravou dados iguais ao mesmo tempo. Simule de novo e confirme.")
    return corpo


# ================================================================================================= busca global
LIMITE_BUSCA = 5


@router.get("/busca", response_model=BuscaSaida)
def busca_global(ctx: Ctx, q: str = Query("", max_length=100)):
    """Empresas, pessoas, oportunidades e títulos (máx. 5 por tipo). Só entra o grupo que o perfil pode ver."""
    termo = q.strip()
    if len(termo) < 2:
        return BuscaSaida(termo=termo, grupos=[])
    chave, like = chave_de_nome(termo), f"%{termo}%"
    grupos: list[GrupoBusca] = []

    if ctx.pode("nucleo.cadastros.ver"):
        emp = ctx.db.scalars(select(Empresa).where(or_(Empresa.nome_chave.contains(chave),
                                                       Empresa.nome_fantasia.ilike(like),
                                                       Empresa.documento.contains(termo)))
                             .order_by(Empresa.ativo.desc(), Empresa.nome_chave).limit(LIMITE_BUSCA)).all()
        if emp:
            grupos.append(GrupoBusca(tipo="empresas", rotulo="Empresas", itens=[
                ItemBusca(id=e.id, titulo=e.nome,
                          subtitulo=" · ".join(x for x in (", ".join(e.papeis).capitalize() or None, e.segmento,
                                                            None if e.ativo else "inativa") if x) or None,
                          href=f"/nucleo/cadastros?aba=empresas&id={e.id}") for e in emp]))
        pes = ctx.db.execute(select(Pessoa, Empresa.nome).outerjoin(Empresa, Empresa.id == Pessoa.empresa_id)
                             .where(Pessoa.ativo.is_(True), or_(Pessoa.nome.ilike(like), Pessoa.email.ilike(like),
                                                       Empresa.nome_chave.contains(chave)))
                             .order_by(Pessoa.nome).limit(LIMITE_BUSCA)).all()
        if pes:
            grupos.append(GrupoBusca(tipo="pessoas", rotulo="Pessoas e contatos", itens=[
                ItemBusca(id=p.id, titulo=p.nome, subtitulo=" · ".join(x for x in (p.cargo, emp_nome) if x) or None,
                          href=f"/nucleo/cadastros?aba=pessoas&id={p.id}") for p, emp_nome in pes]))

    if ctx.pode("comercial.oportunidades.ver"):
        consulta = (select(Oportunidade, Empresa.nome).outerjoin(Empresa, Empresa.id == Oportunidade.empresa_id)
                    .where(or_(Oportunidade.titulo.ilike(like), Empresa.nome_chave.contains(chave))))
        consulta = ctx.filtrar_meus(consulta, Oportunidade.responsavel_id)
        ops = ctx.db.execute(consulta.order_by((Oportunidade.resultado == "aberta").desc(), Oportunidade.id.desc())
                             .limit(LIMITE_BUSCA)).all()
        if ops:
            rot = {"aberta": "aberta", "ganha": "ganha", "perdida": "perdida"}
            grupos.append(GrupoBusca(tipo="oportunidades", rotulo="Oportunidades", itens=[
                ItemBusca(id=o.id, titulo=o.titulo,
                          subtitulo=" · ".join(x for x in (emp_nome, rot.get(o.resultado)) if x) or None,
                          href=f"/comercial/oportunidades?id={o.id}") for o, emp_nome in ops]))

    if ctx.pode("financeiro.titulos.ver"):
        consulta = (select(Titulo, Empresa.nome).join(Empresa, Empresa.id == Titulo.empresa_id)
                    .where(or_(Titulo.descricao.ilike(like), Titulo.documento.ilike(like),
                               Empresa.nome_chave.contains(chave))))
        consulta = ctx.filtrar_meus(consulta, Titulo.responsavel_id)
        tits = ctx.db.execute(consulta.order_by(Titulo.vencimento.desc()).limit(LIMITE_BUSCA)).all()
        if tits:
            grupos.append(GrupoBusca(tipo="titulos", rotulo="Títulos", itens=[
                ItemBusca(id=t.id, titulo=f"{emp_nome} · {t.descricao}",
                          subtitulo=f"{'A receber' if t.direcao == 'receber' else 'A pagar'} · {t.status} · "
                                    f"vence {t.vencimento.strftime('%d/%m/%Y')}",
                          href=f"/financeiro/{t.direcao}?id={t.id}") for t, emp_nome in tits]))

    return BuscaSaida(termo=termo, grupos=grupos)
