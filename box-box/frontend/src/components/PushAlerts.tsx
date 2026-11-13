"use client";

import { useCallback, useEffect, useState } from "react";
import { Bell, BellOff, Share, X } from "lucide-react";
import { apiUrl } from "@/lib/api";
import { authHeaders } from "@/lib/f1tv";

// Race alerts: push notifications on the lock screen for the start, Safety
// Car, flags, a new leader and the result. The server watches the live
// timing and sends them; this turns them on for this device.

type State =
  | "loading"
  | "insecure" // service workers need HTTPS (or localhost)
  | "ios-install" // iPhone: only apps added to the Home Screen get pushes
  | "unsupported"
  | "denied"
  | "off"
  | "on";

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(apiUrl(`/api/push${path}`), {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(data?.detail || `Falha na requisição (${res.status})`);
  return data as T;
}

function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padded = (base64 + "=".repeat((4 - (base64.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(padded);
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

function isIOS(): boolean {
  return /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

function isStandalone(): boolean {
  return window.matchMedia("(display-mode: standalone)").matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true;
}

async function registration(): Promise<ServiceWorkerRegistration> {
  await navigator.serviceWorker.register("/sw.js");
  return navigator.serviceWorker.ready;
}

export function usePushAlerts() {
  const [state, setState] = useState<State>("loading");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!window.isSecureContext) return setState("insecure");
    const supported = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
    if (!supported) return setState(isIOS() && !isStandalone() ? "ios-install" : "unsupported");
    if (Notification.permission === "denied") return setState("denied");
    try {
      const reg = await registration();
      const sub = await reg.pushManager.getSubscription();
      if (!sub) return setState("off");
      // The server may have dropped it (a new data volume, say)
      const { subscribed } = await post<{ subscribed: boolean }>("/status", { endpoint: sub.endpoint });
      if (!subscribed) await post("/subscribe", sub.toJSON());
      setState("on");
    } catch {
      setState("off");
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const enable = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      // Must be asked straight from the tap, or iOS refuses
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        setState(permission === "denied" ? "denied" : "off");
        return;
      }
      const reg = await registration();
      const res = await fetch(apiUrl("/api/push/key"), { headers: authHeaders() });
      if (!res.ok) throw new Error("O servidor não está com os alertas ligados");
      const { public_key } = await res.json();
      let sub = await reg.pushManager.getSubscription();
      if (!sub) {
        sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(public_key),
        });
      }
      await post("/subscribe", sub.toJSON());
      setState("on");
      await post("/test", { endpoint: sub.endpoint }).catch(() => undefined);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não deu para ligar os alertas");
    } finally {
      setBusy(false);
    }
  }, []);

  const disable = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const reg = await registration();
      const sub = await reg.pushManager.getSubscription();
      if (sub) {
        await post("/unsubscribe", { endpoint: sub.endpoint }).catch(() => undefined);
        await sub.unsubscribe();
      }
      setState("off");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não deu para desligar os alertas");
    } finally {
      setBusy(false);
    }
  }, []);

  const test = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const reg = await registration();
      const sub = await reg.pushManager.getSubscription();
      if (!sub) throw new Error("Os alertas não estão ligados neste aparelho");
      await post("/test", { endpoint: sub.endpoint });
    } catch (e) {
      setError(e instanceof Error ? e.message : "O teste falhou");
    } finally {
      setBusy(false);
    }
  }, []);

  return { state, busy, error, enable, disable, test };
}

const EVENTS = [
  "Aviso 15 minutos antes",
  "Largada e início da classificação",
  "Safety Car, VSC e bandeira vermelha",
  "Relargada e troca de líder",
  "Última volta",
  "Pódio e pole position",
];

export default function PushAlertsDialog({ onClose }: { onClose: () => void }) {
  const { state, busy, error, enable, disable, test } = usePushAlerts();

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-f1-card border border-f1-border rounded-xl shadow-xl w-full max-w-md max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}>
        <div className="px-6 pt-5 pb-2 flex items-center justify-between">
          <h3 className="text-white font-bold text-lg flex items-center gap-2">
            <Bell className="w-5 h-5 text-f1-red" /> Alertas de corrida
          </h3>
          <button onClick={onClose} aria-label="Fechar" title="Fechar"
            className="w-7 h-7 flex items-center justify-center rounded text-f1-muted hover:text-white hover:bg-white/10 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="px-6 pb-6 space-y-4 text-sm text-f1-muted leading-relaxed">
          <p>Receba na tela de bloqueio os momentos importantes das corridas, sprints e classificações:</p>
          <ul className="space-y-1">
            {EVENTS.map((e) => (
              <li key={e} className="flex gap-2"><span className="text-f1-red">•</span>{e}</li>
            ))}
          </ul>
          <p className="text-xs">
            Quem manda os alertas é o servidor do Box Box, então ele precisa estar ligado durante a sessão.
          </p>

          {state === "loading" && <p className="text-white">Verificando…</p>}

          {state === "ios-install" && (
            <div className="bg-white/[0.04] border border-white/10 rounded-lg p-4 text-white space-y-2">
              <p className="font-bold">No iPhone, primeiro instale o app:</p>
              <ol className="list-decimal list-inside space-y-1 text-f1-muted">
                <li>No Safari, toque em <Share className="inline w-4 h-4 -mt-1" /> <b className="text-white">Compartilhar</b></li>
                <li>Escolha <b className="text-white">Adicionar à Tela de Início</b></li>
                <li>Abra o Box Box pelo ícone e volte aqui</li>
              </ol>
              <p className="text-xs text-f1-muted">Precisa do iOS 16.4 ou mais novo.</p>
            </div>
          )}

          {state === "insecure" && (
            <p className="text-amber-300">
              Os alertas só funcionam com HTTPS. Abra o Box Box pelo endereço https:// (veja &quot;Usar no iPhone&quot; no README).
            </p>
          )}

          {state === "unsupported" && (
            <p className="text-amber-300">Este navegador não aceita notificações. No iPhone, use o Safari.</p>
          )}

          {state === "denied" && (
            <p className="text-amber-300">
              As notificações estão bloqueadas. No iPhone: Ajustes → Notificações → Box Box → Permitir Notificações.
            </p>
          )}

          {state === "off" && (
            <button onClick={enable} disabled={busy}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-f1-red text-white font-bold rounded-lg hover:bg-red-700 disabled:opacity-60 transition-colors">
              <Bell className="w-4 h-4" /> {busy ? "Ligando…" : "Ligar alertas neste aparelho"}
            </button>
          )}

          {state === "on" && (
            <div className="space-y-3">
              <p className="flex items-center gap-2 text-green-400 font-bold">
                <span className="w-2 h-2 rounded-full bg-green-400 shadow-[0_0_8px_rgba(74,222,128,0.8)]" />
                Alertas ligados neste aparelho
              </p>
              <div className="flex gap-2">
                <button onClick={test} disabled={busy}
                  className="flex-1 px-4 py-2 bg-f1-border text-white font-bold rounded-lg hover:bg-white/20 disabled:opacity-60 transition-colors">
                  Enviar teste
                </button>
                <button onClick={disable} disabled={busy}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2 border border-white/10 text-f1-muted font-bold rounded-lg hover:text-white hover:border-white/30 disabled:opacity-60 transition-colors">
                  <BellOff className="w-4 h-4" /> Desligar
                </button>
              </div>
            </div>
          )}

          {error && <p className="text-red-400">{error}</p>}
        </div>
      </div>
    </div>
  );
}
