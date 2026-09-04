import React from "react";
import { Link } from "react-router-dom";

export default function Logo({ className = "", to = "/", size = "text-xl", onDark = true }) {
  const inner = (
    <span className={`inline-flex items-center gap-2 font-heading font-bold tracking-tight ${size} ${className}`}>
      <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-primary text-primary-foreground font-extrabold">
        T
      </span>
      <span>Testify</span>
    </span>
  );
  return to ? <Link to={to} className="no-underline text-foreground">{inner}</Link> : inner;
}
