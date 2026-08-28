import React from "react";
import LegalPage from "./LegalPage";

export default function Privacy() {
  return (
    <LegalPage title="Privacy Policy" updated="27 January 2026">
      <p>This Privacy Notice for Testify ("<strong>we</strong>", "<strong>us</strong>", "<strong>our</strong>") describes how and why we might access, collect, store, use, and/or share ("<strong>process</strong>") your personal information when you use our services ("<strong>Services</strong>"), including when you:</p>
      <ul>
        <li>Visit our website at <a href="https://www.testify.day">https://www.testify.day</a> or any website of ours that links to this Privacy Notice</li>
        <li>Engage with us in other related ways, including any sales, marketing, or events</li>
      </ul>
      <p><strong>Questions or concerns?</strong> Reading this Privacy Notice will help you understand your privacy rights and choices. If you do not agree with our policies and practices, please do not use our Services. Contact us at <a href="mailto:hello@testify.day">hello@testify.day</a>.</p>

      <h2>Summary of key points</h2>
      <p><strong>What personal information do we process?</strong> When you visit, use, or navigate our Services, we may process personal information depending on how you interact with us, the choices you make, and the features you use.</p>
      <p><strong>Do we process any sensitive personal information?</strong> We do not process sensitive personal information (e.g. race, sexual orientation, religious beliefs).</p>
      <p><strong>Do we collect any information from third parties?</strong> We do not collect any information from third parties.</p>
      <p><strong>How do we process your information?</strong> To provide, improve, and administer our Services, communicate with you, for security and fraud prevention, and to comply with law.</p>
      <p><strong>With whom do we share personal information?</strong> Only with the third-party processors listed in section 4 below.</p>
      <p><strong>What are your rights?</strong> Depending on where you are located, you may have rights to access, correct, delete, port, or restrict processing of your personal information.</p>

      <h2>1. What information do we collect?</h2>
      <p><strong>Personal information you disclose to us.</strong> We collect personal information that you voluntarily provide when you register on the Services, express interest in our products, participate in activities on the Services, or contact us. This may include:</p>
      <ul>
        <li>names</li>
        <li>email addresses</li>
        <li>passwords (stored as bcrypt hashes only)</li>
        <li>optional profile pictures</li>
        <li>workspace details (business name, logo, brand colours)</li>
        <li>testimonial content you or your customers upload (text, images, videos, ratings, and optional respondent name / email / company)</li>
      </ul>
      <p><strong>Sensitive information.</strong> We do not process sensitive information.</p>
      <p><strong>Payment data.</strong> All payment data is handled and stored by Stripe. You may find their privacy notice at <a href="https://stripe.com/privacy">https://stripe.com/privacy</a>. We only receive a Stripe customer ID and subscription status.</p>
      <p><strong>Social media login data.</strong> We may provide you the option to register using your Google account. If you choose to register this way, we collect the profile information described in section 5.</p>
      <p><strong>Information automatically collected.</strong> Some information — such as your IP address and browser characteristics — is collected automatically when you visit our Services. This includes:</p>
      <ul>
        <li><em>Log and usage data</em> — IP address, device information, browser type, pages viewed, features used, error reports.</li>
        <li><em>Device data</em> — device model, operating system, browser, screen resolution.</li>
        <li><em>Location data</em> — approximate location derived from IP address (not GPS).</li>
      </ul>

      <h2>2. How do we process your information?</h2>
      <p>We process your personal information for a variety of reasons, including:</p>
      <ul>
        <li>to facilitate account creation, authentication, and manage user accounts;</li>
        <li>to deliver the Services (hosting your dashboard, serving embed widgets, sending new-testimonial email alerts);</li>
        <li>to process payments and prevent fraud (via Stripe);</li>
        <li>to protect our Services (spam detection, rate limiting, brute-force lockout);</li>
        <li>to respond to your support requests;</li>
        <li>to save or protect an individual's vital interest, such as to prevent harm;</li>
        <li>to comply with legal obligations.</li>
      </ul>

      <h2>3. What legal bases do we rely on to process your information?</h2>
      <p>The GDPR and UK GDPR require us to explain the valid legal bases we rely on. We may rely on the following:</p>
      <ul>
        <li><strong>Consent.</strong> When you have given us permission to use your personal information for a specific purpose. You can withdraw consent at any time.</li>
        <li><strong>Performance of a contract.</strong> To provide the Services you signed up for.</li>
        <li><strong>Legitimate interests.</strong> To improve, secure, and market our Services, provided this is not overridden by your rights.</li>
        <li><strong>Legal obligations.</strong> To comply with tax, accounting, and other legal requirements.</li>
        <li><strong>Vital interests.</strong> To protect the safety of any person.</li>
      </ul>

      <h2>4. When and with whom do we share your personal information?</h2>
      <p><strong>Vendors, consultants, and other third-party service providers.</strong> We may share your data with third parties who perform services on our behalf and require access to do that work.</p>
      <p>The third parties we share personal information with are:</p>
      <ul>
        <li><strong>Database hosting</strong> — MongoDB Atlas</li>
        <li><strong>Backend hosting</strong> — Railway</li>
        <li><strong>Frontend hosting &amp; CDN</strong> — Vercel</li>
        <li><strong>Media storage</strong> (avatars, images, videos) — Amazon Web Services S3</li>
        <li><strong>Invoice and billing</strong> — Stripe</li>
        <li><strong>Transactional email</strong> — Resend</li>
        <li><strong>Spam &amp; bot protection</strong> — Google reCAPTCHA</li>
        <li><strong>Social login</strong> — Google Sign-In</li>
      </ul>
      <p>We also may need to share your personal information in the following situations:</p>
      <ul>
        <li><strong>Business transfers.</strong> In connection with any merger, sale of company assets, financing, or acquisition of all or part of our business.</li>
      </ul>

      <h2>5. How do we handle your social logins?</h2>
      <p>Our Services offer you the ability to register and log in using your Google account. When you do this we receive certain profile information about you from Google — typically your name, email address, and profile picture. We use this information only for the purposes described in this Privacy Notice. We do not control, and are not responsible for, other uses of your personal information by Google. Review Google's privacy notice to understand their practices.</p>

      <h2>6. Is your information transferred internationally?</h2>
      <p>Our servers and cloud providers are located in India and the United States. If you are accessing our Services from outside these countries, be aware that your information may be transferred to, stored by, and processed by us and our processors in the United States, India, and other countries.</p>
      <p>If you are a resident in the European Economic Area (EEA), United Kingdom (UK), or Switzerland, these countries may not have data-protection laws as comprehensive as those in your country. We will take all necessary measures to protect your personal information in accordance with this Privacy Notice and applicable law, including standard contractual clauses where required.</p>

      <h2>7. How long do we keep your information?</h2>
      <p>We only keep your personal information for as long as necessary for the purposes set out in this Privacy Notice, unless a longer retention period is required or permitted by law (such as tax records — kept for 7 years).</p>
      <p>When you delete your account, we remove personal data within 30 days from active databases. If any data has been backed up, we isolate it from further processing until deletion is possible.</p>

      <h2>8. Do we collect information from minors?</h2>
      <p>We do not knowingly collect data from, or market to, children under 16 years of age. By using the Services, you represent that you are at least 16, or that you are the parent or guardian of such a minor. If we learn that personal information from users under 16 has been collected, we will deactivate the account and delete the data. If you become aware of any data we may have collected from a child under 16, contact us at <a href="mailto:hello@testify.day">hello@testify.day</a>.</p>

      <h2>9. What are your privacy rights?</h2>
      <p>In some regions (like the EEA, UK, Switzerland, and California) you have certain rights under applicable data-protection laws. These may include the right (i) to request access and obtain a copy of your personal information, (ii) to request rectification or erasure, (iii) to restrict processing of your personal information, (iv) data portability, and (v) not to be subject to automated decision-making.</p>
      <p>You can exercise most of these directly from Settings → Account in your dashboard, or by emailing <a href="mailto:hello@testify.day">hello@testify.day</a>. We will consider and act on any request in accordance with applicable law.</p>
      <p>If you are located in the EEA or UK and believe we are unlawfully processing your personal information, you also have the right to complain to your local data-protection authority.</p>
      <p><strong>Withdrawing your consent.</strong> If we are relying on your consent, you have the right to withdraw it at any time — this will not affect the lawfulness of processing before its withdrawal.</p>
      <p><strong>Account information.</strong> If you would like to review or change the information in your account or terminate your account, contact us using the contact details in section 12.</p>

      <h2>10. Controls for Do-Not-Track features</h2>
      <p>Most web browsers include a Do-Not-Track ("DNT") feature. No uniform technology standard for recognising and implementing DNT signals has been finalised. As such, we do not currently respond to DNT browser signals. If a standard is adopted that we must follow, we will inform you in a revised version of this Privacy Notice.</p>

      <h2>11. Do we make updates to this notice?</h2>
      <p>We may update this Privacy Notice from time to time. The updated version will be indicated by a revised "Last updated" date at the top. If we make material changes, we may notify you either by prominently posting a notice in-app or by emailing you. We encourage you to review this Privacy Notice frequently.</p>

      <h2>12. How can you contact us about this notice?</h2>
      <p>If you have questions or comments about this notice, email us at <a href="mailto:hello@testify.day">hello@testify.day</a>.</p>

      <h2>13. How can you review, update, or delete the data we collect from you?</h2>
      <p>Based on the applicable laws of your country, you may have the right to request access to the personal information we collect from you, details about how we have processed it, correct inaccuracies, or delete your personal information. To request to review, update, or delete your personal information, please email us at <a href="mailto:hello@testify.day">hello@testify.day</a>. Most of these actions can also be performed directly from Settings → Account inside your dashboard.</p>
    </LegalPage>
  );
}
