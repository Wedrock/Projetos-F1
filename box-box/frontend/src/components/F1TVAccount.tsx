"use client";

import { useEffect, useState } from "react";
import { CircleCheck, Info, X } from "lucide-react";
import { f1tv, type F1TVStatus } from "@/lib/f1tv";

// F1 TV sign-in, needed to download session data since 15 October 2026.
// Used in the home page's F1 TV dialog and the replay Settings tab.

function formatExpiry(exp: number | null): string | null {
  if (!exp) return null;
  const ms = exp * 1000 - Date.now();
  const when = new Date(exp * 1000).toLocaleString("pt-BR", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
  if (ms < 0) return `Expirado ${when}`;
  const days = Math.floor(ms / 86400000);
  const hours = Math.floor(ms / 3600000);
  return `Expira ${when} (${days >= 1 ? `${days} dia${days === 1 ? "" : "s"}` : `${hours} hora${hours === 1 ? "" : "s"}`})`;
}

const inputClass =
  "w-full bg-f1-dark border border-f1-border rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-f1-muted";

export default function F1TVAccount({
  onChange,
  onDone,
}: {
  onChange?: (status: F1TVStatus) => void;
  /** In the dialog: shows a Done button once signed in */
  onDone?: () => void;
}) {
  const [status, setStatus] = useState<F1TVStatus | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [pasteMode, setPasteMode] = useState(false);
  const [pasted, setPasted] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmSignOut, setConfirmSignOut] = useState(false);

  const update = (s: F1TVStatus) => {
    setStatus(s);
    onChange?.(s);
  };

  useEffect(() => {
    f1tv.status().then(update).catch((e) => setError(e.message));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function run(action: () => Promise<F1TVStatus>) {
    setBusy(true);
    setError(null);
    try {
      update(await action());
      setPassword("");
      setPasted("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!status) {
    return <div className="px-2 sm:px-6 py-4 text-sm text-f1-muted">{error || "Verificando o login…"}</div>;
  }

  if (status.signed_in) {
    const expiry = formatExpiry(status.expires_at);
    const fromEnv = status.renews === "env";
    return (
      <div className="px-2 sm:px-6 py-2 space-y-4">
        <div className="flex items-start gap-3 rounded-lg border border-green-500/30 bg-green-500/10 px-3 py-3">
          <CircleCheck className="w-5 h-5 mt-0.5 flex-shrink-0 text-green-400" />
          <div className="min-w-0 space-y-0.5">
            <p className="text-sm text-white font-bold">Conectado ao F1 TV</p>
            <p className="text-xs text-f1-muted truncate">
              {[status.product, status.email].filter(Boolean).join(" · ")}
            </p>
            <p className={`text-xs ${status.renews ? "text-green-400" : "text-orange-400"}`}>
              {fromEnv
                ? "Conectado com F1_USERNAME e F1_PASSWORD. Continua conectado."
                : status.renews === "saved"
                  ? "Continua conectado até você sair."
                  : `Não fica conectado. ${expiry ? `${expiry}. ` : ""}Para continuar conectado, saia e entre de novo com “Manter conectado” marcado.`}
            </p>
          </div>
        </div>
        {status.renews === "saved" && !status.secret_key_set && <SecretKeyNote />}
        <p className="text-xs text-f1-muted leading-relaxed">
          As novas sessões são baixadas com a sua conta F1 TV. As sessões já baixadas continuam funcionando sem ela.
        </p>

        {confirmSignOut ? (
          <div className="rounded-lg border border-f1-border bg-f1-dark px-3 py-3 space-y-3">
            <p className="text-xs text-f1-muted leading-relaxed">
              <span className="text-white font-bold">Sair do F1 TV?</span> Novas sessões não serão baixadas até você entrar de novo{status.renews === "saved" ? ", e a senha salva será apagada" : ""}.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setConfirmSignOut(false)}
                className="px-3 py-1.5 bg-f1-border text-white text-xs font-bold rounded hover:bg-white/10 transition-colors">
                Cancelar
              </button>
              <button onClick={() => { setConfirmSignOut(false); run(f1tv.signOut); }} disabled={busy}
                className="px-3 py-1.5 bg-f1-red text-white text-xs font-bold rounded hover:bg-red-700 transition-colors disabled:opacity-50">
                Sair
              </button>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-between gap-3">
            {fromEnv ? (
              <span className="text-xs text-f1-muted">Remova F1_USERNAME e F1_PASSWORD para sair.</span>
            ) : (
              <button onClick={() => setConfirmSignOut(true)} disabled={busy}
                className="text-xs text-f1-muted hover:text-white underline underline-offset-2 disabled:opacity-50">
                Sair
              </button>
            )}
            {onDone && (
              <button onClick={onDone}
                className="px-5 py-2 bg-f1-red text-white text-sm font-bold rounded hover:bg-red-700 transition-colors">
                Pronto
              </button>
            )}
          </div>
        )}
        {error && <p className="text-xs text-red-400">{error}</p>}
      </div>
    );
  }

  return (
    <div className="px-2 sm:px-6 py-2 space-y-3">
      <p className="text-sm text-f1-muted leading-relaxed">
        Desde 15 de outubro de 2026, a F1 exige uma assinatura do F1 TV (Access ou superior) para baixar os dados de cronometragem. Entre com a sua conta F1 para baixar novas sessões. As sessões já baixadas continuam funcionando.
      </p>

      {!pasteMode ? (
        <form
          className="space-y-2"
          onSubmit={(e) => {
            e.preventDefault();
            run(() => f1tv.signIn(email, password, remember));
          }}
        >
          <input type="email" autoComplete="username" placeholder="E-mail da conta F1" value={email}
            onChange={(e) => setEmail(e.target.value)} className={inputClass} />
          <input type="password" autoComplete="current-password" placeholder="Senha" value={password}
            onChange={(e) => setPassword(e.target.value)} className={inputClass} />
          <label className="flex items-start gap-2 text-xs text-f1-muted leading-relaxed cursor-pointer">
            <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="mt-0.5 accent-f1-red" />
            <span>
              <span className="text-white font-bold">Manter conectado.</span> Continua conectado até você sair. A senha fica guardada criptografada neste servidor e só é enviada para a F1. Sem isso, você vai precisar entrar de novo a cada poucos dias.
            </span>
          </label>
          {remember && !status.secret_key_set && <SecretKeyNote />}
          <button type="submit" disabled={busy || !email.trim() || !password}
            className="px-4 py-2 bg-f1-red text-white text-sm font-bold rounded hover:bg-red-700 transition-colors disabled:opacity-50">
            {busy ? "Entrando…" : "Entrar"}
          </button>
          <button type="button" onClick={() => { setPasteMode(true); setError(null); }}
            className="block text-xs text-f1-muted hover:text-white underline">
            Não consegue entrar com a senha? Cole um token
          </button>
        </form>
      ) : (
        <div className="space-y-2">
          <ol className="text-xs text-f1-muted leading-relaxed list-decimal pl-4 space-y-1">
            <li>Entre em f1tv.formula1.com em outra aba.</li>
            <li>Abra as ferramentas de desenvolvedor, vá em Aplicativo (Armazenamento no Firefox), depois Cookies, depois formula1.com.</li>
            <li>Copie o valor do cookie <span className="text-white font-mono">loginSession</span> e cole abaixo.</li>
          </ol>
          <p className="text-xs text-orange-400">Um token colado não se renova. Você vai precisar colar um novo em cerca de 4 dias.</p>
          <textarea value={pasted} onChange={(e) => setPasted(e.target.value)} rows={3} placeholder="Valor do cookie loginSession"
            className={`${inputClass} text-xs font-mono resize-none`} />
          <div className="flex items-center gap-3">
            <button onClick={() => run(() => f1tv.signInToken(pasted))} disabled={busy || !pasted.trim()}
              className="px-4 py-2 bg-f1-red text-white text-sm font-bold rounded hover:bg-red-700 transition-colors disabled:opacity-50">
              {busy ? "Verificando…" : "Entrar"}
            </button>
            <button onClick={() => { setPasteMode(false); setError(null); }} className="text-xs text-f1-muted hover:text-white underline">
              Usar e-mail e senha
            </button>
          </div>
        </div>
      )}
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  );
}

/** Shown when F1TV_SECRET_KEY isn't set: the saved sign-in then relies on a
 *  key file that Docker rebuilds and file-wiping hosts lose. */
function SecretKeyNote() {
  return (
    <div className="flex items-start gap-2 rounded border border-f1-border bg-f1-dark px-3 py-2">
      <Info className="w-4 h-4 mt-0.5 flex-shrink-0 text-sky-400" />
      <p className="text-xs text-f1-muted leading-relaxed">
        <span className="text-white font-bold">Defina <span className="font-mono">F1TV_SECRET_KEY</span> no seu .env</span>{" "}
        para continuar conectado depois de recriar o Docker ou reimplantar. Gere uma com{" "}
        <span className="font-mono text-white">openssl rand -hex 32</span>e reinicie o app.
      </p>
    </div>
  );
}

/** The sign-in as a dialog, for the home page. */
export function F1TVAccountDialog({ onClose, onChange }: { onClose: () => void; onChange?: (s: F1TVStatus) => void }) {
  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-f1-card border border-f1-border rounded-xl shadow-xl w-full max-w-md max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}>
        <div className="px-6 pt-5 pb-2 flex items-center justify-between">
          <h3 className="text-white font-bold text-lg">Conta F1 TV</h3>
          <button onClick={onClose} aria-label="Fechar" title="Fechar"
            className="w-7 h-7 flex items-center justify-center rounded text-f1-muted hover:text-white hover:bg-white/10 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="pb-5">
          <F1TVAccount onChange={onChange} onDone={onClose} />
        </div>
      </div>
    </div>
  );
}
