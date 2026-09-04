import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  BarChart3,
  Users,
  CreditCard,
  TrendingUp,
  ArrowUpRight,
  RefreshCw,
  Download,
  Award,
  Bell,
  Send,
} from "lucide-react";
import { toast } from "sonner";

const TABS = [
  { id: "overview", label: "Overview", icon: BarChart3 },
  { id: "users", label: "Signups", icon: Users },
  { id: "payments", label: "Payments", icon: CreditCard },
  { id: "collections", label: "Top collections", icon: Award },
  { id: "notifications", label: "Notifications", icon: Bell },
];

function Stat({ label, value, sub, accent = "text-foreground" }) {
  return (
    <div className="p-4 rounded-xl border border-border bg-secondary/30">
      <div className="text-xs text-muted-foreground uppercase tracking-wide">{label}</div>
      <div className={`text-2xl font-heading font-semibold mt-1 ${accent}`}>{value}</div>
      {sub && <div className="text-xs text-muted-foreground mt-1">{sub}</div>}
    </div>
  );
}

function toCsv(rows, headers) {
  const escape = (v) => {
    if (v === null || v === undefined) return "";
    const s = String(v).replace(/"/g, '""');
    return /[",\n]/.test(s) ? `"${s}"` : s;
  };
  const head = headers.map((h) => escape(h.label)).join(",");
  const body = rows.map((r) => headers.map((h) => escape(h.get(r))).join(",")).join("\n");
  return `${head}\n${body}`;
}

function downloadCsv(name, csv) {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function Overview() {
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["admin-stats-overview"],
    queryFn: async () => (await api.get("/admin/stats/overview")).data,
    staleTime: 30_000,
  });
  if (isLoading || !data) return <Skeleton className="h-64 rounded-xl" />;
  const rev = data.revenue?.by_currency || {};
  const currencies = Object.entries(rev);
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">
          {data.conversions?.excludes_admin
            ? "All-time metrics · conversion rate excludes the admin workspace"
            : "All-time metrics · counts include every workspace"}
        </p>
        <Button size="sm" variant="ghost" onClick={() => refetch()} disabled={isFetching} data-testid="refresh-analytics">
          <RefreshCw size={13} className={isFetching ? "animate-spin" : ""} /> Refresh
        </Button>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <Stat label="Total signups" value={data.signups.total} sub={`+${data.signups.this_month} this month`} />
        <Stat label="Paid transactions" value={data.payments.paid} sub={`${data.payments.pending_or_failed} pending/failed`} />
        <Stat
          label="Revenue (all time)"
          value={
            currencies.length
              ? currencies.map(([c, a]) => `${a.toFixed(2)} ${c.toUpperCase()}`).join(" · ")
              : "0.00"
          }
          sub={`This month: ${data.revenue.this_month.toFixed(2)}`}
          accent="text-primary"
        />
        <Stat
          label="Free → paid rate"
          value={`${data.conversions.free_to_paid_rate}%`}
          sub={`${data.conversions.any_paid} of ${data.conversions.counted_workspaces ?? (data.plans.free + data.plans.pro + data.plans.business)} workspaces`}
        />
      </div>

      <div className="grid sm:grid-cols-3 gap-3">
        <Stat label="On Free" value={data.plans.free} />
        <Stat label="On Pro" value={data.plans.pro} accent="text-primary" />
        <Stat label="On Business" value={data.plans.business} accent="text-primary" />
      </div>

      <div className="p-4 rounded-xl border border-border bg-secondary/30">
        <div className="flex items-center gap-2 mb-3">
          <TrendingUp size={16} className="text-primary" />
          <h4 className="font-medium">Plan ladder</h4>
        </div>
        <div className="grid sm:grid-cols-3 gap-3 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Free → Pro</span>
            <span className="font-semibold flex items-center gap-1">
              <ArrowUpRight size={14} className="text-green-500" />
              {data.conversions.pro}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Free → Business</span>
            <span className="font-semibold flex items-center gap-1">
              <ArrowUpRight size={14} className="text-green-500" />
              {data.conversions.business}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Pro → Business</span>
            <span className="font-semibold flex items-center gap-1">
              <ArrowUpRight size={14} className="text-green-500" />
              {data.conversions.pro_to_business}
            </span>
          </div>
        </div>
      </div>

      <div className="grid sm:grid-cols-3 gap-3">
        <Stat label="Collections" value={data.content.collections} />
        <Stat label="Testimonials" value={data.content.testimonials_total} sub={`+${data.content.testimonials_this_month} this month`} />
        <Stat label="Admin email" value={data.signups.admin_email || "not set"} accent="text-muted-foreground text-base font-mono" />
      </div>
    </div>
  );
}

function UsersTable() {
  const [q, setQ] = useState("");
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["admin-users"],
    queryFn: async () => (await api.get("/admin/users", { params: { limit: 500 } })).data,
    staleTime: 30_000,
  });
  if (isLoading || !data) return <Skeleton className="h-64 rounded-xl" />;
  const filtered = data.users.filter(
    (u) => !q || (u.email || "").toLowerCase().includes(q.toLowerCase()) || (u.name || "").toLowerCase().includes(q.toLowerCase())
  );
  const exportCsv = () =>
    downloadCsv(
      `testify-users-${new Date().toISOString().slice(0, 10)}.csv`,
      toCsv(filtered, [
        { label: "Name", get: (r) => r.name },
        { label: "Email", get: (r) => r.email },
        { label: "Provider", get: (r) => r.auth_provider },
        { label: "Plan", get: (r) => r.plan },
        { label: "Workspaces", get: (r) => r.workspace_count },
        { label: "Onboarded", get: (r) => (r.onboarded ? "yes" : "no") },
        { label: "Created", get: (r) => r.created_at },
      ])
    );
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <Input
          placeholder="Search by name or email"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="max-w-xs"
          data-testid="analytics-users-search"
        />
        <div className="flex gap-2">
          <Button size="sm" variant="ghost" onClick={() => refetch()} disabled={isFetching} data-testid="refresh-users">
            <RefreshCw size={13} className={isFetching ? "animate-spin" : ""} /> Refresh
          </Button>
          <Button size="sm" variant="outline" onClick={exportCsv} data-testid="export-users-csv">
            <Download size={13} /> CSV
          </Button>
        </div>
      </div>
      <div className="rounded-xl border border-border overflow-hidden">
        <div className="overflow-x-auto max-h-[420px]">
          <table className="w-full text-sm">
            <thead className="bg-secondary/60 sticky top-0">
              <tr className="text-left">
                <th className="p-2 font-medium">User</th>
                <th className="p-2 font-medium">Provider</th>
                <th className="p-2 font-medium">Plan</th>
                <th className="p-2 font-medium">Onboarded</th>
                <th className="p-2 font-medium">Joined</th>
              </tr>
            </thead>
            <tbody data-testid="analytics-users-table">
              {filtered.map((u) => (
                <tr key={u.id} className="border-t border-border">
                  <td className="p-2">
                    <div className="font-medium">{u.name || "—"}</div>
                    <div className="text-xs text-muted-foreground">{u.email}</div>
                  </td>
                  <td className="p-2 capitalize">{u.auth_provider}</td>
                  <td className="p-2">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs capitalize ${
                        u.plan === "business"
                          ? "bg-primary/20 text-primary"
                          : u.plan === "pro"
                          ? "bg-primary/10 text-primary"
                          : "bg-secondary text-muted-foreground"
                      }`}
                    >
                      {u.plan}
                    </span>
                  </td>
                  <td className="p-2">{u.onboarded ? "yes" : "no"}</td>
                  <td className="p-2 text-muted-foreground">{fmtDate(u.created_at)}</td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={5} className="p-4 text-center text-muted-foreground">No users match.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      <p className="text-xs text-muted-foreground">Showing {filtered.length} of {data.count} accounts.</p>
    </div>
  );
}

function PaymentsTable() {
  const [status, setStatus] = useState("");
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["admin-payments", status],
    queryFn: async () =>
      (await api.get("/admin/payments", { params: { limit: 500, ...(status ? { status } : {}) } })).data,
    staleTime: 30_000,
  });
  if (isLoading || !data) return <Skeleton className="h-64 rounded-xl" />;
  const items = data.payments;
  const exportCsv = () =>
    downloadCsv(
      `testify-payments-${new Date().toISOString().slice(0, 10)}.csv`,
      toCsv(items, [
        { label: "Session", get: (r) => r.session_id },
        { label: "User", get: (r) => r.user_email },
        { label: "Workspace", get: (r) => r.workspace_name },
        { label: "Plan", get: (r) => r.plan },
        { label: "Lookup", get: (r) => r.lookup_key },
        { label: "Amount", get: (r) => r.amount },
        { label: "Currency", get: (r) => r.currency },
        { label: "Status", get: (r) => r.payment_status },
        { label: "Created", get: (r) => r.created_at },
        { label: "Updated", get: (r) => r.updated_at },
      ])
    );
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex gap-2">
          {["", "paid", "pending", "failed"].map((s) => (
            <button
              key={s || "all"}
              onClick={() => setStatus(s)}
              className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                status === s ? "border-primary bg-primary/15 text-primary" : "border-border text-muted-foreground"
              }`}
              data-testid={`payments-filter-${s || "all"}`}
            >
              {s ? s : "all"}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="ghost" onClick={() => refetch()} disabled={isFetching} data-testid="refresh-payments">
            <RefreshCw size={13} className={isFetching ? "animate-spin" : ""} /> Refresh
          </Button>
          <Button size="sm" variant="outline" onClick={exportCsv} data-testid="export-payments-csv">
            <Download size={13} /> CSV
          </Button>
        </div>
      </div>
      <div className="rounded-xl border border-border overflow-hidden">
        <div className="overflow-x-auto max-h-[420px]">
          <table className="w-full text-sm">
            <thead className="bg-secondary/60 sticky top-0">
              <tr className="text-left">
                <th className="p-2 font-medium">User</th>
                <th className="p-2 font-medium">Plan</th>
                <th className="p-2 font-medium">Amount</th>
                <th className="p-2 font-medium">Status</th>
                <th className="p-2 font-medium">Created</th>
              </tr>
            </thead>
            <tbody data-testid="analytics-payments-table">
              {items.map((p) => (
                <tr key={p.session_id} className="border-t border-border">
                  <td className="p-2">
                    <div className="text-xs text-muted-foreground">{p.workspace_name || "—"}</div>
                    <div>{p.user_email || p.user_id}</div>
                  </td>
                  <td className="p-2">
                    <span className="capitalize">{p.plan}</span>
                    <span className="text-xs text-muted-foreground ml-1">({p.lookup_key})</span>
                  </td>
                  <td className="p-2">
                    {p.amount.toFixed(2)} <span className="text-xs uppercase">{p.currency}</span>
                  </td>
                  <td className="p-2">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs capitalize ${
                        p.payment_status === "paid"
                          ? "bg-green-500/15 text-green-500"
                          : p.payment_status === "failed"
                          ? "bg-red-500/15 text-red-500"
                          : "bg-yellow-500/15 text-yellow-600"
                      }`}
                    >
                      {p.payment_status}
                    </span>
                  </td>
                  <td className="p-2 text-muted-foreground">{fmtDate(p.created_at)}</td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td colSpan={5} className="p-4 text-center text-muted-foreground">No payments to show.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      <p className="text-xs text-muted-foreground">Showing {items.length} transactions.</p>
    </div>
  );
}

function TopCollections() {
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["admin-top-collections"],
    queryFn: async () => (await api.get("/admin/collections/top", { params: { limit: 25 } })).data,
    staleTime: 30_000,
  });
  if (isLoading || !data) return <Skeleton className="h-64 rounded-xl" />;
  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button size="sm" variant="ghost" onClick={() => refetch()} disabled={isFetching} data-testid="refresh-collections">
          <RefreshCw size={13} className={isFetching ? "animate-spin" : ""} /> Refresh
        </Button>
      </div>
      <div className="rounded-xl border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-secondary/60">
            <tr className="text-left">
              <th className="p-2 font-medium">#</th>
              <th className="p-2 font-medium">Collection</th>
              <th className="p-2 font-medium">Workspace</th>
              <th className="p-2 font-medium">Plan</th>
              <th className="p-2 font-medium text-right">Testimonials</th>
            </tr>
          </thead>
          <tbody data-testid="analytics-collections-table">
            {data.collections.map((c, i) => (
              <tr key={c.collection_id} className="border-t border-border">
                <td className="p-2 text-muted-foreground">{i + 1}</td>
                <td className="p-2">
                  <div className="font-medium">{c.collection_name}</div>
                  <div className="text-xs text-muted-foreground">/{c.slug}</div>
                </td>
                <td className="p-2">{c.workspace_name || "—"}</td>
                <td className="p-2 capitalize">{c.workspace_plan}</td>
                <td className="p-2 text-right font-semibold">{c.testimonial_count}</td>
              </tr>
            ))}
            {data.collections.length === 0 && (
              <tr>
                <td colSpan={5} className="p-4 text-center text-muted-foreground">No testimonials yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function NotificationsPanel() {
  const qc = useQueryClient();
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["admin-notify-status"],
    queryFn: async () => (await api.get("/admin/notifications/status")).data,
    staleTime: 30_000,
  });
  const setMode = useMutation({
    mutationFn: (mode) => api.put("/admin/settings", { admin_notify_mode: mode }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-notify-status"] });
      qc.invalidateQueries({ queryKey: ["admin-settings"] });
      toast.success("Notification mode saved");
    },
    onError: (e) => toast.error(formatApiError(e)),
  });
  const sendNow = useMutation({
    mutationFn: () => api.post("/admin/notifications/send-digest"),
    onSuccess: (r) => {
      const d = r.data;
      qc.invalidateQueries({ queryKey: ["admin-notify-status"] });
      if (d.sent) toast.success(`Digest sent — ${d.signups} signup(s), ${d.payment_failures} failure(s)`);
      else toast(d.reason || "No new events to send");
    },
    onError: (e) => toast.error(formatApiError(e)),
  });

  if (isLoading || !data) return <Skeleton className="h-64 rounded-xl" />;
  const modes = [
    { id: "instant", label: "Instant", desc: "Email me the moment something happens" },
    { id: "daily", label: "Daily digest", desc: "One email every 24 hours, rolled up" },
    { id: "off", label: "Off", desc: "Log events but never email me" },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="text-xs text-muted-foreground">Applies to both new signups and failed payments.</div>
        <Button size="sm" variant="ghost" onClick={() => refetch()} disabled={isFetching} data-testid="refresh-notify-status">
          <RefreshCw size={13} className={isFetching ? "animate-spin" : ""} /> Refresh
        </Button>
      </div>

      <div className="grid sm:grid-cols-3 gap-3">
        {modes.map((m) => {
          const active = data.mode === m.id;
          return (
            <button
              key={m.id}
              onClick={() => setMode.mutate(m.id)}
              disabled={setMode.isPending}
              className={`text-left rounded-xl border p-3 transition-colors ${
                active ? "border-primary bg-primary/10" : "border-border hover:border-primary/40"
              }`}
              data-testid={`notify-mode-${m.id}`}
            >
              <div className={`text-sm font-medium ${active ? "text-primary" : ""}`}>{m.label}</div>
              <div className="text-xs text-muted-foreground mt-0.5">{m.desc}</div>
            </button>
          );
        })}
      </div>

      <div className="grid sm:grid-cols-3 gap-3">
        <Stat label="Pending signups" value={data.pending_signups} />
        <Stat label="Pending failures" value={data.pending_payment_failures} />
        <Stat
          label="Last digest sent"
          value={data.last_sent ? fmtDate(data.last_sent) : "never"}
          accent="text-muted-foreground text-base"
        />
      </div>

      <div className="flex items-center gap-2">
        <Button onClick={() => sendNow.mutate()} disabled={sendNow.isPending} data-testid="send-digest-now">
          <Send size={14} /> Send digest now
        </Button>
        <p className="text-xs text-muted-foreground">
          Flushes every unsent event and marks them as delivered.
        </p>
      </div>
    </div>
  );
}

export default function AdminAnalytics() {
  const [tab, setTab] = useState("overview");
  return (
    <div className="p-6 rounded-2xl border border-primary/30 bg-card lg:col-span-2" data-testid="admin-analytics">
      <div className="flex items-center gap-2 mb-1">
        <BarChart3 size={18} className="text-primary" />
        <h3 className="font-heading font-semibold">Admin analytics</h3>
        <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-primary/15 text-primary font-medium">Admin</span>
      </div>
      <p className="text-sm text-muted-foreground mb-4">
        All-time platform stats — signups, revenue, Free → Pro → Business conversions and top collections.
      </p>
      <div className="flex gap-1 border-b border-border mb-4 overflow-x-auto">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-3 py-2 text-sm flex items-center gap-1.5 border-b-2 transition-colors ${
              tab === t.id
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
            data-testid={`analytics-tab-${t.id}`}
          >
            <t.icon size={14} /> {t.label}
          </button>
        ))}
      </div>
      {tab === "overview" && <Overview />}
      {tab === "users" && <UsersTable />}
      {tab === "payments" && <PaymentsTable />}
      {tab === "collections" && <TopCollections />}
      {tab === "notifications" && <NotificationsPanel />}
    </div>
  );
}
