"use client";

/**
 * Núcleo › Integrações › WhatsApp pela Evolution API (servidor da própria organização).
 *
 * `GET  /orquestracao/integracoes/whatsapp/evolution`            → ConfigEvolution
 * `PUT  …/whatsapp/evolution` {url, apikey?, instancia?}         (API key somente escrita: vazio = manter)
 * `POST …/whatsapp/evolution/instancias` {url?, apikey?}         → InstanciaEvolution[] (usa o salvo se vazio)
 * `POST …/whatsapp/evolution/testar`                             → TesteEvolution
 * `POST …/whatsapp/evolution/qrcode`                             → QrCodeEvolution (imagem base64 / código de pareamento)
 * Revogar usa a rota genérica `POST /orquestracao/integracoes/whatsapp/revogar`.
 *
 * Com o QR code na tela, o estado é conferido a cada 5 s (Testar conexão) até o número conectar.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, QrCode, RefreshCw, Search } from "lucide-react";
import { useState } from "react";

import { ConfirmDialog } from "@/components/flic/confirm-dialog";
import { CampoDrawer, Drawer } from "@/components/flic/drawer";
import { formatarTelefone, normalizarTelefone } from "@/components/flic/enviar-whatsapp";
import { Etiqueta, type TomEtiqueta } from "@/components/flic/etiqueta";
import { notificar } from "@/components/flic/toast";
import { SegredoCampo } from "@/components/integracoes/segredo-campo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { dataHora } from "@/lib/format";
import type {
  ConfigEvolution,
  ConfigEvolutionIn,
  EstadoEvolution,
  InstanciaEvolution,
  Integracao,
  QrCodeEvolution,
  ResultadoIntegracao,
  TesteEvolution,
} from "@/lib/tipos-orquestracao";
import { cn } from "@/lib/utils";

const BASE = "/orquestracao/integracoes/whatsapp/evolution";
const CHAVE_CFG = ["orquestracao", "integracoes", "whatsapp", "evolution"];

const ROTULO_ESTADO: Record<EstadoEvolution, string> = { conectado: "Conectado", desconectado: "Desconectado", erro: "Erro" };
const TOM_ESTADO: Record<EstadoEvolution, TomEtiqueta> = { conectado: "green", desconectado: "neutra", erro: "amber" };

const ROTULO_INSTANCIA: Record<string, string> = { conectado: "Conectada", conectando: "Conectando", desconectado: "Desconectada" };

const telefone = (n: string | null | undefined) => (n ? formatarTelefone(normalizarTelefone(n) ?? n) : null);

/** Imagem da Evolution pode vir com ou sem o prefixo `data:`. */
const srcQr = (b64: string) => (b64.startsWith("data:") ? b64 : `data:image/png;base64,${b64}`);

export function DetalheWhatsApp({ integracao, onFechar }: { integracao: Integracao; onFechar: () => void }) {
  const cfg = useQuery({
    queryKey: CHAVE_CFG,
    queryFn: () => api.get<ConfigEvolution>(BASE),
    retry: false,
    meta: { silencioso: true },
  });
  const semRota = cfg.error instanceof ApiError && cfg.error.status === 404;

  return (
    <Drawer aberto onFechar={onFechar} rotulo={`INTEGRAÇÃO / ${integracao.grupo}`} titulo={integracao.nome} descricao="API do WhatsApp no seu servidor (Evolution)." largura={560}>
      <div className="rounded-[9px] bg-subtle p-[18px] text-[13px]">
        <h3 className="mb-2 text-sm font-bold">Antes de conectar</h3>
        <ul className="list-disc space-y-1 pl-5">
          {integracao.requisitos.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      </div>
      {cfg.isPending ? (
        <div className="mt-4 space-y-3">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : cfg.isError ? (
        <p className="mt-4 rounded-[7px] bg-amber/10 p-3 text-sm text-amber-ink">
          {semRota ? "O servidor ainda não tem a configuração da Evolution API." : "Não foi possível carregar a configuração do WhatsApp."}
        </p>
      ) : (
        <Formulario inicial={cfg.data} />
      )}
    </Drawer>
  );
}

function Formulario({ inicial }: { inicial: ConfigEvolution }) {
  const { pode } = useAuth();
  const qc = useQueryClient();
  const editar = pode("orquestracao.integracoes.editar");
  const [c, setC] = useState<ConfigEvolution>(inicial);
  const [url, setUrl] = useState(inicial.url ?? "");
  const [apikey, setApikey] = useState("");
  const [instancia, setInstancia] = useState(inicial.instancia ?? "");
  const [instancias, setInstancias] = useState<InstanciaEvolution[] | null>(null);
  const [qr, setQr] = useState<QrCodeEvolution | null>(null);
  const [revogar, setRevogar] = useState(false);

  const recarregar = async () => {
    void qc.invalidateQueries({ queryKey: ["orquestracao", "integracoes"] });
    void qc.invalidateQueries({ queryKey: ["auth", "me", "envio"] });
    const novo = await qc.fetchQuery({ queryKey: CHAVE_CFG, queryFn: () => api.get<ConfigEvolution>(BASE) }).catch(() => null);
    if (novo) setC(novo);
  };

  const urlLimpa = url.trim().replace(/\/+$/, "");
  const alterado = urlLimpa !== (c.url ?? "") || instancia.trim() !== (c.instancia ?? "") || apikey.trim() !== "";

  const salvar = useMutation({
    mutationFn: () => {
      const corpo: ConfigEvolutionIn = { url: urlLimpa, instancia: instancia.trim() || null };
      if (apikey.trim()) corpo.apikey = apikey.trim();
      return api.put<ConfigEvolution>(BASE, corpo);
    },
    onSuccess: (x) => {
      setC(x);
      setApikey("");
      void recarregar();
      notificar.sucesso("Configuração salva. Teste a conexão para confirmar.");
    },
  });

  const buscar = useMutation({
    mutationFn: () => {
      const corpo: { url?: string; apikey?: string } = {};
      if (urlLimpa) corpo.url = urlLimpa;
      if (apikey.trim()) corpo.apikey = apikey.trim();
      return api.post<InstanciaEvolution[]>(`${BASE}/instancias`, corpo);
    },
    onSuccess: (lista) => {
      setInstancias(lista);
      if (!lista.length) notificar("Nenhuma instância neste servidor. Digite um nome: ela é criada ao conectar o número.");
    },
  });

  const testar = useMutation({
    mutationFn: () => api.post<TesteEvolution>(`${BASE}/testar`),
    onSuccess: (r) => {
      void recarregar();
      if (r.ok && r.estado === "conectado") notificar.sucesso(r.mensagem);
      else notificar.erro(r.mensagem);
    },
  });

  const conectar = useMutation({
    mutationFn: () => api.post<QrCodeEvolution>(`${BASE}/qrcode`),
    onSuccess: (r) => {
      if (r.estado === "conectado") {
        notificar.sucesso(r.mensagem ?? "O número já está conectado.");
        void recarregar();
        return;
      }
      if (!r.base64 && !r.codigo_pareamento) {
        notificar(r.mensagem ?? "A instância não devolveu QR code. Ela pode já estar conectada: teste a conexão.");
        return;
      }
      setQr(r);
    },
  });

  // com o QR na tela, confere o estado a cada 5 s até conectar
  const acompanhamento = useQuery({
    queryKey: [...CHAVE_CFG, "acompanhar"],
    queryFn: async () => {
      const r = await api.post<TesteEvolution>(`${BASE}/testar`);
      if (r.estado === "conectado") {
        setQr(null);
        notificar.sucesso("Número conectado ao WhatsApp.");
        void recarregar();
      }
      return r;
    },
    enabled: qr != null,
    refetchInterval: 5000,
    retry: false,
    meta: { silencioso: true },
  });

  const revogacao = useMutation({
    mutationFn: () => api.post<ResultadoIntegracao>("/orquestracao/integracoes/whatsapp/revogar"),
    onSuccess: (r) => {
      setQr(null);
      void recarregar();
      notificar(r.mensagem);
    },
  });

  const estado = c.estado ?? "desconectado";
  const prontoParaConectar = c.configurado && !!c.url && !!c.instancia && !alterado;

  return (
    <>
      <div className="mt-4 rounded-[10px] border border-line p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Etiqueta tom={TOM_ESTADO[estado]}>{c.configurado ? ROTULO_ESTADO[estado] : "Não configurado"}</Etiqueta>
          {c.numero && <span className="num text-sm">{telefone(c.numero)}</span>}
          {c.instancia && <span className="text-xs text-muted">· instância {c.instancia}</span>}
        </div>
        <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs text-muted">
          <dt>Último teste</dt>
          <dd>{c.testado_em ? dataHora(c.testado_em) : "—"}</dd>
        </dl>
        {c.ultimo_erro && <p className="mt-3 rounded-[7px] bg-amber/10 p-2.5 text-xs text-amber-ink">Último erro: {c.ultimo_erro}</p>}
      </div>

      {qr && (
        <section className="mt-4 rounded-[10px] border border-electric/30 bg-electric/5 p-4 text-center">
          <h3 className="text-sm font-bold">Conectar número</h3>
          <p className="mt-1 text-xs text-muted">No celular: WhatsApp › Aparelhos conectados › Conectar um aparelho. Aponte a câmera para o código.</p>
          {qr.base64 && (
            // eslint-disable-next-line @next/next/no-img-element -- imagem base64 gerada na hora pela Evolution
            <img src={srcQr(qr.base64)} alt="QR code para conectar o WhatsApp" className="mx-auto mt-3 size-[240px] rounded-[8px] border border-line bg-surface p-2" />
          )}
          {qr.codigo_pareamento && (
            <p className="mt-3 text-sm">
              Código de pareamento: <strong className="num tracking-widest">{qr.codigo_pareamento}</strong>
            </p>
          )}
          <p className="mt-3 flex items-center justify-center gap-1.5 text-xs text-muted">
            <Loader2 className="size-3 animate-spin" />
            {acompanhamento.data && acompanhamento.data.estado !== "conectado" ? "Aguardando a leitura do código…" : "Conferindo o estado…"}
          </p>
          <div className="mt-3 flex justify-center gap-2">
            <Button size="sm" variant="outline" onClick={() => conectar.mutate()} disabled={conectar.isPending}>
              <RefreshCw /> Novo código
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setQr(null)}>
              Fechar
            </Button>
          </div>
        </section>
      )}

      {editar ? (
        <form
          id="f-evolution"
          className="mt-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (!/^https?:\/\/\S+$/i.test(urlLimpa)) {
              notificar.erro("Informe a URL da API começando com http:// ou https://.");
              return;
            }
            salvar.mutate();
          }}
        >
          <CampoDrawer rotulo="URL da API" obrigatorio htmlFor="ev-url" dica="Endereço do seu servidor Evolution, sem barra no fim.">
            <Input id="ev-url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://evolution.suaempresa.com.br" maxLength={300} inputMode="url" />
          </CampoDrawer>
          <div className="mt-[17px]">
            <SegredoCampo
              id="ev-apikey"
              label="API key"
              atual={{ definido: c.configurado && !!c.chave_final, final: c.chave_final ? c.chave_final.replace(/[•*]/g, "") : null }}
              valor={apikey}
              onChange={setApikey}
              remover={false}
              onRemover={() => setRevogar(true)}
              dica={c.chave_final ? "Deixe em branco para manter. Para apagar, use Revogar." : "Fica cifrada e não pode ser lida depois."}
            />
          </div>
          <CampoDrawer rotulo="Instância" htmlFor="ev-instancia" dica="Nome da instância na Evolution. Se não existir, é criada ao conectar o número.">
            <div className="flex gap-2">
              <Input id="ev-instancia" value={instancia} onChange={(e) => setInstancia(e.target.value)} placeholder="flicsales" maxLength={100} />
              <Button type="button" variant="outline" onClick={() => buscar.mutate()} disabled={buscar.isPending || (!urlLimpa && !c.url)}>
                {buscar.isPending ? <Loader2 className="animate-spin" /> : <Search />}
                Buscar instâncias
              </Button>
            </div>
          </CampoDrawer>
          {instancias && instancias.length > 0 && (
            <ul className="mt-2 divide-y divide-line rounded-[8px] border border-line">
              {instancias.map((x) => (
                <li key={x.nome}>
                  <button
                    type="button"
                    onClick={() => setInstancia(x.nome)}
                    className={cn("flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-subtle", instancia === x.nome && "bg-subtle")}
                  >
                    <span className="min-w-0">
                      <span className="block truncate font-medium">{x.nome}</span>
                      <span className="num block truncate text-xs text-muted">{telefone(x.numero) ?? "Sem número conectado"}</span>
                    </span>
                    <Etiqueta tom={x.estado === "conectado" ? "green" : x.estado === "conectando" ? "azul" : "neutra"}>
                      {ROTULO_INSTANCIA[x.estado ?? ""] ?? x.estado ?? "—"}
                    </Etiqueta>
                  </button>
                </li>
              ))}
            </ul>
          )}

          <div className="mt-5 flex flex-wrap gap-2">
            <Button type="submit" disabled={salvar.isPending}>
              {salvar.isPending && <Loader2 className="animate-spin" />}
              Salvar
            </Button>
            <Button type="button" variant="outline" onClick={() => testar.mutate()} disabled={testar.isPending || !c.configurado || alterado}>
              {testar.isPending && <Loader2 className="animate-spin" />}
              Testar conexão
            </Button>
            <Button type="button" variant="outline" onClick={() => conectar.mutate()} disabled={conectar.isPending || !prontoParaConectar}>
              {conectar.isPending ? <Loader2 className="animate-spin" /> : <QrCode />}
              Conectar número (QR code)
            </Button>
            {c.configurado && (
              <Button type="button" variant="destructive" onClick={() => setRevogar(true)}>
                Revogar
              </Button>
            )}
          </div>
          {alterado && c.configurado && <p className="mt-2 text-xs text-muted">Salve as alterações antes de testar ou conectar.</p>}
          {!c.configurado && <p className="mt-2 text-xs text-muted">Salve a URL, a API key e a instância para testar e conectar o número.</p>}
        </form>
      ) : (
        <p className="mt-4 text-sm text-muted">Seu perfil vê o estado da conexão; configurar, testar e revogar exigem permissão de edição.</p>
      )}

      <p className="mt-5 text-xs text-muted">
        Mensagens só saem quando alguém clica em enviar (comunicação, proposta ou cobrança). Pessoas com opt-out não recebem. A API key nunca é
        mostrada de novo.
      </p>

      <ConfirmDialog
        open={revogar}
        onOpenChange={setRevogar}
        titulo="Revogar WhatsApp?"
        descricao="A API key é apagada e a conexão volta a desconectada. Envios e automações de WhatsApp param."
        confirmar="Revogar"
        destrutivo
        carregando={revogacao.isPending}
        onConfirm={() => {
          setRevogar(false);
          revogacao.mutate();
        }}
      />
    </>
  );
}
