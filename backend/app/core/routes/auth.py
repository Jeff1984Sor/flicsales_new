"""Autenticação. `publico` = sem login (rate limit); `router` = conta do usuário logado."""

import json
from typing import Any

import jwt
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import or_, select

from app.core import audit, envio, perfis, segredos, storage, tenancy
from app.core import auth_service as svc
from app.core import email as mail
from app.core.db import agora
from app.core.deps import DB, Ctx, ip_cliente
from app.core.models import ConfigEmailUsuario, Identidade, PerfilAcesso, Usuario
from app.core.organizacao_http import definir_pelo_token, endereco_bloqueado
from app.core.ratelimit import limitar, verificar
from app.core.schemas import (
    EmailUsuarioIn,
    EmailUsuarioOut,
    EnvioMeOut,
    ForgotIn,
    LoginIn,
    Mensagem,
    MePatch,
    OrganizacaoInfo,
    PrimeiroAcessoIn,
    PrimeiroAcessoInfo,
    RefreshIn,
    ResetCodigoIn,
    ResetIn,
    TesteEmailOut,
    TokenOut,
    TrocarSenhaIn,
    UsuarioMe,
)
from app.domain import RegraViolada

publico = APIRouter(prefix="/auth", tags=["auth"])
router = APIRouter(prefix="/auth", tags=["auth"])

MSG_FORGOT = "Se a conta existir, enviamos as instruções para redefinir a senha."


def foto_url(u: Usuario) -> str | None:
    if not storage.existe(u.foto_path):
        return None
    return f"/auth/usuarios/{u.id}/foto?v={storage.versao(u.foto_path)}"


def organizacao_info() -> OrganizacaoInfo | None:
    """A organização do pedido (um banco por organização); None com um banco só."""
    org = tenancy.atual()
    if not tenancy.multi() or org is None:
        return None
    from app.controle import service

    dados = service.info(org.slug)
    return OrganizacaoInfo(**dados) if dados else None


def organizacao_do_login(identificador: str) -> bool:
    """Um banco por organização: ela vem do endereço (já definida no pedido) ou, no endereço principal, do catálogo de
    logins. False = login inexistente, de organização inativa ou repetido em mais de uma (aí só pelo endereço da
    organização). Quem chama responde com a MESMA mensagem genérica (não revela nada)."""
    if not tenancy.multi() or tenancy.atual() is not None:
        return True
    if endereco_bloqueado():  # endereço de organização inativa: não entra por ali (nem cai no catálogo)
        return False
    from app.controle import service

    org = service.por_login(identificador)
    if org is None:
        return False
    tenancy.definir(org)
    return True


def assinatura_imagem_url(u: Usuario) -> str | None:
    if not storage.existe(u.assinatura_imagem):
        return None
    return f"/auth/me/assinatura-imagem?v={storage.versao(u.assinatura_imagem)}"


def me_out(u: Usuario) -> UsuarioMe:
    return UsuarioMe.model_validate(u).model_copy(update={
        "organizacao": organizacao_info(),
        "foto_url": foto_url(u), "assinatura_imagem_url": assinatura_imagem_url(u), "administrador": u.administrador, "permissoes": sorted(u.permissoes),
        "perfil_acesso_nome": u.perfil_acesso.nome if u.perfil_acesso else None,
        "somente_meus_registros": bool(u.perfil_acesso and not u.administrador and u.perfil_acesso.somente_meus_registros)})


def _tokens(db, u: Usuario) -> TokenOut:
    access, refresh = svc.emitir_tokens(db, u)
    return TokenOut(access_token=access, refresh_token=refresh, usuario=me_out(u))


# ------------------------------------------------------------------------------------------- públicas
@publico.post("/login", response_model=TokenOut, dependencies=[Depends(limitar("login", 20, 60))])
def login(dados: LoginIn, request: Request, db: DB):
    if not organizacao_do_login(dados.identificador):
        verificar(request, "login-conta", 30, 900, chave=dados.identificador.strip().lower())
        svc.gastar_tempo_de_verificacao(dados.senha)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, svc.MSG_LOGIN)
    # além do limite por IP, limita por identificador (ataque distribuído contra uma conta)
    verificar(request, "login-conta", 30, 900, chave=dados.identificador.strip().lower(), db=db)
    u = svc.autenticar(db, dados.identificador, dados.senha, ip_cliente(request))
    out = _tokens(db, u)
    db.commit()
    return out


@publico.post("/refresh", response_model=TokenOut, dependencies=[Depends(limitar("refresh", 60, 60))])
def refresh(dados: RefreshIn, request: Request, db: DB):
    if tenancy.multi() and definir_pelo_token(dados.refresh_token) is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, svc.MSG_SESSAO)
    u, access, refresh_token = svc.rotacionar_refresh(db, dados.refresh_token, ip_cliente(request))
    return TokenOut(access_token=access, refresh_token=refresh_token, usuario=me_out(u))


@publico.post("/forgot", response_model=Mensagem, dependencies=[Depends(limitar("forgot", 5, 900))])
def forgot(dados: ForgotIn, request: Request, db: DB):
    """Recuperação por e-mail. A resposta é a mesma exista a conta ou não."""
    if not organizacao_do_login(dados.identificador):
        return Mensagem(mensagem=MSG_FORGOT)
    verificar(request, "forgot-conta", 3, 3600, chave=dados.identificador.strip().lower(), db=db)
    u = svc.localizar(db, dados.identificador)
    if u and u.ativo and u.acesso_sistema:
        svc.enviar_link_email(db, u)
        db.commit()
    return Mensagem(mensagem=MSG_FORGOT)


@publico.post("/reset", response_model=Mensagem, dependencies=[Depends(limitar("reset", 10, 900))])
def reset(dados: ResetIn, request: Request, db: DB):
    svc.redefinir_por_token(db, dados.token, dados.senha, ip_cliente(request))
    db.commit()
    return Mensagem(mensagem="Senha definida. Você já pode entrar.")


@publico.post("/forgot-codigo", response_model=Mensagem, dependencies=[Depends(limitar("forgot-codigo", 5, 900))])
def forgot_codigo(dados: ForgotIn, request: Request, db: DB):
    """Recuperação por código enviado ao WhatsApp cadastrado. Resposta igual exista a conta (ou o telefone) ou não."""
    msg = Mensagem(mensagem="Se a conta existir e tiver WhatsApp cadastrado, enviamos um código.")
    if not organizacao_do_login(dados.identificador):
        return msg
    verificar(request, "forgot-codigo-conta", 3, 3600, chave=dados.identificador.strip().lower(), db=db)
    u = svc.localizar(db, dados.identificador)
    if u and u.ativo and u.acesso_sistema:
        svc.enviar_codigo_whatsapp(db, u)
        db.commit()
    return msg


@publico.post("/reset-codigo", response_model=Mensagem, dependencies=[Depends(limitar("reset-codigo", 10, 900))])
def reset_codigo(dados: ResetCodigoIn, request: Request, db: DB):
    if not organizacao_do_login(dados.identificador):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, svc.MSG_RESET_INVALIDO)
    svc.redefinir_por_codigo(db, dados.identificador, dados.codigo, dados.senha, ip_cliente(request))
    db.commit()
    return Mensagem(mensagem="Senha definida. Você já pode entrar.")


# ------------------------------------------------------------------------------- primeiro acesso (organização nova)
MSG_PRIMEIRO_INVALIDO = "Link inválido ou expirado. Peça um novo à FlicSales."


def _organizacao_sem_gestor(token: str, db) -> dict[str, Any]:
    """O link de boas-vindas (token assinado `primeiro`, 7 dias, com a organização na claim `org`) vale enquanto a
    organização não tem nenhum usuário administrador (Gestor)."""
    erro = HTTPException(status.HTTP_400_BAD_REQUEST, MSG_PRIMEIRO_INVALIDO)
    try:
        payload = svc.decodificar_token(token, "primeiro")
    except jwt.PyJWTError:
        raise erro from None
    if tenancy.multi() and (definir_pelo_token(token) is None or not tenancy.token_da_organizacao_atual(payload)):
        raise erro
    tem_gestor = db.scalar(select(Usuario.id).join(PerfilAcesso, Usuario.perfil_acesso_id == PerfilAcesso.id)
                           .where(PerfilAcesso.administrador.is_(True)).limit(1))
    if tem_gestor:
        raise HTTPException(status.HTTP_409_CONFLICT, "O Gestor desta organização já foi criado. Entre com ele.")
    return payload


@publico.get("/primeiro-acesso", response_model=PrimeiroAcessoInfo,
             dependencies=[Depends(limitar("primeiro-acesso", 30, 900))])
def ler_primeiro_acesso(token: str, db: DB):
    payload = _organizacao_sem_gestor(token, db)
    ident = db.scalar(select(Identidade).order_by(Identidade.id))
    return PrimeiroAcessoInfo(organizacao=ident.nome_exibicao if ident else "", email=payload.get("email"))


@publico.post("/primeiro-acesso", response_model=TokenOut, dependencies=[Depends(limitar("primeiro-acesso", 30, 900))])
def primeiro_acesso(dados: PrimeiroAcessoIn, request: Request, db: DB):
    """Cria o Gestor (perfil administrador) com o login e a senha escolhidos e já entra. Vale uma vez só."""
    _organizacao_sem_gestor(dados.token, db)
    if erro := svc.validar_politica_senha(dados.senha):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, erro)
    email, login = str(dados.email).strip().lower(), dados.login.strip().lower()
    if db.scalar(select(Usuario.id).where(or_(Usuario.email == email, Usuario.login == login))):
        raise HTTPException(status.HTTP_409_CONFLICT, "Este e-mail ou login já existe nesta organização. Escolha outro.")
    gestor = next(p for p in perfis.garantir_padrao(db).values() if p.administrador)
    u = Usuario(nome=dados.nome.strip(), email=email, login=login, perfil_acesso_id=gestor.id,
                senha_hash=svc.hash_senha(dados.senha), convite_pendente=False, ultimo_acesso=agora())
    db.add(u)
    db.flush()
    audit.registrar(db, usuario=u, acao="auth.primeiro_acesso", entidade="usuario", entidade_id=u.id,
                    ip=ip_cliente(request), descricao="Gestor criado pelo link de boas-vindas")
    out = _tokens(db, u)
    db.commit()
    return out


# ------------------------------------------------------------------------------------------- conta logada
@router.post("/trocar-senha", response_model=TokenOut)
def trocar_senha(dados: TrocarSenhaIn, ctx: Ctx):
    """Exige a senha atual. Derruba as outras sessões e devolve tokens novos para esta."""
    svc.trocar_senha(ctx.db, ctx.usuario, dados.senha_atual, dados.nova_senha, ctx.ip)
    out = _tokens(ctx.db, ctx.usuario)
    ctx.db.commit()
    return out


@router.post("/logout", response_model=Mensagem)
def logout(ctx: Ctx):
    """Encerra TODAS as sessões do usuário (invalida access e refresh em circulação)."""
    svc.invalidar_sessoes(ctx.db, ctx.usuario)
    ctx.auditar("auth.logout", "usuario", ctx.usuario.id)
    ctx.db.commit()
    return Mensagem(mensagem="Sessões encerradas.")


@router.get("/me", response_model=UsuarioMe)
def me(ctx: Ctx):
    return me_out(ctx.usuario)


@router.patch("/me", response_model=UsuarioMe)
def alterar_me(dados: MePatch, ctx: Ctx):
    valores = dados.model_dump(exclude_unset=True)
    if "assinatura_email" in valores:  # vazio = sem assinatura própria (vale a da Identidade)
        valores["assinatura_email"] = (valores["assinatura_email"] or "").strip() or None
    antes = audit.snapshot(ctx.usuario)
    for k, v in valores.items():
        setattr(ctx.usuario, k, v)
    a, d = audit.diff(antes, audit.snapshot(ctx.usuario))
    ctx.auditar("usuario.alterar_proprio", "usuario", ctx.usuario.id, antes=a, depois=d)
    ctx.db.commit()
    return me_out(ctx.usuario)


@router.put("/me/preferencias", response_model=UsuarioMe)
def salvar_preferencias(dados: dict[str, Any], ctx: Ctx):
    """Mescla as preferências enviadas (ex.: {"menu_recolhido": ["Cadastros"]}). Valor null remove a chave."""
    atual = dict(ctx.usuario.preferencias or {})
    for k, v in dados.items():
        if v is None:
            atual.pop(k, None)
        else:
            atual[str(k)[:60]] = v
    if len(json.dumps(atual)) > 20_000:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Preferências grandes demais.")
    ctx.usuario.preferencias = atual
    ctx.db.commit()
    return me_out(ctx.usuario)


async def salvar_foto(u: Usuario, arquivo: UploadFile) -> None:
    conteudo = await arquivo.read(4 * 1024 * 1024 + 1)
    try:
        u.foto_path = storage.salvar("usuarios", arquivo.filename or "", conteudo, nome_base=f"usuario_{u.id}", substituir=True)
    except storage.ArquivoInvalido as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e


@router.post("/me/foto", response_model=UsuarioMe)
async def enviar_foto(ctx: Ctx, arquivo: UploadFile = File(...)):
    await salvar_foto(ctx.usuario, arquivo)
    ctx.auditar("usuario.foto", "usuario", ctx.usuario.id, descricao="Nova foto de perfil")
    ctx.db.commit()
    return me_out(ctx.usuario)


@router.delete("/me/foto", response_model=UsuarioMe)
def remover_foto(ctx: Ctx):
    storage.remover(ctx.usuario.foto_path)
    ctx.usuario.foto_path = None
    ctx.db.commit()
    return me_out(ctx.usuario)


@router.post("/me/assinatura-imagem", response_model=UsuarioMe)
async def enviar_assinatura_imagem(ctx: Ctx, arquivo: UploadFile = File(...)):
    """Imagem da assinatura de e-mail (PNG ou JPG até 1 MB). Substitui a anterior."""
    u = ctx.usuario
    conteudo = await arquivo.read(1024 * 1024 + 1)
    try:
        u.assinatura_imagem = storage.salvar("assinaturas", arquivo.filename or "", conteudo,
                                             nome_base=f"usuario_{u.id}", substituir=True)
    except storage.ArquivoInvalido as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    ctx.auditar("usuario.assinatura_imagem", "usuario", u.id, descricao="Nova imagem da assinatura de e-mail",
                depois={"assinatura_imagem": u.assinatura_imagem})
    ctx.db.commit()
    return me_out(u)


@router.delete("/me/assinatura-imagem", response_model=UsuarioMe)
def remover_assinatura_imagem(ctx: Ctx):
    u = ctx.usuario
    if not u.assinatura_imagem:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Você não tem imagem de assinatura.")
    antes = u.assinatura_imagem
    storage.remover(u.assinatura_imagem)
    u.assinatura_imagem = None
    ctx.auditar("usuario.assinatura_imagem", "usuario", u.id, descricao="Imagem da assinatura de e-mail removida",
                antes={"assinatura_imagem": antes}, depois={"assinatura_imagem": None})
    ctx.db.commit()
    return me_out(u)


@router.get("/me/assinatura-imagem")
def assinatura_imagem(ctx: Ctx):
    if not storage.existe(ctx.usuario.assinatura_imagem):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sem imagem de assinatura. Envie uma em Minha conta.")
    return FileResponse(storage.resolver(ctx.usuario.assinatura_imagem),
                        headers={"Cache-Control": "private, max-age=86400"})


# ------------------------------------------------- e-mail de envio do próprio usuário (contrato de envio 11/2026)
def _email_usuario_out(c: ConfigEmailUsuario | None) -> EmailUsuarioOut:
    if c is None:
        return EmailUsuarioOut(configurado=False)
    senha = segredos.decifrar_texto(c.smtp_senha_cifrada) if c.smtp_senha_cifrada else None
    return EmailUsuarioOut(configurado=True, ativo=c.ativo, remetente_nome=c.remetente_nome,
                           remetente_email=c.remetente_email, smtp_host=c.smtp_host, smtp_porta=c.smtp_porta,
                           smtp_usuario=c.smtp_usuario, senha_final=segredos.mascarar(senha))


@router.get("/me/email", response_model=EmailUsuarioOut)
def ler_email_usuario(ctx: Ctx):
    """SMTP próprio (opcional). Sem ele, os e-mails do usuário saem pela organização com resposta para ele."""
    return _email_usuario_out(ctx.db.get(ConfigEmailUsuario, ctx.usuario.id))


@router.put("/me/email", response_model=EmailUsuarioOut)
def salvar_email_usuario(dados: EmailUsuarioIn, ctx: Ctx):
    c = ctx.db.get(ConfigEmailUsuario, ctx.usuario.id)
    novo = c is None
    if novo:
        c = ConfigEmailUsuario(usuario_id=ctx.usuario.id)
        ctx.db.add(c)
    antes = {} if novo else audit.snapshot(c)
    valores = dados.model_dump()
    senha = (valores.pop("smtp_senha") or "").strip()
    valores["remetente_nome"] = valores["remetente_nome"].strip()
    valores["smtp_host"] = valores["smtp_host"].strip()
    valores["smtp_usuario"] = (valores["smtp_usuario"] or "").strip() or None
    for k, v in valores.items():
        setattr(c, k, v)
    if senha:
        c.smtp_senha_cifrada = segredos.cifrar_texto(senha)
    ctx.db.flush()
    a, d = audit.diff(antes, audit.snapshot(c))
    ctx.auditar("email_usuario.alterar", "config_email_usuario", c.usuario_id, antes=a, depois=d,
                descricao="E-mail de envio próprio" + (" (senha SMTP alterada)" if senha else ""))
    ctx.db.commit()
    return _email_usuario_out(c)


@router.delete("/me/email", response_model=EmailUsuarioOut)
def remover_email_usuario(ctx: Ctx):
    """Volta a usar o e-mail da organização (com resposta para o usuário). A senha guardada é descartada."""
    c = ctx.db.get(ConfigEmailUsuario, ctx.usuario.id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Você não tem e-mail de envio próprio.")
    antes = audit.snapshot(c)
    ctx.db.delete(c)
    ctx.auditar("email_usuario.remover", "config_email_usuario", ctx.usuario.id, antes=antes,
                descricao="E-mail de envio próprio removido: volta a usar o da organização")
    ctx.db.commit()
    return _email_usuario_out(None)


@router.post("/me/email/testar", response_model=TesteEmailOut)
def testar_email_usuario(ctx: Ctx, dados: EmailUsuarioIn | None = None):
    """Conecta e faz login no SMTP (nada é enviado). Sem corpo testa o que está salvo; com corpo testa o formulário
    antes de salvar (senha vazia = usa a salva)."""
    c = ctx.db.get(ConfigEmailUsuario, ctx.usuario.id)
    if dados is None:
        if c is None:
            raise RegraViolada("Salve o e-mail de envio antes de testar.")
        smtp = mail.smtp_de_config_usuario(c)
    else:
        senha = (dados.smtp_senha or "").strip() or (
            segredos.decifrar_texto(c.smtp_senha_cifrada) if c is not None and c.smtp_senha_cifrada else None)
        smtp = mail.Smtp(dados.smtp_host.strip(), dados.smtp_porta, (dados.smtp_usuario or "").strip() or None, senha,
                         f"{dados.remetente_nome} <{dados.remetente_email}>", "usuario")
    ok, mensagem = mail.testar_login(smtp)
    return TesteEmailOut(ok=ok, mensagem=mensagem)


@router.get("/me/envio", response_model=EnvioMeOut)
def envio_do_usuario(ctx: Ctx):
    """Como os e-mails do usuário sairiam agora (a tela mostra "Enviar como …" e habilita o botão)."""
    v = envio.via_de_envio(ctx.db, ctx.usuario)
    return EnvioMeOut(pode_enviar=v.pode_enviar, via=v.via, remetente=v.remetente)


def _usuario(ctx, uid: int) -> Usuario:
    u = ctx.db.get(Usuario, uid)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado.")
    return u


@router.post("/usuarios/{uid}/foto", response_model=Mensagem)
async def enviar_foto_de(uid: int, ctx: Ctx, arquivo: UploadFile = File(...)):
    """Quem pode editar usuários troca a foto de outro (ex.: pessoa sem login)."""
    u = _usuario(ctx, uid)
    await salvar_foto(u, arquivo)
    ctx.auditar("usuario.foto", "usuario", u.id, descricao=f"Foto de {u.nome} trocada por {ctx.usuario.nome}")
    ctx.db.commit()
    return Mensagem(mensagem=f"Foto de {u.nome} atualizada.")


@router.delete("/usuarios/{uid}/foto", response_model=Mensagem)
def remover_foto_de(uid: int, ctx: Ctx):
    u = _usuario(ctx, uid)
    storage.remover(u.foto_path)
    u.foto_path = None
    ctx.auditar("usuario.foto", "usuario", u.id, descricao=f"Foto de {u.nome} removida por {ctx.usuario.nome}")
    ctx.db.commit()
    return Mensagem(mensagem="Foto removida.")


@router.get("/usuarios/{uid}/foto")
def foto(uid: int, ctx: Ctx):
    u = _usuario(ctx, uid)
    if not storage.existe(u.foto_path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sem foto.")
    return FileResponse(storage.resolver(u.foto_path), headers={"Cache-Control": "private, max-age=86400"})
