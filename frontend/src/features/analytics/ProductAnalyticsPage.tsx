import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  CheckCircle2,
  Code2,
  DollarSign,
  Download,
  HelpCircle,
  Layers,
  Lightbulb,
  Percent,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  Tag,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../../api/client";
import type {
  AIInsightsResponse,
  CatalogOverview,
  DiscountsSummaryResponse,
  PerformanceTrendsResponse,
  ProductPerformanceList,
  ProductProfitabilityResponse,
  RevenueComparisonResponse,
  TopSubscribedResponse,
  TopVariantsList,
  UnderperformingListResponse,
} from "../../api/types";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import {
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "../../components/ui/table";
import { formatDate, formatMoney } from "../../lib/utils";

type TabKey =
  | "overview"
  | "performance"
  | "subscriptions"
  | "revenue"
  | "discounts"
  | "underperforming"
  | "ai-insights"
  | "openapi";

export default function ProductAnalyticsPage() {
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [trendInterval, setTrendInterval] = useState<"month" | "week">("month");
  const [focusArea, setFocusArea] = useState<string>("all");
  const queryClient = useQueryClient();

  // Queries
  const { data: overview, isLoading: loadingOverview, refetch: refetchOverview } = useQuery({
    queryKey: ["analytics", "overview"],
    queryFn: () => api<CatalogOverview>("/analytics/overview"),
  });

  const { data: performance, isLoading: loadingPerf } = useQuery({
    queryKey: ["analytics", "performance"],
    queryFn: () => api<ProductPerformanceList>("/analytics/performance"),
  });

  const { data: topSubscribed, isLoading: loadingTopSub } = useQuery({
    queryKey: ["analytics", "top-subscribed"],
    queryFn: () => api<TopSubscribedResponse>("/analytics/top-subscribed"),
  });

  const { data: topVariants, isLoading: loadingVariants } = useQuery({
    queryKey: ["analytics", "top-variants"],
    queryFn: () => api<TopVariantsList>("/analytics/top-variants"),
  });

  const { data: revenueComp, isLoading: loadingRevenue } = useQuery({
    queryKey: ["analytics", "revenue-comparison"],
    queryFn: () => api<RevenueComparisonResponse>("/analytics/revenue-comparison"),
  });

  const { data: discounts, isLoading: loadingDiscounts } = useQuery({
    queryKey: ["analytics", "discounts"],
    queryFn: () => api<DiscountsSummaryResponse>("/analytics/discounts"),
  });

  const { data: underperforming, isLoading: loadingUnderperforming } = useQuery({
    queryKey: ["analytics", "underperforming"],
    queryFn: () => api<UnderperformingListResponse>("/analytics/underperforming"),
  });

  const { data: profitability, isLoading: loadingProfitability } = useQuery({
    queryKey: ["analytics", "profitability"],
    queryFn: () => api<ProductProfitabilityResponse>("/analytics/profitability"),
  });

  const { data: trends, isLoading: loadingTrends } = useQuery({
    queryKey: ["analytics", "trends", trendInterval],
    queryFn: () => api<PerformanceTrendsResponse>(`/analytics/trends?interval=${trendInterval}`),
  });

  const { data: aiInsights, isLoading: loadingInsights, refetch: refetchInsights } = useQuery({
    queryKey: ["analytics", "ai-insights", focusArea],
    queryFn: () =>
      api<AIInsightsResponse>(
        focusArea === "all" ? "/analytics/ai-insights" : `/analytics/ai-insights?focus_area=${focusArea}`
      ),
  });

  // Seed demo mutation
  const seedMutation = useMutation({
    mutationFn: () => api<{ status: string; message: string }>("/analytics/seed-demo-data", { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["analytics"] });
    },
  });

  const tabs: Array<{ key: TabKey; label: string; icon: any; badge?: number | string }> = [
    { key: "overview", label: "Overview", icon: BarChart3 },
    { key: "performance", label: "Performance & Profitability", icon: DollarSign },
    { key: "subscriptions", label: "Most Subscribed & Variants", icon: Layers },
    { key: "revenue", label: "Revenue Comparisons & Trends", icon: TrendingUp },
    {
      key: "discounts",
      label: "Discounts & Availability",
      icon: Tag,
      badge: discounts?.active_discounts,
    },
    {
      key: "underperforming",
      label: "Underperforming",
      icon: AlertTriangle,
      badge: underperforming?.total_underperforming,
    },
    { key: "ai-insights", label: "AI Product Insights", icon: Sparkles },
    { key: "openapi", label: "OpenAPI API", icon: Code2 },
  ];

  const getTierColor = (tier: string) => {
    switch (tier) {
      case "High Margin (>50%)":
        return "bg-emerald-100 text-emerald-800 border-emerald-300";
      case "Healthy (20-50%)":
        return "bg-blue-100 text-blue-800 border-blue-300";
      case "Low Margin (0-20%)":
        return "bg-amber-100 text-amber-800 border-amber-300";
      default:
        return "bg-red-100 text-red-800 border-red-300";
    }
  };

  const getSeverityBadge = (severity: "HIGH" | "MEDIUM" | "LOW") => {
    switch (severity) {
      case "HIGH":
        return <Badge variant="destructive">Critical Risk</Badge>;
      case "MEDIUM":
        return <Badge variant="warning">Moderate Concern</Badge>;
      case "LOW":
        return <Badge variant="secondary">Watchlist</Badge>;
    }
  };

  const getAvailabilityBadge = (status: string) => {
    switch (status) {
      case "Available":
        return <Badge variant="success">Available</Badge>;
      case "Near Capacity":
        return <Badge variant="warning">Near Capacity (&gt;80%)</Badge>;
      case "Exhausted":
        return <Badge variant="destructive">Exhausted (100%)</Badge>;
      case "Expired":
        return <Badge variant="outline">Expired</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Product Performance Analytics
            </h1>
            <Badge variant="default" className="bg-indigo-600 text-white">
              OpenAPI Enabled
            </Badge>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Real-time subscriber rankings, variant popularity, unit margins, discount availability, and AI insights.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => seedMutation.mutate()}
            disabled={seedMutation.isPending}
            className="flex items-center gap-1.5"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${seedMutation.isPending ? "animate-spin" : ""}`} />
            {seedMutation.isPending ? "Seeding Demo Data..." : "Seed / Reset Demo Data"}
          </Button>

          <Button
            size="sm"
            onClick={() => setActiveTab("ai-insights")}
            className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white"
          >
            <Sparkles className="h-3.5 w-3.5" />
            AI Product Insights
          </Button>
        </div>
      </div>

      {/* Top Level KPIs Banner */}
      {overview && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-medium uppercase text-slate-500">
                Catalog Health
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold text-slate-900">
                  {overview.catalog_health_score}
                </span>
                <span className="text-xs text-slate-400">/ 100</span>
                <Badge
                  variant={overview.catalog_health_score >= 80 ? "success" : "warning"}
                  className="ml-auto"
                >
                  Grade {overview.health_grade}
                </Badge>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-medium uppercase text-slate-500">
                Products & Variants
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-slate-900">{overview.total_products}</div>
              <p className="mt-1 text-xs text-slate-500">
                {overview.active_products} active • {overview.total_variants} variants
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-medium uppercase text-slate-500">
                Active Subscriptions
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-indigo-600">
                {overview.active_subscriptions_count}
              </div>
              <p className="mt-1 text-xs text-slate-500">
                {overview.total_units_sold} units billed
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-medium uppercase text-slate-500">
                Invoiced Revenue
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-slate-900">
                {formatMoney(overview.total_invoiced_revenue)}
              </div>
              <p className="mt-1 text-xs text-slate-500">
                Collected: {formatMoney(overview.total_collected_revenue)}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-medium uppercase text-slate-500">
                Blended Margin
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-1.5 text-2xl font-bold text-emerald-600">
                {overview.blended_profit_margin_pct}%
                <ArrowUpRight className="h-4 w-4" />
              </div>
              <p className="mt-1 text-xs text-slate-500">
                Net Profit: {formatMoney(overview.total_net_profit)}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-medium uppercase text-slate-500">
                Active Discounts
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-slate-900">
                {overview.active_discounts_count}
              </div>
              <p className="mt-1 text-xs text-slate-500">
                {discounts?.total_redemptions ?? 0} redemptions tracked
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Sub Navigation Tabs */}
      <div className="border-b border-slate-200">
        <nav className="-mb-px flex flex-wrap gap-2">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-2 border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? "border-indigo-600 text-indigo-600"
                    : "border-transparent text-slate-600 hover:border-slate-300 hover:text-slate-900"
                }`}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
                {tab.badge !== undefined && Number(tab.badge) > 0 && (
                  <span
                    className={`ml-1 rounded-full px-1.5 py-0.2 text-[10px] font-bold ${
                      tab.key === "underperforming"
                        ? "bg-red-100 text-red-700"
                        : "bg-slate-100 text-slate-700"
                    }`}
                  >
                    {tab.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* TAB 1: OVERVIEW */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            {/* Catalog Revenue Summary */}
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="text-base font-semibold text-slate-900">
                  Revenue vs Cost Breakdown
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={
                        revenueComp?.products.map((p) => ({
                          name: p.product_name,
                          Invoiced: p.invoiced_revenue,
                          Cost: p.total_cost,
                          Profit: p.net_profit,
                        })) ?? []
                      }
                      margin={{ top: 10, right: 10, left: 10, bottom: 25 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="name" angle={-15} textAnchor="end" height={45} tick={{ fontSize: 11 }} />
                      <YAxis tickFormatter={(val) => `₹${val / 1000}k`} tick={{ fontSize: 11 }} />
                      <Tooltip formatter={(value) => formatMoney(Number(value))} />
                      <Legend />
                      <Bar dataKey="Invoiced" fill="#4f46e5" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="Cost" fill="#94a3b8" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="Profit" fill="#10b981" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* Quick Action & Health Card */}
            <Card className="flex flex-col justify-between">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base font-semibold text-slate-900">
                    AI Strategic Summary
                  </CardTitle>
                  <Sparkles className="h-4 w-4 text-indigo-600" />
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="rounded-lg bg-indigo-50 p-3.5 text-xs text-indigo-950">
                  <p className="font-semibold text-indigo-900">Executive Catalog Note</p>
                  <p className="mt-1 leading-relaxed">
                    {aiInsights?.executive_summary ||
                      "Catalog margin is healthy. Review underperforming products and replenish near-capacity discounts."}
                  </p>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs font-medium text-slate-600">
                    <span>Critical Underperforming Items:</span>
                    <span className="font-bold text-red-600">
                      {underperforming?.high_severity_count ?? 0} High Priority
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs font-medium text-slate-600">
                    <span>Discount ROI Multiplier:</span>
                    <span className="font-bold text-emerald-600">
                      {discounts?.overall_roi_multiplier ?? 0}x Gross Return
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs font-medium text-slate-600">
                    <span>Top Plan:</span>
                    <span className="font-medium text-slate-900">
                      {topSubscribed?.plans[0]?.plan_name ?? "ERP Growth"}
                    </span>
                  </div>
                </div>

                <Button
                  onClick={() => setActiveTab("ai-insights")}
                  className="w-full bg-slate-900 hover:bg-slate-800 text-xs"
                >
                  View Complete AI Strategic Insights
                </Button>
              </CardContent>
            </Card>
          </div>

          {/* Quick Highlight Grids */}
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            {/* Top Subscribed Products Preview */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-sm font-semibold text-slate-900">
                  Top Subscribed Products
                </CardTitle>
                <Button variant="ghost" size="sm" onClick={() => setActiveTab("subscriptions")}>
                  View all <ArrowRight className="ml-1 h-3.5 w-3.5" />
                </Button>
              </CardHeader>
              <CardContent>
                <Table>
                  <THead>
                    <TR>
                      <TH>Rank</TH>
                      <TH>Product</TH>
                      <TH className="text-right">Subscribers</TH>
                      <TH className="text-right">MRR</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {topSubscribed?.products.slice(0, 4).map((p) => (
                      <TR key={p.product_id}>
                        <TD className="font-bold text-slate-500">#{p.rank}</TD>
                        <TD className="font-medium text-slate-900">{p.product_name}</TD>
                        <TD className="text-right font-semibold text-indigo-600">
                          {p.active_subscribers}
                        </TD>
                        <TD className="text-right">{formatMoney(p.mrr_contribution)}</TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              </CardContent>
            </Card>

            {/* Underperforming Products Warning Preview */}
            <Card className="border-amber-200 bg-amber-50/20">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="flex items-center gap-2 text-sm font-semibold text-amber-900">
                  <AlertTriangle className="h-4 w-4 text-amber-600" />
                  Underperforming Products Detected
                </CardTitle>
                <Button variant="ghost" size="sm" onClick={() => setActiveTab("underperforming")}>
                  Review All ({underperforming?.total_underperforming ?? 0})
                </Button>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {underperforming?.items.slice(0, 3).map((item) => (
                    <div
                      key={item.product_id}
                      className="flex items-start justify-between rounded-md border border-amber-200 bg-white p-2.5 text-xs shadow-sm"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-slate-900">{item.product_name}</span>
                          {getSeverityBadge(item.severity)}
                        </div>
                        <p className="mt-1 text-slate-500">{item.issues[0]}</p>
                      </div>
                      <div className="text-right">
                        <span className="font-medium text-slate-700">Margin: {item.margin_pct}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* TAB 2: PERFORMANCE & PROFITABILITY */}
      {activeTab === "performance" && (
        <div className="space-y-6">
          <Card>
            <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <CardTitle className="text-base font-semibold text-slate-900">
                  Product Profitability Analysis using Sales & Cost Prices
                </CardTitle>
                <p className="text-xs text-slate-500">
                  Calculates unit margins (sales_price − cost_price), gross margin %, total revenue, delivery cost, and net profit.
                </p>
              </div>

              {profitability && (
                <div className="flex items-center gap-4 text-xs">
                  <div>
                    <span className="text-slate-500">Total Profit: </span>
                    <span className="font-bold text-emerald-600">
                      {formatMoney(profitability.total_catalog_profit)}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500">Catalog Margin: </span>
                    <span className="font-bold text-indigo-600">
                      {profitability.catalog_margin_pct}%
                    </span>
                  </div>
                </div>
              )}
            </CardHeader>

            <CardContent>
              <div className="overflow-x-auto">
                <Table>
                  <THead>
                    <TR>
                      <TH>Product Name</TH>
                      <TH>Type</TH>
                      <TH className="text-right">Sales Price</TH>
                      <TH className="text-right">Cost Price</TH>
                      <TH className="text-right">Unit Margin</TH>
                      <TH className="text-right">Margin %</TH>
                      <TH className="text-right">Units Sold</TH>
                      <TH className="text-right">Total Revenue</TH>
                      <TH className="text-right">Total Cost</TH>
                      <TH className="text-right">Net Profit</TH>
                      <TH>Profitability Tier</TH>
                      <TH>Status</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {performance?.items.map((p) => (
                      <TR key={p.product_id} className={p.is_underperforming ? "bg-amber-50/30" : ""}>
                        <TD className="font-semibold text-slate-900">
                          <div className="flex items-center gap-1.5">
                            {p.product_name}
                            {p.is_underperforming && (
                              <AlertCircle className="h-3.5 w-3.5 text-amber-500" />
                            )}
                          </div>
                        </TD>
                        <TD className="text-xs text-slate-500 capitalize">{p.product_type}</TD>
                        <TD className="text-right font-medium">{formatMoney(p.sales_price)}</TD>
                        <TD className="text-right text-slate-500">{formatMoney(p.cost_price)}</TD>
                        <TD
                          className={`text-right font-semibold ${
                            p.unit_margin >= 0 ? "text-slate-900" : "text-red-600"
                          }`}
                        >
                          {formatMoney(p.unit_margin)}
                        </TD>
                        <TD
                          className={`text-right font-bold ${
                            p.margin_pct >= 20 ? "text-emerald-600" : p.margin_pct >= 0 ? "text-amber-600" : "text-red-600"
                          }`}
                        >
                          {p.margin_pct}%
                        </TD>
                        <TD className="text-right">{p.total_units_sold}</TD>
                        <TD className="text-right font-medium">{formatMoney(p.total_revenue)}</TD>
                        <TD className="text-right text-slate-500">{formatMoney(p.total_cost)}</TD>
                        <TD
                          className={`text-right font-bold ${
                            p.net_profit >= 0 ? "text-emerald-700" : "text-red-700"
                          }`}
                        >
                          {formatMoney(p.net_profit)}
                        </TD>
                        <TD>
                          <span
                            className={`inline-block rounded-full border px-2 py-0.5 text-[10px] font-bold ${getTierColor(
                              p.profitability_tier
                            )}`}
                          >
                            {p.profitability_tier}
                          </span>
                        </TD>
                        <TD>
                          <Badge variant={p.status === "active" ? "success" : "secondary"}>
                            {p.status}
                          </Badge>
                        </TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* TAB 3: MOST SUBSCRIBED & VARIANTS */}
      {activeTab === "subscriptions" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Most Subscribed Products */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base font-semibold text-slate-900">
                  Most Subscribed Products
                </CardTitle>
                <p className="text-xs text-slate-500">
                  Ranked by active customer subscriber base and monthly recurring revenue contribution.
                </p>
              </CardHeader>
              <CardContent>
                <Table>
                  <THead>
                    <TR>
                      <TH>Rank</TH>
                      <TH>Product Name</TH>
                      <TH className="text-right">Price</TH>
                      <TH className="text-right">Subscribers</TH>
                      <TH className="text-right">MRR</TH>
                      <TH className="text-right">Total Revenue</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {topSubscribed?.products.map((p) => (
                      <TR key={p.product_id}>
                        <TD className="font-bold text-slate-500">#{p.rank}</TD>
                        <TD className="font-semibold text-slate-900">{p.product_name}</TD>
                        <TD className="text-right text-slate-600">{formatMoney(p.sales_price)}</TD>
                        <TD className="text-right font-bold text-indigo-600">
                          {p.active_subscribers}
                        </TD>
                        <TD className="text-right font-medium text-emerald-600">
                          {formatMoney(p.mrr_contribution)}
                        </TD>
                        <TD className="text-right">{formatMoney(p.total_revenue)}</TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              </CardContent>
            </Card>

            {/* Most Subscribed Plans */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base font-semibold text-slate-900">
                  Most Subscribed Plans
                </CardTitle>
                <p className="text-xs text-slate-500">
                  Subscription plan tier performance normalized by frequency to MRR & ARR equivalents.
                </p>
              </CardHeader>
              <CardContent>
                <Table>
                  <THead>
                    <TR>
                      <TH>Rank</TH>
                      <TH>Plan Name</TH>
                      <TH>Frequency</TH>
                      <TH className="text-right">Price</TH>
                      <TH className="text-right">Subs</TH>
                      <TH className="text-right">MRR Equiv</TH>
                      <TH className="text-right">ARR Equiv</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {topSubscribed?.plans.map((pl) => (
                      <TR key={pl.plan_id}>
                        <TD className="font-bold text-slate-500">#{pl.rank}</TD>
                        <TD>
                          <div className="font-semibold text-slate-900">{pl.plan_name}</div>
                          <div className="text-[10px] text-slate-400">{pl.product_name}</div>
                        </TD>
                        <TD className="capitalize text-xs text-slate-600">{pl.billing_frequency}</TD>
                        <TD className="text-right text-slate-600">{formatMoney(pl.price)}</TD>
                        <TD className="text-right font-bold text-indigo-600">{pl.active_subscribers}</TD>
                        <TD className="text-right font-medium text-emerald-600">
                          {formatMoney(pl.mrr_equivalent)}
                        </TD>
                        <TD className="text-right text-slate-500">{formatMoney(pl.arr_equivalent)}</TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              </CardContent>
            </Card>
          </div>

          {/* Most Popular Product Variants */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold text-slate-900">
                Most Popular Product Variants
              </CardTitle>
              <p className="text-xs text-slate-500">
                Variant SKU breakdown tracking sales price, cost price, margins, and revenue share.
              </p>
            </CardHeader>
            <CardContent>
              <Table>
                <THead>
                  <TR>
                    <TH>Rank</TH>
                    <TH>Variant Name</TH>
                    <TH>SKU</TH>
                    <TH>Parent Product</TH>
                    <TH className="text-right">Sales Price</TH>
                    <TH className="text-right">Cost Price</TH>
                    <TH className="text-right">Unit Margin</TH>
                    <TH className="text-right">Margin %</TH>
                    <TH className="text-right">Units Sold</TH>
                    <TH className="text-right">Revenue Share</TH>
                  </TR>
                </THead>
                <TBody>
                  {topVariants?.items.map((v) => (
                    <TR key={v.variant_id}>
                      <TD className="font-bold text-slate-500">#{v.rank}</TD>
                      <TD className="font-semibold text-slate-900">{v.variant_name}</TD>
                      <TD className="font-mono text-xs text-slate-500">{v.sku || "-"}</TD>
                      <TD className="text-xs text-slate-600">{v.product_name}</TD>
                      <TD className="text-right">{formatMoney(v.sales_price)}</TD>
                      <TD className="text-right text-slate-500">{formatMoney(v.cost_price)}</TD>
                      <TD className="text-right font-medium text-slate-900">{formatMoney(v.unit_margin)}</TD>
                      <TD className="text-right font-bold text-emerald-600">{v.margin_pct}%</TD>
                      <TD className="text-right font-bold text-indigo-600">{v.units_sold}</TD>
                      <TD className="text-right font-medium text-slate-700">{v.revenue_share_pct}%</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      )}

      {/* TAB 4: REVENUE COMPARISONS & TRENDS */}
      {activeTab === "revenue" && (
        <div className="space-y-6">
          {/* Trends Chart */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-base font-semibold text-slate-900">
                  Product & Plan Performance Trends
                </CardTitle>
                <p className="text-xs text-slate-500">
                  Historical revenue trajectory, estimated delivery costs, and net profit over time.
                </p>
              </div>
              <div className="flex items-center gap-1">
                <Button
                  size="sm"
                  variant={trendInterval === "month" ? "default" : "outline"}
                  onClick={() => setTrendInterval("month")}
                  className="text-xs"
                >
                  Monthly
                </Button>
                <Button
                  size="sm"
                  variant={trendInterval === "week" ? "default" : "outline"}
                  onClick={() => setTrendInterval("week")}
                  className="text-xs"
                >
                  Weekly
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={trends?.points ?? []} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorRev" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#4f46e5" stopOpacity={0.0} />
                      </linearGradient>
                      <linearGradient id="colorProfit" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="period" />
                    <YAxis tickFormatter={(val) => `₹${val / 1000}k`} />
                    <Tooltip formatter={(value) => formatMoney(Number(value))} />
                    <Legend />
                    <Area
                      type="monotone"
                      dataKey="total_revenue"
                      name="Invoiced Revenue"
                      stroke="#4f46e5"
                      strokeWidth={2}
                      fillOpacity={1}
                      fill="url(#colorRev)"
                    />
                    <Area
                      type="monotone"
                      dataKey="net_profit"
                      name="Net Profit"
                      stroke="#10b981"
                      strokeWidth={2}
                      fillOpacity={1}
                      fill="url(#colorProfit)"
                    />
                    <Line
                      type="monotone"
                      dataKey="total_cost"
                      name="Estimated Cost"
                      stroke="#94a3b8"
                      strokeDasharray="4 4"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          {/* Cross Product Revenue Comparisons */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base font-semibold text-slate-900">
                  Product Revenue Share & Comparison
                </CardTitle>
                <p className="text-xs text-slate-500">
                  Comparative contribution across all active and legacy products.
                </p>
              </CardHeader>
              <CardContent>
                <Table>
                  <THead>
                    <TR>
                      <TH>Product</TH>
                      <TH className="text-right">Invoiced</TH>
                      <TH className="text-right">Profit</TH>
                      <TH className="text-right">Share %</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {revenueComp?.products.map((p) => (
                      <TR key={p.product_id}>
                        <TD className="font-semibold text-slate-900">{p.product_name}</TD>
                        <TD className="text-right font-medium">{formatMoney(p.invoiced_revenue)}</TD>
                        <TD className="text-right font-medium text-emerald-600">
                          {formatMoney(p.net_profit)}
                        </TD>
                        <TD className="text-right">
                          <div className="flex items-center justify-end gap-2">
                            <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100">
                              <div
                                className="h-full bg-indigo-600"
                                style={{ width: `${Math.min(100, p.revenue_share_pct)}%` }}
                              />
                            </div>
                            <span className="font-bold text-slate-700">{p.revenue_share_pct}%</span>
                          </div>
                        </TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base font-semibold text-slate-900">
                  Subscription Plan Revenue Comparison
                </CardTitle>
                <p className="text-xs text-slate-500">
                  Subscription portfolio comparison by recurring revenue and subscriber volume.
                </p>
              </CardHeader>
              <CardContent>
                <Table>
                  <THead>
                    <TR>
                      <TH>Plan</TH>
                      <TH>Frequency</TH>
                      <TH className="text-right">Subscribers</TH>
                      <TH className="text-right">Total Rev</TH>
                      <TH className="text-right">Share %</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {revenueComp?.plans.map((pl) => (
                      <TR key={pl.plan_id}>
                        <TD className="font-semibold text-slate-900">{pl.plan_name}</TD>
                        <TD className="capitalize text-xs text-slate-500">{pl.billing_frequency}</TD>
                        <TD className="text-right font-bold text-indigo-600">
                          {pl.active_subscribers}
                        </TD>
                        <TD className="text-right font-medium">{formatMoney(pl.total_revenue)}</TD>
                        <TD className="text-right font-bold text-slate-700">
                          {pl.revenue_share_pct}%
                        </TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* TAB 5: DISCOUNTS & AVAILABILITY TRACKING */}
      {activeTab === "discounts" && (
        <div className="space-y-6">
          {/* Summary KPIs */}
          {discounts && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs uppercase text-slate-500">Total Discounts</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-slate-900">
                    {discounts.total_discounts}
                  </div>
                  <p className="mt-1 text-xs text-slate-500">{discounts.active_discounts} currently active</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs uppercase text-slate-500">Total Redemptions</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-indigo-600">
                    {discounts.total_redemptions}
                  </div>
                  <p className="mt-1 text-xs text-slate-500">Across active & past campaigns</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs uppercase text-slate-500">Customer Savings Given</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-amber-600">
                    {formatMoney(discounts.total_savings_given)}
                  </div>
                  <p className="mt-1 text-xs text-slate-500">Total promotional value</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs uppercase text-slate-500">Discount ROI Multiplier</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-1.5 text-2xl font-bold text-emerald-600">
                    {discounts.overall_roi_multiplier}x
                    <ArrowUpRight className="h-4 w-4" />
                  </div>
                  <p className="mt-1 text-xs text-slate-500">
                    Gross revenue: {formatMoney(discounts.total_revenue_from_discounted_orders)}
                  </p>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Discount Tracking Table */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold text-slate-900">
                Track Discount Usage & Remaining Availability
              </CardTitle>
              <p className="text-xs text-slate-500">
                Monitors redemption capacity, remaining uses, expiration countdown, and financial ROI effectiveness.
              </p>
            </CardHeader>
            <CardContent>
              <Table>
                <THead>
                  <TR>
                    <TH>Code / Name</TH>
                    <TH>Type & Value</TH>
                    <TH>Usage Progress</TH>
                    <TH className="text-right">Remaining</TH>
                    <TH>Status</TH>
                    <TH className="text-right">Savings Given</TH>
                    <TH className="text-right">Revenue Generated</TH>
                    <TH>ROI Rating</TH>
                    <TH>Expiry</TH>
                  </TR>
                </THead>
                <TBody>
                  {discounts?.items.map((d) => (
                    <TR key={d.discount_id}>
                      <TD>
                        <div className="font-mono font-bold text-indigo-700">{d.code}</div>
                        <div className="text-xs text-slate-500">{d.name}</div>
                      </TD>
                      <TD className="text-xs font-medium text-slate-700">
                        {d.discount_type === "percentage" ? `${d.discount_value}%` : formatMoney(d.discount_value)}
                      </TD>
                      <TD className="min-w-[140px]">
                        <div className="space-y-1">
                          <div className="flex items-center justify-between text-[11px] text-slate-600">
                            <span>
                              {d.usage_count} / {d.usage_limit ?? "∞"}
                            </span>
                            <span>{d.usage_pct !== null ? `${d.usage_pct}%` : "Unlimited"}</span>
                          </div>
                          <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                            <div
                              className={`h-full ${
                                d.is_exhausted
                                  ? "bg-red-500"
                                  : (d.usage_pct ?? 0) >= 80
                                  ? "bg-amber-500"
                                  : "bg-emerald-500"
                              }`}
                              style={{ width: `${Math.min(100, d.usage_pct ?? 15)}%` }}
                            />
                          </div>
                        </div>
                      </TD>
                      <TD className="text-right font-semibold">
                        {d.remaining_uses !== null ? (
                          <span className={d.remaining_uses <= 5 ? "text-red-600 font-bold" : "text-slate-900"}>
                            {d.remaining_uses} left
                          </span>
                        ) : (
                          <span className="text-slate-400">Unlimited</span>
                        )}
                      </TD>
                      <TD>{getAvailabilityBadge(d.availability_status)}</TD>
                      <TD className="text-right font-medium text-amber-700">
                        {formatMoney(d.total_discount_amount_given)}
                      </TD>
                      <TD className="text-right font-semibold text-slate-900">
                        {formatMoney(d.revenue_generated_with_discount)}
                      </TD>
                      <TD>
                        <Badge
                          variant={
                            d.effectiveness_rating === "High ROI"
                              ? "success"
                              : d.effectiveness_rating === "Healthy"
                              ? "default"
                              : d.effectiveness_rating === "Margin Erosion"
                              ? "destructive"
                              : "secondary"
                          }
                        >
                          {d.effectiveness_rating}
                        </Badge>
                      </TD>
                      <TD className="text-xs text-slate-500">
                        {d.expiry_date ? (
                          <div>
                            <div>{formatDate(d.expiry_date)}</div>
                            <div className="text-[10px] text-slate-400">
                              {d.days_remaining !== null
                                ? d.days_remaining >= 0
                                  ? `${d.days_remaining} days left`
                                  : "Expired"
                                : "-"}
                            </div>
                          </div>
                        ) : (
                          "No Expiry"
                        )}
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      )}

      {/* TAB 6: UNDERPERFORMING PRODUCTS */}
      {activeTab === "underperforming" && (
        <div className="space-y-6">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-900">
                Identify Underperforming Products & Actionable Remedies
              </h2>
              <p className="text-xs text-slate-500">
                Automated detection flags products with negative unit margins, zero adoption, or thin profitability.
              </p>
            </div>
            {underperforming && (
              <div className="flex gap-2">
                <Badge variant="destructive">{underperforming.high_severity_count} Critical Risks</Badge>
                <Badge variant="warning">{underperforming.medium_severity_count} Warnings</Badge>
                <Badge variant="secondary">{underperforming.low_severity_count} Low Watchlist</Badge>
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 gap-4">
            {underperforming?.items.map((item) => (
              <Card
                key={item.product_id}
                className={`border-l-4 ${
                  item.severity === "HIGH"
                    ? "border-l-red-500 bg-red-50/10"
                    : item.severity === "MEDIUM"
                    ? "border-l-amber-500 bg-amber-50/10"
                    : "border-l-blue-500"
                }`}
              >
                <CardHeader className="pb-3">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-center gap-3">
                      <CardTitle className="text-base font-bold text-slate-900">
                        {item.product_name}
                      </CardTitle>
                      <span className="text-xs text-slate-400 capitalize">({item.product_type})</span>
                      {getSeverityBadge(item.severity)}
                    </div>
                    <div className="flex items-center gap-4 text-xs font-semibold">
                      <span>Sales Price: {formatMoney(item.sales_price)}</span>
                      <span className="text-slate-500">Cost: {formatMoney(item.cost_price)}</span>
                      <span className={item.margin_pct < 0 ? "text-red-600 font-bold" : "text-amber-600"}>
                        Margin: {item.margin_pct}%
                      </span>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  {/* Issues */}
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wider text-slate-500">
                      Identified Root Causes & Breaches:
                    </p>
                    <ul className="mt-1.5 space-y-1">
                      {item.issues.map((issue, idx) => (
                        <li key={idx} className="flex items-center gap-2 text-xs font-medium text-red-700">
                          <AlertCircle className="h-3.5 w-3.5 flex-shrink-0 text-red-500" />
                          {issue}
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Recommendations */}
                  <div className="rounded-md bg-slate-50 p-3">
                    <p className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-slate-700">
                      <Lightbulb className="h-3.5 w-3.5 text-amber-500" />
                      Recommended Strategic Action:
                    </p>
                    <ul className="mt-1.5 space-y-1">
                      {item.recommendations.map((rec, idx) => (
                        <li key={idx} className="flex items-start gap-2 text-xs text-slate-700">
                          <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-emerald-600" />
                          {rec}
                        </li>
                      ))}
                    </ul>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* TAB 7: AI PRODUCT INSIGHTS */}
      {activeTab === "ai-insights" && (
        <div className="space-y-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-indigo-600" />
                <h2 className="text-lg font-bold text-slate-900">AI Product & Margin Insights</h2>
              </div>
              <p className="text-xs text-slate-500">
                Generated by {aiInsights?.generated_by || "BrightLoop Analytics AI Engine"} • Updated{" "}
                {aiInsights ? formatDate(aiInsights.generated_at) : "Just now"}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <select
                value={focusArea}
                onChange={(e) => setFocusArea(e.target.value)}
                className="rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 shadow-sm"
              >
                <option value="all">Focus: All Catalog Areas</option>
                <option value="pricing">Focus: Pricing & Margins</option>
                <option value="discounts">Focus: Discounts & Promotions</option>
                <option value="retention">Focus: Retention & Subscriptions</option>
              </select>

              <Button
                size="sm"
                onClick={() => refetchInsights()}
                disabled={loadingInsights}
                className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${loadingInsights ? "animate-spin" : ""}`} />
                {loadingInsights ? "Analyzing..." : "Regenerate AI Insights"}
              </Button>
            </div>
          </div>

          {aiInsights && (
            <div className="space-y-6">
              {/* Executive Summary Card */}
              <Card className="border-indigo-100 bg-gradient-to-br from-indigo-50/50 to-white">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-bold uppercase tracking-wider text-indigo-900">
                      Executive Summary & Catalog Health
                    </CardTitle>
                    <Badge variant="default" className="bg-indigo-600">
                      Health Score: {aiInsights.catalog_health_score}/100 ({aiInsights.health_grade})
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <p className="text-sm font-medium leading-relaxed text-slate-800">
                    {aiInsights.executive_summary}
                  </p>

                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <div className="rounded-lg border border-slate-200 bg-white p-3.5">
                      <p className="text-xs font-bold text-slate-900">Top Performers & Growth Drivers</p>
                      <p className="mt-1 text-xs leading-relaxed text-slate-600">
                        {aiInsights.top_performers_summary}
                      </p>
                    </div>

                    <div className="rounded-lg border border-slate-200 bg-white p-3.5">
                      <p className="text-xs font-bold text-slate-900">Discount Effectiveness Analysis</p>
                      <p className="mt-1 text-xs leading-relaxed text-slate-600">
                        {aiInsights.discount_effectiveness_analysis}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Critical Warnings */}
              {aiInsights.underperforming_warnings.length > 0 && (
                <Card className="border-red-200 bg-red-50/20">
                  <CardHeader className="pb-2">
                    <CardTitle className="flex items-center gap-2 text-sm font-bold text-red-900">
                      <ShieldAlert className="h-4 w-4 text-red-600" />
                      Priority Risk Warnings
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-2">
                      {aiInsights.underperforming_warnings.map((w, idx) => (
                        <li key={idx} className="flex items-center gap-2 text-xs font-semibold text-red-800">
                          <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
                          {w}
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              )}

              {/* Prioritized Actionable Recommendations */}
              <div>
                <h3 className="text-base font-bold text-slate-900">Prioritized Strategic Recommendations</h3>
                <p className="text-xs text-slate-500">
                  AI-recommended tactical actions categorized by business impact and urgency.
                </p>

                <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                  {aiInsights.actionable_recommendations.map((rec) => (
                    <Card key={rec.id} className="flex flex-col justify-between">
                      <CardHeader className="pb-2">
                        <div className="flex items-center justify-between">
                          <Badge
                            variant={
                              rec.priority === "critical"
                                ? "destructive"
                                : rec.priority === "high"
                                ? "warning"
                                : "secondary"
                            }
                          >
                            {rec.priority.toUpperCase()} PRIORITY
                          </Badge>
                          <span className="text-[11px] font-bold uppercase text-slate-400">
                            {rec.category}
                          </span>
                        </div>
                        <CardTitle className="mt-2 text-sm font-bold text-slate-900">
                          {rec.title}
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        <p className="text-xs leading-relaxed text-slate-600">{rec.description}</p>
                        <div className="rounded bg-emerald-50 px-2.5 py-1.5 text-xs font-semibold text-emerald-800">
                          Expected Impact: {rec.expected_impact}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 8: OPENAPI & AI COPILOT INTEGRATION */}
      {activeTab === "openapi" && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base font-bold text-slate-900">
                    OpenAPI Integration & AI Finance Copilot Replacement
                  </CardTitle>
                  <p className="mt-1 text-xs text-slate-500">
                    Standardized REST OpenAPI 3.0 specification enabling external AI agents and automation tools to consume product analytics directly without manual copilot prompts.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <a
                    href="http://localhost:8000/docs#/Product%20Analytics%20%26%20AI%20Insights"
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50"
                  >
                    Interactive Swagger Docs <ArrowUpRight className="h-3.5 w-3.5" />
                  </a>
                  <a
                    href="http://localhost:8000/openapi.json"
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 rounded-md bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-slate-800"
                  >
                    Raw OpenAPI JSON <Code2 className="h-3.5 w-3.5" />
                  </a>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Endpoint Table */}
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Available Machine-Readable Endpoints</h3>
                <Table className="mt-3">
                  <THead>
                    <TR>
                      <TH>Method</TH>
                      <TH>Endpoint Path</TH>
                      <TH>Feature Description</TH>
                      <TH>JSON Schema Output</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {[
                      { method: "GET", path: "/api/v1/analytics/overview", desc: "Catalog KPIs, margins, active subs & health score", schema: "CatalogOverviewOut" },
                      { method: "GET", path: "/api/v1/analytics/performance", desc: "Per-product unit margins, ROI %, revenue & units sold", schema: "ProductPerformanceListOut" },
                      { method: "GET", path: "/api/v1/analytics/top-subscribed", desc: "Most subscribed products and plans with MRR/ARR", schema: "TopSubscribedOut" },
                      { method: "GET", path: "/api/v1/analytics/top-variants", desc: "Ranked popular product variants & revenue share", schema: "TopVariantsListOut" },
                      { method: "GET", path: "/api/v1/analytics/revenue-comparison", desc: "Cross-product and plan revenue comparison", schema: "RevenueComparisonOut" },
                      { method: "GET", path: "/api/v1/analytics/discounts", desc: "Discount redemption tracking, availability & ROI", schema: "DiscountsSummaryOut" },
                      { method: "GET", path: "/api/v1/analytics/underperforming", desc: "Underperforming products with root causes & remedies", schema: "UnderperformingListOut" },
                      { method: "GET", path: "/api/v1/analytics/profitability", desc: "Sales vs cost price profitability breakdown", schema: "ProductProfitabilityOut" },
                      { method: "GET", path: "/api/v1/analytics/trends", desc: "Historical monthly / weekly performance trends", schema: "PerformanceTrendsOut" },
                      { method: "POST", path: "/api/v1/analytics/ai-insights", desc: "Generate AI strategic insights & recommendations", schema: "AIInsightsOut" },
                    ].map((ep, idx) => (
                      <TR key={idx}>
                        <TD>
                          <span
                            className={`rounded px-1.5 py-0.5 font-mono text-[11px] font-bold ${
                              ep.method === "POST" ? "bg-amber-100 text-amber-800" : "bg-blue-100 text-blue-800"
                            }`}
                          >
                            {ep.method}
                          </span>
                        </TD>
                        <TD className="font-mono text-xs font-semibold text-slate-800">{ep.path}</TD>
                        <TD className="text-xs text-slate-600">{ep.desc}</TD>
                        <TD className="font-mono text-xs text-indigo-600">{ep.schema}</TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              </div>

              {/* Sample cURL snippet */}
              <div className="rounded-lg bg-slate-900 p-4 text-slate-100">
                <div className="flex items-center justify-between text-xs text-slate-400">
                  <span>Sample cURL Request for AI Agents</span>
                  <span className="font-mono">bash</span>
                </div>
                <pre className="mt-2 overflow-x-auto text-xs text-emerald-400">
{`# Fetch high-level product analytics and AI insights via OpenAPI
curl -X GET "http://localhost:8000/api/v1/analytics/overview" \\
     -H "Accept: application/json"

# Trigger AI strategic recommendations
curl -X POST "http://localhost:8000/api/v1/analytics/ai-insights" \\
     -H "Content-Type: application/json" \\
     -d '{"focus_area": "pricing", "include_recommendations": true}'`}
                </pre>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
