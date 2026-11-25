import { CheckCircle2, CircleSlash } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { AuthLayout } from "../components/auth/AuthLayout";
import { Field, FormError, SubmitButton } from "../components/auth/FormControls";
import { ApiError, apiRequest } from "../lib/api";
import { useAuth } from "../lib/auth/AuthContext";
import type { InstitutionPublic } from "../lib/auth/types";
import { Link, navigate } from "../lib/router";

const PASSWORD_MIN = 12;

type Lookup =
  | { state: "idle" }
  | { state: "checking" }
  | { state: "found"; institution: InstitutionPublic }
  | { state: "missing" };

/** Debounced lookup of the institution code against GET /api/institutions/{slug}. */
function useInstitutionLookup(slug: string): Lookup {
  const [lookup, setLookup] = useState<Lookup>({ state: "idle" });

  useEffect(() => {
    const value = slug.trim().toLowerCase();
    if (!/^[a-z0-9-]{2,63}$/.test(value)) {
      setLookup({ state: "idle" });
      return;
    }
    const controller = new AbortController();
    setLookup({ state: "checking" });
    const timeout = window.setTimeout(() => {
      apiRequest<InstitutionPublic>(`/api/institutions/${encodeURIComponent(value)}`, { signal: controller.signal })
        .then((institution) => setLookup({ state: "found", institution }))
        .catch((error) => {
          if (error instanceof ApiError && error.status === 404) setLookup({ state: "missing" });
          else if (!(error instanceof DOMException)) setLookup({ state: "idle" });
        });
    }, 350);
    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [slug]);

  return lookup;
}

function LookupHint({ lookup }: { lookup: Lookup }) {
  switch (lookup.state) {
    case "checking":
      return <span>Checking…</span>;
    case "missing":
      return (
        <span className="inline-flex items-center gap-1 text-danger">
          <CircleSlash className="size-3.5" aria-hidden="true" /> No institution with this code
        </span>
      );
    case "found":
      return lookup.institution.registration_open ? (
        <span className="inline-flex items-center gap-1 text-success">
          <CheckCircle2 className="size-3.5" aria-hidden="true" /> {lookup.institution.name}
        </span>
      ) : (
        <span className="inline-flex items-center gap-1 text-pending">
          <CircleSlash className="size-3.5" aria-hidden="true" /> {lookup.institution.name} is not accepting sign-ups
        </span>
      );
    default:
      return <span>The short code your college gave you, e.g. “aldermoor”.</span>;
  }
}

export function RegisterPage() {
  const { register } = useAuth();
  const [slug, setSlug] = useState("");
  const lookup = useInstitutionLookup(slug);
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
        institution_slug: slug.trim().toLowerCase(),
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
      intro="New accounts join as students. Faculty and administrator access is granted by your college."
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
        <Field
          id="institution"
          name="institution"
          label="Institution code"
          value={slug}
          onChange={(e) => setSlug(e.target.value)}
          autoComplete="off"
          autoCapitalize="none"
          spellCheck={false}
          required
          autoFocus
          hint={<span aria-live="polite"><LookupHint lookup={lookup} /></span>}
        />
        <Field id="full_name" name="full_name" label="Full name" autoComplete="name" required maxLength={200} />
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
