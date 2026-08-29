import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import ReCAPTCHA from "react-google-recaptcha";
import api, { formatApiError, mediaUrl } from "@/lib/api";
import VideoRecorder from "@/components/VideoRecorder";
import useMeta from "@/hooks/useMeta";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Video, PenLine, Image as ImageIcon, Star, Loader2, Heart, ArrowLeft, Upload, Check, AlertTriangle, X } from "lucide-react";
import { toast } from "sonner";

const RECAPTCHA_KEY = process.env.REACT_APP_RECAPTCHA_SITE_KEY || "";

export default function PublicCollection() {
  const { slug } = useParams();
  const [col, setCol] = useState(null);
  const [status, setStatus] = useState("loading"); // loading|error|ready|done
  const [mode, setMode] = useState(null); // video|text
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(null);
  const [recaptchaKey, setRecaptchaKey] = useState(RECAPTCHA_KEY);

  const [form, setForm] = useState({ first_name: "", last_name: "", email: "", company: "", role: "", website: "", text: "", rating: 0, consent: false, honeypot: "" });
  const [videoUrl, setVideoUrl] = useState(null);
  const [imageUrl, setImageUrl] = useState(null);
  const [imageUploading, setImageUploading] = useState(false);
  const [avatarUrl, setAvatarUrl] = useState(null);
  const [avatarUploading, setAvatarUploading] = useState(false);
  const [captcha, setCaptcha] = useState(null);

  const accent = col?.brand_color || "#ff5722";

  useMeta({
    title: col ? `${col.headline || "Leave a testimonial"} · ${col.business_name}` : "Leave a testimonial",
    description: col?.description || "Share your experience — it only takes a minute.",
    image: col ? mediaUrl(col.logo_url) : null,
    url: typeof window !== "undefined" ? window.location.href : null,
  });

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get(`/public/collection/${slug}`);
        setCol(data);
        setStatus("ready");
      } catch (e) { setStatus("error"); }
      try {
        const cfg = await api.get(`/public/config`);
        if (cfg.data?.recaptcha_site_key) setRecaptchaKey(cfg.data.recaptcha_site_key);
      } catch (e) { /* non-blocking */ }
    })();
  }, [slug]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const uploadAvatar = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setAvatarUploading(true);
    try {
      const fd = new FormData(); fd.append("file", file);
      const { data } = await api.post("/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setAvatarUrl(data.url);
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setAvatarUploading(false); }
  };

  const uploadImage = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) { toast.error("Image must be under 5 MB."); return; }
    setImageUploading(true);
    try {
      const fd = new FormData(); fd.append("file", file);
      const { data } = await api.post("/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setImageUrl(data.url);
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setImageUploading(false); }
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!form.consent) { toast.error("Please give consent to submit."); return; }
    if (mode === "text" && !form.text.trim()) { toast.error("Please write your testimonial."); return; }
    if (mode === "image" && !imageUrl) { toast.error("Please upload an image first."); return; }
    if (mode === "video" && !videoUrl) { toast.error("Please record or upload your video first."); return; }
    setSubmitting(true);
    try {
      const { data } = await api.post(`/public/collection/${slug}/submit`, {
        ...form,
        video_url: mode === "video" ? videoUrl : null,
        image_url: mode === "image" ? imageUrl : null,
        avatar_url: avatarUrl,
        rating: form.rating || null,
        recaptcha_token: captcha,
      });
      setDone(data);
      setStatus("done");
      if (data.redirect_url) setTimeout(() => { window.location.href = data.redirect_url; }, 2500);
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setSubmitting(false); }
  };

  if (status === "loading") return <CenterBg accent="#ff5722"><Loader2 className="animate-spin text-white" size={30} /></CenterBg>;

  if (status === "error") return (
    <CenterBg accent="#ff5722">
      <div className="text-center text-white/80 max-w-sm px-6">
        <AlertTriangle className="mx-auto mb-4 text-white/60" size={40} />
        <h1 className="font-heading text-2xl font-bold mb-2">Page not available</h1>
        <p className="text-white/50 text-sm">This testimonial page doesn't exist or isn't published yet.</p>
      </div>
    </CenterBg>
  );

  if (status === "done") return (
    <CenterBg accent={accent}>
      <div className="text-center text-white max-w-sm px-6" data-testid="thank-you">
        <div className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-5" style={{ background: accent }}><Heart className="text-white" size={30} fill="white" /></div>
        <h1 className="font-heading text-3xl font-bold mb-3">Thank you, {form.first_name}! ❤️</h1>
        <p className="text-white/70">{done?.thank_you_message || "Your testimonial has been submitted successfully."}</p>
        {col?.redirect_url && <p className="text-white/40 text-sm mt-4">Redirecting…</p>}
      </div>
    </CenterBg>
  );

  return (
    <CenterBg accent={accent}>
      <div className="w-full max-w-lg">
        <div className="rounded-3xl bg-black/60 backdrop-blur-xl border border-white/10 shadow-[0_8px_40px_rgba(0,0,0,0.4)] p-6 sm:p-8">
          {/* Header */}
          <div className="text-center mb-6">
            {col.logo_url && <img src={mediaUrl(col.logo_url)} alt={col.business_name} className="h-10 mx-auto mb-4 object-contain" />}
            <h1 className="font-heading text-2xl sm:text-3xl font-bold text-white mb-2 tracking-tight">{col.headline}</h1>
            <p className="text-white/55 text-sm">{col.description}</p>
          </div>

          {!mode && (
            <div className="space-y-3" data-testid="mode-picker">
              {col.allow_video && (
                <button onClick={() => setMode("video")} data-testid="pick-video" className="w-full p-5 rounded-2xl bg-white/5 border border-white/10 hover:border-white/25 transition-colors text-left flex items-center gap-4 active:scale-[0.99]">
                  <div className="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: accent }}><Video className="text-white" size={20} /></div>
                  <div><div className="font-semibold text-white">Record a video</div><div className="text-white/50 text-sm">Most impactful — takes under a minute</div></div>
                </button>
              )}
              <button onClick={() => setMode("image")} data-testid="pick-image" className="w-full p-5 rounded-2xl bg-white/5 border border-white/10 hover:border-white/25 transition-colors text-left flex items-center gap-4 active:scale-[0.99]">
                <div className="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: accent }}><ImageIcon className="text-white" size={20} /></div>
                <div><div className="font-semibold text-white">Share an image</div><div className="text-white/50 text-sm">Upload a photo or screenshot with a short caption</div></div>
              </button>
              {col.allow_text && (
                <button onClick={() => setMode("text")} data-testid="pick-text" className="w-full p-5 rounded-2xl bg-white/5 border border-white/10 hover:border-white/25 transition-colors text-left flex items-center gap-4 active:scale-[0.99]">
                  <div className="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 bg-white/10"><PenLine className="text-white" size={20} /></div>
                  <div><div className="font-semibold text-white">Write a testimonial</div><div className="text-white/50 text-sm">Quick and easy</div></div>
                </button>
              )}
            </div>
          )}

          {mode && (
            <form onSubmit={submit} className="space-y-4" data-testid="submission-form">
              <button type="button" onClick={() => setMode(null)} className="flex items-center gap-1.5 text-white/50 hover:text-white text-sm mb-2"><ArrowLeft size={15} /> Back</button>

              {mode === "video" && (
                <>
                  {(col.video_max_duration_sec || col.video_max_size_mb) && (
                    <div className="text-xs text-white/50 mb-2" data-testid="video-limits-hint">
                      {col.video_max_duration_sec ? `Up to ${col.video_max_duration_sec >= 60 ? `${Math.floor(col.video_max_duration_sec/60)} min` : `${col.video_max_duration_sec} sec`}` : ""}
                      {col.video_max_duration_sec && col.video_max_size_mb ? " · " : ""}
                      {col.video_max_size_mb ? `${col.video_max_size_mb} MB max` : ""}
                      {col.video_min_duration_sec ? ` · min ${col.video_min_duration_sec}s` : ""}
                    </div>
                  )}
                  <VideoRecorder
                    accent={accent}
                    onUploaded={setVideoUrl}
                    maxDurationSec={col.video_max_duration_sec || 120}
                    minDurationSec={col.video_min_duration_sec || 10}
                    maxSizeMb={col.video_max_size_mb || 200}
                  />
                </>
              )}

              {mode === "image" && (
                <div>
                  <Label className="text-white/70 mb-2 block">Upload an image</Label>
                  {imageUrl ? (
                    <div className="relative rounded-2xl overflow-hidden border border-white/10">
                      <img src={mediaUrl(imageUrl)} alt="" className="w-full max-h-72 object-cover" />
                      <button type="button" onClick={() => setImageUrl(null)} className="absolute top-2 right-2 w-8 h-8 rounded-full bg-black/60 flex items-center justify-center text-white hover:bg-black/80" data-testid="remove-image"><X size={16} /></button>
                    </div>
                  ) : (
                    <label className="flex items-center justify-center gap-2 p-8 rounded-2xl bg-white/5 border-2 border-dashed border-white/15 cursor-pointer hover:border-white/30 transition-colors" data-testid="image-upload">
                      {imageUploading ? <Loader2 className="animate-spin text-white/60" size={20} /> : <><Upload className="text-white/60" size={20} /><span className="text-white/60 text-sm">Tap to choose an image (max 5 MB)</span></>}
                      <input type="file" accept="image/*" className="hidden" onChange={uploadImage} />
                    </label>
                  )}
                  <div className="mt-3">
                    <Label className="text-white/70 mb-2 block">Caption (optional)</Label>
                    <Textarea value={form.text} onChange={(e) => set("text", e.target.value)} maxLength={500} rows={3}
                      placeholder="Add a short caption to your image..." data-testid="image-caption"
                      className="bg-white/5 border-white/10 text-white placeholder:text-white/30 resize-none" />
                  </div>
                </div>
              )}

              {mode === "text" && (
                <div>
                  <Label className="text-white/70 mb-2 block">Your testimonial</Label>
                  <Textarea value={form.text} onChange={(e) => set("text", e.target.value)} maxLength={1000} rows={5}
                    placeholder="Tell us about your experience..." data-testid="testimonial-text"
                    className="bg-white/5 border-white/10 text-white placeholder:text-white/30 resize-none" />
                  <div className="text-right text-xs text-white/30 mt-1">{form.text.length}/1000</div>
                </div>
              )}

              {col.collect_rating && (
                <div>
                  <Label className="text-white/70 mb-2 block">Rating</Label>
                  <div className="flex gap-1" data-testid="rating-stars">
                    {[1,2,3,4,5].map((i) => (
                      <button key={i} type="button" onClick={() => set("rating", i)} className="transition-transform active:scale-90">
                        <Star size={28} style={{ color: i <= form.rating ? accent : "rgba(255,255,255,0.2)" }} fill={i <= form.rating ? accent : "transparent"} />
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <Field label="First name *" value={form.first_name} onChange={(v) => set("first_name", v)} required testid="fld-first" />
                <Field label="Last name" value={form.last_name} onChange={(v) => set("last_name", v)} testid="fld-last" />
              </div>
              <Field label={`Email ${col.require_email ? "*" : ""}`} type="email" value={form.email} onChange={(v) => set("email", v)} required={col.require_email} testid="fld-email" />
              <div className="grid grid-cols-2 gap-3">
                <Field label={`Company ${col.require_company ? "*" : ""}`} value={form.company} onChange={(v) => set("company", v)} required={col.require_company} testid="fld-company" />
                <Field label={`Job title ${col.require_role ? "*" : ""}`} value={form.role} onChange={(v) => set("role", v)} required={col.require_role} testid="fld-role" />
              </div>

              <div>
                <Label className="text-white/70 mb-2 block">Your photo (optional)</Label>
                <label className="flex items-center gap-3 p-3 rounded-xl bg-white/5 border border-white/10 cursor-pointer hover:border-white/25 transition-colors" data-testid="avatar-upload">
                  {avatarUrl ? <img src={mediaUrl(avatarUrl)} className="w-10 h-10 rounded-full object-cover" alt="" /> : <div className="w-10 h-10 rounded-full bg-white/10 flex items-center justify-center">{avatarUploading ? <Loader2 className="animate-spin text-white/60" size={16} /> : <Upload className="text-white/60" size={16} />}</div>}
                  <span className="text-white/60 text-sm">{avatarUrl ? "Photo added — tap to change" : "Upload a profile photo"}</span>
                  <input type="file" accept="image/*" className="hidden" onChange={uploadAvatar} />
                </label>
              </div>

              <label className="flex items-start gap-3 p-3 rounded-xl bg-white/5 border border-white/10 cursor-pointer">
                <Checkbox checked={form.consent} onCheckedChange={(v) => set("consent", !!v)} data-testid="consent-checkbox" className="mt-0.5 border-white/30" />
                <span className="text-white/60 text-sm">I give <strong className="text-white/80">{col.business_name}</strong> permission to use this testimonial on its website and marketing materials.</span>
              </label>

              {recaptchaKey && (
                <div className="flex justify-center"><ReCAPTCHA sitekey={recaptchaKey} theme="dark" onChange={setCaptcha} /></div>
              )}

              <input type="text" tabIndex={-1} autoComplete="off" value={form.honeypot} onChange={(e) => set("honeypot", e.target.value)} className="hidden" aria-hidden />

              <Button type="submit" disabled={submitting} className="w-full h-12 text-base gap-2" style={{ background: accent }} data-testid="submit-testimonial-btn">
                {submitting ? <Loader2 className="animate-spin" size={18} /> : <><Check size={18} /> Submit testimonial</>}
              </Button>
            </form>
          )}
        </div>
        <p className="text-center text-white/25 text-xs mt-5">Powered by Testify</p>
      </div>
    </CenterBg>
  );
}

function Field({ label, value, onChange, type = "text", required, testid }) {
  return (
    <div>
      <Label htmlFor={testid} className="text-white/70 mb-2 block text-sm">{label}</Label>
      <Input id={testid} type={type} value={value} required={required} onChange={(e) => onChange(e.target.value)} data-testid={testid}
        className="bg-white/5 border-white/10 text-white placeholder:text-white/30 h-11" />
    </div>
  );
}

function CenterBg({ children, accent }) {
  return (
    <div className="min-h-screen flex items-center justify-center p-4 sm:p-6 relative overflow-hidden" style={{ background: "#080808" }}>
      <div className="absolute -top-40 left-1/2 -translate-x-1/2 w-[600px] h-[400px] rounded-full blur-[130px] opacity-30" style={{ background: accent }} />
      <div className="relative z-10 w-full flex justify-center">{children}</div>
    </div>
  );
}
