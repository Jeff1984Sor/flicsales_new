import { redirect } from "next/navigation";

/** O Assistente virou módulo próprio (aba do topo): a rota antiga leva para lá. */
export default function AssistenteAntigoPage() {
  redirect("/assistente");
}
