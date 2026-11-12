"use client";

import { useEffect, useState } from "react";
import SiteFooter from "@/components/SiteFooter";
import LeaderboardGuide from "@/components/LeaderboardGuide";
import LapAnalysisGuide from "@/components/LapAnalysisGuide";
import BroadcastGuide, { SyncDiagram } from "@/components/BroadcastGuide";

// Which sessions a feature works in, shown under each section's heading.
function SessionChips({ practice, qualifying, race }: { practice?: boolean; qualifying?: boolean; race?: boolean }) {
  const chips: [string, boolean | undefined][] = [["Treinos", practice], ["Classificação", qualifying], ["Corrida", race]];
  return (
    <div className="flex flex-wrap gap-1.5 mb-3">
      {chips.map(([label, on]) => (
        <span
          key={label}
          className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${
            on ? "border-f1-red/50 bg-f1-red/15 text-f1-red" : "border-f1-border text-f1-muted/50 line-through"
          }`}
        >
          {label}
        </span>
      ))}
    </div>
  );
}

const FEATURE_CATEGORIES: [string, string][] = [
  ["getting-started", "Primeiros passos"],
  ["leaderboard", "Tabela"],
  ["track-map", "Mapa da pista"],
  ["analysis", "Análise"],
  ["session-feed", "Feed da sessão"],
  ["watching", "Watching"],
  ["broadcast", "Transmissão"],
  ["availability", "Availability"],
];

// Feature availability: R = replay, L = live, - = not available.
// Columns: race and sprint, qualifying and sprint qualifying, practice.
const AVAILABILITY_SESSIONS = ["Corrida e Sprint", "Classificação", "Treinos"];
const AVAILABILITY: [string, string, string, string][] = [
  ["Tabela, pneus, diferenças", "RL", "RL", "RL"],
  ["Posição dos carros no mapa da pista", "RL", "RL", "RL"],
  ["Mensagens da direção de prova, clima", "RL", "RL", "RL"],
  ["Rádio das equipes com legendas", "RL", "RL", "RL"],
  ["Previsão de posição no pit", "RL", "-", "-"],
  ["Setores e minissetores", "-", "RL", "RL"],
  ["Indicador de volta de saída", "-", "RL", "RL"],
  ["Tempo da última volta", "RL", "RL", "RL"],
  ["Setores no mapa da pista", "-", "RL", "RL"],
  ["Análise de voltas", "RL", "RL", "RL"],
  ["Domínio na pista", "-", "RL", "RL"],
  ["Avisos de volta", "-", "RL", "-"],
  ["Telemetria", "RL", "RL", "RL"],
  ["Altimetria da pista, bandeiras por setor de fiscais", "RL", "RL", "RL"],
  ["Picture-in-picture", "RL", "RL", "RL"],
  ["Controles de reprodução, sincronizar com uma gravação", "R", "R", "R"],
  ["Transmissão do F1 TV e onboards (F1 TV Pro ou Premium)", "R", "R", "R"],
  ["Atraso da transmissão", "L", "L", "L"],
];

// Sections linked to from elsewhere on the page, and the tab they're in
const SECTION_TAB: Record<string, string> = {
  "driver-leaderboard": "leaderboard",
  sectors: "leaderboard",
  "sectors-map": "track-map",
};

export default function FeaturesPage() {
  const [tab, setTab] = useState(FEATURE_CATEGORIES[0][0]);

  // The URL hash picks the tab (#track-map), or the tab holding a section
  // (#sectors-map), so links within the page and from elsewhere work.
  useEffect(() => {
    const fromHash = () => {
      const id = decodeURIComponent(window.location.hash.slice(1));
      const target = FEATURE_CATEGORIES.some(([c]) => c === id) ? id : SECTION_TAB[id];
      if (!target) return;
      setTab(target);
      requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView());
    };
    fromHash();
    window.addEventListener("hashchange", fromHash);
    return () => window.removeEventListener("hashchange", fromHash);
  }, []);

  const showTab = (id: string) => {
    setTab(id);
    history.replaceState(null, "", `#${id}`);
    window.scrollTo({ top: 0 });
  };

  return (
    <div className="min-h-screen bg-f1-dark">
      <div className="bg-f1-card border-b border-f1-border">
        <div className="max-w-5xl mx-auto px-6 py-8 flex items-center gap-4">
          <button
            onClick={() => {
              if (window.opener || window.history.length <= 1) {
                window.close();
              } else {
                window.location.href = "/";
              }
            }}
            className="text-f1-muted hover:text-white transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <h1 className="text-2xl font-bold text-white">Recursos</h1>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-6 py-12 space-y-10">

        {/* Category tabs */}
        <nav className="sticky top-0 z-20 -mx-6 px-6 py-3 bg-f1-dark/95 backdrop-blur-sm border-b border-f1-border">
          <div className="flex flex-wrap gap-1">
            {FEATURE_CATEGORIES.map(([id, label]) => (
              <button
                key={id}
                onClick={() => showTab(id)}
                className={`flex-shrink-0 px-3 py-1.5 rounded-md text-sm font-bold transition-colors ${
                  tab === id ? "bg-f1-red text-white" : "text-f1-muted hover:text-white hover:bg-white/5"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </nav>

        {tab === "getting-started" && (
          <>

          {/* Session Picker */}
          <section className="bg-f1-card border border-f1-border rounded-xl p-6">
            <h2 className="text-lg font-bold text-white mb-1">Escolha de sessão</h2>
            <p className="text-xs font-bold text-f1-red uppercase tracking-wider mb-3">Página inicial</p>
            <p className="text-f1-text leading-relaxed">
              Um ponto verde
              <span className="inline-block align-middle w-1.5 h-1.5 rounded-full bg-green-400 mx-1.5" />
              ao lado de uma sessão indica que ela já foi baixada e toca na hora. Passe o mouse sobre a sessão para ver o espaço que ocupa. Sessões sem o ponto são processadas na primeira vez que você as abre.
            </p>
          </section>

          {/* F1 TV sign-in */}
          <section className="bg-f1-card border border-f1-border rounded-xl p-6">
            <h2 className="text-lg font-bold text-white mb-1">Login no F1 TV</h2>
            <SessionChips practice qualifying race />
            <p className="text-f1-text leading-relaxed mb-3">
              Desde 15 de outubro de 2026, a F1 exige uma assinatura do F1 TV (Access ou superior) para os dados de cronometragem. Entre pelo botão <span className="font-bold text-white">F1 TV</span> na página inicial ou pela aba F1 TV nas Configurações de um replay. Com <span className="font-bold text-white">Manter conectado</span>, você continua conectado, inclusive para os downloads automáticos dos fins de semana de corrida.
            </p>
            <p className="text-f1-text leading-relaxed">
              O login é necessário para baixar novas sessões e acrescenta a posição dos carros e o rádio das equipes à cronometragem ao vivo. Sessões já baixadas tocam sem ele.
            </p>
          </section>

          {/* Data Availability */}
          <section className="bg-f1-card border border-f1-border rounded-xl p-6">
            <h2 className="text-lg font-bold text-white mb-1">Disponibilidade dos dados</h2>
            <SessionChips practice qualifying race />
            <p className="text-f1-text leading-relaxed">
              De vez em quando, os dados de cronometragem de um piloto podem ficar indisponíveis por um tempo &mdash; por exemplo, durante pit stops ou numa falha breve do sistema da F1. Quando isso acontece, o piloto aparece acinzentado no fim da tabela e volta à posição certa assim que os dados voltam.
            </p>
          </section>
          </>
        )}

        {tab === "leaderboard" && (
          <>

          {/* Reading the leaderboard */}
          <section className="bg-f1-card border border-f1-red/40 rounded-xl p-6">
            <h2 className="text-lg font-bold text-white mb-1">Como ler a tabela</h2>
            <p className="text-f1-text leading-relaxed mb-4">
              O que significa cada coluna da tabela. Mais detalhes em{" "}
              <a href="#driver-leaderboard" className="text-f1-red hover:underline font-semibold">Tabela de pilotos</a> abaixo.
            </p>
            <LeaderboardGuide />
          </section>

          {/* Driver Leaderboard */}
          <section id="driver-leaderboard" className="bg-f1-card border border-f1-border rounded-xl p-6 scroll-mt-20">
            <h2 className="text-lg font-bold text-white mb-1">Tabela de pilotos</h2>
            <SessionChips practice qualifying race />
            <p className="text-f1-text leading-relaxed mb-4">
              A tabela mostra todos os pilotos ordenados pela posição, com dados vindos direto da cronometragem oficial da F1. Cada linha pode mostrar várias informações, todas ativáveis no menu de configurações:
            </p>
            <div className="space-y-4">
              {/* Position */}
              <div className="flex items-center gap-3 flex-wrap sm:flex-nowrap">
                <span className="w-24 flex-shrink-0 text-sm font-bold text-f1-muted">Posição</span>
                <span className="flex items-center gap-2 flex-shrink-0">
                  <span className="w-6 h-6 flex items-center justify-center rounded bg-f1-red text-white text-sm font-extrabold">1</span>
                  <span className="w-6 text-sm font-extrabold text-white text-right">2</span>
                </span>
                <span className="w-full sm:w-auto text-sm text-f1-text">Posição atual na corrida ou na sessão. O líder é destacado com um selo vermelho.</span>
              </div>

              {/* Team colour */}
              <div className="flex items-center gap-3 flex-wrap sm:flex-nowrap">
                <span className="w-24 flex-shrink-0 text-sm font-bold text-f1-muted">Cor da equipe</span>
                <span className="flex items-center gap-1.5 flex-shrink-0">
                  <span className="w-1 h-6 rounded-sm" style={{ backgroundColor: "#FF8000" }} />
                  <span className="w-1 h-6 rounded-sm" style={{ backgroundColor: "#E80020" }} />
                </span>
                <span className="w-full sm:w-auto text-sm text-f1-text">Uma barra com a cor da equipe ao lado de cada piloto.</span>
              </div>

              {/* Team abbr */}
              <div className="flex items-center gap-3 flex-wrap sm:flex-nowrap">
                <span className="w-24 flex-shrink-0 text-sm font-bold text-f1-muted">Sigla da equipe</span>
                <span className="flex items-center gap-1.5 flex-shrink-0">
                  <span className="text-[10px] font-bold text-f1-muted">MCL</span>
                  <span className="text-[10px] font-bold text-f1-muted">FER</span>
                </span>
                <span className="w-full sm:w-auto text-sm text-f1-text">Sigla de três letras da equipe. Desligada por padrão.</span>
              </div>

              {/* Gap */}
              <div className="flex items-center gap-3 flex-wrap sm:flex-nowrap">
                <span className="w-24 flex-shrink-0 text-sm font-bold text-f1-muted">Diferença</span>
                <span className="flex items-center gap-2 flex-shrink-0">
                  <span className="text-xs font-bold text-f1-muted">+3.200</span>
                  <span className="text-xs font-bold text-yellow-400">PIT</span>
                </span>
                <span className="w-full sm:w-auto text-sm text-f1-text">Diferença para o líder (corridas) ou melhor volta (treinos/classificação). Mostra &quot;PIT&quot; quando o carro está no pit lane.</span>
              </div>

              {/* Last lap time */}
              <div className="flex items-center gap-3 flex-wrap sm:flex-nowrap">
                <span className="w-24 flex-shrink-0 text-sm font-bold text-f1-muted">Última volta</span>
                <span className="text-xs tabular-nums text-f1-muted flex-shrink-0">1:32.456</span>
                <span className="w-full sm:w-auto text-sm text-f1-text">O tempo da volta mais recente do piloto. Roxo para a mais rápida da sessão, verde para o melhor pessoal.</span>
              </div>

              {/* Grid delta */}
              <div className="flex items-center gap-3 flex-wrap sm:flex-nowrap">
                <span className="w-24 flex-shrink-0 text-sm font-bold text-f1-muted">Ganho no grid</span>
                <span className="flex items-center gap-2 flex-shrink-0">
                  <span className="text-[10px] font-bold text-green-400">&#9650;3</span>
                  <span className="text-[10px] font-bold text-red-400">&#9660;2</span>
                </span>
                <span className="w-full sm:w-auto text-sm text-f1-text">Posições ganhas ou perdidas em relação ao grid de largada. Só em corridas.</span>
              </div>

              {/* Pit stops */}
              <div className="flex items-center gap-3 flex-wrap sm:flex-nowrap">
                <span className="w-24 flex-shrink-0 text-sm font-bold text-f1-muted">Pit stops</span>
                <span className="w-5 h-5 border border-f1-muted rounded-sm flex items-center justify-center text-[10px] font-extrabold text-white flex-shrink-0">
                  2
                </span>
                <span className="w-full sm:w-auto text-sm text-f1-text">Número de pit stops feitos até agora. Só em corridas.</span>
              </div>

              {/* Pit prediction */}
              <div className="flex items-center gap-3 flex-wrap sm:flex-nowrap">
                <span className="w-24 flex-shrink-0 text-sm font-bold text-f1-muted">Previsão de pit</span>
                <span className="flex items-center gap-0.5 flex-shrink-0">
                  <img src="/pit-return.png" alt="" className="w-3 h-3 opacity-50 invert" />
                  <span className="text-[10px] font-bold text-f1-muted">P5</span>
                </span>
                <span className="flex flex-col items-end flex-shrink-0 leading-tight">
                  <span className="text-[8px] font-bold text-f1-muted">↑3.2s</span>
                  <span className="text-[8px] font-bold text-f1-muted">↓8.4s</span>
                </span>
                <span className="w-full sm:w-auto text-sm text-f1-text">Posição prevista na volta do pit, com a diferença para o carro da frente (em cima) e para o de trás (embaixo). Só em corridas.</span>
              </div>

              {/* Tyre compound */}
              <div className="flex items-center gap-3 flex-wrap sm:flex-nowrap">
                <span className="w-24 flex-shrink-0 text-sm font-bold text-f1-muted">Composto do pneu</span>
                <span className="flex items-center gap-1.5 flex-shrink-0">
                  <span className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-extrabold leading-none border-2" style={{ borderColor: "#E80020", color: "#E80020" }}>S</span>
                  <span className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-extrabold leading-none border-2" style={{ borderColor: "#FFC800", color: "#FFC800" }}>M</span>
                  <span className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-extrabold leading-none border-2" style={{ borderColor: "#FFFFFF", color: "#FFFFFF" }}>H</span>
                </span>
                <span className="w-full sm:w-auto text-sm text-f1-text">O composto atual, mostrado num círculo colorido.</span>
              </div>

              {/* Tyre age */}
              <div className="flex items-center gap-3 flex-wrap sm:flex-nowrap">
                <span className="w-24 flex-shrink-0 text-sm font-bold text-f1-muted">Idade do pneu</span>
                <span className="text-xs font-extrabold text-white flex-shrink-0">12</span>
                <span className="w-full sm:w-auto text-sm text-f1-text">Número de voltas com o jogo de pneus atual.</span>
              </div>

              {/* Tyre history */}
              <div className="flex items-center gap-3 flex-wrap sm:flex-nowrap">
                <span className="w-24 flex-shrink-0 text-sm font-bold text-f1-muted">Histórico de pneus</span>
                <span className="flex items-center gap-0.5 flex-shrink-0">
                  <span className="w-3.5 h-3.5 rounded-full flex items-center justify-center text-[7px] font-extrabold leading-none border opacity-50" style={{ borderColor: "#E80020", color: "#E80020" }}>S</span>
                  <span className="w-3.5 h-3.5 rounded-full flex items-center justify-center text-[7px] font-extrabold leading-none border opacity-50" style={{ borderColor: "#FFC800", color: "#FFC800" }}>M</span>
                </span>
                <span className="w-full sm:w-auto text-sm text-f1-text">Os dois últimos compostos usados, em ícones menores. Só em corridas.</span>
              </div>

              {/* Flags */}
              <div className="flex items-center gap-3 flex-wrap sm:flex-nowrap">
                <span className="w-24 flex-shrink-0 text-sm font-bold text-f1-muted">Volta mais rápida</span>
                <span className="flex items-center gap-1.5 flex-shrink-0">
                  <svg className="w-3.5 h-3.5 text-purple-500" viewBox="0 0 24 24" fill="currentColor">
                    <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" strokeWidth="2.5" />
                    <path d="M12 6v7l4.5 2.5" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
                  </svg>
                </span>
                <span className="w-full sm:w-auto text-sm text-f1-text">Ícone de relógio roxo ao lado do piloto com a volta mais rápida.</span>
              </div>

              {/* Highlight under 1s */}
              <div className="flex items-center gap-3 flex-wrap sm:flex-nowrap">
                <span className="w-24 flex-shrink-0 text-sm font-bold text-f1-muted">Abaixo de 1s</span>
                <span className="text-xs font-bold tabular-nums text-green-400 flex-shrink-0">+0.684</span>
                <span className="w-full sm:w-auto text-sm text-f1-text">Ao mostrar o intervalo para o carro da frente, diferenças abaixo de um segundo ficam verdes. Só em corridas.</span>
              </div>

              {/* Knocked out */}
              <div className="flex items-center gap-3 flex-wrap sm:flex-nowrap">
                <span className="w-24 flex-shrink-0 text-sm font-bold text-f1-muted">Eliminados</span>
                <span className="text-xs font-extrabold text-white opacity-50 flex-shrink-0">STR</span>
                <span className="w-full sm:w-auto text-sm text-f1-text">Pilotos eliminados no Q1 ou Q2 continuam na tabela, esmaecidos, com o melhor tempo. Só na classificação.</span>
              </div>
            </div>
          </section>

          {/* Sectors */}
          <section id="sectors" className="bg-f1-card border border-f1-border rounded-xl p-6 scroll-mt-20">
            <h2 className="text-lg font-bold text-white mb-1">Setores e minissetores</h2>
            <SessionChips practice qualifying />
            <p className="text-f1-text leading-relaxed mb-3">
              A linha de cada piloto mostra o andamento dele pelos três setores da volta atual &mdash; roxo para o melhor da sessão, verde para o melhor pessoal, amarelo nos demais casos.
            </p>
            <p className="text-f1-text leading-relaxed mb-3">
              A F1 também cronometra cada setor em pedaços menores. Com os minissetores ligados, a linha vai sendo preenchida minissetor a minissetor conforme o piloto anda, nas mesmas cores. Só no computador, em replays e ao vivo. Alterne entre os dois em Configurações &gt; Tabela, ou ao lado do botão Mostrar/Ocultar setores no mapa da pista. Eles também podem ser desenhados no mapa; veja{" "}
              <a href="#sectors-map" className="text-f1-red hover:underline font-semibold">Setores no mapa da pista</a>.
            </p>
            <p className="text-f1-text leading-relaxed">
              Enquanto o piloto está numa volta de saída, da saída do pit até completar a volta, a linha mostra{" "}
            <span className="font-bold text-white">OUT</span> no lugar.
          </p>
          <p className="text-f1-text leading-relaxed">
            Replays de sessões processadas antes da chegada dos minissetores mostram os três setores até serem reprocessados.
            </p>
          </section>

          {/* Lap notifications */}
          <section className="bg-f1-card border border-f1-border rounded-xl p-6">
            <h2 className="text-lg font-bold text-white mb-1">Avisos de volta</h2>
            <SessionChips qualifying />
            <p className="text-f1-text leading-relaxed">
              Quando um piloto completa uma volta, um aviso mostra o tempo, em roxo para o melhor da sessão ou verde para o melhor pessoal, com o tempo de cada setor ao lado do marcador. Desligue os avisos, ou só os tempos de setor, em Configurações &gt; Tabela.
            </p>
          </section>

          {/* Starting Grid */}
          <section className="bg-f1-card border border-f1-border rounded-xl p-6">
            <h2 className="text-lg font-bold text-white mb-1">Grid de largada</h2>
            <SessionChips race />
            <p className="text-f1-text leading-relaxed mb-3">
              Nos primeiros 10 segundos da corrida, a tabela mostra a ordem do grid de largada antes de os dados ao vivo assumirem.
            </p>
            <p className="text-f1-text leading-relaxed">
              Quando não há dados oficiais do grid, as posições da classificação são usadas no lugar. Isso pode não refletir punições de grid ou outras mudanças na ordem de largada.
            </p>
          </section>

          {/* Pit Position Prediction */}
          <section className="bg-f1-card border border-f1-border rounded-xl p-6">
            <div className="flex items-center gap-2 mb-1">
              <h2 className="text-lg font-bold text-white">Previsão de posição no pit</h2>
            </div>
            <SessionChips race />
            <p className="text-f1-text leading-relaxed mb-3">
              Mostra a posição em que o piloto voltaria se parasse agora. A previsão usa o tempo exato de pit lane de cada circuito, calculado a partir das entradas e saídas de pit de todas as corridas de 2025.
            </p>
            <p className="text-f1-text leading-relaxed mb-3">
              A perda no pit é medida pelo tempo exato que cada piloto passa no pit lane (PitOutTime &minus; PitInTime), o que dá uma base precisa por circuito, sem influência do ritmo no resto da volta. A previsão soma essa perda à diferença atual do piloto e vê onde ele se encaixaria na ordem.
            </p>
            <p className="text-f1-text leading-relaxed mb-3">
              Com Safety Car ou Virtual Safety Car, é usada uma perda menor (73% da perda em bandeira verde), já que parar sob neutralização custa relativamente menos. As previsões aparecem a partir da volta 5.
            </p>
            <h3 className="text-sm font-bold text-f1-red uppercase tracking-wider mb-2">
              Indicador de confiança
            </h3>
            <p className="text-f1-text leading-relaxed mb-3">
              Como as previsões usam tempos médios de pit, o resultado real pode variar. O indicador de confiança (ativável nas configurações) colore cada previsão conforme a margem para a posição de trás:
            </p>
            <ul className="text-f1-text leading-relaxed space-y-1 ml-4 list-disc">
              <li><span className="text-f1-muted font-bold">Padrão</span> 986</li>
              <li><span className="text-yellow-400 font-bold">999</span> — margem de 1s a 2,5s, um pit mais lento pode custar uma posição</li>
              <li><span className="text-red-400 font-bold">Vermelho</span> — margem abaixo de 1s, muito apertado</li>
            </ul>
            <h3 className="text-sm font-bold text-f1-red uppercase tracking-wider mt-4 mb-2">
              Diferenças no pit
            </h3>
            <p className="text-f1-text leading-relaxed">
              Ao lado da posição prevista, aparecem duas diferenças empilhadas: para o carro da frente (em cima) e para o de trás (embaixo) depois do pit stop. Isso ajuda a ver se o piloto voltaria com pista livre ou no tráfego, e o quão segura seria a posição prevista.
            </p>
          </section>
          </>
        )}

        {tab === "track-map" && (
          <>

          {/* Track Map & Car Positions */}
          <section className="bg-f1-card border border-f1-border rounded-xl p-6">
            <h2 className="text-lg font-bold text-white mb-1">Posição dos carros</h2>
            <SessionChips practice qualifying race />
            <p className="text-f1-text leading-relaxed">
              Um mapa da pista mostra a posição dos carros, atualizada a cada 0,5 segundo com movimento suave. Clique num piloto na tabela ou no mapa para destacá-lo. A orientação da pista segue a visão usual da transmissão de cada circuito. Nos replays, as posições vêm da sessão processada; ao vivo, vêm da transmissão ao vivo da F1, que exige login no F1 TV.
            </p>
          </section>

          {/* Track Elevation */}
          <section className="bg-f1-card border border-f1-border rounded-xl p-6">
            <h2 className="text-lg font-bold text-white mb-1">Altimetria da pista</h2>
            <SessionChips practice qualifying race />
            <p className="text-f1-text leading-relaxed mb-4">
              A linha da pista pode ser colorida pela altitude, tirada da mesma telemetria de GPS do mapa. O ponto mais baixo da volta fica escuro e o mais alto, claro:
            </p>
            <div className="flex items-center gap-3 mb-4">
              <span className="text-xs text-f1-muted">Baixo</span>
              <div
                className="h-3 flex-1 max-w-xs rounded-sm border border-black/30"
                style={{ background: "linear-gradient(to right, #33384a, #6fb7d6, #ffffff)" }}
              />
              <span className="text-xs text-f1-muted">Alto</span>
            </div>
            <p className="text-f1-text leading-relaxed">
              As cores usam uma escala fixa para todos os circuitos, e não a variação de cada pista, então um circuito plano fica todo escuro e um com morros mostra um degradê forte. Uma legenda no mapa mostra a variação total de altitude. Ative em Configurações &gt; Mapa da pista.
            </p>
          </section>

          {/* Track Status */}
          <section className="bg-f1-card border border-f1-border rounded-xl p-6">
            <h2 className="text-lg font-bold text-white mb-1">Situação da pista e bandeiras</h2>
            <SessionChips practice qualifying race />
            <p className="text-f1-text leading-relaxed mb-3">
              As bandeiras aparecem no mapa da pista por setor de fiscais, mostrando exatamente onde estão os incidentes, e não só uma situação geral.
            </p>
            <h3 className="text-sm font-bold text-f1-red uppercase tracking-wider mb-2">
              Bandeiras por setor de fiscais
            </h3>
            <p className="text-f1-text leading-relaxed mb-3">
              Quando é agitada uma bandeira amarela ou amarela dupla, um indicador colorido aparece na posição exata do setor de fiscais no mapa. Se houver um piloto envolvido, a sigla dele aparece ao lado do indicador.
            </p>
            <ul className="text-f1-text leading-relaxed space-y-1 ml-4 list-disc mb-3">
              <li><span className="text-yellow-400 font-bold">Círculo amarelo</span> &mdash; bandeira amarela simples naquele setor</li>
              <li><span className="text-yellow-400 font-bold">Círculo amarelo com anel externo</span> &mdash; bandeira amarela dupla (mais grave, os pilotos precisam reduzir bastante)</li>
              <li><span className="text-red-400 font-bold">Círculo vermelho</span> &mdash; bandeira vermelha naquele local</li>
            </ul>
            <h3 className="text-sm font-bold text-f1-red uppercase tracking-wider mb-2">
              Pista inteira colorida
            </h3>
            <p className="text-f1-text leading-relaxed mb-3">
              Para situações que valem para a pista toda, o contorno inteiro muda de cor:
            </p>
            <ul className="text-f1-text leading-relaxed space-y-1 ml-4 list-disc mb-3">
              <li><span className="text-yellow-400 font-bold">Amarelo</span> &mdash; Safety Car ou Virtual Safety Car na pista</li>
              <li><span className="text-red-400 font-bold">Vermelho</span> &mdash; sessão com bandeira vermelha</li>
            </ul>
            <p className="text-f1-text leading-relaxed">
              Bandeiras amarelas localizadas (em um ou dois setores) não colorem a pista toda, para deixar claro exatamente onde está o incidente.
            </p>
          </section>

          {/* Sectors on the track map */}
          <section id="sectors-map" className="bg-f1-card border border-f1-border rounded-xl p-6 scroll-mt-20">
            <h2 className="text-lg font-bold text-white mb-1">Setores no mapa da pista</h2>
            <SessionChips practice qualifying />
            <p className="text-f1-text leading-relaxed mb-3">
              Clique em <span className="font-bold text-white">Mostrar setores</span> no mapa da pista. A pista é colorida pelos setores do piloto selecionado na volta atual &mdash; roxo, verde ou amarelo, e cinza até cada um ser completado. Com dois pilotos selecionados, alterne entre eles ao lado do botão; sem nenhum, mostra o líder.
            </p>
            <p className="text-f1-text leading-relaxed">
              No computador, alterne entre <span className="font-bold text-white">Setores</span> e{" "}
              <span className="font-bold text-white">Minissetores</span> ao lado do botão para colorir a pista minissetor a minissetor. Ao vivo, os minissetores aparecem no mapa depois que cada um foi percorrido algumas vezes, geralmente em uma ou duas voltas.
            </p>
          </section>
          </>
        )}

        {tab === "analysis" && (
          <>

          {/* Lap Analysis */}
          <section className="bg-f1-card border border-f1-border rounded-xl p-6">
            <div className="flex items-center gap-2 mb-1">
              <h2 className="text-lg font-bold text-white">Análise de voltas</h2>
              <span className="px-1.5 py-0.5 text-[9px] font-bold uppercase rounded bg-f1-red/20 text-f1-red leading-none">Beta</span>
            </div>
            <SessionChips practice qualifying race />
            <p className="text-f1-text leading-relaxed mb-3">
              Um painel para analisar o ritmo dos pilotos. No computador, abra pelo botão &quot;Voltas&quot; no mapa da pista &mdash; o painel abre à esquerda. No celular, aparece como uma seção recolhível. Ao vivo, ele vai sendo montado com as voltas completadas desde que a cronometragem ao vivo conectou.
            </p>
            <p className="text-xs font-bold text-f1-muted uppercase tracking-wider mb-2">Corridas</p>
            <p className="text-f1-text leading-relaxed mb-3">
              Escolha até dois pilotos nos menus do topo do painel para comparar os tempos de volta lado a lado.
            </p>
            <div className="space-y-4">
              <div className="flex items-center gap-3 flex-wrap sm:flex-nowrap">
                <span className="w-24 flex-shrink-0 text-sm font-bold text-f1-muted">Gráfico de voltas</span>
                <span className="flex items-center gap-1 flex-shrink-0">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                </span>
                <span className="w-full sm:w-auto text-sm text-f1-text">Gráfico de linha dos tempos de volta ao longo da corrida. Cada piloto tem a cor da sua equipe. As voltas de pit ficam fora da linha e são marcadas com pontos.</span>
              </div>
              <div className="flex items-center gap-3 flex-wrap sm:flex-nowrap">
                <span className="w-24 flex-shrink-0 text-sm font-bold text-f1-muted">Lista de voltas</span>
                <span className="flex items-center gap-1.5 flex-shrink-0">
                  <span className="text-[10px] tabular-nums text-white">1:32.456</span>
                  <span className="text-[8px] font-bold text-yellow-400">PIT</span>
                  <span className="w-3 h-3 rounded-full flex items-center justify-center text-[6px] font-extrabold leading-none border" style={{ borderColor: "#FF3333", color: "#FF3333" }}>S</span>
                </span>
                <span className="w-full sm:w-auto text-sm text-f1-text">Volta a volta, com o tempo, o composto do pneu e os pit stops de cada piloto selecionado.</span>
              </div>
            </div>
            <p className="text-xs font-bold text-f1-muted uppercase tracking-wider mt-6 mb-3">Classificação e treinos</p>
            <LapAnalysisGuide />

            <div className="mt-6 pt-5 border-t border-f1-border">
              <div className="flex items-center gap-2 mb-1">
                <h3 className="text-base font-bold text-white">Domínio na pista</h3>
                <span className="px-1.5 py-0.5 text-[9px] font-bold uppercase rounded bg-white/10 text-f1-muted leading-none">Computador</span>
              </div>
              <SessionChips practice qualifying />
              <p className="text-f1-text leading-relaxed mb-3">
                Veja em que parte da pista um piloto supera o outro. Em Análise de voltas &gt; Comparar, escolha dois pilotos e aperte Domínio na pista: o mapa é colorido por quem foi mais rápido em cada trecho das melhores voltas, com a contagem de trechos que cada um venceu. Funciona em replays e ao vivo.
              </p>
              <img
                src="/track-dominance.png"
                alt="Domínio na pista: as melhores voltas de Antonelli e Leclerc na classificação do GP dos Estados Unidos de 2026, com a pista colorida por quem foi mais rápido em cada trecho"
                className="w-full max-w-2xl rounded-lg border border-f1-border"
              />
              <p className="text-xs text-f1-muted mt-2">
                Antonelli (16 trechos) e Leclerc (9) na classificação do GP dos Estados Unidos de 2026.
              </p>
            </div>
          </section>

          {/* Telemetry */}
          <section className="bg-f1-card border border-f1-border rounded-xl p-6">
            <h2 className="text-lg font-bold text-white mb-1">Telemetria</h2>
            <SessionChips practice qualifying race />
            <p className="text-f1-text leading-relaxed mb-3">
              Clique em qualquer piloto para abrir a telemetria detalhada da volta atual. Ao vivo, a telemetria exige login no F1 TV e só aparece no computador.
            </p>
            <div className="space-y-3">
              <div className="flex gap-3">
                <span className="w-20 flex-shrink-0 text-sm font-bold text-f1-muted">Velocidade</span>
                <span className="w-full sm:w-auto text-sm text-f1-text">Velocidade do carro em km/h, em relação à distância percorrida na pista.</span>
              </div>
              <div className="flex gap-3">
                <span className="w-20 flex-shrink-0 text-sm font-bold text-f1-muted">Acelerador</span>
                <span className="w-full sm:w-auto text-sm text-f1-text">Uso do acelerador de 0 a 100%.</span>
              </div>
              <div className="flex gap-3">
                <span className="w-20 flex-shrink-0 text-sm font-bold text-f1-muted">Freio</span>
                <span className="w-full sm:w-auto text-sm text-f1-text">Pressão no freio, mostrada como ligado/desligado.</span>
              </div>
              <div className="flex gap-3">
                <span className="w-20 flex-shrink-0 text-sm font-bold text-f1-muted">Marcha</span>
                <span className="w-full sm:w-auto text-sm text-f1-text">Marcha engatada, de 1 a 8.</span>
              </div>
              <div className="flex gap-3">
                <span className="w-20 flex-shrink-0 text-sm font-bold text-f1-muted">DRS</span>
                <span className="w-full sm:w-auto text-sm text-f1-text">Acionamento do DRS. Disponível em sessões de 2025 e anteriores. O DRS saiu dos carros em 2026.</span>
              </div>
            </div>
          </section>
          </>
        )}

        {tab === "session-feed" && (
          <>

          {/* Race Control Messages */}
          <section className="bg-f1-card border border-f1-border rounded-xl p-6">
            <h2 className="text-lg font-bold text-white mb-1">Mensagens da direção de prova</h2>
            <SessionChips practice qualifying race />
            <p className="text-f1-text leading-relaxed mb-3">
              Um feed de todas as mensagens da direção de prova fica no botão RC do mapa da pista. Inclui investigações dos comissários, punições, voltas anuladas por limite de pista, liberação do DRS, entrada do safety car e outros comunicados oficiais.
            </p>
            <p className="text-f1-text leading-relaxed mb-3">
              Cada mensagem tem uma cor para facilitar a leitura:
            </p>
            <ul className="text-f1-text leading-relaxed space-y-1 ml-4 list-disc mb-3">
              <li><span className="text-orange-400 font-bold">Laranja</span> — incidente anotado ou em investigação</li>
              <li><span className="text-red-400 font-bold">Vermelho</span> — punição aplicada</li>
              <li><span className="text-green-400 font-bold">Verde</span> — liberado / nenhuma ação</li>
              <li><span className="text-f1-muted font-bold">Cinza</span> — outras mensagens (DRS, bandeiras etc.)</li>
            </ul>
            <h3 className="text-sm font-bold text-f1-red uppercase tracking-wider mb-2">
              Indicadores nos pilotos
            </h3>
            <p className="text-f1-text leading-relaxed">
              Quando um piloto está sob investigação ou foi punido, aparece um indicador ao lado do nome na tabela: um triângulo de alerta (<svg className="w-3.5 h-3.5 text-orange-400 inline -mt-0.5" viewBox="0 0 24 24"><path d="M12 2L2 22h20L12 2zm0 6v7m0 2v2" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" /></svg>) para investigações e uma exclamação num círculo (<svg className="w-3.5 h-3.5 text-red-500 inline -mt-0.5" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" strokeWidth="2.5" /><path d="M12 8v5m0 3v.01" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" /></svg>) para punições. Eles somem sozinhos quando os comissários dão a decisão.
            </p>
          </section>

          {/* Weather */}
          <section className="bg-f1-card border border-f1-border rounded-xl p-6">
            <h2 className="text-lg font-bold text-white mb-1">Clima</h2>
            <SessionChips practice qualifying race />
            <p className="text-f1-text leading-relaxed">
              As condições do tempo aparecem no cabeçalho da sessão: temperatura do ar, temperatura da pista, umidade, velocidade e direção do vento e se está chovendo. Cada item pode ser ligado ou desligado nas configurações.
            </p>
          </section>

          {/* Team radio */}
          <section className="bg-f1-card border border-f1-border rounded-xl p-6">
            <h2 className="text-lg font-bold text-white mb-1">Rádio das equipes</h2>
            <SessionChips practice qualifying race />
            <p className="text-f1-text leading-relaxed mb-3">
              As mensagens de rádio que a F1 escolhe para a transmissão mundial aparecem sobre o mapa da pista, com o piloto, a legenda e o áudio, em replays e ao vivo. Nos replays, o áudio toca em velocidade 1x. Exige login no F1 TV.
            </p>
            <p className="text-f1-text leading-relaxed">
              As legendas são feitas localmente com o Whisper. A precisão varia com a qualidade e a clareza do áudio. Desligue o rádio ou o áudio dele em Configurações &gt; Rádio das equipes. A mesma aba escolhe os modelos de legenda para replays e ao vivo e, com uma chave do OpenRouter, pode pedir a um modelo de IA que ouça cada mensagem e corrija a legenda.
            </p>
          </section>
          </>
        )}

        {tab === "watching" && (
          <>

          {/* Live Timing */}
          <section className="bg-f1-card border border-f1-border rounded-xl p-6">
            <h2 className="text-lg font-bold text-white mb-1">Cronometragem ao vivo</h2>
            <SessionChips practice qualifying race />
            <p className="text-f1-text leading-relaxed mb-3">
              Durante as sessões da F1, a cronometragem ao vivo se conecta direto à transmissão de dados da F1 para a tabela, pneus, setores e minissetores, mensagens da direção de prova e clima. Na classificação, mostra a parte atual (Q1, Q2 ou Q3) e o tempo restante.
            </p>
            <p className="text-f1-text leading-relaxed mb-3">
              Com login no F1 TV, o mapa mostra todos os carros, o rádio das equipes toca conforme é transmitido e os pilotos selecionados mostram telemetria. A Análise de voltas e os outros recursos só de replay (veja{" "}
              <a href="#availability" className="text-f1-red hover:underline font-semibold">Disponibilidade dos recursos</a>) ficam disponíveis quando a sessão é processada, geralmente 1&ndash;2 horas depois da bandeirada.
            </p>
            <h3 className="text-sm font-bold text-f1-red uppercase tracking-wider mb-2">
              Atraso da transmissão
            </h3>
            <p className="text-f1-text leading-relaxed">
              O controle de atraso segura os dados ao vivo até ficarem alinhados com o seu streaming ou a TV. Ajuste o atraso para o quanto a sua transmissão está atrasada, e a tabela vai atualizar junto com o que você vê na tela. O ajuste é salvo automaticamente. Você também pode digitar um valor exato.
            </p>
          </section>

          {/* Playback */}
          <section className="bg-f1-card border border-f1-border rounded-xl p-6">
            <h2 className="text-lg font-bold text-white mb-1">Controles de reprodução</h2>
            <SessionChips practice qualifying race />
            <p className="text-f1-text leading-relaxed mb-3">
              Controle a velocidade do replay de 0,5x a 20x, avance ou volte 5 segundos, 30 segundos, 1 minuto ou 5 minutos, ou pule direto para qualquer volta. Uma barra mostra a posição atual na sessão. Em classificações e treinos, aparecem o tempo decorrido e o restante.
            </p>
            <h3 className="text-sm font-bold text-f1-red uppercase tracking-wider mb-2">
              Tempo da sessão
            </h3>
            <p className="text-f1-text leading-relaxed">
              O tempo total da sessão fica oculto por padrão para evitar spoilers &mdash; uma sessão mais longa que o normal pode revelar bandeiras vermelhas e interrupções. Você pode ativá-lo nas configurações.
            </p>
          </section>

          {/* Sync to a recording */}
          <section className="bg-f1-card border border-f1-border rounded-xl p-6">
            <h2 className="text-lg font-bold text-white mb-1">Sincronizar com uma gravação</h2>
            <SessionChips practice qualifying race />
            <p className="text-f1-text leading-relaxed mb-3">
              Está assistindo uma gravação em outro lugar? Sincronize o replay com ela para os dados baterem com o que está na tela. (Para assistir o F1 TV dentro do app, veja{" "}
              <a href="#broadcast" className="text-f1-red hover:underline font-semibold">Transmissão</a>.) Há duas formas de sincronizar:
            </p>
            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-bold text-white mb-1">Sincronizar por foto</h3>
                <p className="text-sm text-f1-text leading-relaxed">
                  Tire uma captura da transmissão mostrando a tabela e envie. Um modelo de visão lê as posições e as diferenças da imagem e encontra o ponto correspondente no replay, pulando automaticamente para o momento certo.
                </p>
              </div>
              <div>
                <h3 className="text-sm font-bold text-white mb-1">Sincronização manual</h3>
                <p className="text-sm text-f1-text leading-relaxed">
                  Digite as diferenças dos dois primeiros pilotos como aparecem na transmissão. O replay procura o momento mais parecido com essas diferenças e sincroniza nele.
                </p>
              </div>
            </div>
          </section>

          {/* Picture-in-picture */}
          <section className="bg-f1-card border border-f1-border rounded-xl p-6">
            <h2 className="text-lg font-bold text-white mb-1">Picture-in-Picture</h2>
            <SessionChips practice qualifying race />
            <p className="text-f1-text leading-relaxed">
              Abra o mapa da pista e a tabela numa janelinha separada, para colocá-la ao lado de uma transmissão. Use o botão Picture-in-Picture, em replays e ao vivo. Só no computador.
            </p>
          </section>
          </>
        )}

        {tab === "broadcast" && (
          <>
          {/* Broadcast */}
          <section className="bg-f1-card border border-f1-border rounded-xl p-6">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <h2 className="text-lg font-bold text-white">Transmissão</h2>
              <span className="px-1.5 py-0.5 text-[9px] font-bold uppercase rounded bg-f1-red/20 text-f1-red leading-none">F1 TV Pro ou Premium</span>
              <span className="px-1.5 py-0.5 text-[9px] font-bold uppercase rounded bg-white/10 text-f1-muted leading-none">Só em replays</span>
            </div>
            <SessionChips practice qualifying race />
            <p className="text-f1-text leading-relaxed mb-3">
              Assista o replay do F1 TV da sessão dentro do app, junto com a cronometragem. Mude o mapa da pista para{" "}
              <span className="font-bold text-white">Transmissão</span> (no canto superior direito do mapa). O app encontra a sessão no F1 TV para você, e o vídeo segue o replay: tocar, pausar, mudar a velocidade e pular, inclusive Pular para a relargada depois de uma bandeira vermelha.
            </p>
            <p className="text-f1-text leading-relaxed mb-3">
              <span className="font-bold text-white">Multivisão</span> coloca a transmissão ao lado das câmeras onboard de até dois pilotos e do mapa da pista. <span className="font-bold text-white">Visão única</span> mostra a transmissão na largura toda, com o mapa por cima. Escolha qual abre em Configurações &gt; Transmissão, junto com a telemetria onboard, o mapa da pista e a direção de prova.
            </p>
            <p className="text-f1-text leading-relaxed mb-5">
              Cada onboard pode mostrar a <span className="font-bold text-white">telemetria</span> (velocidade, marcha, acelerador e freio) do piloto e, em classificações e treinos, uma{" "}
              <span className="font-bold text-white">faixa de setores</span>: os minissetores dele numa linha ao longo da borda inferior do vídeo, preenchidos de roxo, verde ou amarelo conforme ele completa cada um, para você acompanhar a volta enquanto assiste.
            </p>
            <BroadcastGuide />
          </section>

          {/* Automatic sync */}
          <section className="bg-f1-card border border-f1-border rounded-xl p-6">
            <h2 className="text-lg font-bold text-white mb-1">Sincronização automática</h2>
            <SessionChips practice qualifying race />
            <p className="text-f1-text leading-relaxed mb-3">
              Na primeira vez que você abre a transmissão de uma sessão, o servidor descobre onde o replay começa no vídeo do F1 TV. O som de uma câmera onboard é quase todo o motor do carro, e o tom do motor sobe e desce com a rotação, que está nos dados de cronometragem. O servidor desliza um contra o outro até se alinharem e confere a resposta com um segundo piloto.
            </p>
            <div className="mb-4">
              <SyncDiagram />
            </div>
            <ul className="space-y-2 mb-4 text-sm text-f1-text leading-relaxed">
              <li><span className="font-bold text-white">Corridas e sprints</span> usam a largada, que nunca se repete.</li>
              <li><span className="font-bold text-white">Classificações e treinos</span> usam uma volta lançada.</li>
              <li>Isso roda quando a sessão é processada, enquanto o áudio do F1 TV ainda pode ser lido. Se não der certo, tenta de novo na primeira vez que você abre a transmissão (cerca de um minuto). O resultado fica salvo para aquela sessão.</li>
              <li>As onboards seguem a transmissão: todos os vídeos do F1 TV de uma sessão compartilham a mesma linha do tempo.</li>
            </ul>
            <p className="text-xs font-bold text-f1-muted uppercase tracking-wider mb-2">Como foi sincronizado</p>
            <p className="text-sm text-f1-text leading-relaxed mb-3">
              Os controles que aparecem ao passar o mouse mostram uma linha dizendo como a sessão foi sincronizada:
            </p>
            <ul className="space-y-2 mb-4 text-sm text-f1-text leading-relaxed">
              <li className="flex items-start gap-2"><span className="mt-1.5 w-2 h-2 rounded-full bg-green-400 flex-shrink-0" /><span><span className="font-bold text-white">Sincronizado pelo som do motor</span> — alinhado como acima, com os pilotos usados. Preciso em frações de segundo.</span></li>
              <li className="flex items-start gap-2"><span className="mt-1.5 w-2 h-2 rounded-full bg-white/50 flex-shrink-0" /><span><span className="font-bold text-white">Alinhando com a cronometragem</span> — o primeiro alinhamento está rodando.</span></li>
              <li className="flex items-start gap-2"><span className="mt-1.5 w-2 h-2 rounded-full bg-amber-400 flex-shrink-0" /><span><span className="font-bold text-white">Sincronizado pela marca de tempo do vídeo</span> — o F1 TV protege o áudio de algumas sessões, então o som do motor não pode ser comparado. Usa-se a marca de tempo do vídeo do F1 TV, geralmente com erro de um ou dois segundos.</span></li>
              <li className="flex items-start gap-2"><span className="mt-1.5 w-2 h-2 rounded-full bg-amber-400 flex-shrink-0" /><span><span className="font-bold text-white">Sincronizado manualmente</span> — você mesmo alinhou.</span></li>
            </ul>
            <p className="text-xs font-bold text-f1-muted uppercase tracking-wider mb-2">Ajustando</p>
            <p className="text-sm text-f1-text leading-relaxed">
              Use <span className="font-bold text-white">Ajuste fino da sincronização</span> para mover o vídeo ±0,5s ou ±5s; o ajuste aparece numa etiqueta, e o × dela volta à sincronização automática. Para controle total, aperte{" "}
              <span className="font-bold text-white">Sincronizar manualmente</span>, ao lado do status da sincronização: o vídeo ganha a própria barra de reprodução, você encontra o momento que bate com a cronometragem (o apagar das luzes ou um carro cruzando a linha funcionam bem) e aperta <span className="font-bold text-white">Sincronizar aqui</span>. Pausar o replay antes facilita. A sincronização manual fica valendo até você apagá-la.
            </p>
          </section>

          {/* Good to know */}
          <section className="bg-f1-card border border-f1-border rounded-xl p-6">
            <h2 className="text-lg font-bold text-white mb-3">Bom saber</h2>
            <ul className="space-y-2 text-sm text-f1-text leading-relaxed">
              <li><span className="font-bold text-white">Por enquanto, só em replays.</span> A transmissão ainda não está disponível ao vivo.</li>
              <li><span className="font-bold text-white">Exige F1 TV Pro ou Premium.</span> O botão Transmissão aparece quando você entra com um desses planos. Só em instalação própria.</li>
              <li><span className="font-bold text-white">Tablets e telas maiores.</span> Em telas de toque, toque no vídeo para mostrar os controles.</li>
              <li><span className="font-bold text-white">Onde você está faz diferença.</span> O F1 TV só transmite em alguns países e decide pelo seu endereço de internet, então uma VPN pode impedir o vídeo. Se não tocar, a mensagem diz o motivo, com um botão Tentar de novo.</li>
              <li><span className="font-bold text-white">A qualidade da imagem se ajusta à sua conexão.</span> Começa mais baixa e melhora depois de alguns segundos, e cai um pouco depois de um salto.</li>
              <li><span className="font-bold text-white">O rádio toca duas vezes?</span> A transmissão muitas vezes toca a mesma mensagem: desligue o Áudio do rádio nos controles e mantenha as legendas.</li>
            </ul>
          </section>
          </>
        )}

        {tab === "availability" && (
          <>
          {/* Feature availability */}
          <section id="availability" className="bg-f1-card border border-f1-border rounded-xl p-6 scroll-mt-20">
            <h2 className="text-lg font-bold text-white mb-4">Disponibilidade dos recursos</h2>
            <div className="overflow-x-auto -mx-2">
              <table className="w-full text-sm min-w-[480px]">
                <thead>
                  <tr className="text-[10px] font-bold text-f1-muted uppercase tracking-wider">
                    <th className="text-left font-bold px-2 pb-2">Recurso</th>
                    {AVAILABILITY_SESSIONS.map((s) => (
                      <th key={s} className="text-center font-bold px-2 pb-2 whitespace-nowrap">{s}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-f1-border">
                  {AVAILABILITY.map(([name, ...cells]) => (
                    <tr key={name}>
                      <td className="px-2 py-1.5 text-f1-text">{name}</td>
                      {cells.map((c, i) => (
                        <td key={i} className="px-2 py-1.5">
                          <span className="flex items-center justify-center gap-1">
                            {c === "-" ? (
                              <span className="text-f1-muted">&mdash;</span>
                            ) : (
                              <>
                                {c.includes("R") && <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-white/10 text-white">Replay</span>}
                                {c.includes("L") && <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-f1-red/20 text-f1-red">Ao vivo</span>}
                              </>
                            )}
                          </span>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-xs text-f1-muted">
              Posição dos carros, telemetria e rádio das equipes ao vivo exigem login no F1 TV. Os minissetores são só para computador.
            </p>
          </section>
          </>
        )}

        <div className="text-center pt-4">
          <button
            onClick={() => {
              if (window.opener || window.history.length <= 1) {
                window.close();
              } else {
                window.location.href = "/";
              }
            }}
            className="text-f1-muted hover:text-white transition-colors text-sm"
          >
            Voltar à escolha de sessão
          </button>
        </div>
      </div>
      <SiteFooter />
    </div>
  );
}
