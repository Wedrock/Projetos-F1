"use client";

import { useAppConfig, reportProblemUrl, REPO_URL, KOFI_URL } from "@/lib/config";

export default function SiteFooter() {
  const config = useAppConfig();
  const publicMode = !!config?.public_mode;
  const linkClass = "hover:text-white transition-colors";

  return (
    <footer className="border-t border-f1-border mt-12">
      <div className="max-w-3xl mx-auto px-6 py-6 space-y-3 text-xs text-f1-muted leading-relaxed">
        <nav className="flex flex-wrap gap-x-5 gap-y-1 font-bold">
          <a href="/about" className={linkClass}>Sobre</a>
          <a href={REPO_URL} target="_blank" rel="noopener noreferrer" className={linkClass}>GitHub</a>
          <a href={reportProblemUrl()} target="_blank" rel="noopener noreferrer" className={linkClass}>Relatar um problema</a>
          <a href={`${REPO_URL}/discussions`} target="_blank" rel="noopener noreferrer" className={linkClass}>Ideias e perguntas</a>
          <a href={KOFI_URL} target="_blank" rel="noopener noreferrer" className={linkClass}>Apoie no Ko-fi</a>
          {publicMode && (
            <a href={`${REPO_URL}#self-hosting-guide`} target="_blank" rel="noopener noreferrer" className={linkClass}>Instale você mesmo</a>
          )}
        </nav>
        <p>
          Este site não é oficial e não tem nenhuma ligação com as empresas da Fórmula 1. F1, FORMULA ONE, FORMULA 1, FIA FORMULA ONE WORLD CHAMPIONSHIP, GRAND PRIX e marcas relacionadas são marcas registradas da Formula One Licensing B.V.
        </p>
      </div>
    </footer>
  );
}
