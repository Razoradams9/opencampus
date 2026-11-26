import { useState, type FormEvent } from "react";
import { AuthLayout } from "../components/auth/AuthLayout";
import { Field, FormError, SubmitButton } from "../components/auth/FormControls";
import { useAuth } from "../lib/auth/AuthContext";
import { Link, navigate } from "../lib/router";

const PASSWORD_MIN = 12;

export function RegisterPage() {
  const { register } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    try {
      await register({
        full_name: String(form.get("full_name")),
        email: String(form.get("email")),
        password: String(form.get("password")),
      });
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
      setBusy(false);
    }
  };

  return (
    <AuthLayout
      eyebrow="Create account"
      title="Join your campus."
      intro="Create a free student account. It only takes a minute."
      footer={
        <>
          Already registered?{" "}
          <Link to="/login" className="font-medium text-accent underline-offset-4 hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-5">
        <FormError message={error} />
        <Field id="full_name" name="full_name" label="Full name" autoComplete="name" required maxLength={200} autoFocus />
        <Field id="email" name="email" type="email" label="Email" autoComplete="email" required />
        <Field
          id="password"
          name="password"
          type="password"
          label="Password"
          autoComplete="new-password"
          required
          minLength={PASSWORD_MIN}
          maxLength={128}
          hint={`At least ${PASSWORD_MIN} characters. A short phrase works well.`}
        />
        <SubmitButton busy={busy}>{busy ? "Creating account…" : "Create account"}</SubmitButton>
      </form>
    </AuthLayout>
  );
}
