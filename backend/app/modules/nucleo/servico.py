"""Serviços do Núcleo que OUTROS módulos chamam. Assinaturas estáveis — mudar exige combinar com o coordenador.

- `obter_ou_criar_empresa(db, nome, ...)`  empresa nascendo dentro da oportunidade (nome basta; sem duplicar).
- `validar_campos_custom(db, objeto, enviados, atuais=None)`  valida o JSON `campos_custom` de empresa/pessoa/
  oportunidade contra o catálogo `campo_custom` e devolve o dicionário final (levanta `RegraViolada` → 400).
- `vinculos_da_empresa(db, empresa_id)` / `mesclar_empresas(db, destino=, origem=)`  qualidade dos dados.
- `dependencias_do_campo(db, campo)`  onde um campo personalizado é usado (dashboards, automações, etapas).
- `propagar_endereco_empresa(db, empresa)`  endereço da empresa mudou → pessoas com `usa_endereco_da_empresa`
  recebem o novo (devolve o que mudou para o chamador auditar como `pessoa.endereco_da_empresa`).

Nenhuma função faz commit: a rota (ou o módulo chamador) audita e confirma.
"""

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import Column, Table, select, update
from sqlalchemy.orm import Session

from app.core.db import Base
from app.domain import RegraViolada
from app.domain.cadastro import (
    PAPEIS_EMPRESA,
    PessoaEndereco,
    chave_de_nome,
    endereco_de,
    endereco_vazio,
    propagar_endereco,
    validar_nome,
    validar_papeis,
)
from app.modules.nucleo.models import CampoCustom, Empresa, Pessoa
from app.modules.nucleo.regras import DefCampo
from app.modules.nucleo.regras import validar_campos_custom as _validar

# ------------------------------------------------------------------------------------------------- empresa


def empresa_com_nome(db: Session, nome: str, *, exceto_id: int | None = None) -> Empresa | None:
    """Empresa (ativa ou não) cujo nome normalizado colide com `nome`."""
    q = select(Empresa).where(Empresa.nome_chave == chave_de_nome(nome))
    if exceto_id is not None:
        q = q.where(Empresa.id != exceto_id)
    return db.scalar(q)


def garantir_nome_livre(db: Session, nome: str, *, exceto_id: int | None = None) -> str:
    """Limpa o nome e recusa duplicidade ("Já existe empresa com este nome")."""
    limpo = validar_nome(nome, o_que="o nome da empresa")
    if empresa_com_nome(db, limpo, exceto_id=exceto_id) is not None:
        raise RegraViolada("Já existe empresa com este nome")
    return limpo


def obter_ou_criar_empresa(db: Session, nome: str, *, responsavel_id: int | None = None,
                           papeis: list[str] | None = None) -> tuple[Empresa, bool]:
    """Devolve (empresa, criada). Se já existe empresa com o mesmo nome normalizado, devolve ELA (sem duplicar) e
    acrescenta os `papeis` pedidos. Só faz flush."""
    limpo = validar_nome(nome, o_que="o nome da empresa")
    existente = empresa_com_nome(db, limpo)
    if existente is not None:
        if papeis:
            existente.papeis = sorted(set(existente.papeis) | set(validar_papeis(papeis)), key=PAPEIS_EMPRESA.index)
            db.flush()
        return existente, False
    e = Empresa(nome=limpo, responsavel_id=responsavel_id, campos_custom={})
    e.papeis = validar_papeis(papeis or ["prospect"])
    db.add(e)
    db.flush()
    return e, True


def propagar_endereco_empresa(db: Session, empresa: Empresa) -> list[tuple[Pessoa, dict, dict]]:
    """Copia o endereço da empresa para as pessoas vinculadas com a marca ligada (regra em
    app.domain.cadastro.propagar_endereco). Devolve [(pessoa, antes, depois)] de quem mudou. Só flush; quem chama
    audita (`pessoa.endereco_da_empresa`) e confirma."""
    pessoas = {p.id: p for p in db.scalars(select(Pessoa).where(Pessoa.empresa_id == empresa.id))}
    mudancas = propagar_endereco(endereco_de(empresa), [
        PessoaEndereco(p.id, p.usa_endereco_da_empresa, endereco_de(p)) for p in pessoas.values()])
    out = []
    for pid, novo in mudancas:
        p = pessoas[pid]
        antes = endereco_de(p)
        for k, v in novo.items():
            setattr(p, k, v)
        out.append((p, {k: v for k, v in antes.items() if novo[k] != v}, {k: v for k, v in novo.items() if antes[k] != v}))
    db.flush()
    return out


# ------------------------------------------------------------------------------------------------- campos custom


def definicoes(db: Session, objeto: str) -> list[DefCampo]:
    campos = db.scalars(select(CampoCustom).where(CampoCustom.objeto == objeto).order_by(CampoCustom.ordem,
                                                                                          CampoCustom.id))
    return [DefCampo(slug=c.slug, nome=c.nome, tipo=c.tipo, opcoes=tuple(c.opcoes or ()), obrigatorio=c.obrigatorio,
                     arquivado=c.arquivado) for c in campos]


def validar_campos_custom(db: Session, objeto: str, enviados: dict[str, Any] | None,
                          atuais: dict[str, Any] | None = None, *, exigir_obrigatorios: bool = True) -> dict[str, Any]:
    """Valida `enviados` (parcial: None apaga a chave) sobre `atuais` e devolve o JSON final para gravar."""
    return _validar(definicoes(db, objeto), enviados, atuais, exigir_obrigatorios=exigir_obrigatorios)


def _modelo_do_objeto(objeto: str):
    if objeto == "empresa":
        return Empresa
    if objeto == "pessoa":
        return Pessoa
    from app.modules.comercial.models import Oportunidade

    return Oportunidade


def preenchimentos(db: Session, objeto: str) -> Counter:
    """Quantos registros do objeto têm cada slug preenchido (contagem em Python: JSON portátil SQLite/Postgres)."""
    modelo = _modelo_do_objeto(objeto)
    c: Counter = Counter()
    for valores in db.scalars(select(modelo.campos_custom)):
        for k, v in (valores or {}).items():
            if v not in (None, ""):
                c[k] += 1
    return c


def valores_em_uso(db: Session, objeto: str, slug: str) -> Counter:
    modelo = _modelo_do_objeto(objeto)
    c: Counter = Counter()
    for valores in db.scalars(select(modelo.campos_custom)):
        v = (valores or {}).get(slug)
        if v not in (None, ""):
            c[str(v)] += 1
    return c


@dataclass
class Uso:
    tipo: str  # dashboard | automacao | etapa | registros
    id: int | None
    nome: str
    detalhe: str
    ativa: bool


def _automacao_usa(a: Any, campo: CampoCustom) -> bool:
    alvo = (a.campo or "").strip().lower()
    nomes = {campo.slug, f"{campo.objeto}.{campo.slug}", f"campos_custom.{campo.slug}",
             f"{campo.objeto}.campos_custom.{campo.slug}", str(campo.id), f"campo:{campo.id}"}
    if alvo and alvo in nomes:
        return True
    variavel = re.compile(r"\{\{\s*" + re.escape(f"{campo.objeto}.{campo.slug}") + r"\s*\}\}")
    return bool(variavel.search(a.conteudo or ""))


def dependencias_do_campo(db: Session, campo: CampoCustom, *, preenchidos: int | None = None) -> list[Uso]:
    """Onde o campo é usado. Só leitura nos modelos dos outros módulos. `ativa=True` bloqueia o arquivamento sem
    confirmação (indicador ativo, automação ativa, etapa que exige o campo)."""
    from app.modules.comercial.models import Etapa, Funil, IndicadorConfig
    from app.modules.orquestracao.models import Automacao

    usos: list[Uso] = []
    for ind in db.scalars(select(IndicadorConfig).where(IndicadorConfig.filtro_campo_id == campo.id)):
        filtro = f" = {ind.filtro_valor}" if ind.filtro_valor else ""
        usos.append(Uso("dashboard", ind.id, ind.nome, f"Indicador filtra por {campo.nome}{filtro}", ind.ativo))
    for a in db.scalars(select(Automacao).order_by(Automacao.id)):
        if _automacao_usa(a, campo):
            usos.append(Uso("automacao", a.id, a.nome, f"Automação {a.area} · estado {a.estado}", a.estado == "ativa"))
    if campo.exigido_na_etapa_id:
        etapa = db.get(Etapa, campo.exigido_na_etapa_id)
        if etapa is not None:
            funil = db.get(Funil, etapa.funil_id)
            usos.append(Uso("etapa", etapa.id, f"{funil.nome if funil else 'Funil'} · {etapa.nome}",
                            "A etapa exige este campo para avançar", True))
    n = preenchidos if preenchidos is not None else preenchimentos(db, campo.objeto).get(campo.slug, 0)
    if n:
        usos.append(Uso("registros", None, f"{n} registro(s) preenchido(s)",
                        "Os valores ficam guardados; arquivar só tira o campo dos formulários.", False))
    return usos


# ------------------------------------------------------------------------------------------------- qualidade dos dados


def referencias_a_empresa() -> list[tuple[Table, Column]]:
    """Todas as colunas (de qualquer módulo) com FK para `empresa.id` — lidas do metadata, então tabela nova de outro
    módulo entra sozinha na mesclagem."""
    refs = []
    for tabela in Base.metadata.sorted_tables:
        for fk in tabela.foreign_keys:
            if fk.column.table.name == "empresa" and fk.column.name == "id":
                refs.append((tabela, fk.parent))
    return refs


def vinculos_da_empresa(db: Session, empresa_id: int) -> dict[str, int]:
    """{"tabela.coluna": quantidade} de registros que apontam para a empresa."""
    from sqlalchemy import func

    out = {}
    for tabela, coluna in referencias_a_empresa():
        n = db.scalar(select(func.count()).select_from(tabela).where(coluna == empresa_id)) or 0
        if n:
            out[f"{tabela.name}.{coluna.name}"] = n
    return out


_COPIAVEIS = ("documento", "nome_fantasia", "segmento", "porte", "site", "email_financeiro", "telefone", "endereco",
              "responsavel_id", "origem", "categoria_padrao_id", "condicao_habitual")


def mesclar_empresas(db: Session, *, destino: Empresa, origem: Empresa, hoje: date) -> dict[str, int]:
    """Move TODOS os vínculos de `origem` para `destino` (UPDATE em cada FK para empresa), completa os campos vazios do
    destino com os da origem, une papéis e campos personalizados (o destino prevalece) e inativa a origem.
    Devolve {"tabela.coluna": movidos}. Só flush."""
    if destino.id == origem.id:
        raise RegraViolada("Escolha duas empresas diferentes para mesclar.")
    if not destino.ativo:
        raise RegraViolada("A empresa que fica precisa estar ativa.")
    movidos: dict[str, int] = {}
    for tabela, coluna in referencias_a_empresa():
        r = db.execute(update(tabela).where(coluna == origem.id).values({coluna.name: destino.id}))
        if r.rowcount:
            movidos[f"{tabela.name}.{coluna.name}"] = r.rowcount
    for campo in _COPIAVEIS:
        if getattr(destino, campo) in (None, "") and getattr(origem, campo) not in (None, ""):
            setattr(destino, campo, getattr(origem, campo))
    if endereco_vazio(endereco_de(destino)) and not endereco_vazio(endereco_de(origem)):  # endereço vem inteiro
        for k, v in endereco_de(origem).items():
            setattr(destino, k, v)
    destino.papeis = [p for p in PAPEIS_EMPRESA if p in set(destino.papeis) | set(origem.papeis)]
    destino.campos_custom = {**(origem.campos_custom or {}), **(destino.campos_custom or {})}
    if origem.observacoes:
        destino.observacoes = "\n".join(x for x in (destino.observacoes, f"[{origem.nome}] {origem.observacoes}") if x)
    origem.ativo = False
    nota = f"Mesclada em “{destino.nome}” em {hoje.strftime('%d/%m/%Y')}."
    origem.observacoes = "\n".join(x for x in (origem.observacoes, nota) if x)
    db.flush()
    # o UPDATE em massa não atualiza objetos já carregados na sessão: recarregue-os (as FKs mudaram no banco)
    for obj in list(db.identity_map.values()):
        if obj is not destino and obj is not origem:
            db.expire(obj)
    return movidos
