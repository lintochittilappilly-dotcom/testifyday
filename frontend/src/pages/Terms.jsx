import React from "react";
import LegalPage from "./LegalPage";

export default function Terms() {
  return (
    <LegalPage title="Terms of Service" updated="27 January 2026">
      <p>Welcome to Testify. These Terms of Service ("<strong>Terms</strong>") govern your access to and use of the Testify website, dashboard, embeddable widgets and related services (together, the "<strong>Service</strong>"), operated by Testify ("<strong>we</strong>", "<strong>us</strong>", "<strong>our</strong>"). By creating an account or using the Service, you agree to these Terms.</p>

      <h2>1. Your account</h2>
      <p>You must be at least 16 years old to use the Service. You are responsible for keeping your credentials secure and for all activity under your account. Notify us at <a href="mailto:hello@testify.day">hello@testify.day</a> if you suspect any unauthorised use.</p>

      <h2>2. Plans, trials and payments</h2>
      <p>Testify is available on a Free plan and paid Pro / Business subscription plans. Prices are shown at checkout. Subscriptions renew automatically for the same period unless cancelled before the next renewal date from your dashboard.</p>
      <ul>
        <li>Payments are processed by Stripe. We never see or store your full card number.</li>
        <li>Refunds are handled case-by-case within 14 days of purchase — email us if a plan didn't work out.</li>
        <li>We may change pricing with 30 days' notice; changes apply from your next billing cycle.</li>
      </ul>

      <h2>3. Your content</h2>
      <p>You retain ownership of the testimonials, images, videos and other content you or your customers upload ("<strong>Your Content</strong>"). By using the Service, you grant Testify a worldwide, non-exclusive licence to host, process, resize, transcode and serve Your Content solely to operate the Service (for example, streaming a video testimonial to your website visitors via our widget).</p>
      <p>You are responsible for ensuring you have permission from anyone appearing in Your Content, and that Your Content does not violate third-party rights or laws.</p>

      <h2>4. Acceptable use</h2>
      <p>You agree not to:</p>
      <ul>
        <li>upload testimonials that are fabricated, misleading, or purchased in exchange for a positive review misrepresented as an authentic one;</li>
        <li>upload unlawful, hateful, harassing, sexually explicit, or infringing content;</li>
        <li>attempt to reverse-engineer, resell, or provide the Service to third parties as a white-label without a written agreement;</li>
        <li>overload, probe, or circumvent our rate limits, captchas, or security measures.</li>
      </ul>
      <p>We may remove content or suspend accounts that violate this section without notice.</p>

      <h2>5. Free plan limits</h2>
      <p>Free workspaces are limited to five (5) testimonials and cannot upload video testimonials. Upgrading unlocks unlimited testimonials and video collection.</p>

      <h2>6. Third-party services</h2>
      <p>The Service integrates with third-party providers including Stripe (payments), Resend (email delivery), Google reCAPTCHA (spam protection), Google Sign-in (authentication), and AWS S3 (media storage). Their own terms and privacy policies apply to their handling of data.</p>

      <h2>7. Termination</h2>
      <p>You can cancel any time from Settings → Billing. On cancellation, paid features stop at the end of the current billing period. You can export testimonial data via the dashboard at any time. We may terminate accounts that materially breach these Terms.</p>

      <h2>8. Warranty and liability</h2>
      <p>The Service is provided "as is". To the maximum extent permitted by law, Testify's total liability for any claim arising out of the Service is limited to the amount you paid us in the twelve months preceding the claim. We are not liable for indirect, incidental, or consequential damages.</p>

      <h2>9. Changes to these Terms</h2>
      <p>We may update these Terms. Material changes will be announced by email or in-app at least 14 days before they take effect.</p>

      <h2>10. Governing law</h2>
      <p>These Terms are governed by the laws of India. Any dispute will be resolved in the courts of Kerala, India, unless local consumer-protection law says otherwise.</p>

      <h2>11. Contact</h2>
      <p>Questions? Email us at <a href="mailto:hello@testify.day">hello@testify.day</a>.</p>
    </LegalPage>
  );
}
