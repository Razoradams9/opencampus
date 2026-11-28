import { Archive, Building2, Megaphone, Pencil, Plus, Send } from "lucide-react";
import { useMemo, useState } from "react";
import { FormError } from "../components/auth/FormControls";
import { Empty, LoadError, Loading } from "../components/ui/DataState";
import { Button, Select, StatusChip, TextArea, TextInput } from "../components/ui/Form";
import { SectionHeading } from "../components/ui/SectionHeading";
import { SubjectMark } from "../components/ui/SubjectMark";
import { ApiError } from "../lib/api";
import { academicApi } from "../lib/academic/api";
import { formatDateTime, fromLocalInput, toLocalInput } from "../lib/academic/deadlines";
import { toneFor } from "../lib/academic/format";
import { loadMySubjects } from "../lib/academic/mySubjects";
import type { Announcement, AnnouncementInput, Audience, Course, MySubject, Priority } from "../lib/academic/types";
import type { ActiveInstitution } from "../lib/auth/types";
import { useApi } from "../lib/useApi";

const PRIORITY: Record<Priority, { label: string; className: string; bar: string }> = {
  urgent: { label: "Urgent", className: "bg-danger-soft text-danger", bar: "var(--oc-danger)" },
  important: { label: "Important", className: "bg-pending-soft text-pending", bar: "var(--oc-subject-amber)" },
  normal: { label: "Notice", className: "bg-sunken text-ink-muted", bar: "var(--oc-line-strong)" },
};

function AudienceLabel({ a }: { a: Announcement }) {
  if (a.audience === "institution")
    return (
      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-accent">
        <Building2 className="size-3.5" aria-hidden="true" /> Institution-wide
      </span>
    );
  if (a.audience === "course" && a.course) return <span className="text-xs font-medium text-ink-muted">Course · {a.course.code}</span>;
  if (a.subject)
    return (
      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-ink-muted">
        <SubjectMark tone={toneFor(a.subject.code)} className="size-2.5" />
        {a.subject.code} · {a.subject.name}
        {a.audience === "subject_students" && <span className="text-ink-subtle">(students)</span>}
      </span>
    );
  return null;
}

function Item({ a, featured = false }: { a: Announcement; featured?: boolean }) {
  const p = PRIORITY[a.priority];
  return (
    <li className={`oc-reveal relative border-b border-line px-5 py-5 last:border-b-0 sm:px-6 ${a.expired ? "opacity-70" : ""}`}>
      <span className="absolute inset-y-4 left-0 w-1 rounded-r-full" style={{ background: p.bar }} aria-hidden="true" />
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className={`rounded-full px-2 py-0.5 text-[0.6875rem] font-semibold ${p.className}`}>{p.label}</span>
        <AudienceLabel a={a} />
        {a.expired && <span className="text-[0.6875rem] font-semibold text-ink-subtle uppercase">Expired</span>}
      </div>
      <h3 className={`mt-2 font-display leading-snug font-medium ${featured ? "text-2xl" : "text-xl"}`}>{a.title}</h3>
      <p className="mt-1.5 max-w-prose text-[0.9375rem] leading-relaxed whitespace-pre-wrap text-ink-muted">{a.body}</p>
      <p className="mt-2 font-mono text-[0.6875rem] text-ink-subtle">
        {a.created_by.full_name}
        {a.published_at && <> · <time dateTime={a.published_at}>{formatDateTime(a.published_at)}</time></>}
        {a.expires_at && !a.expired && <> · until {formatDateTime(a.expires_at)}</>}
      </p>
    </li>
  );
}

function Feed() {
  const [showExpired, setShowExpired] = useState(false);
  const feed = useApi((signal) => academicApi.announcements(showExpired, signal), [showExpired]);
  const pinned = feed.status === "ready" ? feed.data.filter((a) => a.priority !== "normal" && !a.expired) : [];
  const rest = feed.status === "ready" ? feed.data.filter((a) => !pinned.includes(a)) : [];
  return (
    <div className="space-y-8">
      <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-ink-muted">
        <input type="checkbox" checked={showExpired} onChange={(e) => setShowExpired(e.target.checked)} className="size-4 accent-(--oc-accent)" />
        Show expired announcements
      </label>
      {feed.status === "loading" && <div className="oc-panel"><Loading label="Loading announcements…" /></div>}
      {feed.status === "error" && <div className="oc-panel"><LoadError error={feed.error} onRetry={feed.reload} /></div>}
      {feed.status === "ready" && feed.data.length === 0 && (
        <div className="oc-panel"><Empty title="No announcements">Announcements for your institution, courses and subjects appear here.</Empty></div>
      )}
      {pinned.length > 0 && (
        <section aria-labelledby="ann-pinned">
          <SectionHeading id="ann-pinned" title="Needs attention" accent="var(--oc-danger)" meta={pinned.length} />
          <ul className="oc-panel">{pinned.map((a) => <Item key={a.id} a={a} featured />)}</ul>
        </section>
      )}
      {rest.length > 0 && (
        <section aria-labelledby="ann-latest">
          <SectionHeading id="ann-latest" title="Latest" accent="var(--oc-subject-violet)" meta={rest.length} />
          <ul className="oc-panel">{rest.map((a) => <Item key={a.id} a={a} />)}</ul>
        </section>
      )}
    </div>
  );
}

/** Audience options the caller may use: the backend enforces the same rules. */
function audienceOptions(role: ActiveInstitution["role"], subjects: MySubject[], courses: Course[]) {
  const options: { value: string; label: string }[] = [];
  if (role === "college_admin") {
    options.push({ value: "institution|", label: "Whole institution" });
    for (const c of courses.filter((c) => c.status === "active")) options.push({ value: `course|${c.id}`, label: `Course · ${c.code} ${c.name}` });
  }
  for (const s of subjects) {
    options.push({ value: `subject|${s.subject.id}`, label: `${s.subject.code} ${s.subject.name} · students and teachers` });
    options.push({ value: `subject_students|${s.subject.id}`, label: `${s.subject.code} ${s.subject.name} · students only` });
  }
  return options;
}

function targetOf(a: Announcement): string {
  return a.audience === "institution" ? "institution|" : a.audience === "course" ? `course|${a.course?.id}` : `${a.audience}|${a.subject?.id}`;
}

function Composer({ role, editing, onDone }: { role: ActiveInstitution["role"]; editing: Announcement | null; onDone: (changed: boolean) => void }) {
  const subjects = useApi((signal) => loadMySubjects(role, signal), [role]);
  const courses = useApi((signal) => (role === "college_admin" ? academicApi.courses(signal) : Promise.resolve([] as Course[])), [role]);
  const options = useMemo(
    () => audienceOptions(role, subjects.status === "ready" ? subjects.data : [], courses.status === "ready" ? courses.data : []),
    [role, subjects, courses],
  );
  const [title, setTitle] = useState(editing?.title ?? "");
  const [body, setBody] = useState(editing?.body ?? "");
  const [priority, setPriority] = useState<Priority>(editing?.priority ?? "normal");
  const [target, setTarget] = useState(editing ? targetOf(editing) : "");
  const [expires, setExpires] = useState(toLocalInput(editing?.expires_at ?? null));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"draft" | "publish" | null>(null);
  const chosen = target || options[0]?.value || "";

  const save = async (publish: boolean) => {
    setError(null);
    setBusy(publish ? "publish" : "draft");
    const [audience, id] = chosen.split("|") as [Audience, string];
    const input: AnnouncementInput = {
      title,
      body,
      priority,
      audience,
      course_id: audience === "course" ? id : null,
      subject_id: audience === "subject" || audience === "subject_students" ? id : null,
      expires_at: expires ? fromLocalInput(expires) : null,
    };
    try {
      const saved = editing ? await academicApi.updateAnnouncement(editing.id, input) : await academicApi.createAnnouncement(input);
      if (publish) await academicApi.setAnnouncementStatus(saved.id, "publish");
      onDone(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save");
      setBusy(null);
    }
  };

  if (subjects.status === "loading" || courses.status === "loading") return <Loading label="Loading audiences…" />;
  if (options.length === 0) return <Empty title="No audience available">You can announce to subjects you are assigned to teach.</Empty>;

  return (
    <form onSubmit={(e) => { e.preventDefault(); void save(false); }} className="oc-reveal space-y-4 border-b border-line bg-sunken/60 px-5 py-5 sm:px-6" aria-label={editing ? "Edit announcement" : "New announcement"}>
      <p className="oc-eyebrow">{editing ? "Edit draft" : "New announcement"}</p>
      <TextInput id="ann-title" label="Title" required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} />
      <TextArea id="ann-body" label="Message" required rows={5} value={body} onChange={(e) => setBody(e.target.value)} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Select id="ann-audience" label="Audience" value={chosen} onChange={(e) => setTarget(e.target.value)}>
          {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </Select>
        <TextInput id="ann-expires" label="Expires (optional)" type="datetime-local" value={expires} onChange={(e) => setExpires(e.target.value)} />
      </div>
      <fieldset>
        <legend className="text-sm font-medium">Priority</legend>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {(Object.keys(PRIORITY) as Priority[]).map((p) => (
            <label key={p} className={`inline-flex cursor-pointer items-center rounded-full px-3 py-1.5 text-sm font-medium ring-1 has-focus-visible:outline-2 has-focus-visible:outline-accent ${priority === p ? `${PRIORITY[p].className} ring-transparent` : "bg-surface text-ink-muted ring-line-strong"}`}>
              <input type="radio" name="ann-priority" value={p} checked={priority === p} onChange={() => setPriority(p)} className="sr-only" />
              {PRIORITY[p].label}
            </label>
          ))}
        </div>
      </fieldset>
      <FormError message={error} />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" busy={busy === "draft"} disabled={busy !== null}>Save draft</Button>
        <Button variant="primary" busy={busy === "publish"} disabled={busy !== null} onClick={() => void save(true)} icon={<Send className="size-4" aria-hidden="true" />}>Publish</Button>
        <Button variant="ghost" onClick={() => onDone(false)} disabled={busy !== null}>Cancel</Button>
      </div>
    </form>
  );
}

function Manage({ role }: { role: ActiveInstitution["role"] }) {
  const list = useApi((signal) => academicApi.managedAnnouncements(signal), []);
  const [editor, setEditor] = useState<{ editing: Announcement | null } | null>(null);
  const act = async (id: string, action: "publish" | "archive") => {
    await academicApi.setAnnouncementStatus(id, action);
    list.reload();
  };
  return (
    <section aria-labelledby="ann-manage">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <SectionHeading id="ann-manage" title="Your announcements" accent="var(--oc-accent)" className="mb-0" />
        {!editor && <Button variant="primary" onClick={() => setEditor({ editing: null })} icon={<Plus className="size-4" aria-hidden="true" />}>New announcement</Button>}
      </div>
      <div className="oc-panel">
        {editor && <Composer key={editor.editing?.id ?? "new"} role={role} editing={editor.editing} onDone={(changed) => { setEditor(null); if (changed) list.reload(); }} />}
        {list.status === "loading" && <Loading label="Loading…" />}
        {list.status === "error" && <LoadError error={list.error} onRetry={list.reload} />}
        {list.status === "ready" && list.data.length === 0 && !editor && <Empty title="Nothing drafted yet">Drafts stay private until published.</Empty>}
        <ul>
          {list.status === "ready" &&
            list.data.map((a) => (
              <li key={a.id} className="flex flex-col gap-2 border-b border-line px-5 py-4 last:border-b-0 sm:flex-row sm:items-center sm:gap-4 sm:px-6">
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2"><StatusChip status={a.status} /><span className={`rounded-full px-2 py-0.5 text-[0.6875rem] font-semibold ${PRIORITY[a.priority].className}`}>{PRIORITY[a.priority].label}</span><AudienceLabel a={a} /></p>
                  <p className="mt-1 font-display text-lg font-medium">{a.title}</p>
                </div>
                {a.status !== "archived" && (
                  <div className="flex gap-1">
                    {a.status === "draft" && (
                      <>
                        <Button variant="ghost" className="h-8 px-2" onClick={() => setEditor({ editing: a })} icon={<Pencil className="size-3.5" aria-hidden="true" />} aria-label={`Edit ${a.title}`} />
                        <Button variant="ghost" className="h-8 px-2.5" onClick={() => act(a.id, "publish")} icon={<Send className="size-3.5" aria-hidden="true" />}>Publish</Button>
                      </>
                    )}
                    <Button variant="danger" className="h-8 px-2" onClick={() => act(a.id, "archive")} icon={<Archive className="size-3.5" aria-hidden="true" />} aria-label={`Archive ${a.title}`} />
                  </div>
                )}
              </li>
            ))}
        </ul>
      </div>
    </section>
  );
}

/** Academic announcements: a targeted feed for everyone; authoring for faculty and admins. */
export function AnnouncementsPage({ institution }: { institution: ActiveInstitution }) {
  const canAuthor = institution.role !== "student";
  const [tab, setTab] = useState<"feed" | "manage">("feed");
  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex items-start gap-4">
          <Megaphone className="mt-1 size-7 shrink-0 text-subject-amber" aria-hidden="true" />
          <div>
            <p className="oc-eyebrow">{institution.name}</p>
            <h1 className="font-display text-[2.25rem] leading-none font-medium tracking-tight sm:text-[2.75rem]">Announcements</h1>
          </div>
        </div>
        {canAuthor && (
          <div role="tablist" aria-label="View" className="flex rounded-xl bg-surface p-1 shadow-e1">
            {(["feed", "manage"] as const).map((t) => (
              <button key={t} role="tab" aria-selected={tab === t} type="button" onClick={() => setTab(t)} className={`rounded-lg px-3.5 py-1.5 text-sm font-medium transition-colors ${tab === t ? "bg-accent-soft text-accent" : "text-ink-muted hover:text-ink"}`}>
                {t === "feed" ? "Feed" : "Manage"}
              </button>
            ))}
          </div>
        )}
      </header>
      {tab === "manage" && canAuthor ? <Manage role={institution.role} /> : <Feed />}
    </div>
  );
}
