import { Menu, Search, X } from "lucide-react";
import { useEffect, useRef, useState, type RefObject } from "react";
import type { CampusUpdate } from "../data/types";
import type { ConnectionState } from "../lib/useBackendHealth";
import { BrandMark } from "./BrandMark";
import { ConnectionPill } from "./ConnectionStatus";
import { NotificationsMenu } from "./NotificationsMenu";
import { useMediaQuery } from "../lib/useMediaQuery";

interface TopBarProps {
  onMenuClick: () => void;
  menuOpen: boolean;
  connection: ConnectionState;
  query: string;
  onQueryChange: (value: string) => void;
  notifications: CampusUpdate[];
  today: Date;
}

function SearchField({
  query,
  onQueryChange,
  inputRef,
  autoFocus = false,
}: {
  query: string;
  onQueryChange: (value: string) => void;
  inputRef: RefObject<HTMLInputElement | null>;
  autoFocus?: boolean;
}) {
  return (
    <form role="search" onSubmit={(e) => e.preventDefault()} className="relative w-full">
      <label htmlFor="dashboard-search" className="sr-only">
        Search this dashboard
      </label>
      <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-subtle" aria-hidden="true" />
      <input
        ref={inputRef}
        id="dashboard-search"
        autoFocus={autoFocus}
        type="search"
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Escape") onQueryChange("");
        }}
        placeholder="Search subjects, classes, tasks…"
        autoComplete="off"
        className="h-10 w-full rounded-xl border border-white/70 bg-surface pr-12 pl-9 text-sm text-ink shadow-e1 transition-colors placeholder:text-ink-subtle hover:border-line-strong focus:border-accent focus:outline-none [&::-webkit-search-cancel-button]:hidden"
      />
      {query ? (
        <button
          type="button"
          onClick={() => {
            onQueryChange("");
            inputRef.current?.focus();
          }}
          className="absolute top-1/2 right-2 grid size-6 -translate-y-1/2 place-items-center rounded-oc text-ink-subtle hover:bg-sunken hover:text-ink"
          aria-label="Clear search"
        >
          <X className="size-3.5" />
        </button>
      ) : (
        <kbd className="pointer-events-none absolute top-1/2 right-2.5 hidden -translate-y-1/2 border border-line px-1.5 font-mono text-[0.6875rem] text-ink-subtle sm:block">
          /
        </kbd>
      )}
    </form>
  );
}

export function TopBar({ onMenuClick, menuOpen, connection, query, onQueryChange, notifications, today }: TopBarProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [mobileSearch, setMobileSearch] = useState(false);
  const isWide = useMediaQuery("(min-width: 640px)");
  const searchVisible = mobileSearch || query !== "";
  // One search field, placed inline on wide screens and in a second row on phones.
  // On phones the row only mounts when opened, so it takes focus on mount.
  const searchField = (
    <SearchField query={query} onQueryChange={onQueryChange} inputRef={inputRef} autoFocus={!isWide} />
  );

  // "/" focuses search, unless the user is already typing somewhere.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (event.key !== "/" || target.closest("input, textarea, [contenteditable]")) return;
      event.preventDefault();
      // Focus synchronously when the field is mounted so the next keystroke lands in it;
      // otherwise (closed mobile row) wait for it to render.
      // The mobile row auto-focuses when it mounts.
      if (inputRef.current) inputRef.current.focus();
      else setMobileSearch(true);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <header className="sticky top-0 z-20 border-b border-white/50 bg-canvas/80 backdrop-blur-md">
      <div className="flex h-(--oc-topbar-height) items-center gap-2 px-4 sm:gap-3 sm:px-6 lg:px-10">
        <button
          type="button"
          onClick={onMenuClick}
          className="-ml-1.5 hidden rounded-oc p-1.5 text-ink-muted hover:bg-sunken sm:block lg:hidden"
          aria-label="Open navigation"
          aria-controls="oc-sidebar"
          aria-expanded={menuOpen}
        >
          <Menu className="size-5" />
        </button>

        <div className="sm:hidden">
          <BrandMark />
        </div>

        {isWide && <div className="max-w-md flex-1">{searchField}</div>}

        <div className="ml-auto flex items-center gap-1 sm:gap-2">
          {/* API status is a developer aid; students do not need it. */}
          {import.meta.env.DEV && (
            <span className="hidden md:inline-flex">
              <ConnectionPill state={connection} />
            </span>
          )}
          <button
            type="button"
            onClick={() => {
              const next = !searchVisible;
              setMobileSearch(next);
              if (!next) onQueryChange("");
            }}
            aria-label="Search"
            aria-expanded={searchVisible}
            className={`grid size-10 place-items-center rounded-oc text-ink-muted hover:bg-sunken sm:hidden ${
              searchVisible ? "bg-sunken text-ink" : ""
            }`}
          >
            <Search className="size-[1.125rem]" aria-hidden="true" />
          </button>
          <NotificationsMenu items={notifications} today={today} />
        </div>
      </div>

      {/* Mobile search row */}
      {!isWide && searchVisible && <div className="border-t border-line px-4 py-2">{searchField}</div>}
    </header>
  );
}
