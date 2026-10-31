import { useState } from "react";
import { cn } from "../../lib/utils";
import AnalyticsPanel from "./revenue-analytics/AnalyticsPanel";
import RisksPanel from "./risk-analysis/RisksPanel";
import CopilotPanel from "./copilot/CopilotPanel";
import SummariesPanel from "./financial-summaries/SummariesPanel";

const TABS = [
  { key: "analytics", label: "Revenue analytics" },
  { key: "risks", label: "Risk intelligence" },
  { key: "copilot", label: "AI Copilot" },
  { key: "summaries", label: "Financial summaries" },
] as const;

type Tab = (typeof TABS)[number]["key"];

export default function FinanceIntelligencePage() {
  const [tab, setTab] = useState<Tab>("analytics");

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Revenue intelligence</h1>
          <p className="text-sm text-cream0">
            MRR/ARR, growth analytics, collection forecasts, deterministic risk
            detection and the AI Finance Copilot.
          </p>
        </div>
        <nav className="flex gap-1 rounded-lg border border-line bg-cream-card p-1">
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm font-medium text-ink-muted hover:bg-sage-faint",
                tab === t.key && "bg-ink text-cream-card hover:bg-ink",
              )}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </div>

      {tab === "analytics" && <AnalyticsPanel />}
      {tab === "risks" && <RisksPanel />}
      {tab === "copilot" && <CopilotPanel />}
      {tab === "summaries" && <SummariesPanel />}
    </div>
  );
}
