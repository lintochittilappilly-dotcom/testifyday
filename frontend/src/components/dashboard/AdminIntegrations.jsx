import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Save, ShieldCheck, Mail, MapPin, KeyRound, Ticket, DollarSign, CreditCard, CheckCircle2, XCircle, AlertCircle, RefreshCw } from "lucide-react";
import { toast } from "sonner";

function Group({ icon: Icon, title, desc, children }) {
  return (
    <div className="pb-5 mb-5 border-b border-border last:border-0 last:mb-0 last:pb-0">
      <div className="flex items-center gap-2 mb-1"><Icon size={16} className="text-primary" /><h4 className="font-medium">{title}</h4></div>
      <p className="text-xs text-muted-foreground mb-3">{desc}</p>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function PlanEditor({ plans, overrides, setOverrides }) {
  const setField = (id, key, value) => {
    const next = plans.map((p) => {
      const existing = overrides.find((o) => o.id === p.id) || { id: p.id };
      if (p.id !== id) return existing;
      return { ...existing, [key]: value };
    });
    setOverrides(next);
  };
  const getVal = (id, key, fallback) => {
    const o = overrides.find((x) => x.id === id);
    if (o && o[key] !== undefined && o[key] !== "" && o[key] !== null) return o[key];
    return fallback;
  };
  return (
    <div className="space-y-4">
      {plans.map((p) => {
        const isFree = p.id === "free";
        return (
          <div key={p.id} className="rounded-xl border border-border p-4">
            <div className="flex items-center justify-between mb-3">
              <Input
                className="max-w-[220px]"
                value={getVal(p.id, "name", p.name)}
                onChange={(e) => setField(p.id, "name", e.target.value)}
                data-testid={`plan-name-${p.id}`}
              />
              {!isFree && (
                <div className="flex gap-2">
                  <div>
                    <Label className="mb-1 block text-xs">Monthly ($)</Label>
                    <Input
                      type="number"
                      className="w-24"
                      value={getVal(p.id, "price_monthly", p.price_monthly)}
                      onChange={(e) => setField(p.id, "price_monthly", Number(e.target.value))}
                      data-testid={`plan-monthly-${p.id}`}
                    />
                  </div>
                  <div>
                    <Label className="mb-1 block text-xs">Yearly ($)</Label>
                    <Input
                      type="number"
                      className="w-24"
                      value={getVal(p.id, "price_yearly", p.price_yearly)}
                      onChange={(e) => setField(p.id, "price_yearly", Number(e.target.value))}
                      data-testid={`plan-yearly-${p.id}`}
                    />
                  </div>
                </div>
              )}
            </div>
            <Label className="mb-1 block text-xs">Features (one per line)</Label>
            <Textarea
              rows={5}
              value={(getVal(p.id, "features", p.features) || []).join("\n")}
              onChange={(e) =>
                setField(p.id, "features", e.target.value.split("\n").map((s) => s.trim()).filter(Boolean))
              }
              data-testid={`plan-features-${p.id}`}
            />
            <div className="mt-2">
              <Label className="mb-1 block text-xs">Button label</Label>
              <Input
                value={getVal(p.id, "cta", p.cta || "")}
                onChange={(e) => setField(p.id, "cta", e.target.value)}
                data-testid={`plan-cta-${p.id}`}
              />
            </div>
          </div>
        );
      })}
      <p className="text-xs text-muted-foreground">
        Prices here are shown on the landing page and dashboard. Stripe still charges what your Stripe prices (created by <code>setup_stripe.py</code>) are configured for — use the coupon field below to give a real discount at checkout.
      </p>
    </div>
  );
}

function StripeStatus() {
  const { data, isFetching, isError, error, refetch } = useQuery({
    queryKey: ["stripe-status"],
    queryFn: async () => (await api.get("/admin/stripe-status")).data,
    staleTime: 60_000,
  });
  const missing = data?.missing || [];
  const configured = data?.configured;
  const mode = data?.mode;
  const lookupKeys = data?.lookup_keys || {};
  const backendError = data?.error;
  const showSuccess = !isFetching && !isError && configured && !backendError && missing.length === 0;
  const showMissing = !isFetching && !isError && configured && !backendError && missing.length > 0;
  return (
    <div data-testid="stripe-status">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {isFetching ? (
            <RefreshCw size={16} className="text-muted-foreground animate-spin" />
          ) : isError ? (
            <XCircle size={16} className="text-red-500" />
          ) : backendError ? (
            <XCircle size={16} className="text-red-500" />
          ) : !configured ? (
            <XCircle size={16} className="text-red-500" />
          ) : missing.length === 0 ? (
            <CheckCircle2 size={16} className="text-green-500" />
          ) : (
            <AlertCircle size={16} className="text-yellow-500" />
          )}
          <span className="text-sm">
            {isFetching && "Checking Stripe…"}
            {!isFetching && isError && (error?.response?.data?.detail || "Could not reach the backend.")}
            {!isFetching && !isError && backendError && `Stripe error (${mode} mode)`}
            {!isFetching && !isError && !backendError && !configured && "STRIPE_SECRET_KEY is not set on the server."}
            {showSuccess && (<>All 4 plan prices found in <strong className="uppercase">{mode}</strong> mode.</>)}
            {showMissing && (<>{missing.length} price(s) missing in <strong className="uppercase">{mode}</strong> mode.</>)}
          </span>
        </div>
        <Button size="sm" variant="ghost" onClick={() => refetch()} data-testid="refresh-stripe-status" disabled={isFetching}>
          <RefreshCw size={13} className={isFetching ? "animate-spin" : ""} /> Refresh
        </Button>
      </div>
      {backendError && (
        <div className="p-2 rounded bg-red-500/10 border border-red-500/30 text-xs text-red-500 mb-2">{backendError}</div>
      )}
      {configured && !backendError && (
        <div className="grid grid-cols-2 gap-2">
          {Object.entries(lookupKeys).map(([k, v]) => (
            <div key={k} className="flex items-center justify-between text-xs bg-secondary/40 rounded px-2 py-1.5">
              <span className="font-mono">{k}</span>
              {v.exists ? (
                <span className="flex items-center gap-1 text-green-500"><CheckCircle2 size={12} /> ${v.amount}</span>
              ) : (
                <span className="flex items-center gap-1 text-red-500"><XCircle size={12} /> missing</span>
              )}
            </div>
          ))}
        </div>
      )}
      {data?.action && (missing.length > 0 || backendError) && (
        <p className="text-xs text-muted-foreground mt-2">{data.action}</p>
      )}
    </div>
  );
}

export default function AdminIntegrations() {
  const qc = useQueryClient();
  const [s, setS] = useState(null);
  const { data, isLoading } = useQuery({ queryKey: ["admin-settings"], queryFn: async () => (await api.get("/admin/settings")).data });
  const { data: plans = [] } = useQuery({ queryKey: ["plans"], queryFn: async () => (await api.get("/plans")).data });
  useEffect(() => { if (data) setS({ ...data, plans_override: data.plans_override || [] }); }, [data]);

  const save = useMutation({
    mutationFn: () => api.put("/admin/settings", {
      recaptcha_site_key: s.recaptcha_site_key, recaptcha_secret_key: s.recaptcha_secret_key,
      resend_api_key: s.resend_api_key, sender_email: s.sender_email, google_places_api_key: s.google_places_api_key,
      checkout_coupon_id: s.checkout_coupon_id, promo_banner: s.promo_banner, plans_override: s.plans_override,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-settings"] });
      qc.invalidateQueries({ queryKey: ["plans"] });
      toast.success("Platform settings saved");
    },
    onError: (e) => toast.error(formatApiError(e)),
  });

  if (isLoading || !s) return <Skeleton className="h-64 rounded-2xl" />;
  const set = (k, v) => setS((x) => ({ ...x, [k]: v }));

  return (
    <div className="p-6 rounded-2xl border border-primary/30 bg-card lg:col-span-2" data-testid="admin-integrations">
      <div className="flex items-center gap-2 mb-1"><KeyRound size={18} className="text-primary" /><h3 className="font-heading font-semibold">Platform Integrations</h3><span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-primary/15 text-primary font-medium">Admin</span></div>
      <p className="text-sm text-muted-foreground mb-5">Manage API keys, prices and promotions for the whole platform. Keys are stored securely.</p>

      <Group icon={DollarSign} title="Plans & pricing" desc="Displayed everywhere prices show up. Change any name, price or feature list — takes effect the moment you save.">
        <PlanEditor
          plans={plans}
          overrides={s.plans_override}
          setOverrides={(v) => set("plans_override", v)}
        />
      </Group>

      <Group icon={CreditCard} title="Stripe status" desc="Live check of the Stripe prices your Upgrade buttons rely on. If any are missing, run `python setup_stripe.py` on the backend once.">
        <StripeStatus />
      </Group>

      <Group icon={Ticket} title="Sale / Giveaway" desc="Show a banner on the landing page and auto-apply a Stripe coupon on every checkout. Customers can still type their own promo code if this is left blank.">
        <div>
          <Label className="mb-1.5 block text-xs">Banner text (leave blank to hide)</Label>
          <Input value={s.promo_banner || ""} onChange={(e) => set("promo_banner", e.target.value)} placeholder="🎉 Launch week — 30% off with code TESTIFY30" data-testid="set-promo-banner" />
        </div>
        <div>
          <Label className="mb-1.5 block text-xs">Auto-applied Stripe coupon ID</Label>
          <Input value={s.checkout_coupon_id || ""} onChange={(e) => set("checkout_coupon_id", e.target.value)} placeholder="e.g. TESTIFY30 (created in Stripe → Products → Coupons)" data-testid="set-coupon-id" />
          <p className="text-xs text-muted-foreground mt-1">Create the coupon in Stripe → Products → Coupons. Paste the coupon ID (not the code) here.</p>
        </div>
      </Group>

      <Group icon={ShieldCheck} title="Google reCAPTCHA v2" desc="Protect public testimonial forms from spam. Register a v2 Checkbox site at google.com/recaptcha/admin.">
        <div><Label className="mb-1.5 block text-xs">Site key</Label><Input value={s.recaptcha_site_key || ""} onChange={(e) => set("recaptcha_site_key", e.target.value)} placeholder="6Lc..." data-testid="set-recaptcha-site" /></div>
        <div><Label className="mb-1.5 block text-xs">Secret key</Label><Input type="password" value={s.recaptcha_secret_key || ""} onChange={(e) => set("recaptcha_secret_key", e.target.value)} placeholder="6Lc..." data-testid="set-recaptcha-secret" /></div>
      </Group>

      <Group icon={Mail} title="Resend (Email)" desc="Send new-testimonial alerts and password reset emails. Verify a domain at resend.com/domains to email anyone.">
        <div><Label className="mb-1.5 block text-xs">API key</Label><Input type="password" value={s.resend_api_key || ""} onChange={(e) => set("resend_api_key", e.target.value)} placeholder="re_..." data-testid="set-resend-key" /></div>
        <div><Label className="mb-1.5 block text-xs">Sender email</Label><Input value={s.sender_email || ""} onChange={(e) => set("sender_email", e.target.value)} placeholder="hello@yourdomain.com" data-testid="set-sender" /></div>
      </Group>

      <Group icon={MapPin} title="Google Places (Review import)" desc="Enable pulling real Google reviews. Create a key with the Places API enabled at console.cloud.google.com.">
        <div><Label className="mb-1.5 block text-xs">API key</Label><Input type="password" value={s.google_places_api_key || ""} onChange={(e) => set("google_places_api_key", e.target.value)} placeholder="AIza..." data-testid="set-google-key" /></div>
      </Group>

      <Button className="gap-1.5" onClick={() => save.mutate()} disabled={save.isPending} data-testid="save-integrations"><Save size={15} /> Save all settings</Button>
    </div>
  );
}
