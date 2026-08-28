import React from "react";
import { Link } from "react-router-dom";
import Logo from "@/components/Logo";
import { ArrowLeft } from "lucide-react";

export default function LegalPage({ title, updated, children }) {
  return (
    <div className="dark bg-background text-foreground min-h-screen">
      <header className="border-b border-white/10">
        <div className="max-w-3xl mx-auto px-6 py-5 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 text-white/60 hover:text-white text-sm"><ArrowLeft size={15} /> Back to home</Link>
          <Logo />
        </div>
      </header>
      <main className="max-w-3xl mx-auto px-6 py-16">
        <h1 className="font-heading text-4xl font-bold tracking-tight mb-2">{title}</h1>
        <p className="text-white/40 text-sm mb-12">Last updated: {updated}</p>
        <div className="prose prose-invert prose-p:text-white/70 prose-li:text-white/70 prose-h2:font-heading prose-h2:text-white prose-h2:text-2xl prose-h2:mt-12 prose-h2:mb-4 prose-a:text-primary prose-a:no-underline hover:prose-a:underline max-w-none">
          {children}
        </div>
      </main>
      <footer className="border-t border-white/10 mt-20">
        <div className="max-w-3xl mx-auto px-6 py-8 text-white/40 text-sm flex flex-wrap items-center justify-between gap-4">
          <div>© {new Date().getFullYear()} Testify.</div>
          <div className="flex gap-6">
            <Link to="/terms" className="hover:text-white">Terms</Link>
            <Link to="/privacy" className="hover:text-white">Privacy</Link>
            <a href="mailto:hello@testify.day" className="hover:text-white">Contact</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
