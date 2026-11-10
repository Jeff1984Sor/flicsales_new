"""Regras do banco de controle: achar a organização (por slug, domínio ou login), o catálogo de logins e a criação do
banco de uma organização nova. Portado do MayaFit (app/controle/service.py), só o mínimo (sem planos/cobrança).

API estável: por_slug, por_host, por_login, host_conhecido, ativas, info, limpar_cache, normalizar_host, RegraControle,
SLUG, ATIVOS, registrar, adicionar_dominio, dominio_padrao, nome_do_banco, criar_banco, migrar, migrar_controle,
migrar_todos, provisionar, endereco_da_organizacao, definir_status, registrar_principal_se_faltar,
sincronizar_usuario, chave_do_usuario, sincronizar_todos.
"""

import logging
import re
import time
import unicodedata

from sqlalchemy import delete, select, text

from app.controle.models import Dominio, Login, OrganizacaoCliente, SessaoControle
from app.core import tenancy
from app.core.tenancy import Organizacao

log = logging.getLogger(__name__)

SLUG = re.compile(r"^[a-z][a-z0-9-]{1,38}$")
# Viram subdomínio (<slug>.<DOMINIO_BASE>) e nome de banco (<BANCO_PREFIXO><slug>): não podem colidir com infraestrutura.
RESERVADOS = frozenset({"admin", "www", "api", "app", "mail", "email", "smtp", "ftp", "hml", "prod", "dev", "teste",
                        "controle", "flicsales", "suporte", "status", "static", "cdn", "site", "bff"})
ATIVOS = ("ativo", "suspenso")  # suspensa continua entrando (só avisa); inativa não entra
STATUS = ("ativo", "suspenso", "inativo")
_LOGIN = re.compile(r"^[a-z0-9._-]{3,60}$")
_cache: dict[tuple[str, str], tuple[float, object]] = {}
_TTL = 60


class RegraControle(ValueError):
    """Regra do controle violada; a mensagem já está pronta para o usuário."""


def _org(c: OrganizacaoCliente | None) -> Organizacao | None:
    return Organizacao(slug=c.slug, banco=c.banco) if c and c.status in ATIVOS else None


def _memo(tipo: str, chave: str, buscar):
    agora = time.monotonic()
    hit = _cache.get((tipo, chave))
    if hit and agora - hit[0] < _TTL:
        return hit[1]
    valor = buscar()
    _cache[(tipo, chave)] = (agora, valor)
    return valor


def limpar_cache() -> None:
    _cache.clear()


def normalizar_host(host: str) -> str:
    return (host or "").split(":")[0].strip().lower().rstrip(".")


# ---------------------------------------------------------------- achar a organização
def por_slug(slug: str) -> Organizacao | None:
    """Organização que pode entrar (ativa/suspensa); None se não existe ou está inativa."""
    def buscar():
        with SessaoControle() as db:
            return _org(db.scalar(select(OrganizacaoCliente).where(OrganizacaoCliente.slug == slug)))
    return _memo("slug", slug, buscar)


def por_host(host: str) -> Organizacao | None:
    host = normalizar_host(host)

    def buscar():
        with SessaoControle() as db:
            d = db.scalar(select(Dominio).where(Dominio.host == host))
            return _org(d.organizacao) if d else None
    return _memo("host", host, buscar) if host else None


def host_conhecido(host: str) -> bool:
    """O domínio está cadastrado no controle (qualquer status)? Usado na conferência do Host."""
    host = normalizar_host(host)

    def buscar():
        with SessaoControle() as db:
            return db.scalar(select(Dominio.id).where(Dominio.host == host)) is not None
    return bool(_memo("host-conhecido", host, buscar)) if host else False


def por_login(login: str) -> Organizacao | None:
    """Catálogo de logins (no endereço principal). Só resolve quando o login existe em UMA organização que pode
    entrar; repetido em mais de uma → None (a pessoa entra pelo endereço da organização). Sem cache."""
    chave = (login or "").strip().lower()
    if not chave:
        return None
    with SessaoControle() as db:
        orgs = db.scalars(select(OrganizacaoCliente).join(Login, Login.organizacao_id == OrganizacaoCliente.id).where(
            Login.chave == chave, OrganizacaoCliente.status.in_(ATIVOS))).all()
        return _org(orgs[0]) if len(orgs) == 1 else None


def ativas() -> list[Organizacao]:
    with SessaoControle() as db:
        return [o for c in db.scalars(select(OrganizacaoCliente).order_by(OrganizacaoCliente.id)) if (o := _org(c))]


def info(slug: str) -> dict | None:
    """Resumo da organização para o /api/auth/me: slug, nome, status."""
    def buscar():
        with SessaoControle() as db:
            c = db.scalar(select(OrganizacaoCliente).where(OrganizacaoCliente.slug == slug))
            return {"slug": c.slug, "nome": c.nome, "status": c.status} if c else None
    return _memo("info", slug, buscar)


# ---------------------------------------------------------------- catálogo de logins
def _org_id(db, slug: str) -> int:
    oid = db.scalar(select(OrganizacaoCliente.id).where(OrganizacaoCliente.slug == slug))
    if oid is None:
        raise RegraControle(f"Organização {slug} não existe no controle.")
    return oid


def sincronizar_usuario(slug: str, usuario_id: int, login: str | None) -> None:
    """Deixa no catálogo exatamente o login deste usuário (None = tira: sem login, inativo ou sem acesso)."""
    chave = (login or "").strip().lower() or None
    with SessaoControle() as db:
        oid = _org_id(db, slug)
        for x in db.scalars(select(Login).where(Login.organizacao_id == oid, Login.usuario_id == usuario_id)):
            if x.chave != chave:
                db.delete(x)
        if chave:
            x = db.get(Login, (chave, oid))
            if x is None:
                db.add(Login(chave=chave, organizacao_id=oid, usuario_id=usuario_id))
            else:
                x.usuario_id = usuario_id
        db.commit()


def chave_do_usuario(u) -> str | None:
    """O que vai para o catálogo: o login de quem pode entrar."""
    return u.login if u.login and u.ativo and u.acesso_sistema else None


def sincronizar_todos(slug: str) -> int:
    """Reconstrói o catálogo da organização a partir dos usuários do banco dela."""
    from app.core.db import SessionLocal
    from app.core.models import Usuario

    org = _organizacao_qualquer_status(slug)
    with tenancy.usando(org), SessionLocal() as s:
        usuarios = [(u.id, chave_do_usuario(u)) for u in s.scalars(select(Usuario))]
    with SessaoControle() as db:
        oid = _org_id(db, slug)
        db.execute(delete(Login).where(Login.organizacao_id == oid))
        for uid, chave in usuarios:
            if chave and db.get(Login, (chave.lower(), oid)) is None:
                db.add(Login(chave=chave.lower(), organizacao_id=oid, usuario_id=uid))
                db.flush()
        db.commit()
    return len(usuarios)


# ---------------------------------------------------------------- organizações
def _validar_slug(slug: str) -> None:
    if not SLUG.match(slug or ""):
        raise RegraControle("Identificador: letras minúsculas, números e hífen (2 a 39), começando com letra.")
    if slug in RESERVADOS:
        raise RegraControle(f"O identificador {slug} é reservado do sistema. Escolha outro.")


def registrar(slug: str, nome: str, *, banco: str | None, status: str = "ativo",
              dominios: list[str] | None = None) -> OrganizacaoCliente:
    _validar_slug(slug)
    if status not in STATUS:
        raise RegraControle(f"Status inválido: {status}.")
    with SessaoControle() as db:
        if db.scalar(select(OrganizacaoCliente).where(OrganizacaoCliente.slug == slug)):
            raise RegraControle(f"Já existe a organização {slug}.")
        if banco is None and db.scalar(select(OrganizacaoCliente).where(OrganizacaoCliente.banco.is_(None))):
            raise RegraControle("Já existe uma organização no banco principal.")
        c = OrganizacaoCliente(slug=slug, nome=nome, banco=banco, status=status)
        db.add(c)
        db.flush()
        for host in dict.fromkeys(normalizar_host(h) for h in (dominios or []) if h):
            adicionar_dominio(db, c, host)
        db.commit()
        limpar_cache()
        return c


def adicionar_dominio(db, org: OrganizacaoCliente, host: str) -> Dominio:
    host = normalizar_host(host)
    if not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", host):
        raise RegraControle(f"Domínio inválido: {host}")
    if db.scalar(select(Dominio).where(Dominio.host == host)):
        raise RegraControle(f"O domínio {host} já está em uso.")
    d = Dominio(organizacao_id=org.id, host=host)
    db.add(d)
    db.flush()
    limpar_cache()
    return d


def dominio_padrao(slug: str) -> str | None:
    """`<slug>.<DOMINIO_BASE>` (None sem DOMINIO_BASE no .env do servidor)."""
    from app.core.config import settings

    base = normalizar_host(settings.dominio_base or "")
    return f"{slug}.{base}" if base else None


def nome_do_banco(slug: str) -> str:
    """`<BANCO_PREFIXO><slug>` (hífen vira _). Prefixo do .env: hml e prod coexistem no mesmo servidor."""
    from app.core.config import settings

    return settings.banco_prefixo + slug.replace("-", "_")


def criar_banco(banco: str) -> None:
    """CREATE DATABASE no mesmo servidor do principal (no SQLite o arquivo nasce na primeira conexão)."""
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from sqlalchemy.exc import ProgrammingError

    from app.core.config import settings

    url = make_url(settings.database_url)
    if url.get_backend_name() == "sqlite":
        return
    if not re.match(r"^[a-z][a-z0-9_]{1,62}$", banco):
        raise RegraControle("Nome de banco inválido.")
    adm = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with adm.connect() as conn:
            if not conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": banco}):
                conn.execute(text(f'CREATE DATABASE "{banco}"'))
    except ProgrammingError as e:
        if "permission denied" in str(e).lower():
            raise RegraControle(f"O servidor do banco não deixa a FlicSales criar bancos. Rode: "
                                f"ALTER ROLE {url.username} CREATEDB;") from e
        raise
    finally:
        adm.dispose()


def migrar(org: Organizacao) -> None:
    """Aplica as migrations do sistema (alembic/) no banco da organização."""
    from alembic.config import Config

    from alembic import command
    from app.core.config import BASE_DIR

    cfg = Config(str(BASE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BASE_DIR / "alembic"))
    cfg.attributes["configure_logger"] = False
    with tenancy.engine_do(org.banco).connect() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
        conn.commit()


def migrar_controle() -> None:
    """Cria/atualiza as tabelas do banco de controle (alembic_controle/)."""
    from alembic.config import Config

    from alembic import command
    from app.core.config import BASE_DIR

    cfg = Config(str(BASE_DIR / "alembic_controle.ini"))
    cfg.set_main_option("script_location", str(BASE_DIR / "alembic_controle"))
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")


def migrar_todos() -> list[str]:
    """Controle + o banco de cada organização (o principal é migrado pelo deploy de sempre). Devolve as migradas."""
    migrar_controle()
    try:
        registrar_principal_se_faltar()
    except RegraControle:
        log.exception("Não foi possível registrar a organização do banco principal no controle")
    feitos = []
    for org in ativas():
        if org.banco is not None:
            migrar(org)
            feitos.append(org.slug)
    return feitos


def _slugificar(texto: str) -> str:
    s = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:39].strip("-")
    s = s if SLUG.match(s) else (f"org-{s}"[:39].strip("-") if s else "org")
    return f"org-{s}" if s in RESERVADOS else s


def provisionar(slug: str, nome: str, *, admin_email: str, admin_login: str | None = None, admin_nome: str = "",
                admin_senha: str | None = None, dominios: list[str] | None = None,
                primeiro_acesso: bool = False) -> tuple[OrganizacaoCliente, str]:
    """Organização nova: banco próprio, tabelas, identidade (nome), perfis padrão e:
    - com `primeiro_acesso`: devolve o link de boas-vindas (quem contratou cria o Gestor; `admin_email` só o recebe);
    - senão: cria o Gestor (com `admin_senha` → devolve ""; sem senha → devolve o link do convite).
    Com DOMINIO_BASE, o subdomínio entra sozinho. Sem organização pela metade em caso de erro."""
    from app.core import audit, perfis
    from app.core.db import SessionLocal
    from app.core.models import Identidade, Usuario
    from app.core.security import hash_senha, validar_politica_senha

    email = (admin_email or "").strip().lower()
    login = (admin_login or "").strip().lower()
    if not email or "@" not in email:
        raise RegraControle("Informe o e-mail do Gestor.")
    if not primeiro_acesso and not _LOGIN.match(login):
        raise RegraControle("Login: letras minúsculas, números, ponto, hífen ou sublinhado (3 a 60).")
    if admin_senha and (erro := validar_politica_senha(admin_senha)):
        raise RegraControle(erro)
    _validar_slug(slug)
    with SessaoControle() as db:
        if db.scalar(select(OrganizacaoCliente.id).where(OrganizacaoCliente.slug == slug)):
            raise RegraControle(f"Já existe a organização {slug}.")
    hosts = list(dominios or [])
    if (padrao := dominio_padrao(slug)) and padrao not in [normalizar_host(h) for h in hosts]:
        hosts.insert(0, padrao)
    banco = nome_do_banco(slug)
    criar_banco(banco)  # antes de registrar: sem banco, a organização não pode existir no controle
    org_c = registrar(slug, nome, banco=banco, dominios=hosts)
    org = Organizacao(slug=slug, banco=banco)
    try:
        migrar(org)
        with tenancy.usando(org), SessionLocal() as db:
            db.add(Identidade(id=1, nome_exibicao=nome))
            gestor = next(p for p in perfis.garantir_padrao(db).values() if p.administrador)
            if primeiro_acesso:
                db.commit()
                return org_c, link_primeiro_acesso(slug, email)
            u = Usuario(nome=admin_nome or nome, email=email, login=login, perfil_acesso_id=gestor.id,
                        senha_hash=hash_senha(admin_senha) if admin_senha else None, convite_pendente=not admin_senha)
            db.add(u)
            db.flush()
            audit.registrar(db, usuario=None, acao="usuario.criar_provisionamento", entidade="usuario",
                            entidade_id=u.id, descricao="Gestor criado junto com a organização")
            link = ""
            if not admin_senha:
                from app.core import auth_service

                link = auth_service.criar_link_email(db, u)
            db.commit()
    except Exception:
        with SessaoControle() as db:  # não deixa organização pela metade no controle
            db.execute(delete(Login).where(Login.organizacao_id == org_c.id))
            db.execute(delete(Dominio).where(Dominio.organizacao_id == org_c.id))
            db.execute(delete(OrganizacaoCliente).where(OrganizacaoCliente.id == org_c.id))
            db.commit()
        limpar_cache()
        raise
    sincronizar_todos(slug)
    return org_c, link


def link_primeiro_acesso(slug: str, email: str) -> str:
    """Link de boas-vindas (vale 7 dias). O token assinado carrega a organização (`org`)."""
    from app.core.security import criar_token

    with tenancy.usando(_organizacao_qualquer_status(slug)):
        token = criar_token(slug, "primeiro", {"email": (email or "").strip().lower()})
    return f"{endereco_da_organizacao(slug)}/primeiro-acesso?token={token}"


def _organizacao_qualquer_status(slug: str) -> Organizacao:
    with SessaoControle() as db:
        c = db.scalar(select(OrganizacaoCliente).where(OrganizacaoCliente.slug == slug))
        if c is None:
            raise RegraControle(f"Organização {slug} não existe.")
        return Organizacao(slug=c.slug, banco=c.banco)


def endereco_da_organizacao(slug: str | None = None) -> str:
    """URL base do frontend para links (convite, redefinir senha): o endereço da organização (`<slug>.<DOMINIO_BASE>`
    se cadastrado, senão o 1º domínio dela), com o esquema e a porta do FRONTEND_URL. Sem domínio: o FRONTEND_URL."""
    from urllib.parse import urlsplit, urlunsplit

    from app.core.config import settings

    base = settings.frontend_url.rstrip("/")
    slug = slug or (tenancy.atual().slug if tenancy.atual() else None)
    if not slug or not tenancy.multi():
        return base

    def buscar():
        with SessaoControle() as db:
            hosts = list(db.scalars(select(Dominio.host).join(OrganizacaoCliente)
                                    .where(OrganizacaoCliente.slug == slug).order_by(Dominio.id)))
        padrao = dominio_padrao(slug)
        return padrao if padrao in hosts else (hosts[0] if hosts else None)

    host = _memo("endereco", slug, buscar)
    if not host:
        return base
    partes = urlsplit(base)
    netloc = f"{host}:{partes.port}" if partes.port else host
    return urlunsplit((partes.scheme, netloc, partes.path, "", "")).rstrip("/")


def definir_status(slug: str, status: str) -> OrganizacaoCliente:
    """ativo | suspenso | inativo (inativa não entra; o cache curto é limpo na hora)."""
    if status not in STATUS:
        raise RegraControle(f"Status inválido: {status}.")
    with SessaoControle() as db:
        c = db.scalar(select(OrganizacaoCliente).where(OrganizacaoCliente.slug == slug))
        if c is None:
            raise RegraControle(f"Organização {slug} não existe.")
        c.status = status
        db.commit()
    limpar_cache()
    return c


# ---------------------------------------------------------------- primeira ativação
def registrar_principal_se_faltar(slug: str | None = None) -> str | None:
    """Primeira ativação: a organização que já mora no banco principal (há Identidade lá) entra no controle com
    banco=None e com os logins, antes de a API reiniciar no modo novo — ninguém fica sem acesso."""
    from sqlalchemy import inspect
    from sqlalchemy.orm import Session

    from app.core.models import Identidade

    with SessaoControle() as db:
        if db.scalar(select(OrganizacaoCliente.id).where(OrganizacaoCliente.banco.is_(None))):
            return None
    eng = tenancy.engine_do(None)
    if not inspect(eng).has_table("identidade"):
        return None
    with Session(eng) as db:
        ident = db.scalar(select(Identidade).order_by(Identidade.id))
        if ident is None:
            return None
        nome = ident.nome_exibicao
    slug = slug or _slugificar(nome)
    registrar(slug, nome, banco=None)
    sincronizar_todos(slug)
    return slug
