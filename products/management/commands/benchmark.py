"""
Management command: benchmark

Measures REAL response times for:
  1. Supabase (PostgreSQL) — direct psycopg2 connection
  2. Cloudinary — HTTP fetch of real image URLs (via Cloudinary API + DB)

Usage:
    python manage.py benchmark
    python manage.py benchmark --samples 8
"""

import os
import time
import statistics
import urllib.request
import urllib.error
from pathlib import Path

from django.core.management.base import BaseCommand
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[4] / ".env")

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
DIM    = "\033[2m"


def colour_ms(ms: float) -> str:
    val = f"{ms:.1f} ms"
    if ms < 200:   return f"{GREEN}{val}{RESET}"
    if ms < 600:   return f"{YELLOW}{val}{RESET}"
    return f"{RED}{val}{RESET}"


def print_stats(label: str, samples: list):
    mn    = min(samples)
    mx    = max(samples)
    avg   = statistics.mean(samples)
    med   = statistics.median(samples)
    stdev = statistics.stdev(samples) if len(samples) > 1 else 0.0
    print(
        f"  {BOLD}{label:<44}{RESET}"
        f"  min {colour_ms(mn):<26}"
        f"  avg {colour_ms(avg):<26}"
        f"  med {colour_ms(med):<26}"
        f"  max {colour_ms(mx):<26}"
        f"  {DIM}σ {stdev:.1f}ms{RESET}"
    )


def parse_pg_url(url: str) -> dict:
    """Safely parse postgresql:// URL even with '@' in password (uses rfind)."""
    url = url.strip()
    rest = url[url.index("://") + 3:]
    at   = rest.rfind("@")
    userinfo, hostinfo = rest[:at], rest[at + 1:]
    colon = userinfo.index(":")
    user, password = userinfo[:colon], userinfo[colon + 1:]
    slash = hostinfo.index("/")
    host_port, dbname = hostinfo[:slash], hostinfo[slash + 1:]
    host, port = host_port.rsplit(":", 1) if ":" in host_port else (host_port, "5432")
    return dict(host=host, port=int(port), user=user, password=password, dbname=dbname)


def http_fetch_ms(url: str, read_bytes: int = 8192, timeout: int = 20) -> float:
    req = urllib.request.Request(url, headers={"User-Agent": "django-benchmark/1.0"})
    t0  = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp.read(read_bytes)
    return (time.perf_counter() - t0) * 1000


class Command(BaseCommand):
    help = "Benchmark Supabase DB and Cloudinary image response times."

    def add_arguments(self, parser):
        parser.add_argument("--samples", type=int, default=5,
                            help="Repetitions per test (default: 5)")

    def handle(self, *args, **options):
        n              = options["samples"]
        db_url         = os.environ.get("DATABASE_URL", "")
        cloudinary_url = os.environ.get("CLOUDINARY_URL", "")

        print(f"\n{BOLD}{'═' * 78}{RESET}")
        print(f"{BOLD}  BENCHMARK  ·  Supabase & Cloudinary  ·  samples = {n}{RESET}")
        print(f"{BOLD}{'═' * 78}{RESET}\n")

        # ── 1. SUPABASE ────────────────────────────────────────────────────────
        print(f"{BOLD}{CYAN}[ 1 ]  Supabase PostgreSQL{RESET}")
        creds = None

        if not db_url:
            print(f"  {RED}✗  DATABASE_URL not found in .env{RESET}\n")
        else:
            try:
                creds = parse_pg_url(db_url)
            except Exception as e:
                print(f"  {RED}✗  Cannot parse DATABASE_URL: {e}{RESET}\n")

        if creds:
            print(f"  {DIM}Connecting to {creds['host']}:{creds['port']} / {creds['dbname']}{RESET}\n")

            try:
                import psycopg2
            except ImportError:
                print(f"  {RED}✗  psycopg2 not installed → pip install psycopg2-binary{RESET}\n")
                psycopg2 = None
                creds = None

        if creds and psycopg2:
            # ── Connection time ──
            conn = None
            conn_times = []
            for i in range(n):
                t0 = time.perf_counter()
                try:
                    c = psycopg2.connect(
                        host=creds["host"], port=creds["port"],
                        user=creds["user"], password=creds["password"],
                        dbname=creds["dbname"], connect_timeout=15, sslmode="require",
                    )
                    conn_times.append((time.perf_counter() - t0) * 1000)
                    conn = conn or c
                    if c is not conn:
                        c.close()
                except psycopg2.OperationalError as e:
                    err = str(e).strip()
                    # Give helpful hint for paused Supabase projects
                    if "ENOTFOUND" in err or "tenant" in err.lower():
                        print(f"  {RED}✗  Supabase project appears to be PAUSED.{RESET}")
                        print(f"  {YELLOW}  ➜  Go to https://supabase.com/dashboard → your project → Resume{RESET}")
                    else:
                        print(f"  {RED}✗  Connection failed: {err}{RESET}")
                    conn = None
                    break

            if conn_times:
                print_stats("TCP connect + TLS handshake", conn_times)

            if conn:
                cur = conn.cursor()
                queries = [
                    ("SELECT 1  (raw ping)",
                     "SELECT 1"),
                    ("COUNT products",
                     "SELECT COUNT(*) FROM products_product"),
                    ("SELECT 20 products (id, name, price)",
                     "SELECT id, name, price FROM products_product ORDER BY id LIMIT 20"),
                    ("SELECT products JOIN category",
                     "SELECT p.id, p.name, c.name "
                     "FROM products_product p "
                     "JOIN products_category c ON c.id=p.category_id LIMIT 20"),
                    ("SELECT single product by slug",
                     "SELECT * FROM products_product ORDER BY id LIMIT 1"),
                    ("COUNT orders",
                     "SELECT COUNT(*) FROM orders_order"),
                    ("SELECT orders JOIN orderitems",
                     "SELECT o.id, o.created_at, i.quantity "
                     "FROM orders_order o "
                     "JOIN orders_orderitem i ON i.order_id=o.id LIMIT 10"),
                ]

                for label, sql in queries:
                    timings, error = [], None
                    for _ in range(n):
                        try:
                            t0 = time.perf_counter()
                            cur.execute(sql)
                            cur.fetchall()
                            timings.append((time.perf_counter() - t0) * 1000)
                        except Exception as e:
                            error = str(e)
                            conn.rollback()
                            break
                    if error:
                        print(f"  {YELLOW}  ⚠  {label}: {error}{RESET}")
                    else:
                        print_stats(label, timings)

                cur.close()
                conn.close()
            elif not conn_times:
                pass  # error already printed

        # ── 2. CLOUDINARY ──────────────────────────────────────────────────────
        print(f"\n{BOLD}{CYAN}[ 2 ]  Cloudinary Image Fetch  (HTTP GET){RESET}\n")

        image_urls = self._get_image_urls(cloudinary_url, creds)

        if not image_urls:
            print(f"  {YELLOW}⚠  Could not find any Cloudinary image URLs.{RESET}")
            print(f"  {DIM}  Possible reasons:{RESET}")
            print(f"  {DIM}  • Supabase project is paused (images stored there){RESET}")
            print(f"  {DIM}  • No products with uploaded images exist{RESET}")
            print(f"  {DIM}  • CLOUDINARY_URL not set in .env{RESET}\n")
        else:
            print(f"  {DIM}Testing {len(image_urls)} image(s) · reading first 8 KB per sample{RESET}\n")

            for idx, (label, url) in enumerate(image_urls, 1):
                short = url[:75] + "…" if len(url) > 75 else url
                print(f"  {BOLD}Image {idx}  [{label}]{RESET}")
                print(f"  {DIM}{short}{RESET}")
                timings, error = [], None
                for _ in range(n):
                    try:
                        timings.append(http_fetch_ms(url))
                    except Exception as e:
                        error = str(e)
                        break
                if error:
                    print(f"  {RED}  ✗  {error}{RESET}\n")
                else:
                    print_stats(f"  HTTP GET image {idx}", timings)
                    print()

        # ── LEGEND ──────────────────────────────────────────────────────────────
        print(f"{BOLD}{'═' * 78}{RESET}")
        print(f"  {GREEN}● < 200 ms  fast{RESET}   {YELLOW}● 200–599 ms  moderate{RESET}   {RED}● ≥ 600 ms  slow{RESET}")
        print(f"{BOLD}{'═' * 78}{RESET}\n")

    # ── helpers ───────────────────────────────────────────────────────────────

    def _get_image_urls(self, cloudinary_url: str, creds: dict) -> list:
        """
        Returns list of (label, url) tuples for Cloudinary images.
        Tries 3 strategies in order:
          A) Django ORM  (works if using Supabase + Cloudinary storage)
          B) Direct Supabase query (if connection available)
          C) Cloudinary Admin API  (lists uploaded assets directly)
        """
        results = []
        cloud_name = cloudinary_url.split("@")[-1].strip("/") if cloudinary_url else ""

        # Strategy A — Django ORM
        try:
            from products.models import Product, ProductImage
            for p in Product.objects.exclude(image="").exclude(image__isnull=True)[:3]:
                try:
                    url = p.image.url
                    if url.startswith("http"):
                        results.append((p.name[:30], url))
                except Exception:
                    pass
            if len(results) < 3:
                for gi in ProductImage.objects.all()[:3]:
                    try:
                        url = gi.image.url
                        if url.startswith("http") and url not in [u for _, u in results]:
                            results.append((f"Gallery img #{gi.pk}", url))
                    except Exception:
                        pass
        except Exception:
            pass

        # Strategy B — Direct Supabase query
        if not results and creds:
            try:
                import psycopg2
                conn = psycopg2.connect(
                    host=creds["host"], port=creds["port"],
                    user=creds["user"], password=creds["password"],
                    dbname=creds["dbname"], connect_timeout=10, sslmode="require",
                )
                cur = conn.cursor()
                cur.execute(
                    "SELECT name, image FROM products_product "
                    "WHERE image IS NOT NULL AND image <> '' LIMIT 3"
                )
                for name, path in cur.fetchall():
                    if path.startswith("http"):
                        results.append((name[:30], path))
                    elif cloud_name and path:
                        url = f"https://res.cloudinary.com/{cloud_name}/image/upload/{path}"
                        results.append((name[:30], url))
                cur.close()
                conn.close()
            except Exception:
                pass

        # Strategy C — Cloudinary Admin API (works without DB)
        if not results and cloudinary_url and cloud_name:
            try:
                import cloudinary
                import cloudinary.api
                # cloudinary_url is already in env — cloudinary lib reads it automatically
                response = cloudinary.api.resources(
                    type="upload", max_results=3, resource_type="image"
                )
                for asset in response.get("resources", []):
                    url = asset.get("secure_url", "")
                    pid = asset.get("public_id", "asset")
                    if url:
                        results.append((pid[:30], url))
            except Exception as e:
                print(f"  {DIM}(Cloudinary API list failed: {e}){RESET}")

        return results[:3]
