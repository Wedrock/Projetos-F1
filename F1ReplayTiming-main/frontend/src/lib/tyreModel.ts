"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "./api";

/** The Bayesian tyre degradation model, fitted per session by the backend
 *  (backend/services/tyre_model.py, ported from f1-race-replay). */
export interface TyreModel {
  track_abrasion: number;
  compounds: Record<string, { category: string; degradation_rate: number; max_degradation: number; stints_used?: number }>;
  mismatch_penalties: { category: string; condition: string; penalty: number }[];
  /** Track condition per lap number: DRY, DAMP or WET */
  conditions: Record<string, string>;
  drivers?: Record<string, { lap: number; compound: string; stint: number; laps_on_tyre: number; health: number; expected_delta: number; uncertainty?: number }[]>;
}

/** The model's priors, used before a session's fit is loaded and in live timing. */
export const DEFAULT_TYRE_MODEL: TyreModel = {
  track_abrasion: 1,
  compounds: {
    HARD: { category: "SLICK", degradation_rate: 0.01, max_degradation: 2.0 },
    MEDIUM: { category: "SLICK", degradation_rate: 0.03, max_degradation: 2.0 },
    SOFT: { category: "SLICK", degradation_rate: 0.05, max_degradation: 2.0 },
    INTERMEDIATE: { category: "INTER", degradation_rate: 0.04, max_degradation: 3.0 },
    WET: { category: "WET", degradation_rate: 0.02, max_degradation: 2.5 },
  },
  mismatch_penalties: [
    { category: "SLICK", condition: "DAMP", penalty: 2.0 },
    { category: "SLICK", condition: "WET", penalty: 8.0 },
    { category: "INTER", condition: "DRY", penalty: 1.5 },
    { category: "INTER", condition: "WET", penalty: 0.5 },
    { category: "WET", condition: "DRY", penalty: 4.0 },
    { category: "WET", condition: "DAMP", penalty: 1.0 },
  ],
  conditions: {},
};

export interface TyreHealth {
  health: number;
  /** Seconds a lap the tyre has lost to wear */
  expectedDelta: number;
}

/** A tyre's health (0–100) after `laps` laps, as the model's get_health. */
export function tyreHealth(model: TyreModel, compound: string | null, laps: number | null, lap?: number, rainfall?: boolean): TyreHealth | null {
  if (!compound || laps == null) return null;
  const tyre = model.compounds[compound.toUpperCase()];
  if (!tyre) return null;
  const condition = (lap != null && model.conditions[String(lap)]) || (rainfall ? "DAMP" : "DRY");
  const abrasion = tyre.category === "WET" ? 1 + 0.3 * (model.track_abrasion - 1) : model.track_abrasion;
  const eff = tyre.degradation_rate * abrasion;
  const maxLaps = tyre.max_degradation / Math.max(eff, 0.001);
  const penalty = model.mismatch_penalties.find((m) => m.category === tyre.category && m.condition === condition)?.penalty ?? 0;
  const effLaps = penalty > 0.5 ? laps * (1 + penalty / 5) : laps;
  const health = Math.max(0, Math.min(100, Math.floor(100 * (1 - effLaps / maxLaps))));
  return { health, expectedDelta: eff * laps };
}

/** Green at full health, through yellow, to red when worn (as the original's bar). */
export function healthColor(health: number): string {
  const h = Math.max(0, Math.min(100, health));
  let r: number, g: number;
  if (h >= 75) { r = 0; g = 220; }
  else if (h >= 50) { r = Math.round(220 * (1 - (h - 50) / 25)); g = 220; }
  else if (h >= 25) { r = 220; g = Math.round(220 * ((h - 25) / 25)); }
  else { r = 220; g = Math.round(110 * (h / 25)); }
  return `rgb(${r}, ${g}, 0)`;
}

/** The session's fitted model, or the priors until (or unless) it loads. */
export function useTyreModel(year: number | null, round: number | null, sessionType: string | null): TyreModel {
  const [model, setModel] = useState<TyreModel>(DEFAULT_TYRE_MODEL);
  useEffect(() => {
    setModel(DEFAULT_TYRE_MODEL);
    if (!year || !round || !sessionType) return;
    let cancelled = false;
    apiFetch<TyreModel>(`/api/sessions/${year}/${round}/tyre-model?type=${sessionType}`)
      .then((m) => { if (!cancelled && m?.compounds) setModel(m); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [year, round, sessionType]);
  return model;
}
