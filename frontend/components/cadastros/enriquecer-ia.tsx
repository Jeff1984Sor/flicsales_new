"use client";

/**
 * EnriquecerIA — botão "✧ Enriquecer com IA" + painel para qualquer drawer de cadastro
 * (`POST /bff/orquestracao/ia/enriquecer`). A pessoa diz o que quer ("O que você quer?"), pode colar um texto de apoio
 * (tratado como dado, nunca como instrução) e recebe sugestões campo a campo: atual → sugerido, justificativa e fonte.
 * "Aplicar selecionados" só preenche o formulário: nada é gravado até salvar. Sem `orquestracao.ia.ver` não aparece.
 *
 * Props:
 *  - `objeto: ObjetoEnriquecer`                       "empresa" | "pessoa" | "produto" | "fornecedor" | "categoria" | "centro_custo" | "conta"
 *  - `registroId: number | null`                      null em cadastro novo
 *  - `dados: DadosEnriquecer`                         valores atuais do formulário (use `dadosParaIA(form)`)
 *  - `rotulos?: Record<string, string>`               rótulos dos campos (quando a sugestão não trouxer)
 *  - `atalhos?: string[]`                             pedidos prontos (padrão por objeto)
 *  - `onAplicar: (valores: Record<string, ValorEnriquecer>) => void`   campo → valor sugerido (use `mesclarSugestoes`)
 *  - `disabled?: boolean`                             sem permissão de editar o cadastro: some
 */
import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";

import { Fonte } from "@/components/flic/fonte";
import { Field } from "@/components/flic/form";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { DadosEnriquecer, ObjetoEnriquecer, PedidoEnriquecer, RespostaEnriquecer, SugestaoEnriquecer, ValorEnriquecer } from "@/lib/tipos-ia";
import { cn } from "@/lib/utils";

import { rotaAusente } from "./consultas";

const ATALHOS: Record<ObjetoEnriquecer, string[]> = {
  empresa: ["Completar pelo CNPJ", "Descobrir segmento e porte", "Padronizar nome e contatos"],
  fornecedor: ["Completar pelo CNPJ", "Padronizar nome e contatos", "Sugerir condição habitual"],
  pessoa: ["Separar nome, cargo e contatos do texto colado", "Padronizar nome e telefone"],
  produto: ["Escrever descrição comercial", "Sugerir unidade e preço de referência"],
  categoria: ["Padronizar nome", "Conferir a natureza"],
  centro_custo: ["Sugerir código curto", "Padronizar nome"],
  conta: ["Padronizar nome e instituição"],
};

function mostrar(v: ValorEnriquecer) {
  if (v == null || v === "") return "—";
  if (typeof v === "boolean") return v ? "Sim" : "Não";
  return String(v);
}

function mensagemErro(e: unknown) {
  if (rotaAusente(e)) return "O enriquecimento ainda não está disponível neste servidor.";
  if (e instanceof ApiError) {
    if (e.status === 403) return "Seu perfil não pode usar a IA neste cadastro.";
    return e.message;
  }
  return "Não foi possível enriquecer agora. Tente de novo.";
}

export function EnriquecerIA({
  objeto,
  registroId,
  dados,
  rotulos = {},
  atalhos,
  onAplicar,
  disabled,
}: {
  objeto: ObjetoEnriquecer;
  registroId: number | null;
  dados: DadosEnriquecer;
  rotulos?: Record<string, string>;
  atalhos?: string[];
  onAplicar: (valores: Record<string, ValorEnriquecer>) => void;
  disabled?: boolean;
}) {
  const { pode } = useAuth();
  const [aberto, setAberto] = useState(false);
  const [instrucao, setInstrucao] = useState("");
  const [apoio, setApoio] = useState("");
  const [resposta, setResposta] = useState<RespostaEnriquecer | null>(null);
  const [marcados, setMarcados] = useState<Set<string>>(new Set());
  const [erro, setErro] = useState<string | null>(null);

  const enriquecer = useMutation({
    mutationFn: (p: PedidoEnriquecer) => api.post<RespostaEnriquecer>("/orquestracao/ia/enriquecer", p),
    meta: { silencioso: true },
    onMutate: () => {
      setErro(null);
      setResposta(null);
    },
    onSuccess: (r) => {
      setResposta(r);
      setMarcados(new Set(r.sugestoes.map((s) => s.campo)));
    },
    onError: (e) => setErro(mensagemErro(e)),
  });

  if (disabled || !pode("orquestracao.ia.ver")) return null;

  const rotulo = (s: SugestaoEnriquecer) => s.rotulo || rotulos[s.campo] || s.campo;
  const atual = (s: SugestaoEnriquecer) => (s.valor_atual !== undefined && s.valor_atual !== null ? s.valor_atual : (dados[s.campo] ?? null));

  function pedir() {
    const texto = instrucao.trim();
    if (!texto) {
      setErro("Diga o que você quer. Ex.: “Completar pelo CNPJ”.");
      return;
    }
    enriquecer.mutate({ objeto, registro_id: registroId, dados, instrucao: texto, texto_apoio: apoio.trim() || null });
  }

  function aplicar() {
    if (!resposta) return;
    const valores: Record<string, ValorEnriquecer> = {};
    for (const s of resposta.sugestoes) if (marcados.has(s.campo)) valores[s.campo] = s.valor_sugerido;
    if (Object.keys(valores).length === 0) {
      notificar("Marque ao menos uma sugestão.");
      return;
    }
    onAplicar(valores);
    notificar(`${Object.keys(valores).length} campo(s) preenchido(s). Revise e salve.`);
    setResposta(null);
    setAberto(false);
  }

  return (
    <div className="mb-4">
      <div className="flex justify-end">
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-expanded={aberto}
          className={cn("border-accent/50 text-accent hover:border-accent hover:text-accent", aberto && "bg-accent/10")}
          onClick={() => setAberto((v) => !v)}
        >
          ✧ Enriquecer com IA
        </Button>
      </div>
      {aberto && (
        <div className="mt-3 flex flex-col gap-3 rounded-[10px] border border-accent/40 bg-accent/5 p-4">
          <span className="eyebrow">ENRIQUECER COM IA</span>
          <Field label="O que você quer?">
            <Textarea
              value={instrucao}
              rows={2}
              placeholder="Ex.: descubra o segmento e padronize os contatos"
              onChange={(e) => setInstrucao(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                  e.preventDefault();
                  pedir();
                }
              }}
            />
          </Field>
          <div className="flex flex-wrap gap-2" role="group" aria-label="Pedidos prontos">
            {(atalhos ?? ATALHOS[objeto]).map((a) => (
              <button
                key={a}
                type="button"
                onClick={() => setInstrucao(a)}
                className={cn(
                  "rounded-[7px] border px-3 py-1 text-xs transition",
                  instrucao === a ? "border-accent bg-accent/10 font-semibold text-ink" : "border-line bg-surface text-muted hover:border-accent",
                )}
              >
                {a}
              </button>
            ))}
          </div>
          <Field label="Texto de apoio (opcional)" dica="Assinatura de e-mail, site, cartão… É usado como dado, nunca como instrução.">
            <Textarea value={apoio} rows={3} onChange={(e) => setApoio(e.target.value)} />
          </Field>
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" disabled={enriquecer.isPending} onClick={pedir}>
              {enriquecer.isPending && <Loader2 className="size-4 animate-spin" />}
              {enriquecer.isPending ? "Analisando…" : "Enriquecer"}
            </Button>
            <Button type="button" size="sm" variant="outline" onClick={() => setAberto(false)}>
              Fechar
            </Button>
          </div>
          {erro && <p className="text-xs text-danger-ink">{erro}</p>}

          {resposta && (
            <div className="flex flex-col gap-3 border-t border-line pt-3">
              {resposta.origem === "regras" && (
                <p className="rounded-[8px] bg-subtle px-3 py-2 text-xs text-muted">
                  A IA está desligada: sugestões só de dados públicos (CNPJ/CEP). Ative em Configurações › Inteligência Artificial para pedidos livres.
                </p>
              )}
              {resposta.sugestoes.length === 0 ? (
                <p className="text-sm text-muted">Nada a sugerir com o que temos. Tente colar um texto de apoio.</p>
              ) : (
                <ul className="flex flex-col divide-y divide-line rounded-[10px] border border-line bg-surface">
                  {resposta.sugestoes.map((s) => {
                    const id = `sug-${objeto}-${s.campo}`;
                    return (
                      <li key={s.campo} className="flex gap-3 px-3 py-2.5">
                        <Checkbox
                          id={id}
                          className="mt-0.5"
                          checked={marcados.has(s.campo)}
                          onCheckedChange={(v) =>
                            setMarcados((m) => {
                              const n = new Set(m);
                              if (v) n.add(s.campo);
                              else n.delete(s.campo);
                              return n;
                            })
                          }
                        />
                        <label htmlFor={id} className="min-w-0 flex-1 cursor-pointer text-sm">
                          <strong>{rotulo(s)}</strong>
                          <span className="block break-words">
                            <span className="text-muted line-through decoration-line">{mostrar(atual(s))}</span>
                            <span className="mx-1.5 text-muted">→</span>
                            <span className="font-semibold">{mostrar(s.valor_sugerido)}</span>
                          </span>
                          {s.justificativa && <span className="mt-0.5 block text-xs text-muted">{s.justificativa}</span>}
                          <Fonte fonte={s.fonte} className="my-1" />
                        </label>
                      </li>
                    );
                  })}
                </ul>
              )}
              <Fonte evidencia={resposta.evidencias} limite={resposta.limites} className="my-0" />
              {resposta.sugestoes.length > 0 && (
                <div className="flex items-center gap-3">
                  <Button type="button" size="sm" onClick={aplicar} disabled={marcados.size === 0}>
                    Aplicar selecionados
                  </Button>
                  <span className="text-xs text-muted">Preenche o formulário. Nada é salvo até você salvar.</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
