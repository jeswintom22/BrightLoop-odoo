
"use client";

import { useState, FormEvent } from "react";
import { createClient } from "@/lib/supabase/client";

export default function RegisterPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const supabase = createClient();

  async function handleRegister(e: FormEvent) {
    e.preventDefault();
    setMessage("");

    if (password.length < 9) {
      setMessage("Password must have at least 9 characters.");
      return;
    }

    if (
      !/[A-Z]/.test(password) ||
      !/[a-z]/.test(password) ||
      !/[^A-Za-z0-9]/.test(password)
    ) {
      setMessage("Include uppercase, lowercase and special characters.");
      return;
    }

    if (password !== confirmPassword) {
      setMessage("Passwords do not match.");
      return;
    }

    setLoading(true);

    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: { full_name: name },
      },
    });

    setLoading(false);

    if (error) {
      setMessage(error.message);
    } else {
      setMessage("Account created! Check your email for confirmation.");
    }
  }

  return (
    <main className="min-h-screen bg-[#F8F6EE] flex items-center justify-center p-5">

      <div className="w-full max-w-5xl grid md:grid-cols-2 bg-white rounded-3xl overflow-hidden shadow-xl">

        {/* Left section */}
        <section className="bg-[#E5EDE3] p-10 md:p-14 flex flex-col justify-between">

          <div>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-[#42634E] text-white rounded-xl flex items-center justify-center font-bold text-xl">
                B
              </div>

              <span className="text-2xl font-bold text-[#294A36]">
                Brightloop
              </span>
            </div>

            <div className="mt-20">
              <p className="text-sm font-semibold tracking-widest text-black uppercase">
                Subscription Management
              </p>

              <h1 className="text-4xl md:text-5xl font-bold text-[#294A36] leading-tight mt-5">
                Everything in one place.
              </h1>

              <p className="text-black mt-6 leading-7">
                Manage your subscriptions, track invoices and stay in control
                with a simpler way to manage your business.
              </p>
            </div>
          </div>

          <p className="text-sm text-black mt-16">
            Simple. Organized. Effortless.
          </p>

        </section>

        {/* Right section */}
        <section className="p-8 md:p-14">

          <div className="max-w-sm mx-auto">

            <p className="text-sm font-semibold text-black">
              GET STARTED
            </p>

            <h2 className="text-3xl font-bold text-black mt-3">
              Create your account
            </h2>

            <p className="text-black mt-2 mb-8">
              Enter your details to get started with Brightloop.
            </p>

            <form onSubmit={handleRegister} className="space-y-5">

              <div>
                <label className="block text-sm font-medium text-black mb-2">
                  Full Name
                </label>

                <input
                  type="text"
                  placeholder="Your full name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  className="w-full rounded-xl border border-gray-300 p-3.5 text-black placeholder:text-gray-600 outline-none focus:border-[#78977D] focus:ring-2 focus:ring-[#E5EDE3]"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-black mb-2">
                  Email Address
                </label>

                <input
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="w-full rounded-xl border border-gray-300 p-3.5 text-black placeholder:text-gray-600 outline-none focus:border-[#78977D] focus:ring-2 focus:ring-[#E5EDE3]"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-black mb-2">
                  Password
                </label>

                <input
                  type="password"
                  placeholder="Create a password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="w-full rounded-xl border border-gray-300 p-3.5 text-black placeholder:text-gray-600 outline-none focus:border-[#78977D] focus:ring-2 focus:ring-[#E5EDE3]"
                />

                <p className="text-xs text-black mt-2">
                  At least 9 characters, including uppercase, lowercase and a special character.
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-black mb-2">
                  Confirm Password
                </label>

                <input
                  type="password"
                  placeholder="Enter your password again"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  className="w-full rounded-xl border border-gray-300 p-3.5 text-black placeholder:text-gray-600 outline-none focus:border-[#78977D] focus:ring-2 focus:ring-[#E5EDE3]"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-xl bg-[#42634E] hover:bg-[#304D3A] text-white font-semibold p-4 transition disabled:opacity-50"
              >
                {loading ? "Creating Account..." : "Create Account"}
              </button>

              {message && (
                <p className="text-sm text-center text-black">
                  {message}
                </p>
              )}

            </form>

            <p className="text-xs text-center text-black mt-8">
              © 2026 Brightloop. All rights reserved.
            </p>

          </div>
        </section>

      </div>
    </main>
  );
}
