import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { getToken, me, type User as AuthUser } from "./lib/auth";
import AppShell from "./components/AppShell";
import { ToastProvider } from "./components/ui/toast";

import LoginPage from "./features/auth/LoginPage";
import RegisterPage from "./features/auth/RegisterPage";
import { ForgotPasswordPage, ResetPasswordPage } from "./features/auth/ResetPages";

import DashboardPage from "./features/dashboard/DashboardPage";
import InvoicesPage from "./features/invoices/InvoicesPage";
import InvoiceDetailPage from "./features/invoices/InvoiceDetailPage";
import PaymentsPage from "./features/payments/PaymentsPage";
import BillingPage from "./features/billing/BillingPage";
import PortalPage from "./features/portal/PortalPage";
import PortalInvoiceDetailPage from "./features/portal/PortalInvoiceDetailPage";
import NotificationAdminPage from "./features/notifications/NotificationAdminPage";
import NotificationCenterPage from "./features/notifications/NotificationCenterPage";
import NotificationPreferencesPage from "./features/notifications/NotificationPreferencesPage";
import ProductAnalyticsPage from "./features/analytics/ProductAnalyticsPage";

import ProductsPage from "./features/catalog/ProductsPage";
import PlansPage from "./features/catalog/PlansPage";
import TaxesPage from "./features/catalog/TaxesPage";
import DiscountsPage from "./features/catalog/DiscountsPage";
import QuotationsPage from "./features/subscriptions/QuotationsPage";
import QuotationDetailPage from "./features/subscriptions/QuotationDetailPage";
import SubscriptionsPage from "./features/subscriptions/SubscriptionsPage";
import CustomersPage from "./features/users/CustomersPage";
import StaffPage from "./features/users/StaffPage";
import ReportsPage from "./features/reports/ReportsPage";
import SettingsPage from "./features/system/SettingsPage";

import AnalyticsPanel from "./features/finance-intelligence/revenue-analytics/AnalyticsPanel";
import CopilotPanel from "./features/finance-intelligence/copilot/CopilotPanel";
import RisksPanel from "./features/finance-intelligence/risk-analysis/RisksPanel";
import SummariesPanel from "./features/finance-intelligence/financial-summaries/SummariesPanel";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

function useUser() {
  return useQuery<AuthUser>({
    queryKey: ["me"],
    queryFn: me,
    enabled: !!getToken(),
    retry: false,
    staleTime: 60_000,
  });
}

/** Redirects to /login when no token is present. */
function Guard({ children }: { children: React.ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

/** Staff/admin only — customers are sent to their portal. */
function StaffOnly({ children }: { children: React.ReactNode }) {
  const q = useUser();
  if (q.isLoading)
    return <p className="py-10 text-center text-sm text-ink-muted">Loading…</p>;
  if (q.data?.role === "customer") return <Navigate to="/portal" replace />;
  return <>{children}</>;
}

function AdminOnly({ children }: { children: React.ReactNode }) {
  const q = useUser();
  if (q.isLoading) return <p className="py-10 text-center text-slate-500">Loading…</p>;
  if (q.data?.role !== "admin") return <Navigate to="/" replace />;
  return <>{children}</>;
}

function CustomerOnly({ children }: { children: React.ReactNode }) {
  const q = useUser();
  if (q.isLoading)
    return <p className="py-10 text-center text-sm text-ink-muted">Loading…</p>;
  if (q.data && q.data.role !== "customer") return <Navigate to="/" replace />;
  return <>{children}</>;
}

function Shell() {
  const q = useUser();
  if (q.isLoading)
    return <p className="py-10 text-center text-sm text-ink-muted">Loading…</p>;
  if (!q.data) return <Navigate to="/login" replace />;
  return <AppShell user={q.data} />;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route
              element={
                <Guard>
                  <Shell />
                </Guard>
              }
            >
              {/* staff / admin */}
              <Route path="/" element={<StaffOnly><DashboardPage /></StaffOnly>} />
              <Route path="/customers" element={<StaffOnly><CustomersPage /></StaffOnly>} />
              <Route path="/staff" element={<StaffOnly><StaffPage /></StaffOnly>} />
              <Route path="/products" element={<StaffOnly><ProductsPage /></StaffOnly>} />
              <Route path="/plans" element={<StaffOnly><PlansPage /></StaffOnly>} />
              <Route path="/taxes" element={<StaffOnly><TaxesPage /></StaffOnly>} />
              <Route path="/discounts" element={<StaffOnly><DiscountsPage /></StaffOnly>} />
              <Route path="/quotations" element={<StaffOnly><QuotationsPage /></StaffOnly>} />
              <Route path="/quotations/:id" element={<StaffOnly><QuotationDetailPage /></StaffOnly>} />
              <Route path="/subscriptions" element={<StaffOnly><SubscriptionsPage /></StaffOnly>} />
              <Route path="/invoices" element={<StaffOnly><InvoicesPage /></StaffOnly>} />
              <Route path="/invoices/:id" element={<StaffOnly><InvoiceDetailPage /></StaffOnly>} />
              <Route path="/payments" element={<StaffOnly><PaymentsPage /></StaffOnly>} />
              <Route path="/billing" element={<StaffOnly><BillingPage /></StaffOnly>} />
              <Route path="/reports" element={<StaffOnly><ReportsPage /></StaffOnly>} />
              <Route path="/analytics" element={<StaffOnly><ProductAnalyticsPage /></StaffOnly>} />
              <Route path="/intelligence/analytics" element={<StaffOnly><AnalyticsPanel /></StaffOnly>} />
              <Route path="/intelligence/copilot" element={<StaffOnly><CopilotPanel /></StaffOnly>} />
              <Route path="/intelligence/risks" element={<StaffOnly><RisksPanel /></StaffOnly>} />
              <Route path="/intelligence/summaries" element={<StaffOnly><SummariesPanel /></StaffOnly>} />
              <Route path="/notifications" element={<NotificationCenterPage />} />
              <Route path="/notification-preferences" element={<NotificationPreferencesPage />} />
              <Route path="/notification-admin" element={<AdminOnly><NotificationAdminPage /></AdminOnly>} />
              <Route path="/settings" element={<SettingsPage />} />
              {/* customer */}
              <Route path="/portal" element={<CustomerOnly><PortalPage /></CustomerOnly>} />
              <Route path="/portal/invoices" element={<CustomerOnly><PortalPage section="invoices" /></CustomerOnly>} />
              <Route path="/portal/invoices/:id" element={<CustomerOnly><PortalInvoiceDetailPage /></CustomerOnly>} />
              <Route path="/portal/payments" element={<CustomerOnly><PortalPage section="payments" /></CustomerOnly>} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}
