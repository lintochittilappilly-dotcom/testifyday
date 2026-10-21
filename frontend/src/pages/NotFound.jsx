import React from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import Logo from "@/components/Logo";
import useMeta from "@/hooks/useMeta";
import { ArrowLeft } from "lucide-react";

export default function NotFound() {
  useMeta({
    title: "Page not found — Testify",
    description: "This page doesn't exist.",
    robots: "noindex",
  });

  return (
    <div className="dark min-h-screen bg-background text-foreground flex flex-col items-center justify-center px-6 text-center" data-testid="not-found">
      <Logo className="mb-10" />
      <p className="text-xs uppercase tracking-[0.2em] font-bold text-primary mb-3">404</p>
      <h1 className="font-heading text-3xl sm:text-4xl font-bold tracking-tight mb-3">This page doesn't exist</h1>
      <p className="text-white/55 max-w-md mb-8">
        The link may be broken, or the page may have moved. Your collection links look like <span className="text-white/80">/t/your-slug</span> and walls like <span className="text-white/80">/wall/your-slug</span>.
      </p>
      <div className="flex flex-wrap items-center justify-center gap-3">
        <Link to="/">
          <Button className="gap-2" data-testid="not-found-home"><ArrowLeft size={16} /> Back to Testify</Button>
        </Link>
        <Link to="/login">
          <Button variant="outline">Log in</Button>
        </Link>
      </div>
    </div>
  );
}
