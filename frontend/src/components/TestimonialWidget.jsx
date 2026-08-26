import React from "react";
import { Star, BadgeCheck, Quote, Play } from "lucide-react";
import { mediaUrl } from "@/lib/api";

function Stars({ rating, color }) {
  if (!rating) return null;
  return (
    <div className="flex gap-0.5 mb-3">
      {[1, 2, 3, 4, 5].map((i) => (
        <Star key={i} size={15} style={{ color: i <= rating ? color : "rgba(120,120,120,0.35)" }}
          fill={i <= rating ? color : "transparent"} />
      ))}
    </div>
  );
}

function Avatar({ t, cfg }) {
  if (!cfg.show_photo) return null;
  const url = mediaUrl(t.avatar_url);
  const initials = (t.first_name?.[0] || "") + (t.last_name?.[0] || "");
  return url ? (
    <img src={url} alt={t.first_name} className="w-11 h-11 rounded-full object-cover flex-shrink-0" />
  ) : (
    <div className="w-11 h-11 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0"
      style={{ background: cfg.accent_color, color: "#fff" }}>{initials.toUpperCase()}</div>
  );
}

function Meta({ t, cfg, isDark }) {
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-1 font-semibold text-sm truncate" style={{ color: isDark ? "#fff" : "#0a0a0a" }}>
        {t.first_name} {t.last_name}
        <BadgeCheck size={14} style={{ color: cfg.accent_color }} className="flex-shrink-0" />
      </div>
      {(cfg.show_role || cfg.show_company) && (
        <div className="text-xs truncate" style={{ color: isDark ? "rgba(255,255,255,0.55)" : "rgba(0,0,0,0.55)" }}>
          {cfg.show_role && t.role}{cfg.show_role && cfg.show_company && t.company ? " · " : ""}{cfg.show_company && t.company}
        </div>
      )}
    </div>
  );
}

function Card({ t, cfg, isDark }) {
  const bg = isDark ? "#111111" : "#ffffff";
  const border = isDark ? "1px solid rgba(255,255,255,0.09)" : "1px solid rgba(0,0,0,0.08)";
  const textColor = isDark ? "rgba(255,255,255,0.82)" : "rgba(0,0,0,0.78)";
  const hasVideo = cfg.show_video && t.video_url;
  return (
    <div className="break-inside-avoid p-5 flex flex-col gap-1"
      style={{ background: bg, border, borderRadius: cfg.border_radius, boxShadow: isDark ? "none" : "0 1px 3px rgba(0,0,0,0.06)" }}>
      {hasVideo ? (
        <div className="relative w-full rounded-lg overflow-hidden mb-3" style={{ aspectRatio: "9/16", maxHeight: 320, background: "#000" }}>
          <video src={mediaUrl(t.video_url)} controls playsInline poster={mediaUrl(t.video_thumbnail_url)}
            className="w-full h-full object-cover" preload="metadata" />
        </div>
      ) : t.image_url ? (
        <>
          <div className="w-full rounded-lg overflow-hidden mb-3" style={{ background: "#000" }}>
            <img src={mediaUrl(t.image_url)} alt="" className="w-full h-auto object-cover" />
          </div>
          {cfg.show_rating && <Stars rating={t.rating} color={cfg.accent_color} />}
          {t.text && <p className="text-sm leading-relaxed mb-4" style={{ color: textColor }}>{t.text}</p>}
        </>
      ) : (
        <>
          {cfg.show_rating && <Stars rating={t.rating} color={cfg.accent_color} />}
          <Quote size={20} style={{ color: cfg.accent_color, opacity: 0.5 }} className="mb-1" />
          <p className="text-sm leading-relaxed mb-4" style={{ color: textColor }}>{t.text}</p>
        </>
      )}
      <div className="flex items-center gap-3 mt-auto">
        <Avatar t={t} cfg={cfg} />
        <Meta t={t} cfg={cfg} isDark={isDark} />
      </div>
    </div>
  );
}

export default function TestimonialWidget({ widget, testimonials }) {
  const cfg = { columns: 3, border_radius: 16, accent_color: "#ff5722", theme: "dark", show_photo: true, show_company: true, show_role: true, show_rating: true, show_video: true, ...(widget?.configuration || {}) };
  const isDark = cfg.theme === "dark";
  const type = widget?.type || "grid";
  const items = testimonials || [];

  if (items.length === 0) {
    return <div className="p-8 text-center text-sm" style={{ color: isDark ? "#888" : "#666" }}>No testimonials to display yet.</div>;
  }

  const cols = Math.min(parseInt(cfg.columns) || 3, 4);

  if (type === "carousel" || type === "video_wall") {
    return (
      <div className="flex gap-4 overflow-x-auto pb-3 no-scrollbar" style={{ scrollSnapType: "x mandatory" }}>
        {items.map((t) => (
          <div key={t.id} style={{ minWidth: type === "video_wall" ? 240 : 320, maxWidth: type === "video_wall" ? 240 : 320, scrollSnapAlign: "start" }}>
            <Card t={t} cfg={cfg} isDark={isDark} />
          </div>
        ))}
      </div>
    );
  }

  if (type === "single") {
    return <div className="max-w-xl mx-auto"><Card t={items[0]} cfg={cfg} isDark={isDark} /></div>;
  }

  if (type === "masonry") {
    return (
      <div style={{ columnCount: cols, columnGap: "1rem" }} className="[&>*]:mb-4">
        {items.map((t) => <Card key={t.id} t={t} cfg={cfg} isDark={isDark} />)}
      </div>
    );
  }

  // grid
  const gid = `tw-${cols}`;
  return (
    <>
      <style>{`
        .${gid}{display:grid;gap:1rem;grid-template-columns:repeat(1,minmax(0,1fr));}
        @media(min-width:640px){.${gid}{grid-template-columns:repeat(${Math.min(cols,2)},minmax(0,1fr));}}
        @media(min-width:1024px){.${gid}{grid-template-columns:repeat(${cols},minmax(0,1fr));}}
      `}</style>
      <div className={gid}>
        {items.map((t) => <Card key={t.id} t={t} cfg={cfg} isDark={isDark} />)}
      </div>
    </>
  );
}
