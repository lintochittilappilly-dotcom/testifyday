import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { formatApiError, mediaUrl } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import { PageHeader } from "@/components/dashboard/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { Save, Upload, Loader2, Sun, Moon, Crown } from "lucide-react";
import { toast } from "sonner";
import AdminIntegrations from "@/components/dashboard/AdminIntegrations";
import Billing from "@/components/dashboard/Billing";
import TeamMembers from "@/components/dashboard/TeamMembers";
import CustomDomain from "@/components/dashboard/CustomDomain";

function Card({ title, desc, children }) {
  return (
    <div className="p-6 rounded-2xl border border-border bg-card">
      <h3 className="font-heading font-semibold">{title}</h3>
      {desc && <p className="text-sm text-muted-foreground mt-0.5 mb-4">{desc}</p>}
      <div className={desc ? "" : "mt-4"}>{children}</div>
    </div>
  );
}

export default function Settings() {
  const { user, refreshUser } = useAuth();
  const { theme, setTheme } = useTheme();
  const qc = useQueryClient();
  const [name, setName] = useState(user?.name || "");
  const [ws, setWs] = useState(null);
  const [logoUploading, setLogoUploading] = useState(false);

  const { data: workspace, isLoading } = useQuery({ queryKey: ["workspace"], queryFn: async () => (await api.get("/workspace")).data });
  useEffect(() => { if (workspace) setWs(workspace); }, [workspace]);
  useEffect(() => { if (user) setName(user.name); }, [user]);

  const saveProfile = useMutation({ mutationFn: () => api.put("/auth/profile", { name }), onSuccess: async () => { await refreshUser(); toast.success("Profile updated"); }, onError: (e) => toast.error(formatApiError(e)) });
  const saveWs = useMutation({
    mutationFn: () => api.put("/workspace", { name: ws.name, primary_color: ws.primary_color, logo_url: ws.logo_url }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["workspace"] }); toast.success("Workspace updated"); }, onError: (e) => toast.error(formatApiError(e)),
  });

  const uploadLogo = async (e) => {
    const file = e.target.files?.[0]; if (!file) return;
    setLogoUploading(true);
    try { const fd = new FormData(); fd.append("file", file); const { data } = await api.post("/upload", fd, { headers: { "Content-Type": "multipart/form-data" } }); setWs((w) => ({ ...w, logo_url: data.url })); toast.success("Logo uploaded — remember to save"); }
    catch (err) { toast.error(formatApiError(err)); } finally { setLogoUploading(false); }
  };

  if (isLoading || !ws) return <div><PageHeader title="Settings" /><Skeleton className="h-64 rounded-2xl" /></div>;

  return (
    <div>
      <PageHeader title="Settings" subtitle="Manage your account, workspace, and branding." />
      <div className="grid lg:grid-cols-2 gap-6">
        <Card title="Profile" desc="Your personal account details.">
          <div className="flex items-center gap-4 mb-4">
            <Avatar className="w-16 h-16"><AvatarImage src={mediaUrl(user?.avatar)} /><AvatarFallback className="bg-primary/10 text-primary text-xl">{user?.name?.[0]}</AvatarFallback></Avatar>
            <div><div className="font-medium">{user?.email}</div><div className="text-xs text-muted-foreground capitalize">{user?.auth_provider} account</div></div>
          </div>
          <div className="space-y-2 mb-4"><Label>Full name</Label><Input value={name} onChange={(e) => setName(e.target.value)} data-testid="settings-name" /></div>
          <Button className="gap-1.5" onClick={() => saveProfile.mutate()} disabled={saveProfile.isPending} data-testid="save-profile"><Save size={15} /> Save profile</Button>
        </Card>

        <Card title="Workspace & branding" desc="Customize how your brand appears to customers.">
          <div className="space-y-2 mb-4"><Label>Business name</Label><Input value={ws.name} onChange={(e) => setWs({ ...ws, name: e.target.value })} data-testid="settings-ws-name" /></div>
          <div className="space-y-2 mb-4"><Label>Primary color</Label><div className="flex gap-2"><input type="color" value={ws.primary_color} onChange={(e) => setWs({ ...ws, primary_color: e.target.value })} className="w-11 h-10 rounded-lg border border-border bg-transparent cursor-pointer" data-testid="settings-color" /><Input value={ws.primary_color} onChange={(e) => setWs({ ...ws, primary_color: e.target.value })} /></div></div>
          <div className="space-y-2 mb-4"><Label>Logo</Label>
            <label className="flex items-center gap-3 p-3 rounded-xl border border-border cursor-pointer hover:border-primary/40 transition-colors" data-testid="settings-logo-upload">
              {ws.logo_url ? <img src={mediaUrl(ws.logo_url)} className="h-9 object-contain" alt="logo" /> : <div className="w-9 h-9 rounded-lg bg-secondary flex items-center justify-center">{logoUploading ? <Loader2 className="animate-spin" size={16} /> : <Upload size={16} />}</div>}
              <span className="text-sm text-muted-foreground">{ws.logo_url ? "Change logo" : "Upload a logo"}</span>
              <input type="file" accept="image/*" className="hidden" onChange={uploadLogo} />
            </label>
          </div>
          <Button className="gap-1.5" onClick={() => saveWs.mutate()} disabled={saveWs.isPending} data-testid="save-workspace"><Save size={15} /> Save workspace</Button>
        </Card>

        <Card title="Appearance" desc="Choose your dashboard theme.">
          <div className="grid grid-cols-2 gap-3">
            <button onClick={() => setTheme("dark")} className={`flex items-center gap-2 justify-center p-3 rounded-xl border transition-colors ${theme === "dark" ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground"}`} data-testid="theme-dark"><Moon size={16} /> Dark</button>
            <button onClick={() => setTheme("light")} className={`flex items-center gap-2 justify-center p-3 rounded-xl border transition-colors ${theme === "light" ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground"}`} data-testid="theme-light"><Sun size={16} /> Light</button>
          </div>
        </Card>

        <Billing currentPlan={ws.plan || "free"} />

        <TeamMembers />

        <CustomDomain workspace={ws} />

        {user?.is_admin && <AdminIntegrations />}
      </div>
    </div>
  );
}
