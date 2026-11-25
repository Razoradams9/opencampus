import { Check, CircleCheck, CircleSlash } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { AuthLayout } from "../components/auth/AuthLayout";
import { Field, FormError, SubmitButton } from "../components/auth/FormControls";
import { ApiError, apiRequest } from "../lib/api";
import { useAuth } from "../lib/auth/AuthContext";
import { Link } from "../lib/router";

const PASSWORD_MIN = 12;
const TOKEN_PATTERN = /^[A-Za-z0-9_-]{20,200}$/;

/**
 * Reads the token from the URL fragment (#token=…), which browsers never send
 * to servers, then removes it from the address bar and history.
 */
function useResetToken(): string | null {
  const [token] = useState<string | null>(() => {
    const value = new URLSearchParams(window.location.hash.slice(1)).get("token");
    return value && TOKEN_PATTERN.test(value) ? value : null;
  });
  useEffect(() => {
    if (window.location.hash) window.history.replaceState(null, "", window.location.pathname);
  }, []);
  return token;
}

function Requirement({ met, children }: { met: boolean; children: string }) {
  return (
    <li className={`flex items-center gap-1.5 ${met ? "text-success" : "text-ink-subtle"}`}>
      {met ? <Check className="size-3.5" aria-hidden="true" /> : <span className="size-3.5 text-center" aria-hidden="true">·</span>}
      {children}
      <span className="sr-only">{met ? "(met)" : "(not met yet)"}</span>
    </li>
  );
}

const requestNewLink = (
  <Link to="/forgot-password" className="font-medium text-accent underline-offset-4 hover:underline">
    Request a new link
  </Link>
);

export function ResetPasswordPage() {
  const token = useResetToken();
  const { forgetSession } = useAuth();
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [tokenRejected, setTokenRejected] = useState(false);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  const longEnough = password.length >= PASSWORD_MIN;
  const matches = password.length > 0 && password === confirmation;

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token) return;
    if (!longEnough) return setError(`Use at least ${PASSWORD_MIN} characters.`);
    if (!matches) return setError("The two passwords don't match.");
    setBusy(true);
    setError(null);
    try {
      await apiRequest("/api/auth/password-reset/confirm", { method: "POST", body: { token, new_password: password } });
      forgetSession(); // every session was revoked on the server, including this browser's
      setDone(true);
    } catch (err) {
      if (err instanceof ApiError && err.code === "reset_token_invalid") setTokenRejected(true);
      else setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <AuthLayout
        eyebrow="All set"
        title="Password changed."
        intro="For your security we signed you out everywhere. Sign in with your new password."
        footer={
          <Link to="/login" className="font-medium text-accent underline-offset-4 hover:underline">
            Go to sign in
          </Link>
        }
      >
        <p className="flex items-center gap-2 rounded-xl bg-success-soft px-4 py-3 text-sm text-success shadow-e1" role="status">
          <CircleCheck className="size-5 shrink-0" aria-hidden="true" /> Your new password is active.
        </p>
      </AuthLayout>
    );
  }

  if (!token || tokenRejected) {
    return (
      <AuthLayout
        eyebrow="Link problem"
        title={token ? "This link has expired." : "This link isn't complete."}
        intro={
          token
            ? "Reset links work once and last 30 minutes. Ask for a fresh one and use the newest email."
            : "Open the link straight from your email. If it was split across lines, copy the whole thing."
        }
        footer={
          <Link to="/login" className="font-medium text-accent underline-offset-4 hover:underline">
            Back to sign in
          </Link>
        }
      >
        <p className="flex items-center gap-2 rounded-xl bg-pending-soft px-4 py-3 text-sm text-pending shadow-e1" role="alert">
          <CircleSlash className="size-5 shrink-0" aria-hidden="true" /> {requestNewLink}
        </p>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      eyebrow="Reset password"
      title="Choose a new password."
      intro="You'll be signed out of every device, then you can sign in with it."
      footer={
        <Link to="/login" className="font-medium text-accent underline-offset-4 hover:underline">
          Back to sign in
        </Link>
      }
    >
      <form onSubmit={onSubmit} className="space-y-5" noValidate>
        <FormError message={error} />
        <Field
          id="new_password"
          name="new_password"
          type="password"
          label="New password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          maxLength={128}
          required
          autoFocus
          hint={
            <ul className="space-y-0.5" aria-live="polite">
              <Requirement met={longEnough}>{`At least ${PASSWORD_MIN} characters (a short phrase works well)`}</Requirement>
              <Requirement met={matches}>Both passwords match</Requirement>
            </ul>
          }
        />
        <Field
          id="confirm_password"
          name="confirm_password"
          type="password"
          label="Confirm new password"
          autoComplete="new-password"
          value={confirmation}
          onChange={(e) => setConfirmation(e.target.value)}
          maxLength={128}
          required
        />
        <SubmitButton busy={busy}>{busy ? "Saving…" : "Set new password"}</SubmitButton>
      </form>
    </AuthLayout>
  );
}
