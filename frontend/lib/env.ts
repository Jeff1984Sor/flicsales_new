export const AMBIENTE = process.env.NEXT_PUBLIC_AMBIENTE ?? "dev";
export const VERSAO = process.env.NEXT_PUBLIC_VERSAO ?? "v1";
export const EH_HML = AMBIENTE === "hml";
export const EH_PROD = AMBIENTE === "prod";
