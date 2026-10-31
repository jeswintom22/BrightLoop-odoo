import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeader } from "../../components/ui/extras";
import { logout } from "../../lib/auth";

interface Me {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
}

export default function SettingsPage() {
  const me = useQuery({ queryKey: ["me-settings"], queryFn: () => api<Me>("/auth/me") });

  return (
    <div>
      <PageHeader title="Settings" description="Account and workspace preferences." />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Profile</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex justify-between"><span className="text-ink-muted">Name</span><span className="font-medium">{me.data?.full_name ?? "—"}</span></div>
            <div className="flex justify-between"><span className="text-ink-muted">Email</span><span>{me.data?.email ?? "—"}</span></div>
            <div className="flex justify-between"><span className="text-ink-muted">Role</span><Badge>{me.data?.role ?? "—"}</Badge></div>
            <div className="flex justify-between"><span className="text-ink-muted">Status</span><span>{me.data?.is_active ? "Active" : "Disabled"}</span></div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Security</CardTitle></CardHeader>
          <CardContent className="space-y-4 text-sm">
            <p className="text-ink-muted">
              Password changes use the secure reset flow — a reset link is sent to your email.
            </p>
            <div className="flex gap-2">
              <Link to="/forgot-password"><Button variant="outline">Reset password</Button></Link>
              <Button variant="ghost" onClick={logout}>Sign out</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
