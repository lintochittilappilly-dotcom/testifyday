import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { mediaUrl, formatApiError } from "@/lib/api";
import { PageHeader, EmptyState, StatusBadge, GridSkeleton } from "@/components/dashboard/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { MessageSquareQuote, Search, Star, Video, Check, X, Archive, Trash2, MoreVertical, Play, DownloadCloud, Heart } from "lucide-react";
import { toast } from "sonner";
import ImportReviewDialog from "@/components/dashboard/ImportReviewDialog";

const TABS = [["all", "All"], ["pending", "Pending"], ["approved", "Approved"], ["rejected", "Rejected"], ["archived", "Archived"]];

export default function Testimonials() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [tab, setTab] = useState("all");
  const [search, setSearch] = useState("");
  const [type, setType] = useState("all");
  const [importOpen, setImportOpen] = useState(false);

  const { data: ws } = useQuery({ queryKey: ["workspace"], queryFn: async () => (await api.get("/workspace")).data });

  const params = {};
  if (tab !== "all") params.status = tab;
  if (type !== "all") params.type = type;
  if (search) params.search = search;

  const { data: items = [], isLoading } = useQuery({
    queryKey: ["testimonials", tab, type, search],
    queryFn: async () => (await api.get("/testimonials", { params })).data,
  });
  const { data: tags = [] } = useQuery({ queryKey: ["tags"], queryFn: async () => (await api.get("/tags")).data });

  const invalidate = () => { qc.invalidateQueries({ queryKey: ["testimonials"] }); qc.invalidateQueries({ queryKey: ["overview"] }); };

  const setStatus = useMutation({
    mutationFn: ({ id, status }) => api.post(`/testimonials/${id}/status`, { status }),
    onSuccess: (_, v) => { invalidate(); toast.success(`Testimonial ${v.status}`); },
    onError: (e) => toast.error(formatApiError(e)),
  });
  const feature = useMutation({
    mutationFn: (id) => api.post(`/testimonials/${id}/feature`),
    onSuccess: () => { invalidate(); toast.success("Updated featured status"); },
  });
  const del = useMutation({
    mutationFn: (id) => api.delete(`/testimonials/${id}`),
    onSuccess: () => { invalidate(); toast.success("Testimonial deleted"); },
  });

  return (
    <div>
      <PageHeader title="Testimonials" subtitle="Approve, feature, tag, and manage every testimonial you collect.">
        {ws?.slug && (
          <Button variant="outline" className="gap-1.5" onClick={() => window.open(`${window.location.origin}/wall/${ws.slug}`, "_blank")} data-testid="wall-of-love-btn">
            <Heart size={16} /> Wall of Love
          </Button>
        )}
        <Button className="gap-1.5" onClick={() => setImportOpen(true)} data-testid="import-review-btn">
          <DownloadCloud size={16} /> Import review
        </Button>
      </PageHeader>

      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search testimonials..." className="pl-9 h-10" data-testid="testimonial-search" />
        </div>
        <Select value={type} onValueChange={setType}>
          <SelectTrigger className="w-full sm:w-40 h-10" data-testid="type-filter"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All types</SelectItem>
            <SelectItem value="video">Video</SelectItem>
            <SelectItem value="text">Written</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Tabs value={tab} onValueChange={setTab} className="mb-6">
        <TabsList className="flex-wrap h-auto">
          {TABS.map(([v, l]) => <TabsTrigger key={v} value={v} data-testid={`tab-${v}`}>{l}</TabsTrigger>)}
        </TabsList>
      </Tabs>

      {isLoading ? <GridSkeleton /> : items.length === 0 ? (
        <EmptyState icon={MessageSquareQuote} title="No testimonials here"
          description="When customers submit testimonials matching this filter, they'll show up here.">
          <Button onClick={() => navigate("/dashboard/collections")}>Share your collection link</Button>
        </EmptyState>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((t) => (
            <div key={t.id} className="p-5 rounded-2xl border border-border bg-card flex flex-col group hover:border-primary/30 transition-colors" data-testid={`testimonial-card-${t.id}`}>
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2.5 min-w-0">
                  <Avatar className="w-10 h-10"><AvatarImage src={mediaUrl(t.avatar_url)} /><AvatarFallback className="bg-primary/10 text-primary text-sm">{t.first_name?.[0]}</AvatarFallback></Avatar>
                  <div className="min-w-0">
                    <div className="font-medium text-sm truncate">{t.first_name} {t.last_name}</div>
                    <div className="text-xs text-muted-foreground truncate">{[t.role, t.company].filter(Boolean).join(" · ")}</div>
                  </div>
                </div>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild><button className="text-muted-foreground p-1" data-testid={`menu-${t.id}`}><MoreVertical size={16} /></button></DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={() => navigate(`/dashboard/testimonials/${t.id}`)}>View & edit</DropdownMenuItem>
                    <DropdownMenuItem onClick={() => feature.mutate(t.id)}><Star size={14} className="mr-2" /> {t.featured ? "Unfeature" : "Feature"}</DropdownMenuItem>
                    <DropdownMenuItem onClick={() => setStatus.mutate({ id: t.id, status: "archived" })}><Archive size={14} className="mr-2" /> Archive</DropdownMenuItem>
                    <DropdownMenuItem className="text-destructive" onClick={() => del.mutate(t.id)}><Trash2 size={14} className="mr-2" /> Delete</DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>

              {t.video_url ? (
                <div className="relative rounded-xl overflow-hidden bg-black mb-3 cursor-pointer" style={{ aspectRatio: "16/10" }} onClick={() => navigate(`/dashboard/testimonials/${t.id}`)}>
                  <video src={mediaUrl(t.video_url)} className="w-full h-full object-cover" preload="metadata" />
                  <div className="absolute inset-0 flex items-center justify-center bg-black/30"><div className="w-10 h-10 rounded-full bg-white/90 flex items-center justify-center"><Play size={16} className="text-black ml-0.5" /></div></div>
                </div>
              ) : t.image_url ? (
                <div className="rounded-xl overflow-hidden bg-black mb-3 cursor-pointer" style={{ aspectRatio: "16/10" }} onClick={() => navigate(`/dashboard/testimonials/${t.id}`)}>
                  <img src={mediaUrl(t.image_url)} alt="" className="w-full h-full object-cover" />
                </div>
              ) : (
                <>
                  {t.rating ? <div className="flex gap-0.5 mb-2">{[1,2,3,4,5].map(i => <Star key={i} size={13} className={i <= t.rating ? "text-primary" : "text-muted"} fill={i <= t.rating ? "currentColor" : "transparent"} />)}</div> : null}
                  <p className="text-sm text-muted-foreground line-clamp-4 mb-3 flex-1">{t.text}</p>
                </>
              )}

              <div className="flex items-center justify-between gap-2 mt-auto pt-3 border-t border-border">
                <div className="flex items-center gap-1.5">
                  <StatusBadge status={t.status} />
                  {t.featured && <Star size={13} className="text-primary" fill="currentColor" />}
                </div>
                {t.status === "pending" ? (
                  <div className="flex gap-1.5">
                    <Button size="sm" variant="secondary" className="h-7 gap-1 px-2" onClick={() => setStatus.mutate({ id: t.id, status: "approved" })} data-testid={`approve-${t.id}`}><Check size={13} /></Button>
                    <Button size="sm" variant="ghost" className="h-7 gap-1 px-2 text-muted-foreground" onClick={() => setStatus.mutate({ id: t.id, status: "rejected" })} data-testid={`reject-${t.id}`}><X size={13} /></Button>
                  </div>
                ) : (
                  <Button size="sm" variant="ghost" className="h-7 text-muted-foreground" onClick={() => navigate(`/dashboard/testimonials/${t.id}`)}>Details</Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
      <ImportReviewDialog open={importOpen} onClose={() => setImportOpen(false)} />
    </div>
  );
}
