import { useEffect, useState } from "react";

/** The current time, refreshed at the start of every minute, so time-based
 * states (current class, countdowns, now-line) update while the page is open. */
export function useNow(): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    let interval: number | undefined;
    const timeout = window.setTimeout(() => {
      setNow(new Date());
      interval = window.setInterval(() => setNow(new Date()), 60_000);
    }, 60_000 - (Date.now() % 60_000));
    return () => {
      window.clearTimeout(timeout);
      window.clearInterval(interval);
    };
  }, []);
  return now;
}
