import csv
import io
import json
import os
import re
import time
from decimal import Decimal
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from store.context_processors import nav_categories
from store.models import Product

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SEED_DATA_DIR = PROJECT_ROOT / "seed_data"
MANIFEST_PATH = SEED_DATA_DIR / "manifest.json"
ATTRIBUTIONS_PATH = SEED_DATA_DIR / "attributions.csv"
MEDIA_PRODUCTS_DIR = Path(settings.MEDIA_ROOT) / "products"

CATEGORIES = [
    "Home & Living",
    "Kitchen",
    "Fashion",
    "Bags & Travel",
    "Beauty & Care",
    "Electronics & Gadgets",
    "Stationery",
    "Outdoor",
]

DEMO_BLUEPRINTS = [
    {"name": "Stoneware Ceramic Mug", "category": "Kitchen", "description": "A warm, everyday mug with a softly glazed finish that feels at home on a desk or breakfast table.", "price": "24.99", "stock": 18},
    {"name": "Linen Throw Blanket", "category": "Home & Living", "description": "Lightweight and easy to layer, this textured throw adds warmth without a bulky feel.", "price": "59.99", "stock": 11},
    {"name": "Structured Canvas Tote", "category": "Bags & Travel", "description": "A roomy carryall built for errands, weekend plans, and light daily movement.", "price": "42.49", "stock": 20},
    {"name": "Botanical Body Wash", "category": "Beauty & Care", "description": "A gentle daily wash with a clean botanical scent, made for simple rituals and easy routines.", "price": "18.99", "stock": 26},
    {"name": "Wireless Noise Cancelling Headphones", "category": "Electronics & Gadgets", "description": "Comfortable over-ear sound for focused work, travel, and quiet time at home.", "price": "149.99", "stock": 9},
    {"name": "Hardcover Daily Journal", "category": "Stationery", "description": "A neatly structured journal for notes, plans, and the small details that keep a day steady.", "price": "19.99", "stock": 34},
    {"name": "Insulated Water Bottle", "category": "Outdoor", "description": "A durable bottle designed for commuting, walks, and long afternoons outside.", "price": "29.99", "stock": 16},
    {"name": "Woven Storage Basket", "category": "Home & Living", "description": "A practical storage piece that keeps books, throws, and little essentials close at hand.", "price": "34.99", "stock": 15},
    {"name": "Minimalist Desk Lamp", "category": "Home & Living", "description": "A slim, warm-light lamp that brings a calmer glow to desks, nightstands, and reading corners.", "price": "69.99", "stock": 7},
    {"name": "Glass Food Storage Set", "category": "Kitchen", "description": "Reusable containers that help keep leftovers, prep, and pantry staples neatly sorted.", "price": "39.99", "stock": 21},
    {"name": "Soft Cotton T-Shirt", "category": "Fashion", "description": "A versatile staple in a comfortable cotton blend, made for easy layering and everyday wear.", "price": "24.99", "stock": 30},
    {"name": "Leather Card Holder", "category": "Bags & Travel", "description": "A compact everyday accessory that keeps cards and essentials neatly tucked away.", "price": "28.49", "stock": 12},
    {"name": "Hydrating Face Serum", "category": "Beauty & Care", "description": "A lightweight daily serum made to support comfort, hydration, and a fresh start to the day.", "price": "32.99", "stock": 18},
    {"name": "Portable Bluetooth Speaker", "category": "Electronics & Gadgets", "description": "A compact speaker with warm sound and easy portability for rooms, patios, and travel days.", "price": "54.99", "stock": 8},
    {"name": "Letter Writing Set", "category": "Stationery", "description": "A thoughtful set for correspondence, gift notes, and the slower kind of paper rituals.", "price": "16.99", "stock": 24},
    {"name": "Foldable Camp Chair", "category": "Outdoor", "description": "A sturdy seat for porch evenings, picnic breaks, and quick outdoor reset moments.", "price": "79.99", "stock": 10},
    {"name": "Candle in Glass Jar", "category": "Home & Living", "description": "A clean-burning candle with a warm scent profile that settles naturally into a relaxed room.", "price": "21.99", "stock": 17},
    {"name": "Bamboo Serving Tray", "category": "Kitchen", "description": "A simple tray that keeps coffee, snacks, and small essentials organized in a clean, natural style.", "price": "31.99", "stock": 13},
    {"name": "Wool Knit Scarf", "category": "Fashion", "description": "A soft knit layer designed for crisp mornings, daily movement, and easy styling.", "price": "36.99", "stock": 14},
    {"name": "Travel Organizer Pouch", "category": "Bags & Travel", "description": "A compact pouch that keeps cords, toiletries, and small essentials easy to find on the go.", "price": "26.49", "stock": 23},
    {"name": "Nourishing Hand Cream", "category": "Beauty & Care", "description": "A rich cream with a comforting finish that works well after washing hands throughout the day.", "price": "15.99", "stock": 29},
    {"name": "Rechargeable Desk Fan", "category": "Electronics & Gadgets", "description": "A quiet personal fan for warm afternoons, compact desks, and small rooms.", "price": "49.99", "stock": 11},
    {"name": "Pastel Sticky Notes Pack", "category": "Stationery", "description": "Bright notes for reminders, lists, and playful markers in everyday planning.", "price": "9.99", "stock": 42},
    {"name": "Hiking Daypack", "category": "Outdoor", "description": "A practical pack with room for essentials, water, and quick layers for a longer day outside.", "price": "89.99", "stock": 6},
    {"name": "Textured Accent Pillow", "category": "Home & Living", "description": "A small update with a simple silhouette that lends softness and contrast to a room.", "price": "27.99", "stock": 19},
    {"name": "Porcelain Mixing Bowl", "category": "Kitchen", "description": "A versatile bowl for prep, serving, and thoughtful kitchen routines that feel easy and calm.", "price": "35.99", "stock": 10},
    {"name": "Classic Cotton Button-Up", "category": "Fashion", "description": "A crisp, easy-to-style shirt with a relaxed fit designed for day-to-day opening and layering.", "price": "58.99", "stock": 18},
    {"name": "Weekend Weekender Bag", "category": "Bags & Travel", "description": "A neatly sized carry bag with enough room for essentials and a simple overnight escape.", "price": "94.99", "stock": 8},
    {"name": "Rose Clay Face Mask", "category": "Beauty & Care", "description": "A soothing weekly mask for a slower ritual and a little extra care at home.", "price": "22.99", "stock": 20},
    {"name": "Magnetic Charging Dock", "category": "Electronics & Gadgets", "description": "A tidy charging surface that keeps a desk uncluttered while making nightly charging simpler.", "price": "39.99", "stock": 5},
    {"name": "Metal Ruler Set", "category": "Stationery", "description": "A clean measurement set for project notes, craft plans, and everyday desk work.", "price": "14.99", "stock": 27},
    {"name": "Trail Running Cap", "category": "Outdoor", "description": "A breathable cap for movement, sunshine, and lighter daily outdoor routines.", "price": "19.99", "stock": 31},
    {"name": "Handwoven Entry Mat", "category": "Home & Living", "description": "A durable, patterned mat that brings a grounded feel to an entryway or porch.", "price": "48.99", "stock": 7},
    {"name": "Glass Pitcher", "category": "Kitchen", "description": "A simple pitcher for water, infused drinks, and easy serving throughout the day.", "price": "44.99", "stock": 9},
    {"name": "Leather Weekend Belt", "category": "Fashion", "description": "A refined essential with a simple silhouette that works across everyday outfits.", "price": "41.49", "stock": 12},
    {"name": "Packable Rain Shell", "category": "Outdoor", "description": "A light layer built for sudden weather and easy packing for city errands or trail outings.", "price": "109.99", "stock": 4},
    {"name": "Scented Linen Spray", "category": "Beauty & Care", "description": "A fresh room mist that adds an easy, lived-in calm to linens, towels, and common spaces.", "price": "17.99", "stock": 22},
    {"name": "USB C Hub", "category": "Electronics & Gadgets", "description": "A compact adapter that brings a little more flexibility to home work setups and travel kits.", "price": "64.99", "stock": 13},
    {"name": "A5 Dot Grid Notebook", "category": "Stationery", "description": "A versatile notebook for planning, sketching, and quick ideas that need a little room.", "price": "12.99", "stock": 41},
    {"name": "Campfire Coffee Set", "category": "Outdoor", "description": "A small set for simple brewing moments outdoors, from early hikes to slow weekend mornings.", "price": "37.99", "stock": 6},
    {"name": "Oak Serving Board", "category": "Kitchen", "description": "A practical, natural board that works for meals, snacks, and small hosting moments.", "price": "52.99", "stock": 5},
    {"name": "Soft Ribbed Sweater", "category": "Fashion", "description": "An easy layer with a snug knit and approachable silhouette for daily wear.", "price": "75.99", "stock": 14},
    {"name": "Fold Flat Duffle", "category": "Bags & Travel", "description": "A flexible weekend bag that packs down neatly and handles spontaneous plans with ease.", "price": "77.99", "stock": 9},
    {"name": "Citrus Body Scrub", "category": "Beauty & Care", "description": "A textured scrub with a bright finish that helps refresh the skin and reset a morning routine.", "price": "27.49", "stock": 16},
    {"name": "Compact Wireless Charger", "category": "Electronics & Gadgets", "description": "A simple charging solution for desks, bedside tables, and small work surfaces.", "price": "29.99", "stock": 15},
    {"name": "Soft Tip Pens Set", "category": "Stationery", "description": "A clean writing set for lists, notes, and everyday tasks with a relaxed, useful rhythm.", "price": "11.49", "stock": 36},
    {"name": "Alpine Insulated Mug", "category": "Outdoor", "description": "A dependable cup for early walks, long commutes, and lingering outdoor breaks.", "price": "25.99", "stock": 18},
    {"name": "Geometric Wall Shelf", "category": "Home & Living", "description": "A small storage shelf that adds both display space and an architectural note to a room.", "price": "84.99", "stock": 5},
    {"name": "Espresso Tamper", "category": "Kitchen", "description": "A well-balanced tool that brings more control and rhythm to a home coffee routine.", "price": "18.99", "stock": 28},
    {"name": "Everyday Knit Polo", "category": "Fashion", "description": "A polished casual option for workdays, errands, and light layering through the week.", "price": "63.99", "stock": 13},
    {"name": "Zip Pouch Set", "category": "Bags & Travel", "description": "A pair of tidy pouches for organization, packing, and keeping daily essentials in order.", "price": "23.99", "stock": 24},
    {"name": "Cooling Eye Gel", "category": "Beauty & Care", "description": "A calming cooling gel for a quick reset during busy afternoons or late nights.", "price": "19.49", "stock": 17},
    {"name": "Foldable Solar Lantern", "category": "Outdoor", "description": "A practical light for camps, balconies, and small evenings outdoors after dark.", "price": "44.99", "stock": 10},
    {"name": "Glass Storage Canisters", "category": "Kitchen", "description": "A neat set for pantry staples, dry goods, and a more deliberate kitchen rhythm.", "price": "48.99", "stock": 7},
    {"name": "Textured Crossbody Bag", "category": "Bags & Travel", "description": "A simple, all-day carry bag built for hands-free movement and everyday essentials.", "price": "67.99", "stock": 10},
    {"name": "Daily Cleansing Oil", "category": "Beauty & Care", "description": "A gentle oil cleanser that fits a small, nourishing evening routine without fuss.", "price": "26.99", "stock": 14},
    {"name": "Smart Home Plug", "category": "Electronics & Gadgets", "description": "A convenient plug that helps simplify home routines and small device automation.", "price": "24.99", "stock": 0},
    {"name": "Mini Clipboard Board", "category": "Stationery", "description": "A tidy writing board for planning notes, reminders, and quick work sessions at home.", "price": "13.99", "stock": 22},
    {"name": "Trail Map Notebook", "category": "Outdoor", "description": "A durable notebook for route notes, field plans, and the little details of travel days.", "price": "15.99", "stock": 19},
    {"name": "Woven Lidded Box", "category": "Home & Living", "description": "A calm storage piece for remotes, wraps, and everyday items that need a tidy home.", "price": "46.99", "stock": 4},
    {"name": "Crisp White Ceramic Bowl", "category": "Kitchen", "description": "A useful bowl for serving, prep, and daily meals with a fresh, clean feel.", "price": "29.99", "stock": 2},
    {"name": "Layered Silk Scarf", "category": "Fashion", "description": "A soft finishing layer that adds an easy point of color and light texture to an outfit.", "price": "52.49", "stock": 11},
    {"name": "Canvas Travel Sleeve", "category": "Bags & Travel", "description": "A simple sleeve made to protect tablets, journals, and compact daily essentials.", "price": "34.49", "stock": 0},
]

for item in DEMO_BLUEPRINTS:
    if item["stock"] > 0:
        item["is_available"] = True
    else:
        item["is_available"] = False


def normalize_name(value):
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def ensure_seed_dirs():
    SEED_DATA_DIR.mkdir(exist_ok=True)
    MEDIA_PRODUCTS_DIR.mkdir(parents=True, exist_ok=True)


def read_manifest():
    if not MANIFEST_PATH.exists():
        return {"products": []}
    try:
        with MANIFEST_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict) and isinstance(data.get("products"), list):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return {"products": []}


def write_manifest(entries):
    ensure_seed_dirs()
    with MANIFEST_PATH.open("w", encoding="utf-8") as handle:
        json.dump({"products": list(entries or [])}, handle, indent=2)
        handle.write("\n")


def write_attributions(rows):
    ensure_seed_dirs()
    with ATTRIBUTIONS_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["product_name", "file", "photographer", "source_url", "site"])
        for row in rows:
            writer.writerow(row)


def slugify_name(value):
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "product"


def safe_image_filename(name, ext="jpg"):
    base = slugify_name(name)
    return f"{base}-{int(time.time() * 1000)}.{ext}"


def make_placeholder_image(product_name, ext="jpg"):
    width, height = 1200, 1200
    image = Image.new("RGB", (width, height), "#f6f7f3")
    draw = ImageDraw.Draw(image)
    palette = ["#1d5b4f", "#dba85a", "#f6f7f3"]
    for index, color in enumerate(palette):
        radius = 200 + index * 90
        draw.ellipse((width // 2 - radius, height // 2 - radius, width // 2 + radius, height // 2 + radius), fill=color)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rounded_rectangle((120, 120, width - 120, height - 120), radius=60, fill=(30, 41, 38, 26))
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(image)
    first_letter = product_name.strip()[0].upper() if product_name.strip() else "D"
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 420)
        small_font = ImageFont.truetype("DejaVuSans.ttf", 72)
    except OSError:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    draw.text((200, 240), first_letter, font=font, fill="#1d5b4f")
    draw.text((200, 785), "Placeholder", font=small_font, fill="#1d5b4f")
    draw.text((200, 860), "DepalNova demo image", font=small_font, fill="#6d7b74")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=82)
    return buffer.getvalue(), safe_image_filename(product_name, "jpg")


def optimize_image_bytes(data, product_name):
    with Image.open(io.BytesIO(data)) as image:
        image = image.convert("RGB")
        max_side = 1200
        if max(image.size) > max_side:
            ratio = max_side / max(image.size)
            image = image.resize((int(image.width * ratio), int(image.height * ratio)), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=82, optimize=True)
        image_bytes = buffer.getvalue()
    return image_bytes, safe_image_filename(product_name, "jpg")


def collect_local_images(images_dir):
    if not images_dir:
        return []
    folder = Path(images_dir)
    if not folder.exists():
        return []
    return [path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]


def match_local_image(product_name, images_dir):
    product_normalized = normalize_name(product_name)
    files = collect_local_images(images_dir)
    scored = []
    for path in files:
        tokens = normalize_name(path.stem).split()
        item_score = 0
        for token in product_normalized.split():
            if token in tokens:
                item_score += 3
        if product_normalized in normalize_name(path.stem):
            item_score += 10
        if item_score:
            scored.append((item_score, path))
    if scored:
        _, best = sorted(scored, reverse=True)[0]
        return best
    if files:
        return files[0]
    return None


def load_api_keys():
    return {
        "unsplash": os.environ.get("UNSPLASH_ACCESS_KEY"),
        "pexels": os.environ.get("PEXELS_API_KEY"),
        "pixabay": os.environ.get("PIXABAY_API_KEY"),
    }


def explain_missing_api_keys():
    print("No image API keys were found. Set one in PowerShell like: $env:UNSPLASH_ACCESS_KEY = 'your_key_here' ; or $env:PEXELS_API_KEY = 'your_key_here' ; or $env:PIXABAY_API_KEY = 'your_key_here'.")
    print("The command will fall back to local seed_images/ or generated placeholder images if no API key is available.")


def fetch_from_unsplash(query):
    import requests

    key = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not key:
        return None
    url = "https://api.unsplash.com/search/photos"
    params = {"query": query, "per_page": 1, "orientation": "landscape"}
    headers = {"Authorization": f"Client-ID {key}"}
    response = requests.get(url, params=params, headers=headers, timeout=20)
    response.raise_for_status()
    data = response.json()
    results = data.get("results") or []
    if not results:
        return None
    photo = results[0]
    image_url = photo.get("urls", {}).get("regular") or photo.get("urls", {}).get("small")
    photographer = photo.get("user", {}).get("name", "Unsplash contributor")
    source_url = photo.get("links", {}).get("html", image_url)
    return image_url, photographer, source_url, "Unsplash"


def fetch_from_pexels(query):
    import requests

    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return None
    url = "https://api.pexels.com/v1/search"
    headers = {"Authorization": key}
    params = {"query": query, "per_page": 1, "orientation": "landscape"}
    response = requests.get(url, params=params, headers=headers, timeout=20)
    response.raise_for_status()
    data = response.json()
    photos = data.get("photos") or []
    if not photos:
        return None
    photo = photos[0]
    image_url = photo.get("src", {}).get("large") or photo.get("src", {}).get("medium")
    photographer = photo.get("photographer", "Pexels contributor")
    source_url = photo.get("url", image_url)
    return image_url, photographer, source_url, "Pexels"


def fetch_from_pixabay(query):
    import requests

    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        return None
    url = "https://pixabay.com/api/"
    params = {"key": key, "q": query, "image_type": "photo", "per_page": 3, "safesearch": True}
    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    data = response.json()
    hits = data.get("hits") or []
    if not hits:
        return None
    photo = hits[0]
    image_url = photo.get("webformatURL") or photo.get("largeImageURL")
    photographer = photo.get("user", "Pixabay contributor")
    source_url = photo.get("pageURL", image_url)
    return image_url, photographer, source_url, "Pixabay"


def download_remote_image(product_name):
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("Remote image downloads require requests. Run: pip install -r requirements-dev.txt") from exc

    query = product_name
    for source_name, fetcher in (
        ("Unsplash", fetch_from_unsplash),
        ("Pexels", fetch_from_pexels),
        ("Pixabay", fetch_from_pixabay),
    ):
        try:
            result = fetcher(query)
            if not result:
                continue
            image_url, photographer, source_url, site = result
            image_response = requests.get(image_url, timeout=25)
            image_response.raise_for_status()
            data, filename = optimize_image_bytes(image_response.content, product_name)
            return data, filename, photographer, source_url, site
        except Exception:
            time.sleep(0.3)
    return None, None, None, None, None


def synchronize_manifest(entries):
    manifest = read_manifest()
    current = {item.get("name"): item for item in manifest.get("products", [])}
    merged = []
    for item in manifest.get("products", []) + entries:
        key = item.get("name")
        if key and key not in {entry.get("name") for entry in merged}:
            merged.append(item)
    write_manifest(merged)
    return merged


def save_image_for_product(product, image_bytes, filename, source_name, attribution):
    if product.image and product.image.name:
        existing_path = Path(settings.MEDIA_ROOT) / product.image.name
        if existing_path.exists():
            existing_path.unlink(missing_ok=True)
    product.image.save(filename, ContentFile(image_bytes), save=True)
    if source_name and attribution:
        return {"product_name": product.name, "file": filename, "photographer": attribution[0], "source_url": attribution[1], "site": source_name}
    return {"product_name": product.name, "file": filename, "photographer": "DepalNova generated placeholder", "source_url": "https://example.com/placeholder", "site": "DepalNova"}


def clear_demo_products():
    manifest = read_manifest()
    entries = manifest.get("products", [])
    if not entries:
        print("No demo products found in the manifest.")
        write_manifest([])
        write_attributions([])
        return 0

    demo_names = [entry.get("name") for entry in entries if entry.get("name")]
    if not demo_names:
        write_manifest([])
        write_attributions([])
        return 0

    queryset = Product.objects.filter(name__in=demo_names)
    for product in queryset:
        if product.image and product.image.name:
            image_path = Path(settings.MEDIA_ROOT) / product.image.name
            if image_path.exists():
                image_path.unlink(missing_ok=True)
        product.delete()

    write_manifest([])
    write_attributions([])
    print(f"Removed {queryset.count()} demo products and their image files from the manifest.")
    return queryset.count()


def build_demo_product_specs(count):
    specs = []
    for index in range(count):
        blueprint = DEMO_BLUEPRINTS[index % len(DEMO_BLUEPRINTS)]
        product = {**blueprint}
        product["name"] = f"{blueprint['name']} {index // len(DEMO_BLUEPRINTS) + 1}" if index >= len(DEMO_BLUEPRINTS) else blueprint["name"]
        product["price"] = str(Decimal(blueprint["price"]) + (Decimal(index % 7) * Decimal("2.75")))
        product["stock"] = max(0, (blueprint["stock"] + (index % 5) - 2))
        if product["stock"] > 0:
            product["is_available"] = True
        else:
            product["is_available"] = False
        specs.append(product)
    return specs


class Command(BaseCommand):
    help = "Seed the store with demo products and optional media for a realistic DepalNova catalog."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=60, help="How many demo products to create.")
        parser.add_argument("--images-dir", type=str, default="", help="Optional folder with your own product photos.")
        parser.add_argument("--no-images", action="store_true", help="Create products without any images.")
        parser.add_argument("--clear-demo", action="store_true", help="Delete only products created by this seed command and clear the manifest.")

    def handle(self, *args, **options):
        if options["clear_demo"]:
            clear_demo_products()
            return

        count = max(0, int(options["count"]))
        if count == 0:
            self.stdout.write("No products requested; nothing was created.")
            return

        ensure_seed_dirs()
        image_dir = options["images_dir"] or "seed_images"
        if not options["no_images"]:
            images_dir_path = Path(image_dir)
            if not images_dir_path.exists():
                seed_images_dir = PROJECT_ROOT / "seed_images"
                if seed_images_dir.exists():
                    image_dir = str(seed_images_dir)
                else:
                    image_dir = ""
        else:
            image_dir = ""

        if not options["no_images"] and not image_dir:
            api_keys = load_api_keys()
            if not any(api_keys.values()):
                explain_missing_api_keys()

        manifest = read_manifest()
        manifest_entries = manifest.get("products", [])
        existing_names = {normalize_name(name) for name in Product.objects.values_list("name", flat=True)}
        product_specs = build_demo_product_specs(count)
        created_entries = []
        attributions = []
        used_filenames = set()

        for spec in product_specs:
            product_name = spec["name"]
            candidate_name = normalize_name(product_name)
            if Product.objects.filter(name__iexact=product_name).exists() or candidate_name in existing_names:
                continue

            product = Product.objects.create(
                name=product_name,
                description=spec["description"],
                price=str(Decimal(str(spec["price"]))),
                category=spec["category"],
                stock=int(spec["stock"]),
                is_available=bool(spec.get("is_available", True)),
            )

            image_bytes = None
            image_filename = None
            source_name = None
            attribution = None

            if not options["no_images"]:
                local_path = match_local_image(product_name, image_dir) if image_dir else None
                if local_path:
                    image_bytes = local_path.read_bytes()
                    image_filename = safe_image_filename(product_name, local_path.suffix.lower().lstrip("."))
                    if image_filename in used_filenames:
                        image_filename = safe_image_filename(product_name, local_path.suffix.lower().lstrip("."))
                    used_filenames.add(image_filename)
                    image_bytes, image_filename = optimize_image_bytes(image_bytes, product_name)
                    attribution = ("User supplied photo", str(local_path), "Local upload")
                    source_name = "Local photo"
                else:
                    image_bytes, image_filename, photographer, source_url, site = download_remote_image(product_name)
                    if image_bytes:
                        source_name = site
                        attribution = (photographer or "Unknown photographer", source_url or "https://example.com", site or "Source")
                    else:
                        image_bytes, image_filename = make_placeholder_image(product_name)
                        source_name = "Placeholder"
                        attribution = ("DepalNova generated placeholder", "https://example.com/placeholder", "DepalNova")

                if image_bytes:
                    product.image.save(image_filename, ContentFile(image_bytes), save=True)
                    attributions.append([product.name, image_filename, attribution[0], attribution[1], attribution[2]])
                    created_entries.append({"id": product.pk, "name": product.name, "image_filename": image_filename})
                else:
                    created_entries.append({"id": product.pk, "name": product.name, "image_filename": None})
            else:
                created_entries.append({"id": product.pk, "name": product.name, "image_filename": None})

            existing_names.add(normalize_name(product_name))

        if created_entries:
            merged_entries = list(manifest_entries) + created_entries
            manifest_entries = []
            seen = set()
            for entry in merged_entries:
                key = entry.get("name")
                if key and key not in seen:
                    manifest_entries.append(entry)
                    seen.add(key)
            write_manifest(manifest_entries)

        if attributions:
            existing_attributions = []
            if ATTRIBUTIONS_PATH.exists():
                with ATTRIBUTIONS_PATH.open("r", encoding="utf-8", newline="") as handle:
                    existing_attributions = list(csv.reader(handle))
            rows = existing_attributions[1:] if existing_attributions else []
            rows.extend(attributions)
            write_attributions(rows)

        created_count = len(created_entries)
        self.stdout.write(self.style.SUCCESS(f"Created {created_count} demo products."))
        if not options["no_images"]:
            self.stdout.write(f"Images were assigned from local files, API downloads, or generated placeholders as available.")
