import { useMemo, useState } from "react";
import { createDemoDashboard } from "./data/demo";
import { AppShell } from "./layouts/AppShell";
import { useBackendHealth } from "./lib/useBackendHealth";
import { Dashboard } from "./pages/Dashboard";

export default function App() {
  const health = useBackendHealth();
  const today = useMemo(() => new Date(), []);
  const data = useMemo(() => createDemoDashboard(today), [today]);
  const [query, setQuery] = useState("");

  return (
    <AppShell health={health} data={data} today={today} query={query} onQueryChange={setQuery}>
      <Dashboard data={data} today={today} health={health} query={query} onClearQuery={() => setQuery("")} />
    </AppShell>
  );
}
