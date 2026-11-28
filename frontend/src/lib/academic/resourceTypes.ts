import { CirclePlay, FileText, FileType, Link2, Presentation, StickyNote, type LucideIcon } from "lucide-react";
import type { ResourceType } from "./types";

/** Each resource type has its own glyph, label and hue (never colour alone). */
export const RESOURCE_TYPES: Record<ResourceType, { label: string; icon: LucideIcon; tone: string }> = {
  note: { label: "Note", icon: StickyNote, tone: "var(--oc-subject-violet)" },
  link: { label: "Link", icon: Link2, tone: "var(--oc-subject-cobalt)" },
  video: { label: "Video", icon: CirclePlay, tone: "var(--oc-subject-rose)" },
  pdf: { label: "PDF", icon: FileText, tone: "var(--oc-subject-amber)" },
  document: { label: "Document", icon: FileType, tone: "var(--oc-subject-teal)" },
  presentation: { label: "Slides", icon: Presentation, tone: "var(--oc-subject-amber)" },
};

export function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
