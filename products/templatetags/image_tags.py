"""
image_tags.py
─────────────
Cloudinary image optimization template tags.

Usage in templates:
    {% load image_tags %}

    {# Auto-optimize — auto format (WebP/AVIF) + auto quality #}
    <img src="{% cloudinary_url product.image.url %}" loading="lazy" ...>

    {# With resize — thumbnail for cards (width=400, auto height) #}
    <img src="{% cloudinary_url product.image.url width=400 %}" loading="lazy" ...>

    {# Full options #}
    <img src="{% cloudinary_url product.image.url width=800 quality=70 %}" ...>

What this does to the Cloudinary URL:
    BEFORE: https://res.cloudinary.com/dc2djypb7/image/upload/v123/media/products/img.jpg
    AFTER:  https://res.cloudinary.com/dc2djypb7/image/upload/f_auto,q_auto,w_400/v123/media/products/img.jpg

  f_auto  → serves WebP/AVIF to modern browsers (50-70% smaller than JPEG/PNG)
  q_auto  → Cloudinary chooses the best quality level automatically
  w_400   → resizes to 400px wide on the CDN (no more serving 4MB images for thumbnails)

This alone can cut image load time from 700ms → 100-200ms.
"""

import re
from django import template

register = template.Library()


def _inject_transformations(url: str, transforms: str) -> str:
    """
    Injects Cloudinary transformation string after /upload/ in the URL.

    /upload/v123/...   →  /upload/<transforms>/v123/...
    /upload/f_auto/v1/ →  replaces existing transforms (idempotent)
    Non-Cloudinary URLs are returned unchanged.
    """
    if not url or "res.cloudinary.com" not in url:
        return url

    # Match /upload/ followed by existing transforms OR versioned path
    # Pattern: /upload/(optional_transforms/)?(v\d+/|<path>)
    pattern = r"(/image/upload/)(?:[a-z_,0-9]+/)?(?=v\d+/|media/|[^/])"
    replacement = r"\g<1>" + transforms + "/"

    new_url, count = re.subn(pattern, replacement, url, count=1)
    if count == 0:
        # Fallback: just insert after /upload/
        new_url = url.replace("/image/upload/", f"/image/upload/{transforms}/", 1)
    return new_url


@register.simple_tag
def cloudinary_url(url, width=None, height=None, quality="auto", fmt="auto"):
    """
    Returns an optimized Cloudinary URL.

    Args:
        url     : The original Cloudinary URL (from product.image.url)
        width   : Optional pixel width to resize to (e.g. 400 for thumbnails)
        height  : Optional pixel height
        quality : Cloudinary quality level. Default "auto" (recommended)
        fmt     : Cloudinary format. Default "auto" (serves WebP/AVIF to modern browsers)

    Example:
        {% cloudinary_url product.image.url width=400 %}
        → serves a 400px-wide WebP/AVIF image with auto quality
    """
    if not url:
        return ""

    parts = [f"f_{fmt}", f"q_{quality}"]

    if width:
        parts.append(f"w_{width}")
        # Use crop=fill so image fills the requested dimensions cleanly
        parts.append("c_fill")

    if height:
        parts.append(f"h_{height}")
        if "c_fill" not in parts:
            parts.append("c_fill")

    transforms = ",".join(parts)
    return _inject_transformations(url, transforms)
