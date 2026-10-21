import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import api, { mediaUrl } from "@/lib/api";
import TestimonialWidget from "@/components/TestimonialWidget";
import useMeta from "@/hooks/useMeta";
import { Button } from "@/components/ui/button";
import { Star, Loader2, AlertTriangle, Heart, PenLine } from "lucide-react";

export default function WallOfLove() {
  const { slug } = useParams();
  const [data, setData] = useState(null);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get(`/public/wall/${slug}`);
        setData(res.data);
        setStatus("ready");
      } catch (e) { setStatus("error"); }
    })();
  }, [slug]);

  useMeta({
    title: data ? `${data.business_name} — Wall of Love` : "Wall of Love",
    description: data
      ? `See what ${data.count} ${data.count === 1 ? "customer says" : "customers say"} about ${data.business_name}. Real, approved testimonials collected with Testify.`
      : "Customer testimonials wall.",
    // Server-rendered card (1200x630 PNG) so links unfurl with the business name.
    image: data?.og_image ? mediaUrl(data.og_image) : mediaUrl(data?.logo_url),
    url: typeof window !== "undefined" ? window.location.href : null,
    robots: status === "error" ? "noindex" : undefined,
  });

  const accent = data?.primary_color || "#ff5722";

  if (status === "loading") return <div className="min-h-screen flex items-center justify-center bg-[#080808]"><Loader2 className="animate-spin text-white/70" size={30} /></div>;

  if (status === "error") return (
    <div className="min-h-screen flex items-center justify-center bg-[#080808] text-center px-6">
      <div><AlertTriangle className="mx-auto mb-4 text-white/50" size={40} /><h1 className="font-heading text-2xl font-bold text-white mb-2">Wall not found</h1><p className="text-white/50 text-sm">This page doesn't exist.</p></div>
    </div>
  );

  const collectUrl = data.collect_slug ? `${window.location.origin}/t/${data.collect_slug}` : null;

  return (
    <div className="min-h-screen text-white relative overflow-hidden" style={{ background: "#080808" }}>
      <div className="absolute -top-40 left-1/2 -translate-x-1/2 w-[700px] h-[420px] rounded-full blur-[150px] opacity-25" style={{ background: accent }} />
      <div className="relative z-10 max-w-6xl mx-auto px-5 sm:px-8 py-16 sm:py-24">
        <header className="text-center max-w-2xl mx-auto mb-16">
          {data.logo_url && <img src={mediaUrl(data.logo_url)} alt={data.business_name} className="h-12 mx-auto mb-6 object-contain" />}
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-white/10 bg-white/5 text-xs text-white/70 mb-6">
            <Heart size={13} style={{ color: accent }} fill={accent} /> Wall of Love
          </div>
          <h1 className="font-heading text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tighter mb-4">
            What people say about <span style={{ color: accent }}>{data.business_name}</span>
          </h1>
          <p className="text-white/55 text-lg mb-2">{data.count} happy {data.count === 1 ? "customer" : "customers"} and counting.</p>
          <div className="flex items-center justify-center gap-1 mt-4" style={{ color: accent }}>
            {[1,2,3,4,5].map(i => <Star key={i} size={18} fill="currentColor" />)}
          </div>
          {collectUrl && (
            <a href={collectUrl} className="inline-block mt-8">
              <Button className="gap-2 h-11 px-6" style={{ background: accent }} data-testid="wall-collect-cta"><PenLine size={16} /> Leave a testimonial</Button>
            </a>
          )}
        </header>

        {data.count === 0 ? (
          <p className="text-center text-white/40 py-16">No testimonials yet — check back soon!</p>
        ) : (
          <TestimonialWidget
            widget={{ type: "masonry", configuration: { theme: "dark", columns: 3, accent_color: accent, border_radius: 18, show_photo: true, show_company: true, show_role: true, show_rating: true, show_video: true } }}
            testimonials={data.testimonials}
          />
        )}

        <footer className="text-center mt-20 text-white/25 text-xs">{data.branding ? "Powered by Testify" : `© ${new Date().getFullYear()} ${data.business_name}`}</footer>
      </div>
    </div>
  );
}
