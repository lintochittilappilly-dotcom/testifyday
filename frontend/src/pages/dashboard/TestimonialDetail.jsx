import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { mediaUrl, formatApiError } from "@/lib/api";
import { StatusBadge } from "@/components/dashboard/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft, Check, X, Archive, Star, Trash2, Save, Plus, ShieldCheck, Star as StarIcon } from "lucide-react";
import { toast } from "sonner";
import { format } from "date-fns";

export default function TestimonialDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: t, isLoading } = useQuery({ queryKey: ["testimonial", id], queryFn: async () => (await api.get(`/testimonials/${id}`)).data });

  const [form, setForm] = useState(null);
  const [newTag, setNewTag] = useState("");
  useEffect(() => { if (t) setForm({ first_name: t.first_name, last_name: t.last_name, company: t.company, role: t.role, text: t.text, notes: t.notes || "" }); }, [t]);

  const invalidate = () => { qc.invalidateQueries({ queryKey: ["testimonial", id] }); qc.invalidateQueries({ queryKey: ["testimonials"] }); qc.invalidateQueries({ queryKey: ["overview"] }); };

  const save = useMutation({ mutationFn: (body) => api.put(`/testimonials/${id}`, body), onSuccess: () => { invalidate(); toast.success("Saved"); }, onError: (e) => toast.error(formatApiError(e)) });
  const setStatus = useMutation({ mutationFn: (status) => api.post(`/testimonials/${id}/status`, { status }), onSuccess: (_, s) => { invalidate(); toast.success(`Marked ${s}`); } });
  const feature = useMutation({ mutationFn: () => api.post(`/testimonials/${id}/feature`), onSuccess: () => { invalidate(); toast.success("Featured status updated"); } });
  const addTag = useMutation({ mutationFn: (tag) => api.post(`/testimonials/${id}/tags`, { tag }), onSuccess: () => { invalidate(); setNewTag(""); qc.invalidateQueries({ queryKey: ["tags"] }); } });
  const removeTag = useMutation({ mutationFn: (tag) => api.delete(`/testimonials/${id}/tags/${encodeURIComponent(tag)}`), onSuccess: () => invalidate() });
  const del = useMutation({ mutationFn: () => api.delete(`/testimonials/${id}`), onSuccess: () => { toast.success("Deleted"); navigate("/dashboard/testimonials"); } });

  if (isLoading || !form) return <div className="space-y-4"><Skeleton className="h-8 w-40" /><Skeleton className="h-96 rounded-2xl" /></div>;

  return (
    <div>
      <button onClick={() => navigate("/dashboard/testimonials")} className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground text-sm mb-6" data-testid="back-btn"><ArrowLeft size={16} /> Back to testimonials</button>

      <div className="flex flex-wrap items-center gap-2 mb-6">
        {t.status === "pending" && <>
          <Button size="sm" className="gap-1.5" onClick={() => setStatus.mutate("approved")} data-testid="detail-approve"><Check size={15} /> Approve</Button>
          <Button size="sm" variant="outline" className="gap-1.5" onClick={() => setStatus.mutate("rejected")} data-testid="detail-reject"><X size={15} /> Reject</Button>
        </>}
        {t.status !== "pending" && <Button size="sm" variant="outline" className="gap-1.5" onClick={() => setStatus.mutate(t.status === "approved" ? "pending" : "approved")}>{t.status === "approved" ? "Unapprove" : "Approve"}</Button>}
        <Button size="sm" variant="outline" className="gap-1.5" onClick={() => feature.mutate()} data-testid="detail-feature"><Star size={15} className={t.featured ? "text-primary" : ""} fill={t.featured ? "currentColor" : "transparent"} /> {t.featured ? "Featured" : "Feature"}</Button>
        <Button size="sm" variant="outline" className="gap-1.5" onClick={() => setStatus.mutate("archived")}><Archive size={15} /> Archive</Button>
        <Button size="sm" variant="ghost" className="gap-1.5 text-destructive ml-auto" onClick={() => del.mutate()} data-testid="detail-delete"><Trash2 size={15} /> Delete</Button>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {t.video_url && (
            <div className="rounded-2xl overflow-hidden bg-black border border-border"><video src={mediaUrl(t.video_url)} controls className="w-full max-h-[480px]" /></div>
          )}
          {!t.video_url && t.image_url && (
            <div className="rounded-2xl overflow-hidden bg-black border border-border"><img src={mediaUrl(t.image_url)} alt="" className="w-full max-h-[480px] object-contain" /></div>
          )}
          <div className="p-6 rounded-2xl border border-border bg-card space-y-4">
            <h3 className="font-heading font-semibold">Public content</h3>
            <div className="grid sm:grid-cols-2 gap-4">
              <div><Label className="mb-1.5 block">First name</Label><Input value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} data-testid="edit-first" /></div>
              <div><Label className="mb-1.5 block">Last name</Label><Input value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} data-testid="edit-last" /></div>
              <div><Label className="mb-1.5 block">Company</Label><Input value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} data-testid="edit-company" /></div>
              <div><Label className="mb-1.5 block">Role</Label><Input value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} data-testid="edit-role" /></div>
            </div>
            <div><Label className="mb-1.5 block">Testimonial text</Label><Textarea rows={5} value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} data-testid="edit-text" /></div>
            <Button className="gap-1.5" onClick={() => save.mutate(form)} data-testid="save-btn"><Save size={15} /> Save changes</Button>
          </div>

          <div className="p-6 rounded-2xl border border-border bg-card space-y-3">
            <h3 className="font-heading font-semibold">Internal notes</h3>
            <Textarea rows={3} value={form.notes} placeholder="Private notes, not shown publicly..." onChange={(e) => setForm({ ...form, notes: e.target.value })} data-testid="edit-notes" />
            <Button variant="outline" size="sm" onClick={() => save.mutate({ notes: form.notes })}>Save note</Button>
          </div>
        </div>

        <div className="space-y-6">
          <div className="p-6 rounded-2xl border border-border bg-card">
            <div className="flex items-center gap-3 mb-4">
              <Avatar className="w-12 h-12"><AvatarImage src={mediaUrl(t.avatar_url)} /><AvatarFallback className="bg-primary/10 text-primary">{t.first_name?.[0]}</AvatarFallback></Avatar>
              <div><div className="font-medium">{t.first_name} {t.last_name}</div><div className="text-xs text-muted-foreground">{t.email}</div></div>
            </div>
            <dl className="space-y-2.5 text-sm">
              <Row k="Status"><StatusBadge status={t.status} /></Row>
              {t.rating ? <Row k="Rating"><span className="flex gap-0.5">{[1,2,3,4,5].map(i => <StarIcon key={i} size={13} className={i <= t.rating ? "text-primary" : "text-muted"} fill={i <= t.rating ? "currentColor" : "transparent"} />)}</span></Row> : null}
              <Row k="Type">{t.video_url ? "Video" : t.image_url ? "Image" : "Written"}</Row>
              <Row k="Source">{t.source}</Row>
              <Row k="Submitted">{t.submitted_at && format(new Date(t.submitted_at), "MMM d, yyyy")}</Row>
              <Row k="Consent">{t.consent ? <span className="inline-flex items-center gap-1 text-emerald-500"><ShieldCheck size={14} /> Given</span> : "No"}</Row>
            </dl>
          </div>

          <div className="p-6 rounded-2xl border border-border bg-card">
            <h3 className="font-heading font-semibold mb-3">Tags</h3>
            <div className="flex flex-wrap gap-2 mb-3">
              {(t.tags || []).length === 0 && <span className="text-sm text-muted-foreground">No tags yet</span>}
              {(t.tags || []).map((tag) => (
                <Badge key={tag} variant="secondary" className="gap-1 pr-1" data-testid={`tag-${tag}`}>{tag}<button onClick={() => removeTag.mutate(tag)} className="hover:text-destructive"><X size={12} /></button></Badge>
              ))}
            </div>
            <div className="flex gap-2">
              <Input value={newTag} onChange={(e) => setNewTag(e.target.value)} placeholder="Add a tag" className="h-9" data-testid="tag-input" onKeyDown={(e) => { if (e.key === "Enter" && newTag.trim()) addTag.mutate(newTag.trim()); }} />
              <Button size="sm" variant="secondary" className="h-9 px-3" onClick={() => newTag.trim() && addTag.mutate(newTag.trim())} data-testid="add-tag-btn"><Plus size={15} /></Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({ k, children }) {
  return <div className="flex items-center justify-between"><dt className="text-muted-foreground">{k}</dt><dd className="font-medium">{children}</dd></div>;
}
