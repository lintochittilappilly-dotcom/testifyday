import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import AuthShell from "@/components/AuthShell";
import GoogleButton from "@/components/GoogleButton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function Register() {
  const { register, formatApiError } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true); setError("");
    try {
      await register(name, email, password);
      toast.success("Account created!");
      navigate("/onboarding");
    } catch (err) {
      setError(formatApiError(err));
    } finally { setLoading(false); }
  };

  return (
    <AuthShell title="Start collecting testimonials" subtitle="Free forever plan. No credit card required.">
      <form onSubmit={submit} className="space-y-4" data-testid="register-form">
        <GoogleButton label="Sign up with Google" />
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <div className="h-px flex-1 bg-border" /> OR <div className="h-px flex-1 bg-border" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="name">Full name</Label>
          <Input id="name" required value={name} onChange={(e) => setName(e.target.value)} placeholder="Alex Founder" data-testid="register-name" className="h-11" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" data-testid="register-email" className="h-11" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input id="password" type="password" required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="At least 6 characters" data-testid="register-password" className="h-11" />
        </div>
        {error && <p className="text-sm text-destructive" data-testid="register-error">{error}</p>}
        <Button type="submit" disabled={loading} className="w-full h-11" data-testid="register-submit">
          {loading ? <Loader2 className="animate-spin" size={18} /> : "Create free account"}
        </Button>
        <p className="text-xs text-center text-muted-foreground leading-relaxed">
          By creating an account you agree to our{" "}
          <Link to="/terms" className="text-foreground hover:underline" data-testid="register-terms-link">Terms of Service</Link>{" "}and{" "}
          <Link to="/privacy" className="text-foreground hover:underline" data-testid="register-privacy-link">Privacy Policy</Link>.
        </p>
        <p className="text-sm text-center text-muted-foreground">
          Already have an account? <Link to="/login" className="text-primary hover:underline font-medium" data-testid="to-login">Log in</Link>
        </p>
      </form>
    </AuthShell>
  );
}
