"use client";

import { useEffect, useRef, useState } from "react";
import { agent, type MetricsResponse } from "./agent-client";

/**
 * Polls the agent's `/metrics` endpoint for live CPU/RAM/GPU usage while the
 * agent is connected. Returns `null` until the first successful sample.
 *
 * Graceful degradation: agents older than 1.8.0 don't have `/metrics` and will
 * 404. After a few consecutive failures we stop polling and stay `null`, so the
 * status bar simply omits the metrics on older agents instead of spamming
 * requests.
 */
export function useMetrics(enabled: boolean, intervalMs = 3000) {
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  // Once the endpoint proves unavailable, don't keep hammering it this session.
  const unavailable = useRef(false);
  const failures = useRef(0);

  useEffect(() => {
    if (!enabled || unavailable.current) {
      setMetrics(null);
      return;
    }
    let cancelled = false;

    const sample = async () => {
      try {
        const m = await agent.metrics();
        if (cancelled) return;
        failures.current = 0;
        setMetrics(m);
      } catch {
        if (cancelled) return;
        failures.current += 1;
        // 3 strikes => treat as an old agent without /metrics; give up quietly.
        if (failures.current >= 3) {
          unavailable.current = true;
          setMetrics(null);
        }
      }
    };

    void sample();
    const id = setInterval(sample, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [enabled, intervalMs]);

  return metrics;
}
