import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Bell,
  CreditCard,
  LayoutDashboard,
  Receipt,
  RefreshCw,
  Settings,
} from "lucide-react";
import {
  BrowserRouter,
  Link,
  NavLink,
  Route,
  Routes,
} from "react-router-dom";
import { cn } from "./lib/utils";
import BillingPage from "./features/billing/BillingPage";
import DashboardPage from "./features/dashboard/DashboardPage";
import InvoiceDetailPage from "./features/invoices/InvoiceDetailPage";
import InvoicesPage from "./features/invoices/InvoicesPage";
import PaymentsPage from "./features/payments/PaymentsPage";
import NotificationCenterPage from "./features/notifications/NotificationCenterPage";
import NotificationPreferencesPage from "./features/notifications/NotificationPreferencesPage";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/invoices", label: "Invoices", icon: Receipt },
  { to: "/payments", label: "Payments", icon: CreditCard },
  { to: "/billing", label: "Billing runs", icon: RefreshCw },
  { to: "/notifications", label: "Notifications", icon: Bell },
  {
    to: "/notification-preferences",
    label: "Preferences",
    icon: Settings,
  },
];

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center gap-8 px-4 py-3">
          <Link to="/" className="text-lg font-bold tracking-tight">
            Brightloop
            <span className="ml-2 font-normal text-slate-400">Billing</span>
          </Link>
          <nav className="min-w-0 flex flex-1 flex-wrap gap-1">
            {NAV.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100",
                    isActive && "bg-slate-100 text-slate-900",
                  )
                }
              >
                <Icon className="h-4 w-4" />
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/invoices" element={<InvoicesPage />} />
            <Route path="/invoices/:id" element={<InvoiceDetailPage />} />
            <Route path="/payments" element={<PaymentsPage />} />
            <Route path="/billing" element={<BillingPage />} />
            <Route
              path="/notifications"
              element={<NotificationCenterPage />}
            />
            <Route
              path="/notification-preferences"
              element={<NotificationPreferencesPage />}
            />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
