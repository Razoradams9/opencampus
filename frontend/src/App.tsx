import { AppShell } from "./layouts/AppShell";
import { Dashboard } from "./pages/Dashboard";
import { useBackendHealth } from "./lib/useBackendHealth";

export default function App() {
  const health = useBackendHealth();

  return (
    <AppShell health={health}>
      <Dashboard health={health} />
    </AppShell>
  );
}
