import { redirect } from "next/navigation";

/** A configuração da IA mora no módulo Assistente. */
export default function ConfigIAAntigaPage() {
  redirect("/assistente/configuracoes");
}
