import { Archive, ArrowLeft, ChevronDown, Pencil, Plus, Send } from "lucide-react";
import { useMemo, useState } from "react";
import { SubjectRail } from "../academic/SubjectRail";
import { FormError } from "../auth/FormControls";
import { Empty, LoadError, Loading } from "../ui/DataState";
import { Button, Select, StatusChip, TextArea, TextInput } from "../ui/Form";
import { DeadlineBar } from "./Deadline";
import { ApiError } from "../../lib/api";
import { academicApi } from "../../lib/academic/api";
import { formatDateTime, fromLocalInput, LATE_POLICY_TEXT, toLocalInput } from "../../lib/academic/deadlines";
import { loadMySubjects } from "../../lib/academic/mySubjects";
import type { Coursework, CourseworkInput, LatePolicy, MySubject, Role, Submission } from "../../lib/academic/types";
import { Link, navigate, useLocation } from "../../lib/router";
import { useApi } from "../../lib/useApi";

function Editor({ subject, editing, onDone }: { subject: MySubject; editing: Coursework | null; onDone: (changed: boolean) => void }) {
  const inAWeek = new Date(Date.now() + 7 * 86_400_000);
  inAWeek.setHours(23, 59, 0, 0);
  const [f, setF] = useState({
    title: editing?.title ?? "",
    instructions: editing?.instructions ?? "",
    reference_url: editing?.reference_url ?? "",
    available_from: toLocalInput(editing?.available_from ?? new Date().toISOString()),
    due_at: toLocalInput(editing?.due_at ?? inAWeek.toISOString()),
    late_policy: (editing?.late_policy ?? "reject") as LatePolicy,
    late_cutoff_at: toLocalInput(editing?.late_cutoff_at ?? null),
    max_marks: String(editing?.max_marks ?? 20),
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"draft" | "publish" | null>(null);
  const set = (k: keyof typeof f, v: string) => setF((x) => ({ ...x, [k]: v }));

  const save = async (publish: boolean) => {
    setError(null);
    setBusy(publish ? "publish" : "draft");
    try {
      const body: CourseworkInput = {
        title: f.title,
        instructions: f.instructions,
        reference_url: f.reference_url.trim() || null,
        available_from: fromLocalInput(f.available_from),
        due_at: fromLocalInput(f.due_at),
        late_policy: f.late_policy,
        late_cutoff_at: f.late_policy === "accept_until" && f.late_cutoff_at ? fromLocalInput(f.late_cutoff_at) : null,
        max_marks: Number(f.max_marks),
      };
      const saved = editing ? await academicApi.updateCoursework(editing.id, body) : await academicApi.createCoursework(subject.subject.id, body);
      if (publish && saved.status === "draft") await academicApi.setCourseworkStatus(saved.id, "publish");
      onDone(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : e instanceof RangeError ? "Check the dates" : "Could not save");
      setBusy(null);
    }
  };

  return (
    <form onSubmit={(e) => { e.preventDefault(); void save(false); }} className="oc-reveal space-y-4 border-b border-line bg-sunken/60 px-5 py-5 sm:px-6" aria-label={editing ? "Edit assignment" : "New assignment"}>
      <p className="oc-eyebrow">{editing ? "Edit assignment" : `New assignment · ${subject.subject.code}`}</p>
      <div className="grid gap-4 sm:grid-cols-[1fr_8rem]">
        <TextInput id="cw-title" label="Title" required maxLength={200} value={f.title} onChange={(e) => set("title", e.target.value)} />
        <TextInput id="cw-marks" label="Max marks" type="number" min={0.5} max={1000} step={0.5} required value={f.max_marks} onChange={(e) => set("max_marks", e.target.value)} />
      </div>
      <TextArea id="cw-instructions" label="Instructions" required rows={6} value={f.instructions} onChange={(e) => set("instructions", e.target.value)} />
      <TextInput id="cw-url" label="Reference link (optional)" type="url" placeholder="https://" value={f.reference_url} onChange={(e) => set("reference_url", e.target.value)} />
      <div className="grid gap-4 sm:grid-cols-2">
        <TextInput id="cw-from" label="Available from" type="datetime-local" required value={f.available_from} onChange={(e) => set("available_from", e.target.value)} />
        <TextInput id="cw-due" label="Deadline" type="datetime-local" required value={f.due_at} onChange={(e) => set("due_at", e.target.value)} />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Select id="cw-late" label="Late submissions" value={f.late_policy} onChange={(e) => set("late_policy", e.target.value)} hint={LATE_POLICY_TEXT[f.late_policy]}>
          <option value="reject">Not accepted</option>
          <option value="accept">Accepted, marked late</option>
          <option value="accept_until">Accepted until a cut-off</option>
        </Select>
        {f.late_policy === "accept_until" && (
          <TextInput id="cw-cutoff" label="Late cut-off" type="datetime-local" required value={f.late_cutoff_at} onChange={(e) => set("late_cutoff_at", e.target.value)} />
        )}
      </div>
      <p className="text-xs text-ink-subtle">Times are in your device's time zone. File attachments are not available yet: link to the brief instead.</p>
      <FormError message={error} />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" busy={busy === "draft"} disabled={busy !== null}>{editing?.status === "published" ? "Save changes" : "Save draft"}</Button>
        {(!editing || editing.status === "draft") && (
          <Button variant="primary" busy={busy === "publish"} disabled={busy !== null} onClick={() => void save(true)} icon={<Send className="size-4" aria-hidden="true" />}>
            Save and publish
          </Button>
        )}
        <Button variant="ghost" onClick={() => onDone(false)} disabled={busy !== null}>Cancel</Button>
      </div>
    </form>
  );
}

function GradeForm({ s, max, onGraded }: { s: Submission; max: number; onGraded: () => void }) {
  const [marks, setMarks] = useState(s.grade ? String(s.grade.marks_awarded) : "");
  const [feedback, setFeedback] = useState(s.grade?.feedback ?? "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        setError(null);
        setBusy(true);
        try {
          await academicApi.gradeSubmission(s.id, Number(marks), feedback.trim() || null);
          onGraded();
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "Could not save the grade");
        } finally {
          setBusy(false);
        }
      }}
      className="mt-4 grid gap-3 sm:grid-cols-[8rem_1fr]"
    >
      <TextInput id={`marks-${s.id}`} label={`Marks / ${max}`} type="number" min={0} max={max} step={0.25} required value={marks} onChange={(e) => setMarks(e.target.value)} />
      <TextArea id={`fb-${s.id}`} label="Feedback" rows={3} value={feedback} onChange={(e) => setFeedback(e.target.value)} />
      <div className="sm:col-span-2">
        <FormError message={error} />
        <Button type="submit" variant="primary" busy={busy} className="mt-2">{s.grade ? "Regrade" : "Save grade"}</Button>
        {s.grade_history.length > 1 && <span className="ml-3 text-xs text-ink-subtle">{s.grade_history.length} grading events kept</span>}
      </div>
    </form>
  );
}

function Review({ id }: { id: string }) {
  const assignment = useApi((signal) => academicApi.coursework(id, signal), [id]);
  const subs = useApi((signal) => academicApi.submissionsFor(id, signal), [id]);
  const [open, setOpen] = useState<string | null>(null);
  const byStudent = useMemo(() => {
    const map = new Map<string, Submission[]>();
    if (subs.status === "ready") for (const s of subs.data) map.set(s.student.membership_id, [...(map.get(s.student.membership_id) ?? []), s]);
    return [...map.values()];
  }, [subs]);

  if (assignment.status === "loading") return <div className="oc-panel"><Loading label="Loading…" /></div>;
  if (assignment.status === "error") return <div className="oc-panel"><LoadError error={assignment.error} onRetry={assignment.reload} /></div>;
  const a = assignment.data;
  return (
    <article className="space-y-6">
      <Link to={`/assignments?subject=${a.subject.id}`} className="inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:underline">
        <ArrowLeft className="size-4" aria-hidden="true" /> {a.subject.code} assignments
      </Link>
      <header className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_18rem] lg:items-end">
        <div>
          <p className="font-mono text-xs text-ink-subtle">{a.subject.code} · {a.max_marks} marks · <StatusChip status={a.status} /></p>
          <h1 className="mt-1 font-display text-[2rem] leading-tight font-medium tracking-tight">{a.title}</h1>
          <p className="mt-1 text-sm text-ink-muted">{a.submitted_students} submitted · {a.graded_students} graded</p>
        </div>
        <div className="oc-panel px-5 py-4"><DeadlineBar a={a} /></div>
      </header>
      <div className="oc-panel">
        {subs.status === "loading" && <Loading label="Loading submissions…" />}
        {subs.status === "error" && <LoadError error={subs.error} onRetry={subs.reload} />}
        {subs.status === "ready" && byStudent.length === 0 && <Empty title="No submissions yet" />}
        <ul>
          {byStudent.map((attempts) => {
            const latest = attempts[0];
            const isOpen = open === latest.student.membership_id;
            return (
              <li key={latest.student.membership_id} className="border-b border-line last:border-b-0">
                <button type="button" onClick={() => setOpen(isOpen ? null : latest.student.membership_id)} aria-expanded={isOpen} className="flex w-full flex-wrap items-center gap-3 px-5 py-4 text-left hover:bg-sunken/60 sm:px-6">
                  <span className="min-w-0 flex-1">
                    <span className="block font-medium">{latest.student.full_name}</span>
                    <span className="block font-mono text-[0.6875rem] text-ink-subtle">
                      Attempt {latest.attempt} · {formatDateTime(latest.submitted_at)}{latest.is_late ? " · late" : ""}
                    </span>
                  </span>
                  {latest.grade ? (
                    <span className="font-display text-lg font-medium">{latest.grade.marks_awarded}<span className="font-sans text-xs text-ink-subtle">/{a.max_marks}</span></span>
                  ) : (
                    <span className="rounded-full bg-pending-soft px-2 py-0.5 text-[0.6875rem] font-semibold text-pending">To grade</span>
                  )}
                  <ChevronDown className={`size-4 text-ink-subtle transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`} aria-hidden="true" />
                </button>
                {isOpen && (
                  <div className="oc-reveal border-t border-line bg-sunken/40 px-5 py-4 sm:px-6">
                    <p className="text-[0.9375rem] leading-relaxed whitespace-pre-wrap">{latest.body}</p>
                    <GradeForm s={latest} max={a.max_marks} onGraded={() => { subs.reload(); assignment.reload(); }} />
                    {attempts.length > 1 && (
                      <details className="mt-4">
                        <summary className="cursor-pointer text-sm font-medium text-accent">Earlier attempts ({attempts.length - 1})</summary>
                        <ol className="mt-2 space-y-3">
                          {attempts.slice(1).map((s) => (
                            <li key={s.id} className="rounded-xl bg-surface px-3 py-2.5 text-sm">
                              <p className="font-mono text-[0.6875rem] text-ink-subtle">Attempt {s.attempt} · {formatDateTime(s.submitted_at)}{s.is_late ? " · late" : ""}{s.grade ? ` · ${s.grade.marks_awarded}/${a.max_marks}` : ""}</p>
                              <p className="mt-1 whitespace-pre-wrap text-ink-muted">{s.body}</p>
                            </li>
                          ))}
                        </ol>
                      </details>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </div>
    </article>
  );
}

function Overview({ role }: { role: Role }) {
  const { search } = useLocation();
  const subjects = useApi((signal) => loadMySubjects(role, signal), [role]);
  const list = useApi((signal) => academicApi.managedCoursework(signal), []);
  const [editor, setEditor] = useState<{ editing: Coursework | null } | null>(null);
  const all = subjects.status === "ready" ? subjects.data : [];
  const requested = new URLSearchParams(search).get("subject");
  const current = all.find((s) => s.subject.id === requested) ?? all[0] ?? null;
  const items = list.status === "ready" && current ? list.data.filter((a) => a.subject.id === current.subject.id) : [];
  const counts = useMemo(() => {
    const m = new Map<string, number>();
    if (list.status === "ready") for (const a of list.data) if (a.status !== "archived") m.set(a.subject.id, (m.get(a.subject.id) ?? 0) + 1);
    return m;
  }, [list]);

  if (subjects.status === "loading") return <div className="oc-panel"><Loading label="Loading your subjects…" /></div>;
  if (subjects.status === "error") return <div className="oc-panel"><LoadError error={subjects.error} onRetry={subjects.reload} /></div>;
  if (!current) return <div className="oc-panel"><Empty title="No subjects assigned to you">Assignments are set per subject you teach.</Empty></div>;

  return (
    <div className="grid gap-6 lg:grid-cols-[17rem_minmax(0,1fr)] lg:gap-8">
      <SubjectRail subjects={all} selected={current.subject.id} counts={list.status === "ready" ? counts : undefined} label="Subjects" onSelect={(id) => { setEditor(null); navigate(`/assignments?subject=${id}`, { replace: true }); }} />
      <section className="min-w-0" aria-labelledby="cw-subject">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="font-mono text-xs text-ink-subtle">{current.subject.code} · {current.course.code}</p>
            <h2 id="cw-subject" className="font-display text-[1.75rem] leading-tight font-medium tracking-tight sm:text-[2rem]">{current.subject.name}</h2>
          </div>
          {!editor && <Button variant="primary" onClick={() => setEditor({ editing: null })} icon={<Plus className="size-4" aria-hidden="true" />}>New assignment</Button>}
        </div>
        <div className="oc-panel">
          {editor && <Editor key={editor.editing?.id ?? "new"} subject={current} editing={editor.editing} onDone={(changed) => { setEditor(null); if (changed) list.reload(); }} />}
          {list.status === "loading" && <Loading label="Loading assignments…" />}
          {list.status === "error" && <LoadError error={list.error} onRetry={list.reload} />}
          {list.status === "ready" && items.length === 0 && <Empty title="No assignments for this subject">Drafts stay private until you publish them.</Empty>}
          <ul>
            {items.map((a) => (
              <li key={a.id} className="oc-reveal flex flex-col gap-3 border-b border-line px-5 py-4 last:border-b-0 sm:flex-row sm:items-center sm:gap-5 sm:px-6">
                <div className="min-w-0 flex-1">
                  <Link to={`/assignments?id=${a.id}`} className="font-display text-lg leading-snug font-medium hover:text-accent">{a.title}</Link>
                  <p className="mt-0.5 flex flex-wrap items-center gap-2 font-mono text-[0.6875rem] text-ink-subtle">
                    <StatusChip status={a.status} /> {a.max_marks} marks · {a.submitted_students} submitted · {a.graded_students} graded
                  </p>
                </div>
                <DeadlineBar a={a} compact />
                {a.status !== "archived" && (
                  <div className="flex gap-1">
                    <Button variant="ghost" className="h-8 px-2" onClick={() => setEditor({ editing: a })} icon={<Pencil className="size-3.5" aria-hidden="true" />} aria-label={`Edit ${a.title}`} />
                    {a.status === "draft" && (
                      <Button variant="ghost" className="h-8 px-2.5" onClick={async () => { await academicApi.setCourseworkStatus(a.id, "publish"); list.reload(); }} icon={<Send className="size-3.5" aria-hidden="true" />}>Publish</Button>
                    )}
                    <Button variant="danger" className="h-8 px-2" onClick={async () => { await academicApi.setCourseworkStatus(a.id, "archive"); list.reload(); }} icon={<Archive className="size-3.5" aria-hidden="true" />} aria-label={`Archive ${a.title}`} />
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  );
}

export function ManageCoursework({ id, role }: { id: string | null; role: Role }) {
  return id ? <Review key={id} id={id} /> : <Overview role={role} />;
}
