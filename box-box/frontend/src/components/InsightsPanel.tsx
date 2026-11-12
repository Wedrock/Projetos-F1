"use client";

import { useEffect, useMemo, useState } from "react";
import { ReplayDriver } from "@/hooks/useReplaySocket";
import { apiFetch } from "@/lib/api";
import { TYRE_COLORS, TYRE_SHORT } from "@/lib/constants";
import { TyreModel, tyreHealth, healthColor } from "@/lib/tyreModel";

/** Tyre strategy, live championship standings and the tyre model's fit.
 *  Ported from f1-race-replay's insights windows. */

interface Stint {
  stint: number;
  compound: string | null;
  start_lap: number;
  end_lap: number;
  laps: number;
  start_tyre_life: number;
  new: boolean;
}

interface Strategy {
  total_laps: number;
  drivers: Record<string, Stint[]>;
}

interface Standings {
  scoring: boolean;
  points: number[];
  drivers: { code: string; name: string; points: number; constructor_id: string | null }[];
  constructors: { id: string; name: string; points: number }[];
}

interface Props {
  year: number;
  round: number;
  sessionType: string;
  drivers: ReplayDriver[];
  currentLap: number;
  tyreModel: TyreModel;
  onClose: () => void;
}

type Tab = "strategy" | "standings" | "tyres";

export default function InsightsPanel({ year, round, sessionType, drivers, currentLap, tyreModel, onClose }: Props) {
  const isRace = sessionType === "R" || sessionType === "S";
  const [tab, setTab] = useState<Tab>("strategy");

  const tabs: { id: Tab; label: string }[] = [
    { id: "strategy", label: "Estratégia" },
    ...(isRace ? [{ id: "standings" as Tab, label: "Campeonato" }] : []),
    { id: "tyres", label: "Modelo de pneus" },
  ];

  return (
    <div className="w-[380px] max-w-[calc(100vw-24px)] max-h-full flex flex-col bg-f1-card/95 border border-f1-border rounded-lg shadow-xl backdrop-blur-sm overflow-hidden">
      <div className="flex items-center gap-1 px-2 py-1.5 border-b border-f1-border">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase transition-colors ${
              tab === t.id ? "bg-f1-red text-white" : "text-f1-muted hover:text-white"
            }`}
          >
            {t.label}
          </button>
        ))}
        <button
          onClick={onClose}
          className="ml-auto px-1.5 py-0.5 text-[9px] font-bold text-f1-muted hover:text-white border border-f1-border rounded transition-colors"
        >
          Fechar
        </button>
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto p-2">
        {tab === "strategy" && <StrategyView year={year} round={round} sessionType={sessionType} drivers={drivers} currentLap={currentLap} />}
        {tab === "standings" && isRace && <StandingsView year={year} round={round} sessionType={sessionType} drivers={drivers} />}
        {tab === "tyres" && <TyreModelView model={tyreModel} drivers={drivers} currentLap={currentLap} />}
      </div>
    </div>
  );
}

function useSessionData<T>(path: string): { data: T | null; error: string | null } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    apiFetch<T>(path)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(String(e?.message || e)); });
    return () => { cancelled = true; };
  }, [path]);
  return { data, error };
}

function byPosition(drivers: ReplayDriver[]): ReplayDriver[] {
  return [...drivers].sort((a, b) => (a.position ?? 999) - (b.position ?? 999));
}

// ---------------------------------------------------------------------------

function StrategyView({ year, round, sessionType, drivers, currentLap }: { year: number; round: number; sessionType: string; drivers: ReplayDriver[]; currentLap: number }) {
  const { data, error } = useSessionData<Strategy>(`/api/sessions/${year}/${round}/strategy?type=${sessionType}`);
  if (error) return <p className="text-[11px] text-f1-muted py-4 text-center">A estratégia de pneus não está disponível para esta sessão.</p>;
  if (!data) return <p className="text-[11px] text-f1-muted py-4 text-center">Carregando…</p>;

  const total = Math.max(data.total_laps, 1);
  // Only what has happened so far, so the panel never spoils the session
  const upTo = Math.max(1, Math.min(currentLap || total, total));

  return (
    <div className="flex flex-col gap-[3px]">
      <div className="flex items-center text-[9px] text-f1-muted mb-1">
        <span className="w-9" />
        <span className="flex-1 flex justify-between"><span>Volta 1</span><span>Volta {total}</span></span>
      </div>
      {byPosition(drivers).map((drv) => {
        const stints = (data.drivers[drv.abbr] || []).filter((s) => s.start_lap <= upTo);
        return (
          <div key={drv.abbr} className="flex items-center gap-1">
            <span className="w-8 text-[10px] font-bold" style={{ color: drv.color }}>{drv.abbr}</span>
            <div className="relative flex-1 h-3.5 bg-white/5 rounded-sm overflow-hidden">
              {stints.map((s) => {
                const end = Math.min(s.end_lap, upTo);
                const left = ((s.start_lap - 1) / total) * 100;
                const width = ((end - s.start_lap + 1) / total) * 100;
                const color = (s.compound && TYRE_COLORS[s.compound]) || "#666";
                return (
                  <div
                    key={s.stint}
                    className="absolute top-0 bottom-0 border-r border-black/60 flex items-center justify-center text-[8px] font-extrabold"
                    style={{ left: `${left}%`, width: `${width}%`, backgroundColor: color, color: s.compound === "HARD" || s.compound === "MEDIUM" ? "#000" : "#FFF", opacity: s.new ? 1 : 0.7 }}
                    title={`${s.compound ?? "Desconhecido"}${s.new ? " (novo)" : ` (usado, ${s.start_tyre_life} voltas de uso)`} · voltas ${s.start_lap}–${end}`}
                  >
                    {width > 6 ? (s.compound ? TYRE_SHORT[s.compound] : "?") : ""}
                  </div>
                );
              })}
              <div className="absolute top-0 bottom-0 w-px bg-white/70" style={{ left: `${(upTo / total) * 100}%` }} />
            </div>
          </div>
        );
      })}
      <p className="text-[9px] text-f1-muted mt-2">Passagens esmaecidas começaram com um jogo usado.</p>
    </div>
  );
}

// ---------------------------------------------------------------------------

function StandingsView({ year, round, sessionType, drivers }: { year: number; round: number; sessionType: string; drivers: ReplayDriver[] }) {
  const { data, error } = useSessionData<Standings>(`/api/sessions/${year}/${round}/standings?type=${sessionType}`);
  const [view, setView] = useState<"drivers" | "constructors">("drivers");

  const table = useMemo(() => {
    if (!data) return null;
    const scored = (drv: ReplayDriver | undefined) =>
      drv && !drv.retired && drv.position != null ? data.points[drv.position - 1] ?? 0 : 0;
    const inSession = new Map(drivers.map((d) => [d.abbr, d]));

    const before = new Map<string, number>();
    data.drivers.forEach((d, i) => before.set(d.code, i));
    const driverRows = data.drivers.map((d) => {
      const drv = inSession.get(d.code);
      return { key: d.code, label: d.code, color: drv?.color, before: d.points, gained: scored(drv) };
    });
    for (const drv of drivers) {
      if (!before.has(drv.abbr)) driverRows.push({ key: drv.abbr, label: drv.abbr, color: drv.color, before: 0, gained: scored(drv) });
    }

    // Ergast's constructors -> this session's team names, through their drivers
    const teamOf = new Map<string, string>();
    for (const d of data.drivers) {
      const drv = inSession.get(d.code);
      if (d.constructor_id && drv?.team) teamOf.set(d.constructor_id, drv.team);
    }
    const teamColor = new Map(drivers.map((d) => [d.team, d.color]));
    const consRows = data.constructors.map((c) => {
      const team = teamOf.get(c.id);
      const gained = team ? drivers.filter((d) => d.team === team).reduce((sum, d) => sum + scored(d), 0) : 0;
      return { key: c.id, label: team || c.name, color: team ? teamColor.get(team) : undefined, before: c.points, gained };
    });

    const rank = (rows: typeof driverRows) => {
      const prior = new Map([...rows].sort((a, b) => b.before - a.before).map((r, i) => [r.key, i]));
      return [...rows]
        .sort((a, b) => b.before + b.gained - (a.before + a.gained))
        .map((r, i) => ({ ...r, total: r.before + r.gained, moved: (prior.get(r.key) ?? i) - i }));
    };
    return { drivers: rank(driverRows), constructors: rank(consRows) };
  }, [data, drivers]);

  if (error) return <p className="text-[11px] text-f1-muted py-4 text-center">A classificação do campeonato está indisponível no momento.</p>;
  if (!table) return <p className="text-[11px] text-f1-muted py-4 text-center">Carregando…</p>;

  const rows = view === "drivers" ? table.drivers : table.constructors;
  return (
    <div>
      <div className="flex items-center gap-1 mb-2">
        {(["drivers", "constructors"] as const).map((v) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={`px-2 py-0.5 rounded text-[10px] font-bold transition-colors ${view === v ? "bg-white/15 text-white" : "text-f1-muted hover:text-white"}`}
          >
            {v === "drivers" ? "Pilotos" : "Construtores"}
          </button>
        ))}
        <span className="ml-auto text-[9px] text-f1-muted">Se a ordem ficar como está agora</span>
      </div>
      <div className="flex flex-col">
        {rows.map((r, i) => (
          <div key={r.key} className="flex items-center gap-2 py-0.5 text-[11px] border-b border-white/5">
            <span className="w-5 text-right text-f1-muted tabular-nums">{i + 1}</span>
            <span className={`w-6 text-[9px] font-bold tabular-nums ${r.moved > 0 ? "text-green-400" : r.moved < 0 ? "text-red-400" : "text-f1-muted"}`}>
              {r.moved > 0 ? `▲${r.moved}` : r.moved < 0 ? `▼${-r.moved}` : "–"}
            </span>
            <span className="w-1 h-3 rounded-sm" style={{ backgroundColor: r.color || "#555" }} />
            <span className="flex-1 font-bold truncate">{r.label}</span>
            {r.gained > 0 && <span className="text-[10px] text-green-400 tabular-nums">+{r.gained}</span>}
            <span className="w-10 text-right font-bold tabular-nums">{r.total}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------

function TyreModelView({ model, drivers, currentLap }: { model: TyreModel; drivers: ReplayDriver[]; currentLap: number }) {
  const abrasion = model.track_abrasion;
  const surface = abrasion > 1.05 ? "abrasive" : abrasion < 0.95 ? "smooth" : "neutral";
  return (
    <div className="flex flex-col gap-3">
      <div>
        <div className="text-[10px] font-bold text-f1-muted uppercase mb-1">Desgaste (ajustado a esta sessão)</div>
        {Object.entries(model.compounds).map(([name, c]) => (
          <div key={name} className="flex items-center gap-2 text-[11px] py-0.5">
            <span className="w-4 h-4 rounded-full border-2 flex items-center justify-center text-[8px] font-extrabold" style={{ borderColor: TYRE_COLORS[name], color: TYRE_COLORS[name] }}>
              {TYRE_SHORT[name]}
            </span>
            <span className="flex-1">{name.charAt(0) + name.slice(1).toLowerCase()}</span>
            <span className="tabular-nums font-bold">{c.degradation_rate.toFixed(3)} s/volta</span>
            <span className="w-16 text-right text-[9px] text-f1-muted">{c.stints_used ? `${c.stints_used} passagens` : "padrão"}</span>
          </div>
        ))}
        <p className="text-[10px] text-f1-muted mt-1">Superfície da pista: {surface} (abrasão ×{abrasion.toFixed(2)})</p>
      </div>
      <div>
        <div className="text-[10px] font-bold text-f1-muted uppercase mb-1">Saúde dos pneus agora</div>
        {byPosition(drivers).filter((d) => !d.retired).map((d) => {
          const th = tyreHealth(model, d.compound, d.tyre_life, currentLap);
          return (
            <div key={d.abbr} className="flex items-center gap-2 text-[11px] py-0.5">
              <span className="w-8 font-bold" style={{ color: d.color }}>{d.abbr}</span>
              <span className="w-4 text-[9px] font-extrabold" style={{ color: d.compound ? TYRE_COLORS[d.compound] : undefined }}>{d.compound ? TYRE_SHORT[d.compound] : "-"}</span>
              <div className="flex-1 h-2 bg-white/10 rounded-full overflow-hidden">
                {th && <div className="h-full rounded-full" style={{ width: `${th.health}%`, backgroundColor: healthColor(th.health) }} />}
              </div>
              <span className="w-9 text-right tabular-nums">{th ? `${th.health}%` : ""}</span>
              <span className="w-12 text-right text-[10px] text-f1-muted tabular-nums">{th ? `+${th.expectedDelta.toFixed(2)}s` : ""}</span>
            </div>
          );
        })}
        <p className="text-[9px] text-f1-muted mt-2">
          Um modelo bayesiano de espaço de estados: a taxa de desgaste de cada composto parte de um valor padrão e é atualizada com as passagens desta sessão, corrigida pelo combustível e pela abrasão da pista. São estimativas, não dados da F1.
        </p>
      </div>
    </div>
  );
}
