"use client";

import { useSyncExternalStore } from "react";

// Team radio sound: while a clip talks, the broadcast is turned down
// ("ducking") so the radio is heard over it, and a radio squelch plays as the
// channel opens and closes, with a faint hiss underneath. The sounds are
// synthesised here with the Web Audio API (no audio files).

// --- Ducking -------------------------------------------------------------

/** How loud the broadcast stays while a radio clip talks (share of its volume). */
export const DUCK_LEVEL = 0.2;

let talking = false;
const listeners = new Set<() => void>();

/** TeamRadio calls this as a clip's audio starts and stops. */
export function setRadioTalking(on: boolean): void {
  if (talking === on) return;
  talking = on;
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Whether a radio clip is talking right now (videos turn themselves down). */
export function useRadioTalking(): boolean {
  return useSyncExternalStore(subscribe, () => talking, () => false);
}

const ramps = new WeakMap<HTMLMediaElement, number>();

/** Move a video's volume to target smoothly (no jump when ducking). */
export function rampVolume(el: HTMLMediaElement, target: number, ms = 350): void {
  const to = Math.max(0, Math.min(1, target));
  const prev = ramps.get(el);
  if (prev) cancelAnimationFrame(prev);
  const from = el.volume;
  if (Math.abs(from - to) < 0.01) {
    el.volume = to;
    return;
  }
  const start = performance.now();
  const step = (now: number) => {
    // rAF's timestamp can be a little before `start`: keep k in [0, 1]
    const k = Math.max(0, Math.min(1, (now - start) / ms));
    el.volume = Math.max(0, Math.min(1, from + (to - from) * k));
    if (k < 1) ramps.set(el, requestAnimationFrame(step));
    else ramps.delete(el);
  };
  ramps.set(el, requestAnimationFrame(step));
}

// --- Radio squelch -------------------------------------------------------

let ctx: AudioContext | null = null;
let hiss: { source: AudioBufferSourceNode; gain: GainNode } | null = null;

function audio(): AudioContext | null {
  if (typeof window === "undefined") return null;
  try {
    if (!ctx) {
      const AC = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      ctx = new AC();
    }
    if (ctx.state === "suspended") void ctx.resume();
    return ctx;
  } catch {
    return null;
  }
}

function noiseBuffer(ac: AudioContext, seconds: number): AudioBuffer {
  const buf = ac.createBuffer(1, Math.ceil(ac.sampleRate * seconds), ac.sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
  return buf;
}

/** Noise through a radio-like band (telephone band, a little resonant). */
function bandNoise(ac: AudioContext, seconds: number, loop = false) {
  const source = ac.createBufferSource();
  source.buffer = noiseBuffer(ac, seconds);
  source.loop = loop;
  const band = ac.createBiquadFilter();
  band.type = "bandpass";
  band.frequency.value = 1800;
  band.Q.value = 0.9;
  const gain = ac.createGain();
  source.connect(band).connect(gain).connect(ac.destination);
  return { source, gain };
}

function beep(ac: AudioContext, at: number, freq: number, length: number, level: number) {
  const osc = ac.createOscillator();
  osc.type = "square";
  osc.frequency.value = freq;
  const gain = ac.createGain();
  gain.gain.setValueAtTime(0, at);
  gain.gain.linearRampToValueAtTime(level, at + 0.005);
  gain.gain.setValueAtTime(level, at + length - 0.01);
  gain.gain.linearRampToValueAtTime(0, at + length);
  const tone = ac.createBiquadFilter();
  tone.type = "lowpass";
  tone.frequency.value = 3000;
  osc.connect(tone).connect(gain).connect(ac.destination);
  osc.start(at);
  osc.stop(at + length + 0.02);
}

/** The channel opening (start of a clip) or closing (end of it). */
export function playSquelch(kind: "open" | "close", volume = 1): void {
  const ac = audio();
  if (!ac) return;
  const t = ac.currentTime + 0.01;
  const level = 0.18 * volume;
  const burst = bandNoise(ac, 0.25);
  burst.gain.gain.setValueAtTime(0, t);
  burst.gain.gain.linearRampToValueAtTime(level, t + 0.01);
  burst.gain.gain.exponentialRampToValueAtTime(0.001, t + (kind === "open" ? 0.16 : 0.22));
  burst.source.start(t);
  burst.source.stop(t + 0.3);
  if (kind === "open") {
    beep(ac, t + 0.02, 1250, 0.07, 0.05 * volume);
  } else {
    beep(ac, t + 0.03, 900, 0.05, 0.04 * volume);
    beep(ac, t + 0.1, 700, 0.06, 0.035 * volume);
  }
}

/** A faint hiss under the voice while the channel is open. */
export function startHiss(volume = 1): void {
  const ac = audio();
  if (!ac || hiss) return;
  const h = bandNoise(ac, 2, true);
  h.gain.gain.setValueAtTime(0, ac.currentTime);
  h.gain.gain.linearRampToValueAtTime(0.012 * volume, ac.currentTime + 0.15);
  h.source.start();
  hiss = h;
}

export function stopHiss(): void {
  const ac = ctx;
  const h = hiss;
  hiss = null;
  if (!ac || !h) return;
  const t = ac.currentTime;
  h.gain.gain.cancelScheduledValues(t);
  h.gain.gain.setValueAtTime(h.gain.gain.value, t);
  h.gain.gain.linearRampToValueAtTime(0, t + 0.12);
  h.source.stop(t + 0.15);
}
