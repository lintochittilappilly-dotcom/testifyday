import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { formatApiError } from "@/lib/api";
import { PageHeader, EmptyState } from "@/components/dashboard/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Webhook, Plus, Trash2, Send, Copy, Lock, CheckCircle2, XCircle, Clock } from "lucide-react";
import { toast } from "sonner";

const EVENT_LABELS = {
  "testimonial.submitted": "New testimonial submitted",
  "testimonial.approved": "Testimonial approved",
  "testimonial.updated": "Testimonial edited",
  "request_email.sent": "Review-request batch sent",
};

const ALL_EVENTS = Object.keys(EVENT_LABELS);

function StatusPill({ delivery }) {
  if (!delivery) return <span className="text-xs text-muted-foreground flex items-center gap-1"><Clock size={12} /> No deliveries yet</span>;
  const map = {
    delivered: { icon: CheckCircle2, cls: "text-emerald-500", label: `Delivered${delivery.response_status ? ` (${delivery.response_status})` : ""}` },
    retrying: { icon: Clock, cls: "text-amber-500", label: `Retrying (attempt ${delivery.attempts || 1})` },
    pending: { icon: Clock, cls: "text-muted-foreground", label: "Queued" },
    failed: { icon: XCircle, cls: "text-destructive", label: `Failed${delivery.response_status ? ` (${delivery.response_status})` : ""}` },
    skipped: { icon: XCircle, cls: "text-muted-foreground", label: "Skipped" },
  };
  const item = map[delivery.status] || map.pending;
  const Icon = item.icon;
  return <span className={`text-xs flex items-center gap-1 ${item.cls}`}><Icon size={12} /> {item.label}</span>;
}

export default function Webhooks() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState("");
  const [events, setEvents] = useState(["*"]);
  const [secret, setSecret] = useState(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["webhooks"],
    queryFn: async () => (await api.get("/webhooks")).data,
    retry: false,
  });

  const create = useMutation({
    mutationFn: () => api.post("/webhooks", { url, events }),
    onSuccess: (r) => {
      setSecret({ id: r.data.id, value: r.data.secret });
      setOpen(false);
      setUrl("");
      setEvents(["*"]);
      qc.invalidateQueries({ queryKey: ["webhooks"] });
      toast.success("Endpoint created — copy the signing secret now");
    },
    onError: (e) => toast.error(formatApiError(e)),
  });

  const test = useMutation({
    mutationFn: (id) => api.post(`/webhooks/${id}/test`),
    onSuccess: (r) => {
      const d = r.data;
      if (d.ok) toast.success("Delivered — check your receiver");
      else toast.error(d.detail || `Delivery failed${d.response_status ? ` (${d.response_status})` : ""}${d.error ? `: ${d.error}` : ""}`);
      qc.invalidateQueries({ queryKey: ["webhooks"] });
    },
    onError: (e) => toast.error(formatApiError(e)),
  });

  const toggle = useMutation({
    mutationFn: ({ id, active }) => api.put(`/webhooks/${id}`, { active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["webhooks"] }),
    onError: (e) => toast.error(formatApiError(e)),
  });

  const remove = useMutation({
    mutationFn: (id) => api.delete(`/webhooks/${id}`),
    onSuccess: () => { toast.success("Endpoint deleted"); qc.invalidateQueries({ queryKey: ["webhooks"] }); },
    onError: (e) => toast.error(formatApiError(e)),
  });

  const rotate = useMutation({
    mutationFn: (id) => api.post(`/webhooks/${id}/rotate-secret`),
    onSuccess: (r, id) => setSecret({ id, value: r.data.secret }),
    onError: (e) => toast.error(formatApiError(e)),
  });

  const upgradeNeeded = error?.response?.status === 402;
  const endpoints = data?.endpoints || [];
  const lastByEndpoint = {};
  for (const d of data?.deliveries || []) {
    if (!lastByEndpoint[d.endpoint_id]) lastByEndpoint[d.endpoint_id] = d;
  }

  return (
    <div>
      <PageHeader title="Webhooks" subtitle="Send every testimonial event to Zapier, Make, Slack relays or your own service.">
        <Button className="gap-1.5" onClick={() => setOpen((v) => !v)} data-testid="new-webhook-btn"><Plus size={16} /> Add endpoint</Button>
      </PageHeader>

      {upgradeNeeded ? (
        <EmptyState icon={Lock} title="Webhooks are a Pro feature"
          description="Upgrade to Pro to connect Zapier, Make or your own endpoint. Every delivery is signed so your receiver can verify it.">
          <Button onClick={() => (window.location.href = "/dashboard/settings")}>See plans</Button>
        </EmptyState>
      ) : isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : (
        <>
          {open && (
            <div className="rounded-2xl border border-border bg-card p-5 mb-5 space-y-4">
              <div>
                <Label className="mb-1.5 block">Endpoint URL</Label>
                <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://hooks.zapier.com/hooks/catch/123456/abcdef/" data-testid="webhook-url-input" />
              </div>
              <div>
                <Label className="mb-1.5 block">Events</Label>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => setEvents(["*"])}
                    className={`px-3 py-1.5 rounded-full text-xs border ${events.includes("*") ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground"}`}
                    data-testid="event-all"
                  >
                    All events
                  </button>
                  {ALL_EVENTS.map((e) => (
                    <button
                      key={e}
                      type="button"
                      onClick={() => setEvents((prev) => {
                        const rest = prev.filter((x) => x !== "*");
                        return rest.includes(e) ? (rest.filter((x) => x !== e).length ? rest.filter((x) => x !== e) : ["*"]) : [...rest, e];
                      })}
                      className={`px-3 py-1.5 rounded-full text-xs border ${events.includes(e) ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground"}`}
                      data-testid={`event-${e}`}
                    >
                      {EVENT_LABELS[e]}
                    </button>
                  ))}
                </div>
              </div>
              <Button disabled={!url.trim() || create.isPending} onClick={() => create.mutate()} data-testid="create-webhook">Create endpoint</Button>
            </div>
          )}

          {secret && (
            <div className="rounded-2xl border border-primary/40 bg-primary/5 p-5 mb-5" data-testid="webhook-secret">
              <p className="text-sm font-medium mb-1">Signing secret — shown once</p>
              <p className="text-xs text-muted-foreground mb-3">
                Verify every request: HMAC-SHA256 of <code className="font-mono">X-Testify-Timestamp + "." + rawBody</code> (keyed with your secret) must equal <code className="font-mono">X-Testify-Signature</code>.
              </p>
              <div className="flex items-center gap-2">
                <code className="flex-1 text-xs bg-background border border-border rounded-lg px-3 py-2 font-mono overflow-x-auto">{secret.value}</code>
                <Button size="sm" variant="outline" className="gap-1" onClick={() => { navigator.clipboard?.writeText(secret.value); toast.success("Copied"); }}>
                  <Copy size={13} /> Copy
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setSecret(null)}>Done</Button>
              </div>
            </div>
          )}

          {endpoints.length === 0 ? (
            <EmptyState icon={Webhook} title="No endpoints yet"
              description="Point Testify at a Zapier Catch Hook to create rows in a spreadsheet, ping Slack, or push testimonials into your CRM." />
          ) : (
            <div className="space-y-3" data-testid="webhook-list">
              {endpoints.map((ep) => (
                <div key={ep.id} className="rounded-2xl border border-border bg-card p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-mono truncate">{ep.url}</p>
                      <div className="flex flex-wrap items-center gap-2 mt-1">
                        <span className="text-xs text-muted-foreground">{ep.events?.[0] === "*" ? "All events" : ep.events.join(", ")}</span>
                        <span className="text-muted-foreground">·</span>
                        <StatusPill delivery={lastByEndpoint[ep.id]} />
                        {!ep.active && <span className="text-xs text-amber-500">Paused</span>}
                      </div>
                      {ep.description && <p className="text-xs text-muted-foreground mt-1">{ep.description}</p>}
                    </div>
                    <div className="flex items-center gap-2">
                      <Button size="sm" variant="outline" className="gap-1" onClick={() => test.mutate(ep.id)} disabled={test.isPending} data-testid={`test-webhook-${ep.id}`}>
                        <Send size={13} /> Send test
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => toggle.mutate({ id: ep.id, active: !ep.active })}>
                        {ep.active ? "Pause" : "Resume"}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => rotate.mutate(ep.id)} title="Rotate signing secret"><Lock size={14} /></Button>
                      <Button size="sm" variant="ghost" className="text-destructive" onClick={() => remove.mutate(ep.id)} data-testid={`delete-webhook-${ep.id}`}><Trash2 size={14} /></Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {data?.deliveries?.length > 0 && (
            <>
              <h2 className="font-heading text-lg font-semibold mt-8 mb-3">Recent deliveries</h2>
              <div className="rounded-2xl border border-border bg-card divide-y divide-border" data-testid="webhook-deliveries">
                {data.deliveries.slice(0, 8).map((d) => (
                  <div key={d.id} className="p-3 flex items-center justify-between gap-3 text-xs">
                    <span className="font-mono text-muted-foreground">{d.event}</span>
                    <span className="flex items-center gap-3">
                      <span className="text-muted-foreground">{new Date(d.created_at).toLocaleString()}</span>
                      <StatusPill delivery={d} />
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
