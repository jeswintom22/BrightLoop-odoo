import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, ApiError, qs } from "../../../api/client";
import type { FinancialSummary, Page } from "../../../api/types";
import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import { formatDate } from "../../../lib/utils";

export default function SummariesPanel() {
  const queryClient = useQueryClient();
  const [kind, setKind] = useState<"month" | "custom">("month");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<string | null>(null);

  const summaries = useQuery({
    queryKey: ["fi-summaries", page],
    queryFn: () =>
      api<Page<FinancialSummary>>(
        `/finance-intelligence/summaries${qs({ page, page_size: 10 })}`,
      ),
  });

  const generate = useMutation({
    mutationFn: () =>
      api<FinancialSummary>("/finance-intelligence/summaries/generate", {
        method: "POST",
        body: JSON.stringify({
          period_kind: kind,
          ...(kind === "custom" && start ? { period_start: start } : {}),
          ...(kind === "custom" && end ? { period_end: end } : {}),
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fi-summaries"] });
      setPage(1);
    },
  });

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Generate financial summary</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <Label>Period</Label>
              <select
                className="block rounded-md border border-line px-2 py-1.5 text-sm"
                value={kind}
                onChange={(e) => setKind(e.target.value as "month" | "custom")}
              >
                <option value="month">Current month</option>
                <option value="custom">Custom range</option>
              </select>
            </div>
            {kind === "custom" && (
              <>
                <div>
                  <Label htmlFor="sum-from">From</Label>
                  <Input
                    id="sum-from"
                    type="date"
                    value={start}
                    onChange={(e) => setStart(e.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor="sum-to">To</Label>
                  <Input
                    id="sum-to"
                    type="date"
                    value={end}
                    onChange={(e) => setEnd(e.target.value)}
                  />
                </div>
              </>
            )}
            <Button
              onClick={() => generate.mutate()}
              disabled={generate.isPending}
            >
              {generate.isPending ? "Generating…" : "Generate summary"}
            </Button>
          </div>
          <p className="text-xs text-cream0">
            An existing report for the same period is returned instead of
            regenerated. Metrics are computed deterministically; the provider
            badge shows whether text came from an LLM or the grounded template.
          </p>
          {generate.isError && (
            <p className="text-sm text-danger">
              {(generate.error as ApiError).message ?? "Generation failed."}
            </p>
          )}
        </CardContent>
      </Card>

      {summaries.isLoading && <p className="text-cream0">Loading…</p>}
      {summaries.data && summaries.data.items.length === 0 && (
        <Card>
          <CardContent className="py-10 text-center text-cream0">
            No summaries generated yet.
          </CardContent>
        </Card>
      )}

      {summaries.data?.items.map((s) => {
        const open = expanded === s.id;
        const cur = (s.metrics?.current ?? {}) as Record<string, number>;
        return (
          <Card key={s.id}>
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <CardTitle>
                  {s.period_kind === "month" ? "Monthly" : "Custom"} summary —{" "}
                  {formatDate(s.period_start)} → {formatDate(s.period_end)}
                </CardTitle>
                <div className="flex items-center gap-1.5">
                  <Badge variant="outline">{s.provider}</Badge>
                  {s.model && <Badge variant="outline">{s.model}</Badge>}
                  <Badge variant="secondary">
                    {formatDate(s.created_at)}
                  </Badge>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap gap-4 text-sm text-ink-muted">
                <span>
                  Collected{" "}
                  <strong>₹{Number(cur.collected ?? 0).toLocaleString("en-IN")}</strong>
                </span>
                <span>
                  Invoiced{" "}
                  <strong>₹{Number(cur.invoiced ?? 0).toLocaleString("en-IN")}</strong>
                </span>
                <span>
                  Overdue{" "}
                  <strong>{cur.overdue_count ?? 0} invoice(s)</strong>
                </span>
              </div>
              <button
                type="button"
                className="text-sm font-medium text-ink underline underline-offset-2 hover:text-ink"
                onClick={() => setExpanded(open ? null : s.id)}
              >
                {open ? "Hide report" : "View report"}
              </button>
              {open && (
                <pre className="whitespace-pre-wrap rounded-md border border-line bg-cream p-4 text-sm text-ink">
                  {s.summary_text}
                </pre>
              )}
            </CardContent>
          </Card>
        );
      })}

      {summaries.data && summaries.data.total > summaries.data.page_size && (
        <div className="flex items-center gap-3 text-sm">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Previous
          </Button>
          <span className="text-cream0">
            Page {page} of {Math.ceil(summaries.data.total / summaries.data.page_size)}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page * summaries.data.page_size >= summaries.data.total}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
