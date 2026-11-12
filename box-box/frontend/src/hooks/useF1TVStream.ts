"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type shakaNs from "shaka-player/dist/shaka-player.compiled.js";
import { authHeaders, f1tv, F1TVRequestError, type F1TVPlayback } from "@/lib/f1tv";

type Shaka = typeof shakaNs;
type ShakaPlayer = InstanceType<Shaka["Player"]>;

/** A plain message for a video player (Shaka) error, with its number for
 *  troubleshooting. Request errors carry the HTTP status in data[1]. */
function playerErrorMessage(code: number | undefined, data: unknown): string {
  const status = Array.isArray(data) && typeof data[1] === "number" ? (data[1] as number) : null;
  const licenceStatus = Array.isArray(data)
    ? ((data[0] as { data?: unknown[] } | undefined)?.data?.[1] as number | undefined)
    : undefined;
  const ref = ` (player error ${code ?? "unknown"}${status ? `, HTTP ${status}` : ""})`;
  switch (code) {
    case 1001: // bad HTTP status
      if (status === 403)
        return "O servidor de vídeo do F1 TV recusou este vídeo. Isso costuma significar que o F1 TV não o transmite no lugar onde a sua conexão parece estar, por exemplo por uma VPN em outro país." + ref;
      if (status === 404) return "O F1 TV não tem mais este vídeo." + ref;
      return `O servidor de vídeo do F1 TV devolveu um erro.` + ref;
    case 1002: // no response the browser can read: unreachable, or refused without CORS headers
      return "O servidor de vídeo do F1 TV não respondeu, ou recusou o vídeo sem dizer o motivo (o navegador esconde o motivo). Isso costuma acontecer quando o seu endereço de internet mudou depois de o vídeo começar, por exemplo ao ligar ou desligar uma VPN. Tente de novo ou recarregue a página." + ref;
    case 1003:
      return "O servidor de vídeo do F1 TV demorou demais para responder." + ref;
    case 6007: // licence request failed
      return (
        "O F1 TV se recusou a liberar este vídeo" +
        (licenceStatus ? ` (HTTP ${licenceStatus})` : "") +
        ". O F1 TV limita quantos vídeos uma conta toca ao mesmo tempo: feche o F1 TV em outros aparelhos ou mostre menos onboards e tente de novo." +
        ref
      );
    case 6000:
    case 6001:
    case 6002:
    case 6012:
      return "Este navegador não consegue tocar o vídeo protegido do F1 TV. Use uma versão atual do Chrome, Edge, Firefox ou Safari e confira se o conteúdo protegido está permitido nas configurações." + ref;
    default:
      if (code && code >= 4000 && code < 5000) return "Não foi possível ler a descrição deste vídeo no F1 TV." + ref;
      if (code && code >= 3000 && code < 4000) return "O navegador não conseguiu tocar este vídeo." + ref;
      return "O vídeo não pôde ser tocado." + ref;
  }
}

export interface StreamOptions {
  /** Send the licence request through our backend (adds the user's token) instead of straight to F1. */
  licenceViaServer: boolean;
  /** Fetch the manifest and segments through our backend, for when the CDN refuses this page. */
  relay: boolean;
}

export interface StreamDebug {
  playback: Omit<F1TVPlayback, "raw"> | null;
  playbackRaw: unknown;
  licence: { attempts: number; ok: number; lastStatus: number | null; via: "server" | "direct" | null };
  keySystem: string | null;
  videoRobustness: string | null;
  active: { width: number; height: number; frameRate: number | null; bandwidth: number } | null;
  availableHeights: number[];
  droppedFrames: number;
  decodedFrames: number;
  estimatedBandwidth: number;
  error: { message: string; code?: number; data?: unknown } | null;
}

const EMPTY_DEBUG: StreamDebug = {
  playback: null,
  playbackRaw: null,
  licence: { attempts: 0, ok: 0, lastStatus: null, via: null },
  keySystem: null,
  videoRobustness: null,
  active: null,
  availableHeights: [],
  droppedFrames: 0,
  decodedFrames: 0,
  estimatedBandwidth: 0,
  error: null,
};

let shakaPromise: Promise<Shaka> | null = null;
function loadShaka(): Promise<Shaka> {
  if (!shakaPromise) {
    shakaPromise = import("shaka-player/dist/shaka-player.compiled.js").then((m) => {
      const shaka = (m.default ?? m) as Shaka;
      shaka.polyfill.installAll();
      return shaka;
    });
  }
  return shakaPromise;
}

function relayUrl(pid: string, uri: string): string {
  if (uri.includes("/api/f1tv/relay/")) return uri;
  const u = new URL(uri);
  return `${window.location.origin}/api/f1tv/relay/${pid}/${u.host}${u.pathname}${u.search}`;
}

/** Plays one F1 TV feed (main broadcast or an onboard) into a <video>. */
export function useF1TVStream(videoRef: React.RefObject<HTMLVideoElement | null>) {
  const playerRef = useRef<ShakaPlayer | null>(null);
  const [state, setState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [debug, setDebug] = useState<StreamDebug>(EMPTY_DEBUG);
  const loadIdRef = useRef(0);

  const unload = useCallback(async () => {
    loadIdRef.current++;
    const player = playerRef.current;
    playerRef.current = null;
    if (player) await player.destroy().catch(() => {});
    setState("idle");
  }, []);

  useEffect(() => () => { void unload(); }, [unload]);

  const load = useCallback(
    async (content: string, channelId: string | null, opts: StreamOptions, live = false) => {
      const video = videoRef.current;
      if (!video) return;
      await unload();
      const loadId = ++loadIdRef.current;
      setState("loading");
      setDebug({ ...EMPTY_DEBUG, licence: { ...EMPTY_DEBUG.licence, via: opts.licenceViaServer ? "server" : "direct" } });

      const fail = (message: string, code?: number, data?: unknown) => {
        if (loadId !== loadIdRef.current) return;
        setState("error");
        setDebug((d) => ({ ...d, error: { message, code, data } }));
      };

      let pb: F1TVPlayback;
      try {
        pb = await f1tv.play(content, channelId, live);
      } catch (e) {
        const err = e as F1TVRequestError;
        return fail(err.message, err.status, err.body);
      }
      if (loadId !== loadIdRef.current) return;
      const { raw, ...playback } = pb;
      setDebug((d) => ({ ...d, playback, playbackRaw: raw }));

      const shaka = await loadShaka();
      if (!shaka.Player.isBrowserSupported()) return fail("Este navegador não consegue tocar vídeo protegido");

      const player = new shaka.Player();
      playerRef.current = player;
      await player.attach(video);

      const licenceUrl = opts.licenceViaServer
        ? `${window.location.origin}/api/f1tv/license/${pb.playback_id}`
        : pb.license_url;
      if (licenceUrl) {
        player.configure({ drm: { servers: { "com.widevine.alpha": licenceUrl } } });
      }

      const RT = shaka.net.NetworkingEngine.RequestType;
      const net = player.getNetworkingEngine()!;
      net.registerRequestFilter((type, request) => {
        if (type === RT.LICENSE) {
          if (opts.licenceViaServer) Object.assign(request.headers, authHeaders());
          setDebug((d) => ({ ...d, licence: { ...d.licence, attempts: d.licence.attempts + 1 } }));
        }
        if (opts.relay && (type === RT.MANIFEST || type === RT.SEGMENT)) {
          request.uris = request.uris.map((u) => relayUrl(pb.playback_id, u));
          Object.assign(request.headers, authHeaders());
        }
      });
      net.registerResponseFilter((type, response) => {
        if (type === RT.LICENSE) {
          setDebug((d) => ({ ...d, licence: { ...d.licence, ok: d.licence.ok + 1, lastStatus: response.status ?? 200 } }));
        }
      });

      player.addEventListener("error", (event) => {
        const detail = (event as unknown as { detail: shakaNs.util.Error }).detail;
        if (detail?.code === shaka.util.Error.Code.LICENSE_REQUEST_FAILED) {
          const status = (detail.data?.[0] as { data?: unknown[] } | undefined)?.data?.[1];
          setDebug((d) => ({ ...d, licence: { ...d.licence, lastStatus: typeof status === "number" ? status : null } }));
        }
        fail(playerErrorMessage(detail?.code, detail?.data), detail?.code, detail?.data);
      });

      try {
        await player.load(opts.relay ? relayUrl(pb.playback_id, pb.manifest_url) : pb.manifest_url);
      } catch (e) {
        const err = e as shakaNs.util.Error;
        return fail(playerErrorMessage(err.code, err.data), err.code, err.data);
      }
      if (loadId !== loadIdRef.current) return;
      const drm = player.drmInfo();
      setDebug((d) => ({ ...d, keySystem: drm?.keySystem ?? null, videoRobustness: drm?.videoRobustness || null }));
      setState("ready");
    },
    [videoRef, unload],
  );

  // Poll quality stats for the debug panel.
  useEffect(() => {
    if (state !== "ready") return;
    const id = setInterval(() => {
      const player = playerRef.current;
      if (!player) return;
      const stats = player.getStats();
      const tracks = player.getVideoTracks();
      const active = tracks.find((t) => t.active);
      setDebug((d) => ({
        ...d,
        active: active
          ? { width: active.width ?? stats.width, height: active.height ?? stats.height, frameRate: active.frameRate, bandwidth: active.bandwidth }
          : null,
        availableHeights: Array.from(new Set(tracks.map((t) => t.height ?? 0).filter(Boolean))).sort((a, b) => b - a),
        droppedFrames: stats.droppedFrames,
        decodedFrames: stats.decodedFrames,
        estimatedBandwidth: stats.estimatedBandwidth,
      }));
    }, 2000);
    return () => clearInterval(id);
  }, [state]);

  /** The real time (epoch seconds) of the moment showing, for a live stream:
   *  F1 TV's live video carries the time it was sent out. Null otherwise. */
  const playheadUtc = useCallback((): number | null => {
    const player = playerRef.current;
    if (!player || !player.isLive()) return null;
    const date = player.getPlayheadTimeAsDate();
    return date ? date.getTime() / 1000 : null;
  }, []);

  return { state, debug, load, unload, playheadUtc };
}
