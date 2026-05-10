"""
Management command: benchmark

Measures REAL response times for:
  1. Supabase (PostgreSQL) — direct psycopg2 using parsed .env credentials
  2. Cloudinary — HTTP fetch of actual image URLs

Usage:
    python manage.py benchmark
    python manage.py benchmark --samples 8
"""

import os
import re
import time
import statistics
import urllib.request
from pathlib import Path

from django.core.management.base import BaseCommand
from dotenv import load_dotenv

# Load .env from the project root
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
    if ms < 200:
        return f"{GREEN}{val}{RESET}"
    elif ms < 600:
        return f"{YELLOW}{val}{RESET}"
    return f"{RED}{val}{RESET}"


def print_stats(label: str, samples: list):
    mn    = min(samples)
    mx    = max(samples)
    avg   = statistics.mean(samples)
    med   = statistics.median(samples)
    stdev = statistics.stdev(samples) if len(samples) > 1 else 0.0
    print(
        f"  {BOLD}{label:<42}{RESET}"
        f"  min {colour_ms(mn):<26}"
        f"  avg {colour_ms(avg):<26}"
        f"  med {colour_ms(med):<26}"
        f"  max {colour_ms(mx):<26}"
        f"  {DIM}σ={stdev:.1f}ms{RESET}"
    )


def parse_pg_url(url: str) -> dict:
    """
    Safely parse a postgresql:// URL even when the password contains '@'.
    Format: postgresql://user:password@host:port/dbname
    We find the LAST '@' before the host part.
    """
    # Strip scheme
    url = url.strip()
    scheme_end = url.index("://") + 3
    rest = url[scheme_end:]  # user:password@host:port/dbname

    # Split on the LAST @ to handle passwords containing @
    at_idx = rest.rfind("@")
    userinfo = rest[:at_idx]           # user:password
    hostinfo = rest[at_idx + 1:]      # host:port/dbname

    # userinfo: split on FIRST colon only
    colon_idx = userinfo.index(":")
    user = userinfo[:colon_idx]
    password = userinfo[colon_idx + 1:]

    # hostinfo: host:port/dbname
    slash_idx = hostinfo.index("/")
    host_port = hostinfo[:slash_idx]
    dbname = hostinfo[slash_idx + 1:]

    if ":" in host_port:
        host, port_str = host_port.rsplit(":", 1)
        port = int(port_str)
    else:
        host = host_port
        port = 5432

    return {
        "host":     host,
        "port":     port,
        "user":     user,
        "password": password,
        "dbname":   dbname,
    }


class Command(BaseCommand):
    help = "Benchmark real Supabase response times and Cloudinary image fetch times."

    def add_arguments(self, parser):
        parser.add_argument(
            "--samples",
            type=int,
            default=5,
            help="Repetitions per test (default: 5)",
        )

    def handle(self, *args, **options):
        n = options["samples"]
        db_url        = os.environ.get("DATABASE_URL", "")
        cloudinary_url = os.environ.get("CLOUDINARY_URL", "")

        print(f"\n{BOLD}{'═' * 75}{RESET}")
        print(f"{BOLD}  BENCHMARK  ·  Supabase & Cloudinary  ·  samples={n}{RESET}")
        print(f"{BOLD}{'═' * 75}{RESET}\n")

        # ── 1. Supabase ────────────────────────────────────────────────────────
        print(f"{BOLD}{CYAN}[ 1 ]  Supabase PostgreSQL  (Direct Connection){RESET}")

        if not db_url:
            print(f"  {RED}✗  DATABASE_URL not found in .env{RESET}\n")
        else:
            try:
                creds = parse_pg_url(db_url)
                print(f"  {DIM}Host: {creds['host']}:{creds['port']}  db={creds['dbname']}  user={creds['user']}{RESET}\n")
            except Exception as e:
                print(f"  {RED}✗  Failed to parse DATABASE_URL: {e}{RESET}\n")
                creds = None

            try:
                import psycopg2
            except ImportError:
                print(f"  {RED}✗  psycopg2 not installed. Run: pip install psycopg2-binary{RESET}\n")
                psycopg2 = None
                creds = None

            if creds and psycopg2:
                # -- Measure connection time --
                conn_times = []
                conn = None
                for i in range(n):
                    t0 = time.perf_counter()
                    try:
                        c = psycopg2.connect(
                            host=creds["host"],
                            port=creds["port"],
                            user=creds["user"],
                            password=creds["password"],
                            dbname=creds["dbname"],
                            connect_timeout=15,
                            sslmode="require",
                        )
                        elapsed = (time.perf_counter() - t0) * 1000
                        conn_times.append(elapsed)
                        if conn is None:
                            conn = c
                        else:
                            c.close()
                    except Exception as e:
                        print(f"  {RED}✗  Connection failed on sample {i+1}: {e}{RESET}\n")
                        conn = None
                        break

                if conn_times:
                    print_stats("TCP connect + TLS handshake", conn_times)

                if conn:
                    cur = conn.cursor()
                    supabase_tests = [
                        ("SELECT 1  (raw ping)",
                         "SELECT 1"),
                        ("COUNT products_product",
                         "SELECT COUNT(*) FROM products_product"),
                        ("SELECT 20 products (id, name, price)",
                         "SELECT id, name, price FROM products_product ORDER BY id LIMIT 20"),
                        ("SELECT products JOIN category",
                         "SELECT p.id, p.name, c.name FROM products_product p "
                         "JOIN products_category c ON c.id = p.category_id LIMIT 20"),
                        ("Single product by slug (indexed)",
                         "SELECT * FROM products_product ORDER BY id LIMIT 1"),
                        ("COUNT orders_order",
                         "SELECT COUNT(*) FROM orders_order"),
                        ("SELECT 10 orders + orderitems JOIN",
                         "SELECT o.id, o.created_at, i.quantity "
                         "FROM orders_order o "
                         "JOIN orders_orderitem i ON i.order_id = o.id LIMIT 10"),
                    ]

                    for label, sql in supabase_tests:
                        timings = []
                        error = None
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

        # ── 2. Cloudinary ──────────────────────────────────────────────────────
        print(f"\n{BOLD}{CYAN}[ 2 ]  Cloudinary Image Fetch  (HTTP GET){RESET}\n")

        image_urls = self._collect_cloudinary_urls(db_url, cloudinary_url, creds if db_url else None)

        if not image_urls:
            print(f"  {YELLOW}⚠  No Cloudinary image URLs found.{RESET}")
            print(f"  Make sure products have images uploaded to Cloudinary.\n")
        else:
            print(f"  {DIM}Testing {len(image_urls)} image(s) — downloading first 4 KB per sample{RESET}\n")
            for idx, url in enumerate(image_urls, 1):
                short = url[:72] + "…" if len(url) > 72 else url
                print(f"  {BOLD}Image {idx}:{RESET} {DIM}{short}{RESET}")
                timings = []
                error = None
                for _ in range(n):
                    try:
                        t0 = time.perf_counter()
                        req = urllib.request.Request(
                            url, headers={"User-Agent": "django-benchmark/1.0"}
                        )
                        with urllib.request.urlopen(req, timeout=20) as resp:
                            resp.read(4096)
                        timings.append((time.perf_counter() - t0) * 1000)
                    except Exception as e:
                        error = str(e)
                        break

                if error:
                    print(f"  {RED}  ✗  Fetch failed: {error}{RESET}\n")
                else:
                    print_stats(f"  Image {idx} HTTP GET", timings)
                    print()

        # ── Legend ─────────────────────────────────────────────────────────────
        print(f"{BOLD}{'═' * 75}{RESET}")
        print(
            f"  {GREEN}● < 200 ms  fast{RESET}   "
            f"{YELLOW}● 200–599 ms  moderate{RESET}   "
            f"{RED}● ≥ 600 ms  slow{RESET}"
        )
        print(f"{BOLD}{'═' * 75}{RESET}\n")

    # ── helpers ───────────────────────────────────────────────────────────────

    def _collect_cloudinary_urls(self, db_url: str, cloudinary_url: str, creds: dict) -> list:
        urls = []
        cloud_name = self._extract_cloud_name(cloudinary_url)

        # Strategy A: Django ORM (works with SQLite or Supabase if settings is correct)
        try:
            from products.models import Product, ProductImage
            for p in Product.objects.exclude(image="").exclude(image__isnull=True)[:4]:
                try:
                    url = p.image.url
                    if url.startswith("http"):
                        urls.append(url)
                except Exception:
                    pass

            for gi in ProductImage.objects.all()[:4]:
                try:
                    url = gi.image.url
                    if url.startswith("http") and url not in urls:
                        urls.append(url)
                except Exception:
                    pass
        except Exception:
            pass

        # Strategy B: Query Supabase directly for raw paths, build URL
        if not urls and creds and cloud_name:
            try:
                import psycopg2
                conn = psycopg2.connect(
                    host=creds["host"], port=creds["port"],
                    user=creds["user"], password=creds["password"],
                    dbname=creds["dbname"], connect_timeout=10, sslmode="require",
                )
                cur = conn.cursor()
                cur.execute(
                    "SELECT image FROM products_product "
                    "WHERE image IS NOT NULL AND image <> '' LIMIT 4"
                )
                rows = cur.fetchall()
                cur.close()
                conn.close()

                for (path,) in rows:
                    if path.startswith("http"):
                        urls.append(path)
                    elif path:
                        urls.append(
                            f"https://res.cloudinary.com/{cloud_name}/image/upload/{path}"
                        )
            except Exception as e:
                print(f"  {DIM}(Could not query Supabase for image paths: {e}){RESET}")

        return urls[:3]

    def _extract_cloud_name(self, cloudinary_url: str) -> str:
        """Extract cloud name from cloudinary://key:secret@cloud_name"""
        try:
            return cloudinary_url.strip().split("@")[-1].strip("/")
        except Exception:
            return ""
