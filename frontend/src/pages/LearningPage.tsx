import { Archive, ChevronDown, ExternalLink, Library, Pencil, Plus, Send } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";
import { SubjectRail } from "../components/academic/SubjectRail";
import { FormError } from "../components/auth/FormControls";
import { Empty, LoadError, Loading } from "../components/ui/DataState";
import { Button, StatusChip, TextArea, TextInput } from "../components/ui/Form";
import { ApiError } from "../lib/api";
import { academicApi } from "../lib/academic/api";
import { loadMySubjects } from "../lib/academic/mySubjects";
import { RESOURCE_TYPES, hostOf } from "../lib/academic/resourceTypes";
import type { LearningResource, MySubject, ResourceInput, ResourceType } from "../lib/academic/types";
import type { ActiveInstitution } from "../lib/auth/types";
import { navigate, useLocation } from "../lib/router";
import { useApi } from "../lib/useApi";

function TypeTag({ type }: { type: ResourceType }) {
  const { label, icon: Icon, tone } = RESOURCE_TYPES[type];
  return (
    <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full px-2 py-0.5 text-[0.6875rem] font-semibold" style={{ color: tone, background: `color-mix(in srgb, ${tone} 12%, var(--oc-surface))` }}>
      <Icon className="size-3.5" aria-hidden="true" />
      {label}
    </span>
  );
}

function ResourceRow({ resource, manage, onEdit, onAction }: {
  resource: LearningResource;
  manage: boolean;
  onEdit: () => void;
  onAction: (action: "publish" | "archive") => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const isNote = resource.resource_type === "note";
  const run = async (action: "publish" | "archive") => {
    setBusy(action);
    try {
      await onAction(action);
    } finally {
      setBusy(null);
    }
  };

  return (
    <li className="oc-reveal border-b border-line px-5 py-4 last:border-b-0 sm:px-6">
      <div className="flex flex-wrap items-start gap-x-3 gap-y-2">
        <TypeTag type={resource.resource_type} />
        <div className="min-w-0 flex-1 basis-60">
          {isNote ? (
            <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} className="group flex items-center gap-1.5 text-left">
              <span className="font-display text-lg leading-snug font-medium group-hover:text-accent">{resource.title}</span>
              <ChevronDown className={`size-4 text-ink-subtle transition-transform duration-200 ${open ? "rotate-180" : ""}`} aria-hidden="true" />
            </button>
          ) : resource.external_url ? (
            <a href={resource.external_url} target="_blank" rel="noopener noreferrer" className="group inline-flex items-center gap-1.5">
              <span className="font-display text-lg leading-snug font-medium group-hover:text-accent">{resource.title}</span>
              <ExternalLink className="size-3.5 text-ink-subtle" aria-hidden="true" />
              <span className="sr-only">(opens in a new tab)</span>
            </a>
          ) : (
            <span className="font-display text-lg font-medium">{resource.title}</span>
          )}
          {resource.description && <p className="mt-0.5 text-sm text-ink-muted">{resource.description}</p>}
          <p className="mt-1 font-mono text-[0.6875rem] text-ink-subtle">
            {resource.external_url ? `${hostOf(resource.external_url)} · ` : ""}
            {resource.created_by.full_name}
            {resource.published_at ? ` · ${new Date(resource.published_at).toLocaleDateString(undefined, { day: "numeric", month: "short" })}` : ""}
          </p>
        </div>
        {manage && (
          <div className="flex items-center gap-1">
            <StatusChip status={resource.status} />
            {resource.status !== "archived" && (
              <>
                <Button variant="ghost" className="h-8 px-2" onClick={onEdit} icon={<Pencil className="size-3.5" aria-hidden="true" />} aria-label={`Edit ${resource.title}`} />
                {resource.status === "draft" && (
                  <Button variant="ghost" className="h-8 px-2.5" busy={busy === "publish"} onClick={() => run("publish")} icon={<Send className="size-3.5" aria-hidden="true" />}>
                    Publish
                  </Button>
                )}
                <Button variant="danger" className="h-8 px-2" busy={busy === "archive"} onClick={() => run("archive")} icon={<Archive className="size-3.5" aria-hidden="true" />} aria-label={`Archive ${resource.title}`} />
              </>
            )}
          </div>
        )}
      </div>
      {isNote && open && (
        <div className="oc-reveal mt-3 rounded-xl border-l-4 border-subject-violet bg-lavender px-4 py-3 text-[0.9375rem] leading-relaxed whitespace-pre-wrap">
          {resource.body}
        </div>
      )}
    </li>
  );
}

const EMPTY: ResourceInput = { title: "", description: null, resource_type: "note", topic: null, body: null, external_url: null };

function ResourceEditor({ subject, editing, onDone }: { subject: MySubject; editing: LearningResource | null; onDone: (changed: boolean) => void }) {
  const [form, setForm] = useState<ResourceInput>(
    editing
      ? { title: editing.title, description: editing.description, resource_type: editing.resource_type, topic: editing.topic, body: editing.body, external_url: editing.external_url }
      : EMPTY,
  );
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"draft" | "publish" | null>(null);
  const isNote = form.resource_type === "note";
  const set = <K extends keyof ResourceInput>(key: K, value: ResourceInput[K]) => setForm((f) => ({ ...f, [key]: value }));
  const blank = (v: string | null) => (v && v.trim() ? v : null);

  const save = async (publish: boolean) => {
    setError(null);
    setBusy(publish ? "publish" : "draft");
    const body: ResourceInput = {
      ...form,
      description: blank(form.description),
      topic: blank(form.topic),
      body: isNote ? blank(form.body) : null,
      external_url: isNote ? null : blank(form.external_url),
    };
    try {
      const saved = editing ? await academicApi.updateResource(editing.id, body) : await academicApi.createResource(subject.subject.id, body);
      if (publish && saved.status === "draft") await academicApi.setResourceStatus(saved.id, "publish");
      onDone(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save the resource");
      setBusy(null);
    }
  };

  return (
    <form
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        void save(false);
      }}
      className="oc-reveal space-y-4 border-b border-line bg-sunken/60 px-5 py-5 sm:px-6"
      aria-label={editing ? "Edit resource" : "New resource"}
    >
      <p className="oc-eyebrow">{editing ? "Edit resource" : `New resource · ${subject.subject.code}`}</p>
      <fieldset>
        <legend className="text-sm font-medium">Type</legend>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {(Object.keys(RESOURCE_TYPES) as ResourceType[]).map((t) => {
            const { label, icon: Icon, tone } = RESOURCE_TYPES[t];
            const on = form.resource_type === t;
            return (
              <label key={t} className={`inline-flex cursor-pointer items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium ring-1 transition-colors has-focus-visible:outline-2 has-focus-visible:outline-accent ${on ? "ring-transparent text-white" : "bg-surface ring-line-strong text-ink-muted hover:text-ink"}`} style={on ? { background: tone } : undefined}>
                <input type="radio" name="resource-type" value={t} checked={on} onChange={() => set("resource_type", t)} className="sr-only" />
                <Icon className="size-3.5" aria-hidden="true" />
                {label}
              </label>
            );
          })}
        </div>
      </fieldset>
      <div className="grid gap-4 sm:grid-cols-[2fr_1fr]">
        <TextInput id="res-title" label="Title" required maxLength={200} value={form.title} onChange={(e) => set("title", e.target.value)} />
        <TextInput id="res-topic" label="Topic or section" placeholder="e.g. Week 3" maxLength={120} value={form.topic ?? ""} onChange={(e) => set("topic", e.target.value)} />
      </div>
      {isNote ? (
        <TextArea id="res-body" label="Note" required rows={8} value={form.body ?? ""} onChange={(e) => set("body", e.target.value)} hint="Plain text. Line breaks are kept." />
      ) : (
        <TextInput
          id="res-url"
          label="Link"
          type="url"
          required
          placeholder="https://"
          value={form.external_url ?? ""}
          onChange={(e) => set("external_url", e.target.value)}
          hint={form.resource_type === "link" || form.resource_type === "video" ? undefined : "File uploads are not available yet: link to where the file is hosted."}
        />
      )}
      <TextArea id="res-desc" label="Description (optional)" rows={2} maxLength={4000} value={form.description ?? ""} onChange={(e) => set("description", e.target.value)} />
      <FormError message={error} />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="secondary" busy={busy === "draft"} disabled={busy !== null}>
          {editing && editing.status === "published" ? "Save changes" : "Save draft"}
        </Button>
        {(!editing || editing.status === "draft") && (
          <Button variant="primary" busy={busy === "publish"} disabled={busy !== null} onClick={() => void save(true)} icon={<Send className="size-4" aria-hidden="true" />}>
            Save and publish
          </Button>
        )}
        <Button variant="ghost" onClick={() => onDone(false)} disabled={busy !== null}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

/**
 * Learning resources. Students browse published material for their enrolled
 * subjects; faculty (and admins) also write, publish and archive it.
 */
export function LearningPage({ institution }: { institution: ActiveInstitution }) {
  const manage = institution.role !== "student";
  const { search } = useLocation();
  const subjects = useApi((signal) => loadMySubjects(institution.role, signal), [institution.role]);
  const resources = useApi((signal) => (manage ? academicApi.managedResources(signal) : academicApi.availableResources(signal)), [manage]);
  const [editor, setEditor] = useState<{ editing: LearningResource | null } | null>(null);

  const requested = new URLSearchParams(search).get("subject");
  const list = subjects.status === "ready" ? subjects.data : [];
  const current = list.find((s) => s.subject.id === requested) ?? list[0] ?? null;
  const select = (id: string) => {
    setEditor(null);
    navigate(`/learning?subject=${encodeURIComponent(id)}`, { replace: true });
  };

  const counts = useMemo(() => {
    const map = new Map<string, number>();
    if (resources.status === "ready") for (const r of resources.data) if (r.status !== "archived") map.set(r.subject.id, (map.get(r.subject.id) ?? 0) + 1);
    return map;
  }, [resources]);

  const forSubject = resources.status === "ready" && current ? resources.data.filter((r) => r.subject.id === current.subject.id) : [];
  const groups = useMemo(() => {
    const map = new Map<string, LearningResource[]>();
    for (const r of forSubject) {
      if (!manage && r.status !== "published") continue;
      const key = r.status === "archived" ? "\u0000Archived" : r.topic ?? "General";
      map.set(key, [...(map.get(key) ?? []), r]);
    }
    return [...map].sort(([a], [b]) => (a.startsWith("\u0000") ? 1 : b.startsWith("\u0000") ? -1 : a === "General" ? 1 : b === "General" ? -1 : a.localeCompare(b)));
  }, [forSubject, manage]);

  const act = async (id: string, action: "publish" | "archive") => {
    await academicApi.setResourceStatus(id, action);
    resources.reload();
  };

  return (
    <div className="space-y-6">
      <header className="flex items-start gap-4">
        <Library className="mt-1 size-7 shrink-0 text-subject-violet" aria-hidden="true" />
        <div>
          <p className="oc-eyebrow">{manage ? "Teaching materials" : "Your subjects"}</p>
          <h1 className="font-display text-[2.25rem] leading-none font-medium tracking-tight sm:text-[2.75rem]">Learning</h1>
        </div>
      </header>

      {subjects.status === "loading" && <div className="oc-panel"><Loading label="Loading your subjects…" /></div>}
      {subjects.status === "error" && <div className="oc-panel"><LoadError error={subjects.error} onRetry={subjects.reload} /></div>}
      {subjects.status === "ready" && list.length === 0 && (
        <div className="oc-panel">
          <Empty title={manage ? "No subjects assigned to you" : "No enrolled subjects"}>
            {manage ? "Resources are managed per subject. Ask your administrators to assign you a subject." : "Once you are enrolled in a course, its subjects and materials appear here."}
          </Empty>
        </div>
      )}

      {current && (
        <div className="grid gap-6 lg:grid-cols-[17rem_minmax(0,1fr)] lg:gap-8">
          <SubjectRail subjects={list} selected={current.subject.id} onSelect={select} counts={resources.status === "ready" ? counts : undefined} label="Subjects" />

          <section aria-labelledby="subject-title" className="min-w-0">
            <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="font-mono text-xs text-ink-subtle">
                  {current.subject.code} · {current.course.code} · Semester {current.subject.semester}
                </p>
                <h2 id="subject-title" className="font-display text-[1.75rem] leading-tight font-medium tracking-tight sm:text-[2rem]">
                  {current.subject.name}
                </h2>
              </div>
              {manage && !editor && (
                <Button variant="primary" onClick={() => setEditor({ editing: null })} icon={<Plus className="size-4" aria-hidden="true" />}>
                  New resource
                </Button>
              )}
            </div>

            <div className="oc-panel">
              {editor && (
                <ResourceEditor
                  key={editor.editing?.id ?? "new"}
                  subject={current}
                  editing={editor.editing}
                  onDone={(changed) => {
                    setEditor(null);
                    if (changed) resources.reload();
                  }}
                />
              )}
              {resources.status === "loading" && <Loading label="Loading resources…" />}
              {resources.status === "error" && <LoadError error={resources.error} onRetry={resources.reload} />}
              {resources.status === "ready" && groups.length === 0 && (
                <Empty title="Nothing here yet">{manage ? "Add notes and links for this subject. Drafts stay private until you publish them." : "Your teachers have not published materials for this subject yet."}</Empty>
              )}
              {groups.map(([topic, items]) => (
                <div key={topic}>
                  <p className="oc-eyebrow border-b border-line bg-sunken/50 px-5 py-2 sm:px-6">{topic.replace("\u0000", "")}</p>
                  <ul>
                    {items.map((r) => (
                      <ResourceRow key={r.id} resource={r} manage={manage} onEdit={() => setEditor({ editing: r })} onAction={(a) => act(r.id, a)} />
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
