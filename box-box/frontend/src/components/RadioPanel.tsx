"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Pause, Play, Radio, RotateCcw, X } from "lucide-react";
import type { ReplayDriver } from "@/hooks/useReplaySocket";
import { apiUrl } from "@/lib/api";
import { authHeaders } from "@/lib/f1tv";
import { useAppConfig } from "@/lib/config";
import { type RadioClip, RadioCaption, audioSource, releaseSource } from "./TeamRadio";

// Every team radio message of the session so far: filter by driver, play
// any of them and, in replays, jump to the moment it was said. Replays only
// list what has already happened, so nothing is spoiled.

interface RefreshStatus {
  running: boolean;
  done?: number;
  total?: number;
  step?: string;
  error?: string;
  missing?: number;
  clips?: number;
}

interface Props {
  clips: RadioClip[] | undefined;
  drivers: ReplayDriver[];
  mode: "replay" | "live";
  /** Replay seconds now: later clips stay hidden */
  currentTime?: number;
  /** Replays: jump the playback to a moment */
  onSeek?: (t: number) => void;
  showEnglish: boolean;
  /** Replays: the session, to fetch missing radio and captions */
  session?: { year: number; round: number; type: string };
  /** Called when the server has new clips or captions for this session */
  onUpdated?: () => void;
  onClose?: () => void;
  className?: string;
}

const clipKey = (c: RadioClip) => c.id ?? `${c.t}_${c.racing_number}`;

function clock(t: number): string {
  const sign = t < 0 ? "-" : "";
  const s = Math.abs(Math.round(t));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = String(s % 60).padStart(2, "0");
  return h ? `${sign}${h}:${String(m).padStart(2, "0")}:${sec}` : `${sign}${m}:${sec}`;
}

function localTime(utc: string | null): string {
  if (!utc) return "";
  const d = new Date(utc);
  return isNaN(d.getTime()) ? "" : d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

export default function RadioPanel({
  clips, drivers, mode, currentTime = 0, onSeek, showEnglish, session, onUpdated, onClose, className = "",
}: Props) {
  const appConfig = useAppConfig();
  const [filter, setFilter] = useState<string | null>(null);
  const [playingKey, setPlayingKey] = useState<string | null>(null);
  const [loadingKey, setLoadingKey] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [refresh, setRefresh] = useState<RefreshStatus | null>(null);
  const pollRef = useRef<(() => void) | null>(null);
  const canRefresh = mode === "replay" && !!session && !!appConfig && !appConfig.public_mode;

  const visible = useMemo(() => {
    const list = (clips ?? []).filter((c) => mode === "live" || (c.t !== undefined && c.t <= currentTime));
    return list.slice().reverse();
  }, [clips, mode, currentTime]);

  const speakers = useMemo(() => {
    const seen = new Set<string>();
    for (const c of visible) if (c.driver) seen.add(c.driver);
    return drivers.filter((d) => seen.has(d.abbr)).map((d) => d.abbr);
  }, [visible, drivers]);

  const shown = filter ? visible.filter((c) => c.driver === filter) : visible;

  const stop = () => {
    const el = audioRef.current;
    if (el) { el.pause(); releaseSource(el.src); }
    audioRef.current = null;
    setPlayingKey(null);
    setLoadingKey(null);
  };

  useEffect(() => () => stop(), []); // eslint-disable-line react-hooks/exhaustive-deps

  const play = async (clip: RadioClip) => {
    const key = clipKey(clip);
    if (playingKey === key || loadingKey === key) { stop(); return; }
    stop();
    if (!clip.url) return;
    const el = new Audio();
    audioRef.current = el;
    setLoadingKey(key);
    const src = await audioSource(clip.url);
    if (audioRef.current !== el) { releaseSource(src); return; }
    setLoadingKey(null);
    if (!src) return;
    el.src = src;
    el.onended = () => { releaseSource(el.src); if (audioRef.current === el) { audioRef.current = null; setPlayingKey(null); } };
    el.play().then(() => setPlayingKey(key)).catch(() => stop());
  };

  // Replays: how many clips the server could still fill in, and progress
  const sessionPath = session ? `/api/sessions/${session.year}/${session.round}/team-radio/refresh?type=${session.type}` : null;
  useEffect(() => {
    if (!canRefresh || !sessionPath) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let lastDone = -1;
    const poll = async () => {
      try {
        const res = await fetch(apiUrl(sessionPath), { headers: authHeaders() });
        if (!res.ok) return;
        const data: RefreshStatus = await res.json();
        if (cancelled) return;
        setRefresh(data);
        if (data.running) {
          if ((data.done ?? 0) !== lastDone) { lastDone = data.done ?? 0; onUpdated?.(); }
          timer = setTimeout(poll, 3000);
        } else if (lastDone >= 0) {
          lastDone = -1;
          onUpdated?.();
        }
      } catch { /* try again on the next start */ }
    };
    poll();
    pollRef.current = poll;
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, [canRefresh, sessionPath]); // eslint-disable-line react-hooks/exhaustive-deps

  const startRefresh = async () => {
    if (!sessionPath) return;
    try {
      const res = await fetch(apiUrl(sessionPath), { method: "POST", headers: authHeaders() });
      const data: RefreshStatus = await res.json();
      setRefresh((r) => ({ ...r, ...data }));
      pollRef.current?.();
    } catch {
      setRefresh((r) => ({ ...(r ?? { running: false }), error: "Não deu para falar com o servidor." }));
    }
  };

  const noClips = (clips?.length ?? 0) === 0;
  const missing = refresh?.missing ?? 0;
  const minutes = Math.max(1, Math.ceil((missing * 5) / 60));

  return (
    <div className={`flex flex-col min-h-0 bg-f1-card ${className}`}>
      <div className="flex items-center gap-2 px-3 py-2 border-b border-f1-border">
        <Radio className="w-4 h-4 text-f1-red" />
        <span className="text-[11px] font-bold text-f1-muted uppercase tracking-wider">Rádios das equipes</span>
        <span className="text-[11px] text-f1-muted">{visible.length > 0 ? `· ${visible.length}` : ""}</span>
        {onClose && (
          <button onClick={onClose} aria-label="Fechar" title="Fechar"
            className="ml-auto w-6 h-6 flex items-center justify-center rounded text-f1-muted hover:text-white hover:bg-white/10">
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {canRefresh && refresh && (refresh.running || refresh.error || noClips || missing > 0) && (
        <div className="px-3 py-2 border-b border-f1-border text-xs text-f1-muted space-y-1.5">
          {refresh.running ? (
            <p className="flex items-center gap-2 text-white">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              {refresh.total ? `Legendando os rádios (${refresh.done ?? 0}/${refresh.total})...` : refresh.step || "Buscando os rádios..."}
            </p>
          ) : (
            <>
              {refresh.error && <p className="text-amber-300">{refresh.error}</p>}
              {noClips && !refresh.error && <p>Esta sessão ainda não tem rádios. Dá para buscar no OpenF1.</p>}
              {!noClips && missing > 0 && (
                <p>{missing} {missing === 1 ? "rádio está" : "rádios estão"} sem legenda{appConfig?.radio_pt ? " em português com as falas do piloto e da equipe separadas" : ""}.</p>
              )}
              <button onClick={startRefresh}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-f1-border text-white font-bold hover:bg-f1-red transition-colors">
                <RotateCcw className="w-3.5 h-3.5" />
                {noClips ? "Buscar rádios" : `Legendar agora (uns ${minutes} min)`}
              </button>
            </>
          )}
        </div>
      )}

      {speakers.length > 1 && (
        <div className="flex gap-1 px-3 py-2 overflow-x-auto border-b border-f1-border scrollbar-none">
          <button onClick={() => setFilter(null)}
            className={`px-2 py-0.5 rounded text-[11px] font-bold flex-shrink-0 ${filter === null ? "bg-f1-red text-white" : "bg-white/5 text-f1-muted hover:text-white"}`}>
            Todos
          </button>
          {speakers.map((abbr) => {
            const color = drivers.find((d) => d.abbr === abbr)?.color || "#fff";
            return (
              <button key={abbr} onClick={() => setFilter(filter === abbr ? null : abbr)}
                className={`flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold flex-shrink-0 ${filter === abbr ? "bg-white/15 text-white" : "bg-white/5 text-f1-muted hover:text-white"}`}>
                <span className="w-1 h-3 rounded-sm" style={{ backgroundColor: color }} />
                {abbr}
              </button>
            );
          })}
        </div>
      )}

      <div className="flex-1 min-h-0 overflow-y-auto">
        {shown.length === 0 ? (
          <p className="px-3 py-6 text-center text-xs text-f1-muted">
            {noClips ? "Nenhum rádio por enquanto." : mode === "replay" ? "Nenhum rádio até este momento da sessão." : "Nenhum rádio deste piloto."}
          </p>
        ) : (
          <ul className="divide-y divide-f1-border/60">
            {shown.map((clip) => {
              const key = clipKey(clip);
              const color = drivers.find((d) => d.abbr === clip.driver)?.color || "#fff";
              const hasCaption = !!(clip.transcript_pt || clip.transcript || clip.lines?.length);
              const isPlaying = playingKey === key;
              return (
                <li key={key} className="flex gap-2.5 px-3 py-2.5">
                  <span className="w-1 self-stretch rounded-sm flex-shrink-0" style={{ backgroundColor: color }} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-extrabold text-white">{clip.driver || `#${clip.racing_number}`}</span>
                      <span className="text-[10px] text-f1-muted tabular-nums">
                        {mode === "replay" && clip.t !== undefined ? clock(clip.t) : localTime(clip.utc)}
                      </span>
                      {mode === "replay" && onSeek && clip.t !== undefined && (
                        <button onClick={() => onSeek(Math.max(0, clip.t! - 3))}
                          className="text-[10px] font-bold text-f1-muted hover:text-white underline-offset-2 hover:underline">
                          ir para
                        </button>
                      )}
                    </div>
                    {hasCaption ? (
                      <RadioCaption clip={clip} showEnglish={showEnglish} color={color} size="xs" />
                    ) : (
                      <p className="text-[12px] text-f1-muted italic mt-0.5">Sem legenda</p>
                    )}
                  </div>
                  {clip.url && (
                    <button onClick={() => play(clip)} aria-label={isPlaying ? "Parar" : "Ouvir"} title={isPlaying ? "Parar" : "Ouvir"}
                      className={`w-9 h-9 flex-shrink-0 self-center flex items-center justify-center rounded-full border transition-colors ${isPlaying ? "bg-f1-red border-f1-red text-white" : "border-white/15 text-f1-muted hover:text-white hover:border-white/40"}`}>
                      {loadingKey === key ? <Loader2 className="w-4 h-4 animate-spin" /> : isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
