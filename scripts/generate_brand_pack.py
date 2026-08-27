"""One-shot script to generate the full Testify brand pack using Nano Banana.

Run: python scripts/generate_brand_pack.py
Outputs saved to /app/frontend/public/brand/
"""
import asyncio
import base64
import os
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image

from emergentintegrations.llm.chat import LlmChat, UserMessage

load_dotenv("/app/backend/.env")

OUT = Path("/app/frontend/public/brand")
OUT.mkdir(parents=True, exist_ok=True)

MODEL = "gemini-3.1-flash-image-preview"
API_KEY = os.environ["EMERGENT_LLM_KEY"]

BRAND_CONTEXT = (
    "Brand: Testify — a modern testimonial-collection SaaS for founders and marketers. "
    "Primary color: vibrant orange #ff5722 (like sunset ember). "
    "Secondary: near-black #0a0a0a and warm charcoal #151515. Accent: white. "
    "Style: bold, confident, editorial. Not corporate. Modern minimalism with subtle grain/noise texture. "
    "Never generic AI slop. No purple-blue gradients. No stock imagery clichés. "
    "Feel: trustworthy but energetic — think Linear, Vercel, Framer aesthetic."
)

ASSETS = [
    {
        "name": "logo-mark",
        "size": (1024, 1024),
        "final_size": (512, 512),
        "prompt": (
            f"{BRAND_CONTEXT}\n\n"
            "Design a single, iconic square LOGO MARK (just the symbol, no wordmark). "
            "Concept: a stylized open quotation mark morphing into a checkmark, or a bold 'T' "
            "made of two overlapping speech bubbles. Fully solid orange #ff5722 on a completely "
            "transparent background. Flat vector look, clean edges, no gradients, no shadows, "
            "no 3D, no photorealism. Must read clearly at 32px. Centered with generous padding. "
            "Output ONLY the mark on transparent background."
        ),
    },
    {
        "name": "wordmark",
        "size": (1024, 1024),
        "final_size": (1200, 400),
        "prompt": (
            f"{BRAND_CONTEXT}\n\n"
            "Create a WORDMARK LOGO: the word 'testify' in lowercase, custom modern sans-serif, "
            "letter-spacing slightly tight. Solid orange #ff5722 text on transparent background. "
            "The dot on the 'i' replaced with a small orange checkmark symbol. "
            "Editorial, confident, geometric like Söhne or Neue Haas. Centered horizontally. "
            "No taglines, no other text, no borders."
        ),
    },
    {
        "name": "plan-pro-stripe",
        "size": (1024, 1024),
        "final_size": (768, 768),
        "prompt": (
            f"{BRAND_CONTEXT}\n\n"
            "Design a premium product card image for STRIPE CHECKOUT representing the 'PRO' subscription tier. "
            "Square composition. Dark background #0a0a0a with subtle grain texture. "
            "Centered: a large, elegant lowercase word 'Pro' in orange #ff5722 (custom sans-serif). "
            "Above it, a small orange star or spark icon. Below it, three horizontal orange lines "
            "of decreasing width suggesting features. In the top-right corner, a small 'testify' wordmark in white. "
            "Warm ambient orange glow behind the 'Pro' word for depth. NO people, NO stock photos, "
            "NO abstract 3D blobs. Editorial and clean like a Vercel product card."
        ),
    },
    {
        "name": "plan-business-stripe",
        "size": (1024, 1024),
        "final_size": (768, 768),
        "prompt": (
            f"{BRAND_CONTEXT}\n\n"
            "Design a premium product card image for STRIPE CHECKOUT representing the 'BUSINESS' subscription tier. "
            "Square composition. Dark background #0a0a0a with subtle grain texture. "
            "Centered: a large, elegant lowercase word 'Business' in orange #ff5722. "
            "Above it, three small orange stars in a row (denoting higher tier than Pro). "
            "Below it, five horizontal orange lines of decreasing width. "
            "Top-right corner: 'testify' wordmark in white. "
            "Add a subtle orange corner accent or crown-like flourish (small, not gaudy) to indicate premium. "
            "Warm ambient orange glow. NO people, NO stock photos. Editorial like a Vercel product card. "
            "Feel: slightly more luxurious than the Pro card while remaining minimalist."
        ),
    },
    {
        "name": "og-image",
        "size": (1024, 1024),
        "final_size": (1200, 630),
        "prompt": (
            f"{BRAND_CONTEXT}\n\n"
            "Design an Open Graph SOCIAL SHARE IMAGE for testify.day. Wide 16:9-ish composition. "
            "Dark #0a0a0a background with subtle grain. Left side: bold headline text 'Collect testimonials "
            "customers love to give' in white lowercase sans-serif, tight line-height, 3 lines. "
            "Right side: an abstract stack of 3 tilted testimonial cards (small chips with quote marks, star ratings, "
            "avatar circles) floating with subtle drop shadows, primary card highlighted in orange #ff5722. "
            "Bottom-left corner: small 'testify' wordmark in orange. "
            "Editorial magazine layout. No emojis, no clip art, no purple/blue."
        ),
    },
    {
        "name": "instagram-square",
        "size": (1024, 1024),
        "final_size": (1080, 1080),
        "prompt": (
            f"{BRAND_CONTEXT}\n\n"
            "Design an Instagram SQUARE POST. 1:1. Dark #0a0a0a background with subtle grain. "
            "Center-top: a large orange #ff5722 quote glyph (\") 30% of the height. "
            "Below it, the phrase 'Your customers are your best marketers.' in white lowercase, "
            "large modern sans-serif, tight line-height, 2 lines maximum, left-aligned or centered. "
            "Bottom-right corner: small orange 'testify' wordmark. "
            "Bottom-left corner: small orange dot + 'testify.day' text in white. "
            "Editorial, high contrast, no stock imagery. Reads at thumbnail size."
        ),
    },
    {
        "name": "twitter-header",
        "size": (1024, 1024),
        "final_size": (1500, 500),
        "prompt": (
            f"{BRAND_CONTEXT}\n\n"
            "Design a Twitter/X HEADER banner. Very wide 3:1 composition. Dark #0a0a0a background with grain. "
            "Left third: the word 'testify' in large orange #ff5722 lowercase custom sans-serif. "
            "Middle third: a horizontal row of 5 small floating testimonial chip cards, each with a quote mark "
            "and star rating, slightly tilted, primary color orange, secondary chips in white/gray. "
            "Right third: negative space with a small tagline 'Testimonials, minus the awkward ask' in white "
            "lowercase, 2 lines. Subtle orange glow behind the middle chips. Editorial, minimalist."
        ),
    },
    {
        "name": "linkedin-banner",
        "size": (1024, 1024),
        "final_size": (1584, 396),
        "prompt": (
            f"{BRAND_CONTEXT}\n\n"
            "Design a LinkedIn cover banner. Ultra-wide 4:1 composition. Dark #0a0a0a background with grain. "
            "Left: the word 'testify' large in orange #ff5722. "
            "Center: tagline 'Turn happy customers into your best sales team' in white lowercase, 1 line, "
            "elegant modern sans-serif. Right: 3 small tilted testimonial cards with quote marks and orange 5-star rows. "
            "Bottom-right small text: 'testify.day'. Professional but not stiff. Editorial magazine feel."
        ),
    },
]


async def generate_one(asset):
    print(f"→ Generating {asset['name']} …")
    chat = LlmChat(
        api_key=API_KEY,
        session_id=f"brand-{asset['name']}",
        system_message="You are a senior brand designer at a top digital design agency. Produce editorial, print-quality brand imagery.",
    ).with_model("gemini", MODEL).with_params(modalities=["image", "text"])
    msg = UserMessage(text=asset["prompt"])
    _text, images = await chat.send_message_multimodal_response(msg)
    if not images:
        print(f"  ✗ no image returned for {asset['name']}")
        return None
    raw = base64.b64decode(images[0]["data"])
    img = Image.open(BytesIO(raw)).convert("RGBA")
    if asset.get("final_size"):
        target = asset["final_size"]
        # Fit-to-cover then crop centered
        src_ratio = img.width / img.height
        tgt_ratio = target[0] / target[1]
        if src_ratio > tgt_ratio:
            new_w = int(img.height * tgt_ratio)
            left = (img.width - new_w) // 2
            img = img.crop((left, 0, left + new_w, img.height))
        else:
            new_h = int(img.width / tgt_ratio)
            top = (img.height - new_h) // 2
            img = img.crop((0, top, img.width, top + new_h))
        img = img.resize(target, Image.LANCZOS)
    out_png = OUT / f"testify-{asset['name']}.png"
    img.save(out_png, "PNG", optimize=True)
    if asset["name"] in {"plan-pro-stripe", "plan-business-stripe"}:
        # Stripe accepts JPG/PNG/WEBP under 2MB — provide a JPG copy for size safety
        rgb = img.convert("RGB")
        out_jpg = OUT / f"testify-{asset['name']}.jpg"
        rgb.save(out_jpg, "JPEG", quality=88, optimize=True)
    print(f"  ✓ saved {out_png.name} ({out_png.stat().st_size // 1024} KB)")
    return out_png


async def main():
    for asset in ASSETS:
        try:
            await generate_one(asset)
        except Exception as e:
            print(f"  ✗ {asset['name']} failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
