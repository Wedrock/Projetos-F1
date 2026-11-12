"use client";

import { useAppConfig, reportProblemUrl, REPO_URL } from "@/lib/config";

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
          {publicMode && (
            <a href={`${REPO_URL}#self-hosting-guide`} target="_blank" rel="noopener noreferrer" className={linkClass}>Instale você mesmo</a>
          )}
        </nav>
        <p>
          Este site não é oficial e não tem nenhuma ligação com as empresas da Fórmula 1.
        </p>
      </div>
    </footer>
  );
}
