import { ArrowLeft, CircleCheck, ExternalLink, History, Send, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { FormError } from "../auth/FormControls";
import { Empty, LoadError, Loading } from "../ui/DataState";
import { Button, TextArea } from "../ui/Form";
import { SectionHeading } from "../ui/SectionHeading";
import { SubjectMark } from "../ui/SubjectMark";
import { DeadlineBar, GradeBadge } from "./Deadline";
import { ApiError } from "../../lib/api";
import { academicApi } from "../../lib/academic/api";
import { bucketOf, formatDateTime, LATE_POLICY_TEXT, type Bucket } from "../../lib/academic/deadlines";
import { toneFor } from "../../lib/academic/format";
import type { Coursework } from "../../lib/academic/types";
import { Link } from "../../lib/router";
import { useApi } from "../../lib/useApi";

const SECTIONS: { id: Bucket; title: string; accent: string; empty: string }[] = [
  { id: "due", title: "Due", accent: "var(--oc-subject-teal)", empty: "Nothing due right now." },
  { id: "overdue", title: "Overdue", accent: "var(--oc-subject-rose)", empty: "Nothing overdue." },
  { id: "submitted", title: "Submitted", accent: "var(--oc-subject-cobalt)", empty: "" },
  { id: "graded", title: "Graded", accent: "var(--oc-subject-violet)", empty: "" },
];

function Row({ a }: { a: Coursework }) {
  return (
    <li className="border-b border-line last:border-b-0">
      <Link to={`/assignments?id=${a.id}`} className="oc-reveal flex flex-col gap-3 px-5 py-4 transition-colors hover:bg-sunken/60 sm:flex-row sm:items-center sm:gap-6 sm:px-6">
        <div className="flex min-w-0 flex-1 items-start gap-3">
          <SubjectMark tone={toneFor(a.subject.code)} className="mt-1.5 size-3" />
          <div className="min-w-0">
            <p className="font-display text-lg leading-snug font-medium">{a.title}</p>
            <p className="font-mono text-[0.6875rem] text-ink-subtle">
              {a.subject.code} · {a.subject.name} · {a.max_marks} marks
            </p>
          </div>
        </div>
        {a.me?.grade ? (
          <GradeBadge marks={a.me.grade.marks_awarded} max={a.max_marks} />
        ) : a.me?.status === "submitted" ? (
          <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-success">
            <CircleCheck className="size-4" aria-hidden="true" /> Submitted{a.me.is_late ? " (late)" : ""}
          </span>
        ) : (
          <DeadlineBar a={a} compact />
        )}
      </Link>
    </li>
  );
}

function StudentList() {
  const list = useApi((signal) => academicApi.myCoursework(signal), []);
  if (list.status === "loading") return <div className="oc-panel"><Loading label="Loading assignments…" /></div>;
  if (list.status === "error") return <div className="oc-panel"><LoadError error={list.error} onRetry={list.reload} /></div>;
  if (list.data.length === 0)
    return (
      <div className="oc-panel">
        <Empty title="No assignments yet">Assignments from your enrolled subjects appear here once your teachers publish them.</Empty>
      </div>
    );
  return (
    <div className="grid gap-8 lg:grid-cols-2">
      {SECTIONS.map((section) => {
        const items = list.data.filter((a) => bucketOf(a) === section.id);
        if (items.length === 0 && !section.empty) return null;
        return (
          <section key={section.id} aria-labelledby={`cw-${section.id}`} className={section.id === "due" ? "lg:col-span-2" : ""}>
            <SectionHeading id={`cw-${section.id}`} title={section.title} accent={section.accent} meta={`${items.length}`} />
            <div className="oc-panel">
              {items.length === 0 ? <p className="px-5 py-5 text-sm text-ink-subtle sm:px-6">{section.empty}</p> : <ul>{items.map((a) => <Row key={a.id} a={a} />)}</ul>}
            </div>
          </section>
        );
      })}
    </div>
  );
}

function StudentDetail({ id }: { id: string }) {
  const assignment = useApi((signal) => academicApi.coursework(id, signal), [id]);
  const history = useApi((signal) => academicApi.mySubmissions(id, signal), [id]);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmed, setConfirmed] = useState<string | null>(null);

  if (assignment.status === "loading") return <div className="oc-panel"><Loading label="Loading assignment…" /></div>;
  if (assignment.status === "error") return <div className="oc-panel"><LoadError error={assignment.error} onRetry={assignment.reload} /></div>;
  const a = assignment.data;
  const canSubmit = a.status === "published" && (a.window === "open" || a.window === "late");

  const send = async () => {
    setError(null);
    setBusy(true);
    try {
      const s = await academicApi.submitWork(a.id, text);
      setText("");
      setConfirmed(`Attempt ${s.attempt} received ${formatDateTime(s.submitted_at)}${s.is_late ? " — marked late" : ""}.`);
      history.reload();
      assignment.reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not submit");
    } finally {
      setBusy(false);
    }
  };

  return (
    <article className="space-y-6">
      <Link to="/assignments" className="inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:underline">
        <ArrowLeft className="size-4" aria-hidden="true" /> All assignments
      </Link>
      <header className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem] lg:items-end">
        <div>
          <p className="flex items-center gap-2 font-mono text-xs text-ink-subtle">
            <SubjectMark tone={toneFor(a.subject.code)} className="size-2.5" /> {a.subject.code} · {a.subject.name}
          </p>
          <h1 className="mt-1 font-display text-[2rem] leading-tight font-medium tracking-tight sm:text-[2.5rem]">{a.title}</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Set by {a.created_by.full_name} · {a.max_marks} marks · {LATE_POLICY_TEXT[a.late_policy]}
            {a.late_cutoff_at ? ` Cut-off ${formatDateTime(a.late_cutoff_at)}.` : ""}
          </p>
        </div>
        {a.me?.grade ? (
          <div className="oc-panel px-5 py-4">
            <p className="oc-eyebrow">Your grade</p>
            <div className="mt-2"><GradeBadge marks={a.me.grade.marks_awarded} max={a.max_marks} /></div>
          </div>
        ) : (
          <div className="oc-panel px-5 py-4"><DeadlineBar a={a} /></div>
        )}
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <section className="space-y-6">
          <div className="oc-panel px-5 py-5 sm:px-6">
            <p className="oc-eyebrow mb-2">Instructions</p>
            <p className="text-[0.9375rem] leading-relaxed whitespace-pre-wrap">{a.instructions}</p>
            {a.reference_url && (
              <a href={a.reference_url} target="_blank" rel="noopener noreferrer" className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:underline">
                Reference material <ExternalLink className="size-3.5" aria-hidden="true" /><span className="sr-only">(opens in a new tab)</span>
              </a>
            )}
          </div>

          <div className="oc-panel px-5 py-5 sm:px-6">
            <p className="oc-eyebrow mb-3">{a.me && a.me.attempts > 0 ? "Submit a new attempt" : "Your submission"}</p>
            {confirmed && (
              <p role="status" className="mb-4 flex items-start gap-2 rounded-xl bg-success-soft px-3 py-2.5 text-sm text-success">
                <CircleCheck className="mt-0.5 size-4 shrink-0" aria-hidden="true" /> {confirmed}
              </p>
            )}
            {canSubmit ? (
              <form onSubmit={(e) => { e.preventDefault(); void send(); }} className="space-y-3">
                {a.window === "late" && (
                  <p className="flex items-start gap-2 rounded-xl bg-pending-soft px-3 py-2.5 text-sm text-pending">
                    <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" /> The deadline has passed. This submission will be marked late.
                  </p>
                )}
                <TextArea id="submission" label="Your answer" required rows={10} value={text} onChange={(e) => setText(e.target.value)} hint="Earlier attempts are kept; your teacher sees every attempt." />
                <FormError message={error} />
                <Button type="submit" variant="primary" busy={busy} disabled={!text.trim()} icon={<Send className="size-4" aria-hidden="true" />}>
                  Submit
                </Button>
              </form>
            ) : (
              <p className="text-sm text-ink-muted">
                {a.window === "not_open" ? "This assignment is not open yet." : a.status !== "published" ? "This assignment is closed." : "The deadline has passed and late submissions are not accepted."}
              </p>
            )}
          </div>
        </section>

        <aside aria-labelledby="history-title">
          <h2 id="history-title" className="mb-3 flex items-center gap-2 font-display text-xl font-medium">
            <History className="size-5 text-ink-subtle" aria-hidden="true" /> History
          </h2>
          <div className="oc-panel">
            {history.status === "loading" && <Loading label="Loading…" />}
            {history.status === "error" && <LoadError error={history.error} onRetry={history.reload} />}
            {history.status === "ready" && history.data.length === 0 && <p className="px-5 py-5 text-sm text-ink-subtle">No submissions yet.</p>}
            {history.status === "ready" && (
              <ol>
                {[...history.data].reverse().map((s) => (
                  <li key={s.id} className="border-b border-line px-5 py-4 last:border-b-0">
                    <p className="flex flex-wrap items-center gap-2 text-sm font-semibold">
                      Attempt {s.attempt}
                      {s.is_late && <span className="rounded-full bg-pending-soft px-2 py-px text-[0.6875rem] text-pending">Late</span>}
                      {s.status === "superseded" && <span className="text-[0.6875rem] font-normal text-ink-subtle">replaced</span>}
                    </p>
                    <p className="font-mono text-[0.6875rem] text-ink-subtle">{formatDateTime(s.submitted_at)}</p>
                    <p className="mt-2 line-clamp-4 text-sm whitespace-pre-wrap text-ink-muted">{s.body}</p>
                    {s.grade && (
                      <div className="mt-3 rounded-xl border-l-4 border-subject-violet bg-lavender px-3 py-2.5">
                        <p className="text-sm font-semibold">{s.grade.marks_awarded} / {a.max_marks}</p>
                        {s.grade.feedback && <p className="mt-1 text-sm whitespace-pre-wrap">{s.grade.feedback}</p>}
                        <p className="mt-1 font-mono text-[0.6875rem] text-ink-subtle">{s.grade.graded_by.full_name} · {formatDateTime(s.grade.graded_at)}</p>
                      </div>
                    )}
                  </li>
                ))}
              </ol>
            )}
          </div>
        </aside>
      </div>
    </article>
  );
}

export function StudentCoursework({ id }: { id: string | null }) {
  return id ? <StudentDetail key={id} id={id} /> : <StudentList />;
}
