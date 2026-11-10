import pytest

from app.core import links, storage
from app.core.config import settings
from tests.conftest import auth, criar_usuario, entrar

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
PDF = b"%PDF-1.4\n" + b"0" * 64


# ---------------------------------------------------------------------------------------------- storage
def test_salvar_devolve_caminho_relativo_e_le_de_volta():
    rel = storage.salvar("usuarios", "foto.PNG", PNG, nome_base="usuario_1")
    assert rel == "usuarios/usuario_1.png"
    assert not rel.startswith("/") and ":" not in rel
    assert storage.ler(rel) == PNG
    assert storage.existe(rel) and storage.resolver(rel).is_file()


def test_substituir_apaga_a_versao_anterior_de_outra_extensao():
    a = storage.salvar("usuarios", "a.png", PNG, nome_base="usuario_2")
    b = storage.salvar("usuarios", "a.jpg", b"\xff\xd8\xff" + b"0" * 32, nome_base="usuario_2", substituir=True)
    assert a != b and not storage.existe(a) and storage.existe(b)


@pytest.mark.parametrize("nome,conteudo,trecho", [
    ("script.html", b"<script>alert(1)</script>", "Tipo de arquivo"),
    ("img.svg", b"<svg onload=alert(1)/>", "Tipo de arquivo"),
    ("falsa.png", b"isto nao e uma imagem", "não corresponde"),
    ("vazia.png", b"", "vazio"),
    ("sem_extensao", PNG, "Tipo de arquivo"),
])
def test_validacao_de_extensao_e_conteudo(nome, conteudo, trecho):
    with pytest.raises(storage.ArquivoInvalido, match=trecho):
        storage.salvar("usuarios", nome, conteudo)


def test_validacao_de_tamanho():
    with pytest.raises(storage.ArquivoInvalido, match="no máximo 4 MB"):
        storage.salvar("usuarios", "g.png", PNG + b"0" * (4 * 1024 * 1024))


def test_categoria_desconhecida_e_recusada():
    with pytest.raises(storage.ArquivoInvalido):
        storage.salvar("nao_existe", "a.png", PNG)


@pytest.mark.parametrize("ruim", ["../segredo.txt", "usuarios/../../x", "/etc/passwd", "C:/Windows/win.ini", "usuarios\\x.png",
                                  "usuarios//x.png", "usuarios/./x.png", "", "a\x00b"])
def test_path_traversal_e_caminhos_absolutos_sao_recusados(ruim):
    with pytest.raises(storage.ArquivoInvalido):
        storage.resolver(ruim)


def test_categoria_registrada_por_modulo():
    storage.registrar_categoria("documentos_teste", "financeiro.baixas.ver", storage.DOCUMENTOS, 1)
    rel = storage.salvar("documentos_teste", "laudo.pdf", PDF, subpasta="titulo_7")
    assert rel.startswith("documentos_teste/titulo_7/") and rel.endswith(".pdf")
    assert storage.categoria_do_caminho(rel).permissao == "financeiro.baixas.ver"


# ---------------------------------------------------------------------------------------------- rota autenticada
def test_arquivo_so_por_rota_autenticada_e_com_permissao(client, db, admin):
    storage.registrar_categoria("documentos_teste", "financeiro.baixas.ver", storage.DOCUMENTOS, 1)
    rel = storage.salvar("documentos_teste", "laudo.pdf", PDF)
    assert client.get(f"/api/arquivos/{rel}").status_code == 401  # sem login
    adm = entrar(client, "admin@exemplo.com").json()["access_token"]
    r = client.get(f"/api/arquivos/{rel}", headers=auth(adm))
    assert r.status_code == 200 and r.content == PDF
    assert r.headers["x-content-type-options"] == "nosniff"
    # Comercial não tem financeiro.baixas.ver
    criar_usuario(db, "Comercial", email="prof@exemplo.com")
    prof = entrar(client, "prof@exemplo.com").json()["access_token"]
    assert client.get(f"/api/arquivos/{rel}", headers=auth(prof)).status_code == 403
    # categoria sem permissão específica (fotos) qualquer logado lê; traversal e inexistente dão 404
    foto = storage.salvar("usuarios", "f.png", PNG)
    assert client.get(f"/api/arquivos/{foto}", headers=auth(prof)).status_code == 200
    assert client.get("/api/arquivos/usuarios/nao-existe.png", headers=auth(prof)).status_code == 404
    assert client.get("/api/arquivos/..%2f..%2fsegredo", headers=auth(prof)).status_code == 404
    assert client.get("/api/arquivos/categoria_inexistente/x.png", headers=auth(prof)).status_code == 404


def test_foto_do_usuario_pela_api_nao_vaza_caminho_absoluto(client, db, admin):
    h = auth(entrar(client, "admin@exemplo.com").json()["access_token"])
    r = client.post("/api/auth/me/foto", headers=h, files={"arquivo": ("eu.png", PNG, "image/png")})
    assert r.status_code == 200 and r.json()["foto_url"].startswith("/auth/usuarios/")
    db.expire_all()
    from app.core.models import Usuario

    caminho = db.get(Usuario, admin.id).foto_path
    assert caminho == f"usuarios/usuario_{admin.id}.png"  # RELATIVO ao storage
    assert client.get(f"/api/auth/usuarios/{admin.id}/foto", headers=h).content == PNG
    ruim = client.post("/api/auth/me/foto", headers=h, files={"arquivo": ("x.exe", b"MZ", "application/octet-stream")})
    assert ruim.status_code == 400


# ---------------------------------------------------------------------------------------------- link assinado
def test_link_assinado_ida_e_volta():
    t = links.assinar("arquivo", {"p": "recibos/1.pdf"}, 60, agora_s=1000)
    assert links.verificar(t, "arquivo", agora_s=1030) == {"p": "recibos/1.pdf"}


def test_link_expira():
    t = links.assinar("arquivo", {"p": "x"}, 60, agora_s=1000)
    with pytest.raises(links.LinkExpirado):
        links.verificar(t, "arquivo", agora_s=1061)


def test_link_adulterado_ou_de_outra_finalidade_e_recusado():
    t = links.assinar("arquivo", {"p": "recibos/1.pdf"}, 600)
    corpo, mac = t.split(".")
    with pytest.raises(links.LinkInvalido):
        links.verificar(f"{corpo}x.{mac}", "arquivo")
    with pytest.raises(links.LinkInvalido):
        links.verificar(f"{corpo}.{mac[:-2]}aa", "arquivo")
    with pytest.raises(links.LinkInvalido):
        links.verificar(t, "contrato")  # token de uma finalidade não vale em outra
    for lixo in ("", "a.b", "sem-ponto", "...."):
        with pytest.raises(links.LinkInvalido):
            links.verificar(lixo, "arquivo")


def test_link_publico_serve_o_arquivo_sem_login_ate_expirar(client, monkeypatch):
    storage.registrar_categoria("recibos_teste", "financeiro_receber.ver", storage.DOCUMENTOS, 1)
    rel = storage.salvar("recibos_teste", "recibo.pdf", PDF)
    url = storage.link_publico(rel, nome_download="recibo.pdf")
    assert url.startswith("/api/arquivos-publicos/")
    r = client.get(url)
    assert r.status_code == 200 and r.content == PDF
    assert "attachment" in r.headers["content-disposition"] and "no-store" in r.headers["cache-control"]
    # expirado
    vencido = storage.link_publico(rel, validade_s=-1)
    assert client.get(vencido).status_code == 404
    # adulterado / caminho forjado com assinatura válida de outra coisa
    assert client.get(url[:-3] + "xyz").status_code == 404
    forjado = links.assinar("arquivo", {"p": "../../etc/passwd"}, 60)
    assert client.get(f"/api/arquivos-publicos/{forjado}").status_code == 404
    assert settings.link_assinado_horas > 0


def test_link_publico_exige_categoria_conhecida():
    with pytest.raises(storage.ArquivoInvalido):
        storage.link_publico("pasta_qualquer/x.pdf")
