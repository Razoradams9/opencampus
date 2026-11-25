import { MailCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { AuthLayout } from "../components/auth/AuthLayout";
import { Field, FormError, SubmitButton } from "../components/auth/FormControls";
import { apiRequest } from "../lib/api";
import { Link } from "../lib/router";

const backToSignIn = (
  <Link to="/login" className="font-medium text-accent underline-offset-4 hover:underline">
    Back to sign in
  </Link>
);

export function ForgotPasswordPage() {
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const email = String(new FormData(event.currentTarget).get("email")).trim();
    setBusy(true);
    setError(null);
    try {
      const result = await apiRequest<{ message: string }>("/api/auth/password-reset/request", {
        method: "POST",
        body: { email },
      });
      setMessage(result.message);
      setSentTo(email);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  if (sentTo) {
    // The server answers the same way for every address, so this page does too.
    return (
      <AuthLayout eyebrow="Check your email" title="Link on its way." intro={message} footer={backToSignIn}>
        <div className="flex items-start gap-3 rounded-xl bg-success-soft px-4 py-3 text-sm text-success shadow-e1" role="status">
          <MailCheck className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
          <p>
            We sent it to <strong className="font-semibold">{sentTo}</strong> if it belongs to an account. The link
            works once and expires in 30 minutes.
          </p>
        </div>
        <p className="mt-5 text-sm text-ink-muted">
          Nothing arrived? Check spam, or{" "}
          <button type="button" onClick={() => setSentTo(null)} className="font-medium text-accent underline-offset-4 hover:underline">
            try again
          </button>
          .
        </p>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      eyebrow="Password help"
      title="Forgot your password?"
      intro="Enter your account email and we'll send you a link to choose a new one."
      footer={backToSignIn}
    >
      <form onSubmit={onSubmit} className="space-y-5">
        <FormError message={error} />
        <Field id="email" name="email" type="email" label="Email" autoComplete="email" required autoFocus />
        <SubmitButton busy={busy}>{busy ? "Sending…" : "Send reset link"}</SubmitButton>
      </form>
    </AuthLayout>
  );
}
