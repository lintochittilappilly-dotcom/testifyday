import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { formatApiError } from "@/lib/api";
import { PageHeader, EmptyState } from "@/components/dashboard/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Send, Loader2, RotateCw, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

function UsageBar({ usage }) {
  const pct = usage?.limit_30d ? Math.min(100, Math.round((usage.sent_30d / usage.limit_30d) * 100)) : 0;
  return (
    <div className="rounded-2xl border border-border bg-card p-5" data-testid="request-usage">
      <div className="flex items-baseline justify-between mb-2">
        <p className="text-sm font-medium">Review requests this month</p>
        <p className="text-sm text-muted-foreground">
          <span className="text-foreground font-semibold">{usage?.sent_30d ?? 0}</span> / {usage?.limit_30d ?? 0}
        </p>
      </div>
      <div className="h-2 rounded-full bg-secondary overflow-hidden">
        <div className="h-full bg-primary transition-all" style={{ width: `${pct}%` }} />
      </div>
      <p className="text-xs text-muted-foreground mt-2 capitalize">{usage?.plan || "free"} plan · resets 30 days after each send</p>
    </div>
  );
}

export default function Requests() {
  const qc = useQueryClient();
  const [collectionId, setCollectionId] = useState("");
  const [emails, setEmails] = useState("");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [skipped, setSkipped] = useState(null);

  const { data: cols = [] } = useQuery({ queryKey: ["collections"], queryFn: async () => (await api.get("/collections")).data });
  const { data, isLoading } = useQuery({ queryKey: ["request-emails"], queryFn: async () => (await api.get("/request-emails")).data });
  const published = cols.filter((c) => c.published);
  const selected = collectionId || published[0]?.id || "";

  const send = useMutation({
    mutationFn: () =>
      api.post("/request-emails", {
        collection_id: selected,
        emails,
        subject: subject || undefined,
        message: message || undefined,
      }),
    onSuccess: (r) => {
      const queued = r.data.queued;
      toast.success(`Queued ${queued} ${queued === 1 ? "email" : "emails"}`);
      setSkipped(r.data.skipped);
      setEmails("");
      setMessage("");
      setSubject("");
      qc.invalidateQueries({ queryKey: ["request-emails"] });
      setTimeout(() => qc.invalidateQueries({ queryKey: ["request-emails"] }), 3000);
    },
    onError: (e) => toast.error(formatApiError(e)),
  });

  const retry = useMutation({
    mutationFn: (id) => api.post(`/request-emails/${id}/retry`),
    onSuccess: (r) => {
      toast.success(`Retrying ${r.data.retried} ${r.data.retried === 1 ? "recipient" : "recipients"}`);
      qc.invalidateQueries({ queryKey: ["request-emails"] });
    },
    onError: (e) => toast.error(formatApiError(e)),
  });

  const campaigns = data?.campaigns || [];
  const count = emails.split(/[\s,;]+/).filter(Boolean).length;

  return (
    <div>
      <PageHeader title="Review requests" subtitle="Email customers a link to your collection page — no copy-paste, no manual follow-up." />

      <div className="grid lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 rounded-2xl border border-border bg-card p-5">
          <div className="space-y-4">
            <div>
              <Label className="mb-1.5 block">Collection page</Label>
              <select
                className="w-full h-10 rounded-md border border-border bg-background px-3 text-sm"
                value={selected}
                onChange={(e) => setCollectionId(e.target.value)}
                data-testid="request-collection-select"
              >
                {published.length === 0 && <option value="">No published pages yet</option>}
                {published.map((c) => <option key={c.id} value={c.id}>{c.name} · /t/{c.slug}</option>)}
              </select>
              {published.length === 0 && (
                <p className="text-xs text-muted-foreground mt-1">Publish a collection page first — the email links straight to it.</p>
              )}
            </div>

            <div>
              <Label className="mb-1.5 block">Recipients <span className="text-muted-foreground font-normal">(one per line or comma separated)</span></Label>
              <Textarea
                rows={4}
                value={emails}
                onChange={(e) => setEmails(e.target.value)}
                placeholder={"priya@northwind.com\nmarcus@brightlabs.io"}
                data-testid="request-emails-input"
              />
              <p className="text-xs text-muted-foreground mt-1">
                {count} address{count === 1 ? "" : "es"} detected · duplicates, existing customers and invalid addresses are skipped automatically.
              </p>
            </div>

            <div className="grid sm:grid-cols-2 gap-3">
              <div>
                <Label className="mb-1.5 block">Subject <span className="text-muted-foreground font-normal">(optional)</span></Label>
                <Input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Quick favour, 60 seconds" data-testid="request-subject" />
              </div>
              <div>
                <Label className="mb-1.5 block">Link text is filled in for you</Label>
                <p className="text-xs text-muted-foreground h-10 flex items-center">We add a “Leave a testimonial” button to every email.</p>
              </div>
            </div>

            <div>
              <Label className="mb-1.5 block">Message <span className="text-muted-foreground font-normal">(optional)</span></Label>
              <Textarea rows={4} value={message} onChange={(e) => setMessage(e.target.value)}
                placeholder="Hi! Would you mind sharing a couple of lines about working with us? It takes about a minute and helps other people decide."
                data-testid="request-message" />
            </div>

            <Button className="gap-1.5" disabled={!selected || count === 0 || send.isPending} onClick={() => send.mutate()} data-testid="request-send">
              {send.isPending ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
              Send request{count > 1 ? `s (${count})` : ""}
            </Button>

            {skipped && (skipped.already_testimonial?.length || skipped.invalid?.length || skipped.over_quota?.length) > 0 && (
              <div className="rounded-xl border border-border bg-secondary/40 p-3 text-xs space-y-1" data-testid="request-skipped">
                <p className="flex items-center gap-1.5 font-medium"><AlertTriangle size={13} className="text-primary" /> Not sent</p>
                {skipped.already_testimonial?.length > 0 && <p className="text-muted-foreground">Already left a testimonial: {skipped.already_testimonial.join(", ")}</p>}
                {skipped.invalid?.length > 0 && <p className="text-muted-foreground">Invalid address: {skipped.invalid.join(", ")}</p>}
                {skipped.over_quota?.length > 0 && <p className="text-muted-foreground">Over this month’s quota: {skipped.over_quota.join(", ")}</p>}
              </div>
            )}
          </div>
        </div>

        <div className="space-y-5">
          {data?.usage && <UsageBar usage={data.usage} />}
          <div className="rounded-2xl border border-border bg-card p-5 text-sm text-muted-foreground">
            <p className="font-medium text-foreground mb-2">How this stays out of spam</p>
            <ul className="space-y-1.5 list-disc pl-4 text-xs leading-relaxed">
              <li>One email per person, never a bulk blast from your own inbox.</li>
              <li>Existing customers who already left a testimonial are skipped.</li>
              <li>Any failure is retried from the campaign row, so nothing is lost.</li>
            </ul>
          </div>
        </div>
      </div>

      <h2 className="font-heading text-lg font-semibold mt-10 mb-3">Campaigns</h2>
      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : campaigns.length === 0 ? (
        <EmptyState icon={Send} title="No review requests sent yet" description="Send your first batch above — every recipient gets a personal link to your collection page." />
      ) : (
        <div className="rounded-2xl border border-border bg-card divide-y divide-border" data-testid="request-campaigns">
          {campaigns.map((c) => (
            <div key={c.id} className="p-4 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-medium truncate">{c.subject || "Testimonial request"}</p>
                <p className="text-xs text-muted-foreground">
                  {new Date(c.created_at).toLocaleString()} · {c.sent_count || 0} sent
                  {c.failed_count ? ` · ${c.failed_count} failed` : ""} · /t/{c.collection_slug}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-xs px-2 py-0.5 rounded-full ${c.status === "completed" ? "bg-secondary text-muted-foreground" : "bg-primary/15 text-primary"}`}>{c.status}</span>
                {c.failed_count > 0 && (
                  <Button size="sm" variant="outline" className="gap-1" onClick={() => retry.mutate(c.id)} data-testid={`retry-${c.id}`}>
                    <RotateCw size={13} /> Retry
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
