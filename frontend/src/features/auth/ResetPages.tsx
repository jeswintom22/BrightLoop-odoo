import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { forgotPassword, resetPassword } from "../../lib/auth";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await forgotPassword(email);
      setMessage(r.message);
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-cream px-4">
      <Card className="w-full max-w-sm">
        <CardHeader><CardTitle className="text-xl">Reset password</CardTitle></CardHeader>
        <CardContent>
          {message ? (
            <div className="space-y-4">
              <p className="text-sm text-ink">{message}</p>
              <Link to="/login" className="text-sm text-ink-muted hover:underline">
                Back to sign in
              </Link>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-4">
              <div className="space-y-1">
                <Label htmlFor="email">Registered email</Label>
                <Input id="email" type="email" required value={email}
                  onChange={(e) => setEmail(e.target.value)} />
              </div>
              <Button type="submit" className="w-full" disabled={busy}>
                {busy ? "Sending…" : "Send reset link"}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export function ResetPasswordPage() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [pw, setPw] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await resetPassword(token, pw);
      nav("/login");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Reset failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-cream px-4">
      <Card className="w-full max-w-sm">
        <CardHeader><CardTitle className="text-xl">Choose a new password</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="pw">New password</Label>
              <Input id="pw" type="password" required value={pw}
                onChange={(e) => setPw(e.target.value)} />
            </div>
            {error && <p className="text-sm text-danger">{error}</p>}
            <Button type="submit" className="w-full" disabled={busy || !token}>
              {busy ? "Saving…" : "Reset password"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
