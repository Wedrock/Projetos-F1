import SiteFooter from "@/components/SiteFooter";
import PaywallNotice from "@/components/PaywallNotice";
import { REPO_URL, UPSTREAM_URL } from "@/lib/config";

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-f1-dark">
      <div className="bg-f1-card border-b border-f1-border">
        <div className="max-w-3xl mx-auto px-6 py-8 flex items-center gap-4">
          <a href="/" className="text-f1-muted hover:text-white transition-colors">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </a>
          <h1 className="text-2xl font-bold text-white">Sobre</h1>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-6 py-12 space-y-8">
        <PaywallNotice />

        <div className="bg-f1-card border border-f1-red/40 rounded-xl p-6">
          <h2 className="text-lg font-bold text-f1-red mb-3">Aviso legal</h2>
          <p className="text-f1-text leading-relaxed">
            O Box Box e este site não são oficiais e não têm nenhuma ligação com as empresas da Fórmula 1.
          </p>
        </div>

        <div className="bg-f1-card border border-f1-border rounded-xl p-6">
          <h2 className="text-lg font-bold text-white mb-3">O que é isto?</h2>
          <p className="text-f1-text leading-relaxed">
            O Box Box é um projeto independente para rever sessões passadas da Fórmula 1 com o traçado da pista, a posição dos pilotos e os dados de cronometragem. Foi feito só para fins educativos e de entretenimento.
          </p>
        </div>

        <div className="bg-f1-card border border-f1-border rounded-xl p-6">
          <h2 className="text-lg font-bold text-white mb-3">Fontes de dados</h2>
          <p className="text-f1-text leading-relaxed mb-4">
            Todos os dados vêm de APIs disponíveis publicamente. Nenhum dado proprietário ou restrito é usado.
          </p>
          <p className="text-f1-text leading-relaxed">
            Este projeto usa os dados fornecidos pelo{" "}
            <a
              href="https://github.com/theOehrly/Fast-F1"
              target="_blank"
              rel="noopener noreferrer"
              className="text-f1-red hover:underline font-semibold"
            >
              FastF1
            </a>
            , uma biblioteca Python de código aberto para acessar os dados de cronometragem e telemetria da Fórmula 1. Agradecemos aos mantenedores e colaboradores do FastF1 por tornarem isso possível.
          </p>
        </div>

        <div className="bg-f1-card border border-f1-border rounded-xl p-6">
          <h2 className="text-lg font-bold text-white mb-3">Código aberto</h2>
          <p className="text-f1-text leading-relaxed">
            O Box Box é baseado no{" "}
            <a href={UPSTREAM_URL} target="_blank" rel="noopener noreferrer" className="text-f1-red hover:underline font-semibold">F1 Replay Timing</a>
            , código aberto sob a licença MIT. O código, o guia para rodar a sua própria cópia e o registro de problemas estão no{" "}
            <a
              href={REPO_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="text-f1-red hover:underline font-semibold"
            >
              GitHub
            </a>
            . Relatos de bugs vão em Issues; ideias e perguntas em Discussions.
          </p>
        </div>

        <div className="text-center pt-4">
          <a href="/" className="text-f1-muted hover:text-white transition-colors text-sm">
            Voltar à escolha de sessão
          </a>
        </div>
      </div>
      <SiteFooter />
    </div>
  );
}
