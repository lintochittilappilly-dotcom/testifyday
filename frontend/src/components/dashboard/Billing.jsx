import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api, { formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Check, Crown, Loader2, Zap, Settings2 } from "lucide-react";
import { toast } from "sonner";

export default function Billing({ currentPlan = "free" }) {
  const [loadingKey, setLoadingKey] = useState(null);
  const [portalLoading, setPortalLoading] = useState(false);
  const [cycle, setCycle] = useState("yearly"); // monthly | yearly
  const { data: plans = [], isLoading } = useQuery({ queryKey: ["plans"], queryFn: async () => (await api.get("/plans")).data });

  const upgrade = async (lookup_key) => {
    if (!lookup_key) return;
    setLoadingKey(lookup_key);
    try {
      const { data } = await api.post("/payments/checkout", { lookup_key, origin_url: window.location.origin });
      window.location.href = data.checkout_url;
    } catch (e) { toast.error(formatApiError(e)); setLoadingKey(null); }
  };

  const openPortal = async () => {
    setPortalLoading(true);
    try {
      const { data } = await api.post("/payments/portal", { origin_url: window.location.origin });
      window.location.href = data.portal_url;
    } catch (e) { toast.error(formatApiError(e)); setPortalLoading(false); }
  };

  const isYearly = cycle === "yearly";

  return (
    <div className="p-6 rounded-2xl border border-border bg-card lg:col-span-2" data-testid="billing">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-1">
        <div className="flex items-center gap-2"><Crown size={18} className="text-primary" /><h3 className="font-heading font-semibold">Plans & billing</h3></div>
        <div className="flex items-center gap-1 p-1 rounded-full bg-secondary/70" data-testid="cycle-toggle">
          <button onClick={() => setCycle("monthly")} className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${!isYearly ? "bg-background shadow-sm" : "text-muted-foreground"}`} data-testid="cycle-monthly">Monthly</button>
          <button onClick={() => setCycle("yearly")} className={`px-3 py-1 rounded-full text-xs font-medium transition-colors flex items-center gap-1 ${isYearly ? "bg-background shadow-sm" : "text-muted-foreground"}`} data-testid="cycle-yearly">Yearly <span className="text-primary font-semibold">-17%</span></button>
        </div>
      </div>
      <div className="flex items-center gap-3 mb-5">
        <p className="text-sm text-muted-foreground">You're currently on the <span className="capitalize font-medium text-foreground">{currentPlan}</span> plan.</p>
        {currentPlan !== "free" && (
          <Button variant="outline" size="sm" className="gap-1.5 h-8" onClick={openPortal} disabled={portalLoading} data-testid="manage-subscription">
            {portalLoading ? <Loader2 className="animate-spin" size={14} /> : <><Settings2 size={14} /> Manage subscription</>}
          </Button>
        )}
      </div>

      {isLoading ? <Skeleton className="h-52 rounded-2xl" /> : (
        <div className="grid md:grid-cols-3 gap-4">
          {plans.map((p) => {
            const isCurrent = p.id === currentPlan;
            const isPro = p.id === "pro";
            const price = isYearly ? p.price_yearly : p.price_monthly;
            const lookup = isYearly ? p.lookup_yearly : p.lookup_monthly;
            const perMonth = isYearly && price > 0 ? (price / 12).toFixed(2) : null;
            return (
              <div key={p.id} className={`p-5 rounded-2xl border flex flex-col ${isPro ? "border-primary bg-primary/[0.05]" : "border-border"}`} data-testid={`plan-${p.id}`}>
                <div className="flex items-center justify-between mb-1">
                  <h4 className="font-heading font-semibold">{p.name}</h4>
                  {isPro && <span className="text-xs px-2 py-0.5 rounded-full bg-primary/15 text-primary font-medium">Popular</span>}
                </div>
                <div className="flex items-end gap-1 mb-1">
                  <span className="font-heading text-3xl font-bold">${isYearly ? price : price}</span>
                  {price > 0 && <span className="text-muted-foreground text-sm mb-1">/{isYearly ? "yr" : "mo"}</span>}
                </div>
                <div className="h-4 mb-3">{perMonth ? <span className="text-xs text-primary">≈ ${perMonth}/mo · 2 months free</span> : null}</div>
                <ul className="space-y-2 mb-5 flex-1">
                  {p.features.map((f) => <li key={f} className="flex items-start gap-2 text-sm text-muted-foreground"><Check size={15} className="text-primary mt-0.5 flex-shrink-0" /> {f}</li>)}</ul>
                {isCurrent ? (
                  <Button variant="secondary" disabled className="w-full" data-testid={`current-${p.id}`}>Current plan</Button>
                ) : lookup ? (
                  <Button className="w-full gap-1.5" onClick={() => upgrade(lookup)} disabled={loadingKey === lookup} data-testid={`upgrade-${p.id}`}>
                    {loadingKey === lookup ? <Loader2 className="animate-spin" size={16} /> : <><Zap size={15} /> Upgrade to {p.name}</>}
                  </Button>
                ) : (
                  <Button variant="outline" disabled className="w-full">Free forever</Button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
