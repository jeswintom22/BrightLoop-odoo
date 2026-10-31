import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, ApiError, qs } from "../../../api/client";
import type {
  RiskExplanation,
  RiskList,
  RiskRecord,
} from "../../../api/types";
import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { formatMoney } from "../../../lib/utils";

const SEVERITY_VARIANT: Record<string, "destructive" | "warning" | "secondary"> = {
  high: "destructive",
  medium: "warning",
  low: "secondary",
};

const CATEGORY_LABEL: Record<string, string> = {
  high_value_overdue: "High-value overdue",
  multiple_overdue: "Multiple overdue",
  repeated_late_payments: "Repeated late payments",
  renewal_unpaid: "Renewal with unpaid invoices",
  large_exposure: "Large exposure",
};

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xs font-medium uppercase tracking-wide text-cream0">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-bold">{value}</p>
      </CardContent>
    </Card>
  );
}

export default function RisksPanel() {
  const [severity, setSeverity] = useState("");
  const [category, setCategory] = useState("");
  const [explained, setExplained] = useState<Record<number, RiskExplanation>>({});

  const risks = useQuery({
    queryKey: ["fi-risks", severity, category],
    queryFn: () =>
      api<RiskList>(`/finance-intelligence/risks${qs({ severity, category })}`),
  });

  const explain = useMutation({
    mutationFn: (risk: RiskRecord) =>
      api<RiskExplanation>("/finance-intelligence/risks/explain", {
        method: "POST",
        body: JSON.stringify({ risk }),
      }),
    onSuccess: (data, risk) => {
      setExplained((m) => ({ ...m, [risk.risk_index]: data }));
    },
  });

  const data = risks.data;

  return (
    <div className="space-y-6">
      {data && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Kpi label="Open risks" value={String(data.summary.total_risks)} />
          <Kpi label="Customers at risk" value={String(data.summary.customers_at_risk)} />
          <Kpi
            label="Outstanding at risk"
            value={formatMoney(data.summary.total_outstanding_at_risk)}
          />
          <Kpi
            label="High severity"
            value={String(data.summary.by_severity.high ?? 0)}
          />
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        <select
          className="rounded-md border border-line px-2 py-1.5 text-sm"
          value={severity}
          onChange={(e) => setSeverity(e.target.value)}
        >
          <option value="">All severities</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <select
          className="rounded-md border border-line px-2 py-1.5 text-sm"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          <option value="">All categories</option>
          {Object.entries(CATEGORY_LABEL).map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
        <span className="self-center text-xs text-cream0">
          Detection is deterministic backend logic — AI only explains records.
        </span>
      </div>

      {risks.isLoading && <p className="text-cream0">Loading…</p>}
      {risks.isError && <p className="text-danger">Failed to load risks.</p>}

      {data && data.risks.length === 0 && (
        <Card>
          <CardContent className="py-10 text-center text-cream0">
            No risks detected for the current filters.
          </CardContent>
        </Card>
      )}

      {data &&
        data.risks.map((r) => {
          const exp = explained[r.risk_index];
          const pending =
            explain.isPending && explain.variables?.risk_index === r.risk_index;
          return (
            <Card key={`${r.risk_category}-${r.risk_index}`}>
              <CardHeader>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <CardTitle className="flex items-center gap-2">
                    <Badge variant={SEVERITY_VARIANT[r.severity] ?? "secondary"}>
                      {r.severity}
                    </Badge>
                    <span>{CATEGORY_LABEL[r.risk_category] ?? r.risk_category}</span>
                  </CardTitle>
                  <span className="text-lg font-bold">
                    {formatMoney(r.outstanding_amount)}
                  </span>
                </div>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="grid gap-2 md:grid-cols-2">
                  <p>
                    <span className="text-cream0">Customer: </span>
                    {r.customer_name ?? r.customer_id ?? "—"}
                  </p>
                  <p>
                    <span className="text-cream0">Invoice: </span>
                    {r.invoice_number ?? "—"}
                    {r.days_overdue > 0 && (
                      <span className="ml-2 text-cream0">
                        {r.days_overdue} day(s) overdue
                      </span>
                    )}
                  </p>
                </div>
                <p className="text-ink">{r.detection_reason}</p>
                <p className="text-cream0">
                  <span className="font-medium">Recommended: </span>
                  {r.recommended_action}
                </p>

                {exp ? (
                  <div className="rounded-md border border-line bg-cream p-3">
                    <p className="mb-1 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-cream0">
                      AI explanation
                      <Badge variant="outline">{exp.provider}</Badge>
                      {exp.model && <Badge variant="outline">{exp.model}</Badge>}
                    </p>
                    <p className="whitespace-pre-wrap text-ink">
                      {exp.explanation}
                    </p>
                  </div>
                ) : (
                  <div>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={pending}
                      onClick={() => explain.mutate(r)}
                    >
                      {pending ? "Explaining…" : "AI explanation"}
                    </Button>
                    {explain.isError &&
                      explain.variables?.risk_index === r.risk_index && (
                        <p className="mt-2 text-xs text-danger">
                          {(explain.error as ApiError).message ??
                            "Failed to generate explanation."}
                        </p>
                      )}
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
    </div>
  );
}
