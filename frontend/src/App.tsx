import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import {
  Bell,
  CreditCard,
  LayoutDashboard,
  Mail,
  LogOut,
  Receipt,
  RefreshCw,
  Settings,
  User,
} from "lucide-react";
import {
  BrowserRouter,
  Link,
  Navigate,
  NavLink,
  Route,
  Routes,
  useNavigate,
} from "react-router-dom";
import { cn } from "./lib/utils";
import { getToken, logout, me, type User as AuthUser } from "./lib/auth";
import BillingPage from "./features/billing/BillingPage";
import DashboardPage from "./features/dashboard/DashboardPage";
import InvoiceDetailPage from "./features/invoices/InvoiceDetailPage";
import InvoicesPage from "./features/invoices/InvoicesPage";
import PaymentsPage from "./features/payments/PaymentsPage";
import NotificationCenterPage from "./features/notifications/NotificationCenterPage";
import NotificationPreferencesPage from "./features/notifications/NotificationPreferencesPage";
import LoginPage from "./features/auth/LoginPage";
import RegisterPage from "./features/auth/RegisterPage";
import { ForgotPasswordPage, ResetPasswordPage } from "./features/auth/ResetPages";
import PortalPage from "./features/portal/PortalPage";
import PortalInvoiceDetailPage from "./features/portal/PortalInvoiceDetailPage";
import NotificationAdminPage from "./features/notifications/NotificationAdminPage";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

const STAFF_NAV = [
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

const CUSTOMER_NAV = [
  { to: "/portal", label: "My account", icon: User, end: true },
  { to: "/notifications", label: "Notifications", icon: Bell },
  { to: "/notification-preferences", label: "Preferences", icon: Settings },
];

function useUser() {
  return useQuery<AuthUser>({
    queryKey: ["me"],
    queryFn: me,
    enabled: !!getToken(),
    retry: false,
    staleTime: 60_000,
  });
}

function Layout({ children }: { children: React.ReactNode }) {
  const nav = useNavigate();
  const user = useUser().data;
  const items =
    user?.role === "customer"
      ? CUSTOMER_NAV
      : user?.role === "admin"
        ? [
            ...STAFF_NAV,
            { to: "/notification-admin", label: "Notification admin", icon: Mail },
          ]
        : STAFF_NAV;
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center gap-8 px-4 py-3">
          <Link to="/" className="text-lg font-bold tracking-tight">
            Brightloop
            <span className="ml-2 font-normal text-slate-400">Billing</span>
          </Link>
          <nav className="flex min-w-0 flex-1 flex-wrap gap-1">
            {items.map(({ to, label, icon: Icon, end }) => (
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
          {user && (
            <div className="flex items-center gap-3 text-sm text-slate-600">
              <span>
                {user.full_name}
                <span className="ml-1 rounded bg-slate-100 px-1.5 py-0.5 text-xs capitalize">
                  {user.role}
                </span>
              </span>
              <button
                onClick={() => {
                  logout();
                  nav("/login");
                }}
                className="flex items-center gap-1 rounded-md px-2 py-1 hover:bg-slate-100"
                title="Sign out"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  );
}

/** Redirects to /login when no token; customers land on /portal. */
function Guard({ children }: { children: React.ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function StaffOnly({ children }: { children: React.ReactNode }) {
  const q = useUser();
  if (q.isLoading) return <p className="py-10 text-center text-slate-500">Loading…</p>;
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
  if (q.isLoading) return <p className="py-10 text-center text-slate-500">Loading…</p>;
  if (q.data && q.data.role !== "customer") return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route
            path="/*"
            element={
              <Guard>
                <Layout>
                  <Routes>
                    <Route path="/" element={<StaffOnly><DashboardPage /></StaffOnly>} />
                    <Route path="/invoices" element={<StaffOnly><InvoicesPage /></StaffOnly>} />
                    <Route path="/invoices/:id" element={<StaffOnly><InvoiceDetailPage /></StaffOnly>} />
                    <Route path="/payments" element={<StaffOnly><PaymentsPage /></StaffOnly>} />
                    <Route path="/billing" element={<StaffOnly><BillingPage /></StaffOnly>} />
                    <Route path="/notifications" element={<NotificationCenterPage />} />
                    <Route path="/notification-preferences" element={<NotificationPreferencesPage />} />
                    <Route path="/notification-admin" element={<AdminOnly><NotificationAdminPage /></AdminOnly>} />
                    <Route path="/portal" element={<CustomerOnly><PortalPage /></CustomerOnly>} />
                    <Route path="/portal/invoices/:id" element={<CustomerOnly><PortalInvoiceDetailPage /></CustomerOnly>} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Routes>
                </Layout>
              </Guard>
            }
          />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
