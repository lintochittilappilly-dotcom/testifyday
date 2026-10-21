import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import Marquee from "react-fast-marquee";
import Logo from "@/components/Logo";
import api, { mediaUrl } from "@/lib/api";
import useMeta from "@/hooks/useMeta";
import { Button } from "@/components/ui/button";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import {
  Star, Video, MessageSquareQuote, Share2, CheckCircle2, LayoutGrid, Zap,
  ShieldCheck, Sparkles, ArrowRight, Play, Check, Menu, X,
} from "lucide-react";

// The homepage wall shows real, approved testimonials from a workspace wall
// (set in Admin → Platform integrations, or REACT_APP_HOMEPAGE_WALL at build time).
// We never render invented quotes: if no wall is configured/approved, we show a
// product preview instead.
const HOMEPAGE_WALL_SLUG = process.env.REACT_APP_HOMEPAGE_WALL || "";

function wallInitials(t) {
  return `${(t.first_name || "")[0] || ""}${(t.last_name || "")[0] || ""}`.toUpperCase() || "?";
}

function WallCard({ t, accent = "#ff5722" }) {
  const avatar = mediaUrl(t.avatar_url);
  return (
    <div className="p-4 rounded-2xl bg-[#111] border border-white/10 mb-3 last:mb-0" data-testid="homepage-wall-card">
      {t.rating ? (
        <div className="flex gap-0.5 mb-2" style={{ color: accent }}>
          {[1, 2, 3, 4, 5].map((s) => <Star key={s} size={13} fill={s <= t.rating ? "currentColor" : "transparent"} />)}
        </div>
      ) : null}
      <p className="text-sm text-white/80 mb-3 leading-relaxed line-clamp-4">“{t.text || "Video testimonial"}”</p>
      <div className="flex items-center gap-2.5">
        {avatar ? (
          <img src={avatar} className="w-9 h-9 rounded-full object-cover" alt="" />
        ) : (
          <div className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold text-white" style={{ background: accent }}>{wallInitials(t)}</div>
        )}
        <div>
          <div className="text-sm font-semibold flex items-center gap-1">
            {t.first_name} {t.last_name} <CheckCircle2 size={13} className="text-primary" />
          </div>
          <div className="text-xs text-white/50">{[t.role, t.company].filter(Boolean).join(" · ") || "Verified customer"}</div>
        </div>
      </div>
    </div>
  );
}

const STEPS = [
  { icon: Share2, title: "Ask", d: "Share your personal testimonial collection link with your customers via email, SMS, or WhatsApp." },
  { icon: Video, title: "Collect", d: "Customers record a video or write a testimonial directly from their browser — no account needed." },
  { icon: LayoutGrid, title: "Showcase", d: "Approve your favorites and embed a beautiful, responsive widget anywhere on your website." },
];

const FEATURES = [
  { icon: Video, title: "Browser video recording", d: "Customers record straight from their phone or webcam. Nothing to install." },
  { icon: LayoutGrid, title: "5 stunning widget layouts", d: "Grid, carousel, masonry wall, single spotlight, and video wall." },
  { icon: Zap, title: "One-line embed", d: "Works with Webflow, WordPress, Shopify, Wix, Framer, and plain HTML." },
  { icon: ShieldCheck, title: "Approval & moderation", d: "Every testimonial is yours to approve, tag, feature, or archive." },
  { icon: MessageSquareQuote, title: "Video + written", d: "Collect both formats with custom questions and star ratings." },
  { icon: Sparkles, title: "Fully on-brand", d: "Match your colors, logo, and style. Widgets update live everywhere." },
];

const USE_CASES = ["SaaS", "Agencies", "Coaches", "Course creators", "Freelancers", "Ecommerce", "Startups", "Consultants", "Local business"];

const FAQ = [
  { q: "Do my customers need an account?", a: "No. They just open your link, record or write a testimonial, and submit. It takes under two minutes." },
  { q: "Where can I embed the widgets?", a: "Anywhere — Webflow, WordPress, Shopify, Wix, Squarespace, Framer, Carrd, or any custom HTML site. Just paste one line of code." },
  { q: "Can I collect video testimonials?", a: "Yes. Customers can record directly in their browser on desktop or mobile, or upload an existing video." },
  { q: "Will widgets update automatically?", a: "Yes. When you approve, edit, or feature a testimonial, your embedded widgets update instantly everywhere." },
  { q: "Is there a free plan?", a: "Yes. The Free plan is free forever and never asks for a card — unlimited collection pages and widgets, up to 10 testimonials." },
  { q: "Do I need a credit card to start?", a: "Not for the Free plan. If you start a paid plan you get a 7-day free trial, and that trial does require a card so it can continue automatically — cancel any time before day 8 and you're not charged." },
];

function Nav() {
  const [open, setOpen] = useState(false);
  return (
    <header className="sticky top-0 z-50 border-b border-white/10 bg-black/60 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <Logo />
        <nav className="hidden md:flex items-center gap-8 text-sm text-white/70">
          <a href="#how" className="hover:text-white transition-colors">How it works</a>
          <a href="#features" className="hover:text-white transition-colors">Features</a>
          <a href="#pricing" className="hover:text-white transition-colors">Pricing</a>
          <a href="#faq" className="hover:text-white transition-colors">FAQ</a>
        </nav>
        <div className="hidden md:flex items-center gap-3">
          <Link to="/login"><Button variant="ghost" size="sm" data-testid="nav-login">Log in</Button></Link>
          <Link to="/register"><Button size="sm" data-testid="nav-signup">Start free</Button></Link>
        </div>
        <button className="md:hidden text-white" onClick={() => setOpen(!open)} data-testid="mobile-menu-btn">{open ? <X /> : <Menu />}</button>
      </div>
      {open && (
        <div className="md:hidden border-t border-white/10 px-6 py-4 flex flex-col gap-3 bg-black">
          <a href="#how" onClick={() => setOpen(false)} className="text-white/70">How it works</a>
          <a href="#features" onClick={() => setOpen(false)} className="text-white/70">Features</a>
          <a href="#pricing" onClick={() => setOpen(false)} className="text-white/70">Pricing</a>
          <Link to="/login"><Button variant="outline" className="w-full">Log in</Button></Link>
          <Link to="/register"><Button className="w-full">Start free</Button></Link>
        </div>
      )}
    </header>
  );
}

export default function Landing() {
  const [pricing, setPricing] = useState([]);
  const [promo, setPromo] = useState("");
  const [trial, setTrial] = useState({ days: 0, requires_card: true });
  const [wall, setWall] = useState(null);
  useEffect(() => {
    (async () => {
      try {
        const [plansRes, cfgRes] = await Promise.all([
          api.get("/plans"),
          api.get("/public/config").catch(() => ({ data: {} })),
        ]);
        setPricing(Array.isArray(plansRes.data) ? plansRes.data : []);
        setPromo((cfgRes.data && cfgRes.data.promo_banner) || "");
        setTrial({
          days: Number(cfgRes.data?.trial_period_days || 0),
          requires_card: cfgRes.data?.trial_requires_card !== false,
        });
        const wallSlug = cfgRes.data?.homepage_wall_slug || HOMEPAGE_WALL_SLUG;
        if (wallSlug) {
          const wallRes = await api.get(`/public/wall/${wallSlug}`).catch(() => null);
          if (wallRes?.data?.testimonials?.length) setWall(wallRes.data);
        }
      } catch (e) {
        setPricing([]);
      }
    })();
  }, []);

  useMeta({
    title: "Testify — Customer Testimonials Made Simple",
    description:
      "Collect video and written customer testimonials in the browser, approve them, and embed them anywhere with one line of code. Free plan, no card required.",
    url: typeof window !== "undefined" ? `${window.location.origin}/` : null,
  });

  const wallItems = wall?.testimonials || [];
  const rated = wallItems.filter((t) => typeof t.rating === "number" && t.rating > 0);
  const avgRating = rated.length ? (rated.reduce((sum, t) => sum + t.rating, 0) / rated.length).toFixed(1) : null;

  return (
    <div className="dark bg-background text-foreground min-h-screen">
      <Nav />
      {promo && (
        <div className="bg-primary text-white text-center text-sm py-2 px-4" data-testid="promo-banner">{promo}</div>
      )}

      {/* Hero */}
      <section className="relative overflow-hidden grain">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[500px] bg-primary/20 blur-[140px] rounded-full" />
        <div className="max-w-7xl mx-auto px-6 pt-20 pb-16 grid lg:grid-cols-12 gap-12 items-center relative z-10">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }} className="lg:col-span-7">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-white/10 bg-white/5 text-xs text-white/70 mb-6">
              <Sparkles size={14} className="text-primary" /> {wallItems.length ? `${wall.count} real ${wall.count === 1 ? "testimonial" : "testimonials"} on our own wall` : "Video + written testimonials, one link"}
            </div>
            <h1 className="font-heading text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tighter leading-[1.05] mb-6">
              Turn happy customers into your <span className="text-primary">best marketing</span>.
            </h1>
            <p className="text-lg text-white/60 max-w-xl mb-8 leading-relaxed">
              Collect beautiful video and written testimonials, then showcase them anywhere on your website — in minutes, with one line of code.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link to="/register"><Button size="lg" className="h-12 px-7 gap-2 text-base" data-testid="hero-cta">Start collecting testimonials <ArrowRight size={18} /></Button></Link>
              <a href="#how"><Button size="lg" variant="outline" className="h-12 px-7 gap-2 text-base border-white/15" data-testid="hero-secondary"><Play size={16} /> See how it works</Button></a>
            </div>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 mt-8 text-sm text-white/50">
              <span className="inline-flex items-center gap-1.5"><Check size={15} className="text-primary" /> Free plan, no card</span>
              <span className="inline-flex items-center gap-1.5"><Video size={15} className="text-primary" /> Recorded in the browser</span>
              {wall && (
                <Link to={`/wall/${wall.slug}`} className="inline-flex items-center gap-1 text-white/70 hover:text-white" data-testid="hero-wall-link">
                  See a live wall <ArrowRight size={14} />
                </Link>
              )}
            </div>
          </motion.div>
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.7, delay: 0.15 }} className="lg:col-span-5">
            <div className="relative rounded-3xl border border-white/10 bg-white/[0.03] backdrop-blur-xl p-5 shadow-2xl">
              <div className="absolute -top-3 -right-3 px-3 py-1.5 rounded-full bg-primary text-white text-xs font-semibold animate-float">{wallItems.length ? "Live widget" : "How it works"}</div>
              {wallItems.length ? (
                <>
                  <p className="text-[11px] uppercase tracking-[0.18em] text-white/40 mb-3 px-1">Approved customers of {wall.business_name}</p>
                  {wallItems.slice(0, 3).map((t) => <WallCard key={t.id} t={t} />)}
                  <Link to={`/wall/${wall.slug}`} className="block mt-3 text-xs text-white/60 hover:text-white" data-testid="hero-wall-card-link">
                    See all {wall.count} on the wall →
                  </Link>
                </>
              ) : (
                <div className="p-4 rounded-2xl bg-[#111] border border-white/10">
                  <div className="flex items-center gap-2 text-xs text-white/40 mb-3"><MessageSquareQuote size={14} className="text-primary" /> A testimonial, start to finish</div>
                  <p className="text-sm text-white/75 leading-relaxed mb-3">“We ask every customer for a testimonial with one link. They record a 60-second video on their phone — no app, no login — and we approve it from the dashboard.”</p>
                  <div className="flex items-center gap-2.5">
                    <div className="w-9 h-9 rounded-full bg-primary flex items-center justify-center text-white text-xs font-bold">YT</div>
                    <div><div className="text-sm font-semibold">Your customer</div><div className="text-xs text-white/50">Where this card will sit</div></div>
                  </div>
                  <Link to="/register" className="mt-4 inline-flex items-center gap-1 text-xs text-primary hover:underline">Collect your first one <ArrowRight size={13} /></Link>
                </div>
              )}
            </div>
          </motion.div>
        </div>

        {/* Real customer wall — rendered only when a wall is configured and approved */}
        {wallItems.length > 0 && (
          <div id="wall" className="py-6 border-y border-white/10 bg-white/[0.02]">
            <div className="max-w-7xl mx-auto px-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
              <p className="text-sm text-white/50">
                Real, approved testimonials from <span className="text-white/80">{wall.business_name}</span>
                {avgRating && <span className="ml-2 text-primary">{avgRating}/5</span>}
              </p>
              <Link to={`/wall/${wall.slug}`} className="text-sm text-white/70 hover:text-white inline-flex items-center gap-1" data-testid="homepage-wall-link">
                See the full wall <ArrowRight size={14} />
              </Link>
            </div>
            <Marquee gradient gradientColor="#0a0a0a" gradientWidth={80} speed={40} pauseOnHover>
              {wallItems.map((t) => (
                <div key={t.id} className="mx-3 w-80 p-4 rounded-2xl bg-[#111] border border-white/10">
                  <p className="text-sm text-white/75 mb-3 leading-relaxed line-clamp-3">“{t.text || "Video testimonial"}”</p>
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center text-[11px] font-bold text-white">{wallInitials(t)}</div>
                    <div><div className="text-xs font-semibold">{t.first_name} {t.last_name}</div><div className="text-xs text-white/50">{[t.role, t.company].filter(Boolean).join(" · ")}</div></div>
                  </div>
                </div>
              ))}
            </Marquee>
          </div>
        )}
      </section>

      {/* How it works */}
      <section id="how" className="max-w-7xl mx-auto px-6 py-24">
        <div className="text-center max-w-2xl mx-auto mb-16">
          <div className="text-xs uppercase tracking-[0.2em] font-bold text-primary mb-3">How it works</div>
          <h2 className="font-heading text-3xl sm:text-4xl font-bold tracking-tight">Three steps from happy customer to social proof</h2>
        </div>
        <div className="grid md:grid-cols-3 gap-6">
          {STEPS.map((s, i) => (
            <motion.div key={i} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.1 }}
              className="p-8 rounded-3xl border border-white/10 bg-white/[0.02] hover:border-primary/40 transition-colors">
              <div className="w-12 h-12 rounded-2xl bg-primary/15 flex items-center justify-center mb-5"><s.icon className="text-primary" size={22} /></div>
              <div className="text-xs font-bold text-primary mb-2">STEP {i + 1}</div>
              <h3 className="font-heading text-xl font-semibold mb-2">{s.title}</h3>
              <p className="text-white/55 text-sm leading-relaxed">{s.d}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Features bento */}
      <section id="features" className="max-w-7xl mx-auto px-6 py-24">
        <div className="max-w-2xl mb-16">
          <div className="text-xs uppercase tracking-[0.2em] font-bold text-primary mb-3">Features</div>
          <h2 className="font-heading text-3xl sm:text-4xl font-bold tracking-tight">Everything you need to build trust</h2>
        </div>
        <div className="grid md:grid-cols-3 gap-5">
          {FEATURES.map((f, i) => (
            <div key={i} className="p-7 rounded-3xl border border-white/10 bg-white/[0.02] hover:bg-white/[0.04] transition-colors">
              <f.icon className="text-primary mb-4" size={24} />
              <h3 className="font-heading text-lg font-semibold mb-2">{f.title}</h3>
              <p className="text-white/55 text-sm leading-relaxed">{f.d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Use cases */}
      <section className="max-w-7xl mx-auto px-6 py-12">
        <p className="text-center text-white/40 text-sm mb-6">Built for every kind of business</p>
        <div className="flex flex-wrap justify-center gap-3">
          {USE_CASES.map((u) => <span key={u} className="px-4 py-2 rounded-full border border-white/10 bg-white/[0.03] text-sm text-white/70">{u}</span>)}
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="max-w-7xl mx-auto px-6 py-24">
        <div className="text-center max-w-2xl mx-auto mb-16">
          <div className="text-xs uppercase tracking-[0.2em] font-bold text-primary mb-3">Pricing</div>
          <h2 className="font-heading text-3xl sm:text-4xl font-bold tracking-tight">Simple pricing that scales with you</h2>
        </div>
        <div className="grid md:grid-cols-3 gap-6 items-start">
          {pricing.map((p) => {
            const isFree = p.id === "free";
            const priceLabel = isFree ? "$0" : `$${p.price_monthly}`;
            const period = isFree ? "forever" : "/mo";
            const showTrial = !isFree && trial.days > 0;
            const cta = showTrial
              ? `Start ${trial.days}-day free trial`
              : (p.cta || (isFree ? "Start free" : "Start free trial"));
            // Spell out the card requirement exactly, so the pricing card and the
            // FAQ can never disagree about what checkout will ask for.
            const trialNote = isFree
              ? "Free forever · no credit card required"
              : showTrial
                ? `${trial.days}-day free trial · ${trial.requires_card ? "card required at checkout" : "no card required"} · cancel anytime`
                : "Cancel anytime · no setup fee";
            return (
              <div key={p.id} className={`p-8 rounded-3xl border ${p.featured ? "border-primary bg-primary/[0.06] relative" : "border-white/10 bg-white/[0.02]"}`}>
                {p.featured && <div className="absolute -top-3 left-8 px-3 py-1 rounded-full bg-primary text-white text-xs font-semibold">Most popular</div>}
                <h3 className="font-heading text-lg font-semibold mb-1">{p.name}</h3>
                <div className="flex items-end gap-1 mb-2"><span className="font-heading text-4xl font-bold">{priceLabel}</span><span className="text-white/50 text-sm mb-1">{period}</span></div>
                <p className={`text-xs mb-5 ${isFree ? "text-white/45" : "text-primary"}`} data-testid={`pricing-trial-${p.id}`}>
                  {trialNote}
                </p>
                <Link to="/register"><Button className="w-full mb-6" variant={p.featured ? "default" : "outline"} data-testid={`pricing-${p.id}`}>{cta}</Button></Link>
                <ul className="space-y-3">{(p.features || []).map((f) => <li key={f} className="flex items-start gap-2 text-sm text-white/70"><Check size={16} className="text-primary mt-0.5 flex-shrink-0" /> {f}</li>)}</ul>
              </div>
            );
          })}
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="max-w-3xl mx-auto px-6 py-24">
        <h2 className="font-heading text-3xl sm:text-4xl font-bold tracking-tight text-center mb-12">Frequently asked questions</h2>
        <Accordion type="single" collapsible className="w-full">
          {FAQ.map((f, i) => (
            <AccordionItem key={i} value={`item-${i}`} className="border-white/10">
              <AccordionTrigger className="text-left font-heading font-medium hover:no-underline">{f.q}</AccordionTrigger>
              {/* forceMount keeps every answer in the served HTML so crawlers and
                  no-JS readers can see it, even while the panel is collapsed. */}
              <AccordionContent forceMount className="text-white/55">{f.a}</AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </section>

      {/* CTA */}
      <section className="max-w-7xl mx-auto px-6 pb-24">
        <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-white/[0.03] p-12 sm:p-16 text-center grain">
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[500px] h-[300px] bg-primary/25 blur-[120px]" />
          <div className="relative z-10">
            <h2 className="font-heading text-3xl sm:text-4xl font-bold tracking-tight mb-4">Start collecting testimonials today</h2>
            <p className="text-white/60 mb-8 max-w-lg mx-auto">Start on the Free plan — no credit card, no trial clock, unlimited widgets. Upgrade to Pro when you need video testimonials.</p>
            <Link to="/register"><Button size="lg" className="h-12 px-8 gap-2" data-testid="footer-cta">Get started free <ArrowRight size={18} /></Button></Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-white/10">
        <div className="max-w-7xl mx-auto px-6 py-10 flex flex-col sm:flex-row items-center justify-between gap-4">
          <Logo />
          <div className="flex gap-6 text-white/40 text-sm">
            <Link to="/terms" className="hover:text-white" data-testid="footer-terms-link">Terms</Link>
            <Link to="/privacy" className="hover:text-white" data-testid="footer-privacy-link">Privacy</Link>
            <a href="mailto:hello@testify.day" className="hover:text-white">Contact</a>
          </div>
          <p className="text-white/40 text-sm">© {new Date().getFullYear()} Testify.</p>
        </div>
      </footer>
    </div>
  );
}
