import { useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  BadgePercent,
  BarChart3,
  Bell,
  BrainCircuit,
  ChartLine,
  CreditCard,
  FileText,
  FileSignature,
  LayoutDashboard,
  LogOut,
  Mail,
  Menu,
  Package,
  RefreshCw,
  Receipt,
  Settings,
  ShieldAlert,
  SlidersHorizontal,
  Store,
  User,
  Users,
  UserCog,
  X,
  type LucideIcon,
} from "lucide-react";
import { cn } from "../lib/utils";
import { logout, type User as AuthUser } from "../lib/auth";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
  adminOnly?: boolean;
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

const NAV: NavGroup[] = [
  {
    title: "Overview",
    items: [{ to: "/", label: "Dashboard", icon: LayoutDashboard, end: true }],
  },
  {
    title: "Customers",
    items: [
      { to: "/customers", label: "Customers", icon: Users },
      { to: "/staff", label: "Staff", icon: UserCog, adminOnly: true },
    ],
  },
  {
    title: "Catalog",
    items: [
      { to: "/products", label: "Products", icon: Package },
      { to: "/plans", label: "Subscription Plans", icon: Store },
      { to: "/taxes", label: "Taxes", icon: BadgePercent },
      { to: "/discounts", label: "Discounts", icon: BadgePercent },
    ],
  },
  {
    title: "Subscriptions",
    items: [
      { to: "/quotations", label: "Quotations", icon: FileSignature },
      { to: "/subscriptions", label: "Subscriptions", icon: RefreshCw },
    ],
  },
  {
    title: "Finance",
    items: [
      { to: "/invoices", label: "Invoices", icon: Receipt },
      { to: "/payments", label: "Payments", icon: CreditCard },
      { to: "/billing", label: "Billing", icon: RefreshCw },
      { to: "/reports", label: "Financial Reports", icon: FileText },
    ],
  },
  {
    title: "Intelligence",
    items: [
      { to: "/analytics", label: "Product Analytics", icon: BarChart3 },
      { to: "/intelligence/analytics", label: "Revenue Analytics", icon: ChartLine },
      { to: "/intelligence/copilot", label: "Finance Copilot", icon: BrainCircuit },
      { to: "/intelligence/risks", label: "Revenue Risks", icon: ShieldAlert },
      { to: "/intelligence/summaries", label: "Financial Summaries", icon: FileText },
    ],
  },
  {
    title: "System",
    items: [
      { to: "/notifications", label: "Notifications", icon: Bell },
      { to: "/notification-preferences", label: "Preferences", icon: SlidersHorizontal },
      { to: "/notification-admin", label: "Notification Admin", icon: Mail, adminOnly: true },
      { to: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

const CUSTOMER_NAV: NavGroup[] = [
  {
    title: "My account",
    items: [
      { to: "/portal", label: "Overview", icon: User, end: true },
      { to: "/portal/invoices", label: "Invoices", icon: Receipt },
      { to: "/portal/payments", label: "Payments", icon: CreditCard },
      { to: "/notifications", label: "Notifications", icon: Bell },
      { to: "/notification-preferences", label: "Preferences", icon: SlidersHorizontal },
    ],
  },
];

const TITLES: [RegExp, string][] = [
  [/^\/$/, "Dashboard"],
  [/^\/customers/, "Customers"],
  [/^\/staff/, "Staff"],
  [/^\/products/, "Products"],
  [/^\/plans/, "Subscription Plans"],
  [/^\/taxes/, "Taxes"],
  [/^\/discounts/, "Discounts"],
  [/^\/quotations/, "Quotations"],
  [/^\/subscriptions/, "Subscriptions"],
  [/^\/invoices/, "Invoices"],
  [/^\/payments/, "Payments"],
  [/^\/billing/, "Billing"],
  [/^\/reports/, "Financial Reports"],
  [/^\/analytics/, "Product Analytics"],
  [/^\/intelligence\/analytics/, "Revenue Analytics"],
  [/^\/intelligence\/copilot/, "Finance Copilot"],
  [/^\/intelligence\/risks/, "Revenue Risks"],
  [/^\/intelligence\/summaries/, "Financial Summaries"],
  [/^\/notification-preferences/, "Notification Preferences"],
  [/^\/notification-admin/, "Notification Admin"],
  [/^\/notifications/, "Notifications"],
  [/^\/settings/, "Settings"],
  [/^\/portal/, "My account"],
];

function SidebarContent({
  groups,
  onNavigate,
}: {
  groups: NavGroup[];
  onNavigate?: () => void;
}) {
  return (
    <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
      {groups.map((g) => (
        <div key={g.title}>
          <p className="mb-1 px-2 text-[11px] font-medium uppercase tracking-wider text-ink-muted/70">
            {g.title}
          </p>
          <div className="space-y-0.5">
            {g.items.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm text-ink-muted hover:bg-sage-faint hover:text-ink",
                    isActive && "bg-sage-soft font-medium text-ink",
                  )
                }
              >
                <Icon className="h-4 w-4 shrink-0" />
                {label}
              </NavLink>
            ))}
          </div>
        </div>
      ))}
    </nav>
  );
}

export default function AppShell({ user }: { user: AuthUser }) {
  const [open, setOpen] = useState(false);
  const nav = useNavigate();
  const { pathname } = useLocation();
  const title = TITLES.find(([re]) => re.test(pathname))?.[1] ?? "Brightloop";
  const groups = (user.role === "customer" ? CUSTOMER_NAV : NAV).map((g) => ({
    ...g,
    items: g.items.filter((i) => !i.adminOnly || user.role === "admin"),
  }));

  return (
    <div className="flex min-h-screen bg-cream text-ink">
      {/* Sidebar — desktop */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-60 flex-col border-r border-line bg-cream-card md:flex">
        <div className="flex h-14 items-center gap-2 border-b border-line px-4">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-sage text-sm font-bold text-ink">
            B
          </span>
          <span className="text-base font-semibold tracking-tight">Brightloop</span>
        </div>
        <SidebarContent groups={groups} />
        <div className="border-t border-line p-3">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-sage-soft text-xs font-semibold text-ink">
              {user.full_name.slice(0, 1).toUpperCase()}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-ink">{user.full_name}</p>
              <p className="text-xs capitalize text-ink-muted">{user.role}</p>
            </div>
            <button
              title="Sign out"
              onClick={() => {
                logout();
                nav("/login");
              }}
              className="rounded p-1.5 text-ink-muted hover:bg-sage-faint hover:text-ink"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Sidebar — mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div className="absolute inset-0 bg-ink/40" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 flex w-64 flex-col bg-cream-card">
            <div className="flex h-14 items-center justify-between border-b border-line px-4">
              <span className="text-base font-semibold">Brightloop</span>
              <button onClick={() => setOpen(false)} className="rounded p-1 hover:bg-sage-faint">
                <X className="h-5 w-5" />
              </button>
            </div>
            <SidebarContent groups={groups} onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col md:pl-60">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line bg-cream/90 px-4 backdrop-blur md:px-6">
          <button
            className="rounded p-1.5 text-ink-muted hover:bg-sage-faint md:hidden"
            onClick={() => setOpen(true)}
          >
            <Menu className="h-5 w-5" />
          </button>
          <h1 className="text-sm font-semibold text-ink">{title}</h1>
          <div className="ml-auto flex items-center gap-2">
            <span className="hidden text-xs capitalize text-ink-muted sm:block">
              {user.full_name} · {user.role}
            </span>
          </div>
        </header>
        <main className="flex-1 px-4 py-6 md:px-6">
          <div className="mx-auto max-w-6xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
