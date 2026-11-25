import type { ReactNode } from "react";
import { BrandMark } from "../BrandMark";
import { CampusIllustration } from "../dashboard/CampusIllustration";

interface AuthLayoutProps {
  eyebrow: string;
  title: string;
  intro: ReactNode;
  children: ReactNode;
  footer: ReactNode;
}

/**
 * Asymmetric split: an architectural panel (wide screens only) beside the
 * form column. Reuses the blueprint grid and campus drawing from M1.
 */
export function AuthLayout({ eyebrow, title, intro, children, footer }: AuthLayoutProps) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <aside className="oc-blueprint relative hidden flex-col justify-between overflow-hidden border-r border-line bg-surface px-10 py-9 lg:flex">
        <BrandMark />
        <div>
          <p className="oc-eyebrow">Open-source academic platform</p>
          <p className="mt-4 max-w-sm font-display text-[2.5rem] leading-[1.08] font-medium tracking-tight">
            Many colleges.
            <br />
            One open campus.
          </p>
          <p className="mt-4 max-w-sm text-sm leading-relaxed text-ink-muted">
            Each institution keeps its own people and records. Your account can belong to more than one.
          </p>
        </div>
        <div className="-mx-4">
          <CampusIllustration className="w-full max-w-md" />
        </div>
        <span className="absolute top-0 right-10 h-16 w-1 bg-signal" aria-hidden="true" />
      </aside>

      <main className="flex flex-col px-5 py-8 sm:px-10 lg:px-16 lg:py-12">
        <div className="lg:hidden">
          <BrandMark />
        </div>
        <div className="my-auto w-full max-w-md py-10 lg:py-0">
          <p className="oc-eyebrow">{eyebrow}</p>
          <h1 className="mt-3 font-display text-4xl leading-tight font-medium tracking-tight">{title}</h1>
          <div className="mt-2 text-[0.9375rem] leading-relaxed text-ink-muted">{intro}</div>
          <div className="mt-8">{children}</div>
          <div className="mt-8 border-t border-line pt-5 text-sm text-ink-muted">{footer}</div>
        </div>
      </main>
    </div>
  );
}
