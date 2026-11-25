import { Menu, Search } from "lucide-react";
import type { ConnectionState } from "../lib/useBackendHealth";
import { BrandMark } from "./BrandMark";
import { ConnectionPill } from "./ConnectionStatus";

interface TopBarProps {
  onMenuClick: () => void;
  menuOpen: boolean;
  connection: ConnectionState;
}

export function TopBar({ onMenuClick, menuOpen, connection }: TopBarProps) {
  return (
    <header className="sticky top-0 z-20 flex h-(--oc-topbar-height) items-center gap-3 border-b border-line bg-canvas/90 px-4 backdrop-blur-sm sm:px-6 lg:px-10">
      <button
        type="button"
        onClick={onMenuClick}
        className="-ml-1.5 rounded-oc p-1.5 text-ink-muted hover:bg-sunken lg:hidden"
        aria-label="Open navigation"
        aria-controls="oc-sidebar"
        aria-expanded={menuOpen}
      >
        <Menu className="size-5" />
      </button>

      <div className="sm:hidden">
        <BrandMark />
      </div>

      {/* Search is laid out now; it is disabled until there is content to search. */}
      <label className="relative hidden max-w-md flex-1 sm:block">
        <span className="sr-only">Search</span>
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-subtle" />
        <input
          type="search"
          disabled
          placeholder="Search — available once content exists"
          className="h-9 w-full cursor-not-allowed rounded-oc border border-line bg-surface pr-3 pl-9 text-sm text-ink placeholder:text-ink-subtle"
        />
      </label>

      <div className="ml-auto">
        <ConnectionPill state={connection} />
      </div>
    </header>
  );
}
