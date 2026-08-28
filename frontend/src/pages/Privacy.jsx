import React from "react";
import LegalPage from "./LegalPage";

export default function Privacy() {
  return (
    <LegalPage title="Privacy Policy" updated="27 January 2026">
      <p>This Privacy Policy explains how Testify ("<strong>we</strong>") collects, uses and protects your information when you use testify.day and the Testify service.</p>

      <h2>1. What we collect</h2>
      <p><strong>Account data</strong> — your name, email address, hashed password, and optional profile picture.</p>
      <p><strong>Workspace data</strong> — the business name, logo, brand colours, and settings you configure.</p>
      <p><strong>Testimonial data</strong> — the text, image, or video testimonials submitted to your collection pages by your customers (including their name, email, company and any avatar). Your customers see a consent notice before submitting.</p>
      <p><strong>Payment data</strong> — handled entirely by Stripe. We only receive a subscription status and a Stripe customer ID; we never see your card number.</p>
      <p><strong>Usage data</strong> — pages visited, features used, IP address, and browser type, used to keep the Service secure and improve it.</p>

      <h2>2. How we use it</h2>
      <ul>
        <li>To provide the Service (host your dashboard, deliver your embed widgets, send new-testimonial notifications).</li>
        <li>To bill you correctly and respond to support requests.</li>
        <li>To detect fraud, abuse, and spam submissions.</li>
        <li>To improve the product — aggregated, anonymous usage statistics only.</li>
      </ul>
      <p>We do <strong>not</strong> sell your data or share it with advertisers.</p>

      <h2>3. Cookies</h2>
      <p>We use only essential cookies:</p>
      <ul>
        <li><code>testify_token</code> — keeps you signed in.</li>
        <li>Google reCAPTCHA cookies — set by Google on public testimonial forms to detect bots.</li>
        <li>Stripe cookies — set by Stripe on checkout pages for fraud prevention.</li>
      </ul>

      <h2>4. Third-party processors</h2>
      <p>To operate Testify we share the minimum necessary data with:</p>
      <ul>
        <li><strong>MongoDB Atlas</strong> — database hosting.</li>
        <li><strong>Railway</strong> — backend server hosting.</li>
        <li><strong>Vercel</strong> — frontend hosting and CDN.</li>
        <li><strong>AWS S3</strong> — storage of uploaded avatars, images and video testimonials.</li>
        <li><strong>Stripe</strong> — payment processing and billing portal.</li>
        <li><strong>Resend</strong> — transactional email delivery (new-testimonial alerts, password reset).</li>
        <li><strong>Google reCAPTCHA</strong> — spam and bot protection on public forms.</li>
        <li><strong>Google Sign-in</strong> — optional social login for you and your customers.</li>
      </ul>
      <p>Each provider has its own privacy policy and data-processing terms.</p>

      <h2>5. Data retention</h2>
      <p>We keep account and workspace data for as long as your account is active. When you delete your account, we remove personal data within 30 days, except where retention is required by law (for example, tax invoices for payments — kept for 7 years).</p>

      <h2>6. Your rights</h2>
      <p>Depending on where you live (EU, UK, California, etc.), you may have the right to:</p>
      <ul>
        <li>access a copy of the personal data we hold about you;</li>
        <li>correct inaccurate data;</li>
        <li>delete your account and associated data;</li>
        <li>export your testimonials in a portable format;</li>
        <li>object to certain processing.</li>
      </ul>
      <p>You can exercise all of these from Settings → Account, or by emailing <a href="mailto:hello@testify.day">hello@testify.day</a>.</p>

      <h2>7. Children</h2>
      <p>The Service is not directed to children under 16. We do not knowingly collect personal data from children. If you believe a child has provided us data, contact us and we will delete it.</p>

      <h2>8. Security</h2>
      <p>We use bcrypt-hashed passwords, JWT session tokens, TLS in transit, encrypted storage at rest, and time-boxed brute-force protection on the login endpoint. No system is 100% secure — please use a strong, unique password.</p>

      <h2>9. International transfers</h2>
      <p>Your data may be processed in countries other than yours (for example, our S3 bucket lives in the United States). We rely on standard contractual clauses where applicable.</p>

      <h2>10. Changes to this policy</h2>
      <p>We will announce material changes by email or in-app at least 14 days before they take effect.</p>

      <h2>11. Contact</h2>
      <p>For any privacy question, email <a href="mailto:hello@testify.day">hello@testify.day</a>.</p>
    </LegalPage>
  );
}
