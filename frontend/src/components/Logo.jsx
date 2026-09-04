import React from "react";
import { Link } from "react-router-dom";

export default function Logo({ className = "", size = "text-xl" }) {
  return (
    <span className={`inline-flex items-center ${className} ${size}`}>
      <img
        src="/brand/testify-logo-mark.png"
        alt="Testify Logo"
        className="h-8 w-8"
      />
    </span>
      <span>Testify</span>
    </span>
  );
  return to ? <Link to={to} className="no-underline text-foreground">{inner}</Link> : inner;
}
