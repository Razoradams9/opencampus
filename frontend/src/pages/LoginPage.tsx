import { useState, type FormEvent } from "react";
import { AuthLayout } from "../components/auth/AuthLayout";
import { Field, FormError, SubmitButton } from "../components/auth/FormControls";
import { useAuth } from "../lib/auth/AuthContext";
import { Link, navigate, safeNextPath, useLocation } from "../lib/router";

export function LoginPage() {
  const { login } = useAuth();
  const { search } = useLocation();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    try {
      await login(String(form.get("email")), String(form.get("password")));
      navigate(safeNextPath(search), { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
      setBusy(false);
    }
  };

  return (
    <AuthLayout
      eyebrow="Sign in"
      title="Welcome back."
      intro="Use the email and password for your OpenCampus account."
      footer={
        <>
          New here?{" "}
          <Link to="/register" className="font-medium text-accent underline-offset-4 hover:underline">
            Create a student account
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-5" noValidate={false}>
        <FormError message={error} />
        <Field id="email" name="email" type="email" label="Email" autoComplete="email" required autoFocus />
        <div>
          <Field id="password" name="password" type="password" label="Password" autoComplete="current-password" required />
          <p className="mt-2 text-right text-sm">
            <Link to="/forgot-password" className="font-medium text-accent underline-offset-4 hover:underline">
              Forgot password?
            </Link>
          </p>
        </div>
        <SubmitButton busy={busy}>{busy ? "Signing in…" : "Sign in"}</SubmitButton>
      </form>

      {import.meta.env.DEV && (
        <p className="mt-6 border border-dashed border-line-strong px-3 py-2.5 text-xs leading-relaxed text-ink-subtle">
          Development: create fictional demo accounts with{" "}
          <code className="font-mono text-ink-muted">python -m app.cli seed-demo</code>, e.g.{" "}
          <code className="font-mono text-ink-muted">maya.okafor@aldermoor.example</code>.
        </p>
      )}
    </AuthLayout>
  );
}
