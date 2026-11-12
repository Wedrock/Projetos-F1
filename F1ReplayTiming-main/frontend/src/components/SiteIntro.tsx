"use client";

import { useEffect, useState } from "react";
import { Flag, CircleDot, Smartphone, RefreshCw, PictureInPicture2, X } from "lucide-react";

// Short "what is this" panel for the public site's home page. Hiding it is
// remembered per browser; an Overview button in the header brings it back.

const DISMISS_KEY = "f1replay_intro_dismissed";

const HIGHLIGHTS = [
  { icon: <Flag className="w-4 h-4" />, title: "Direção de prova", text: "Mensagens dos comissários, punições e bandeiras por setor de fiscais no mapa da pista." },
  { icon: <img src="/pit-return.png" alt="" className="w-4 h-4 invert opacity-80" />, title: "Previsão de pit", text: "Onde cada piloto voltaria se parasse agora." },
  { icon: <CircleDot className="w-4 h-4" />, title: "Desgaste dos pneus", text: "Composto atual, idade do pneu e histórico de pneus." },
  { icon: <RefreshCw className="w-4 h-4" />, title: "Sincronize com a sua TV", text: "Alinhe o replay com uma gravação digitando a volta e as diferenças." },
  { icon: <PictureInPicture2 className="w-4 h-4" />, title: "Picture-in-picture", text: "Uma janela flutuante para assistir junto com a transmissão." },
  { icon: <Smartphone className="w-4 h-4" />, title: "Celular e tablet", text: "Funciona em celulares e tablets, além do computador." },
];

/** Whether the intro is showing (null until the saved choice is read, so nothing flashes). */
export function useIntroVisibility() {
  const [show, setShow] = useState<boolean | null>(null);

  useEffect(() => {
    try {
      setShow(localStorage.getItem(DISMISS_KEY) !== "1");
    } catch {
      setShow(true);
    }
  }, []);

  const set = (visible: boolean) => {
    setShow(visible);
    try {
      if (visible) localStorage.removeItem(DISMISS_KEY);
      else localStorage.setItem(DISMISS_KEY, "1");
    } catch {}
  };

  return { show, open: () => set(true), dismiss: () => set(false) };
}

export default function SiteIntro({ onDismiss }: { onDismiss: () => void }) {
  const dismiss = onDismiss;

  return (
    <div className="max-w-3xl mx-auto mb-8 bg-f1-card border border-f1-border rounded-xl p-5 relative">
      <button
        onClick={dismiss}
        className="absolute top-3 right-3 w-7 h-7 flex items-center justify-center rounded text-f1-muted hover:text-white hover:bg-white/10 transition-colors"
        aria-label="Ocultar a introdução"
        title="Ocultar"
      >
        <X className="w-4 h-4" />
      </button>
      <p className="text-white font-bold text-base sm:text-lg pr-8 leading-snug">
        Reveja sessões da F1 de 2024 em diante com cronometragem, posição dos carros na pista e telemetria.
      </p>
      <ul className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3">
        {HIGHLIGHTS.map((h) => (
          <li key={h.title} className="flex items-start gap-3">
            <span className="mt-0.5 w-7 h-7 flex-shrink-0 flex items-center justify-center rounded bg-f1-red/15 text-f1-red">
              {h.icon}
            </span>
            <span className="text-sm leading-snug">
              <span className="font-bold text-white">{h.title}</span>
              <span className="text-f1-muted"> — {h.text}</span>
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-4 text-xs text-f1-muted">
        Escolha uma corrida abaixo para começar.{" "}
        <a href="/features" className="text-f1-red hover:underline font-semibold">Ver todos os recursos</a>
      </p>
    </div>
  );
}
