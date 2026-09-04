import React from "react";
import { Link } from "react-router-dom";

export default function Logo({ className = "", to = "/", size = "text-xl", onDark = true }) {
  const inner = (
    <span className={`inline-flex items-center gap-2 font-heading font-bold tracking-tight ${size} ${className}`}>
      <img
        src="/brand/testify-logo-mark.png"
        alt="Testify logo"
        className="w-8 h-8 rounded-lg object-contain"
        loading="eager"
        decoding="async"
      />
      <span>Testify</span>
    </span>
  );
  return to ? <Link to={to} className="no-underline text-foreground">{inner}</Link> : inner;
}
