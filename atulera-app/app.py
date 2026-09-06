import sqlite3
import os
import uuid
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, g
from dotenv import load_dotenv

load_dotenv()  # Load .env file

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DB_PATH    = os.path.join(BASE_DIR, "atulera.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-secret-key-before-going-live")

# ElevenLabs config
ELEVENLABS_AGENT_ID = os.getenv("ELEVENLABS_AGENT_ID", "")
ELEVENLABS_API_KEY  = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")

# Supabase (optional — only activated when both URL and KEY are present)
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()
supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        from supabase import create_client
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print(f"[ATULÉRA] Supabase connected: {SUPABASE_URL}")
    except Exception as e:
        print(f"[ATULÉRA] Supabase connection failed: {e} — falling back to SQLite")
        supabase = None
else:
    print("[ATULÉRA] Using SQLite (set SUPABASE_URL + SUPABASE_KEY in .env to use Supabase)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file_storage, sub="general"):
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename):
        return None
    ext  = file_storage.filename.rsplit(".", 1)[1].lower()
    fname = f"{uuid.uuid4().hex}.{ext}"
    folder = os.path.join(UPLOAD_DIR, sub)
    os.makedirs(folder, exist_ok=True)
    file_storage.save(os.path.join(folder, fname))
    return f"uploads/{sub}/{fname}"


# ---------------------------------------------------------------------------
# Database helpers — SQLite (Supabase swap-in ready)
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def slugify(text):
    text = text.lower().strip()
    out = []
    prev_dash = False
    for ch in text:
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    return "".join(out).strip("-") or "service"


def make_slug(db, title, exclude_id=None):
    base = slugify(title)
    slug = base
    n = 2
    while True:
        row = db.execute(
            "SELECT id FROM services WHERE slug=? AND id IS NOT ?", (slug, exclude_id or -1)
        ).fetchone()
        if not row:
            return slug
        slug = f"{base}-{n}"
        n += 1


def lines_to_list(text):
    return [line.strip() for line in (text or "").split("\n") if line.strip()]

def get_site_setting(db, key, default=""):
    row = db.execute("SELECT value FROM site_settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default

def set_site_setting(db, key, value):
    db.execute(
        "INSERT INTO site_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=?",
        (key, value, value)
    )
    db.commit()


# ---------------------------------------------------------------------------
# DB Init & Seeding
# ---------------------------------------------------------------------------
def init_db():
    fresh = not os.path.exists(DB_PATH)
    db = sqlite3.connect(DB_PATH)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS services (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name    TEXT NOT NULL,
            title         TEXT NOT NULL,
            slug          TEXT UNIQUE,
            description   TEXT NOT NULL,
            benefits      TEXT DEFAULT '',
            who_for       TEXT DEFAULT '',
            process_steps TEXT DEFAULT '',
            icon          TEXT DEFAULT 'spark',
            sort_order    INTEGER DEFAULT 0,
            active        INTEGER DEFAULT 1,
            image_url     TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS service_requests (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id       INTEGER,
            service_title    TEXT NOT NULL,
            name             TEXT NOT NULL,
            phone            TEXT,
            email            TEXT,
            business_name    TEXT,
            message          TEXT,
            preferred_contact TEXT DEFAULT 'phone',
            status           TEXT DEFAULT 'New',
            created_at       TEXT NOT NULL,
            client_file      TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS inquiries (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            phone      TEXT,
            email      TEXT,
            message    TEXT NOT NULL,
            created_at TEXT NOT NULL,
            responded  INTEGER DEFAULT 0,
            admin_note TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS faqs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            question   TEXT NOT NULL,
            answer     TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS admin_users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            password      TEXT NOT NULL,
            profile_photo TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS testimonials (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name     TEXT NOT NULL,
            client_business TEXT DEFAULT '',
            review          TEXT NOT NULL,
            rating          INTEGER DEFAULT 5,
            active          INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS service_gallery (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id INTEGER NOT NULL,
            image_url  TEXT NOT NULL,
            FOREIGN KEY(service_id) REFERENCES services(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS site_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    db.commit()

    # Idempotent column migrations
    existing_svc = {row[1] for row in db.execute("PRAGMA table_info(services)").fetchall()}
    for col, ddl in [
        ("slug",          "ALTER TABLE services ADD COLUMN slug TEXT"),
        ("benefits",      "ALTER TABLE services ADD COLUMN benefits TEXT DEFAULT ''"),
        ("who_for",       "ALTER TABLE services ADD COLUMN who_for TEXT DEFAULT ''"),
        ("process_steps", "ALTER TABLE services ADD COLUMN process_steps TEXT DEFAULT ''"),
        ("image_url",     "ALTER TABLE services ADD COLUMN image_url TEXT DEFAULT ''"),
    ]:
        if col not in existing_svc:
            db.execute(ddl)

    existing_req = {row[1] for row in db.execute("PRAGMA table_info(service_requests)").fetchall()}
    if "client_file" not in existing_req:
        db.execute("ALTER TABLE service_requests ADD COLUMN client_file TEXT DEFAULT ''")

    existing_admin = {row[1] for row in db.execute("PRAGMA table_info(admin_users)").fetchall()}
    if "profile_photo" not in existing_admin:
        db.execute("ALTER TABLE admin_users ADD COLUMN profile_photo TEXT DEFAULT ''")
    db.commit()

    # Backfill missing slugs
    for row in db.execute("SELECT id, title FROM services WHERE slug IS NULL OR slug=''").fetchall():
        db.execute("UPDATE services SET slug=? WHERE id=?", (make_slug(db, row[1], row[0]), row[0]))
    db.commit()

    if fresh:
        # ── Services seed (image_url uses only EXISTING images) ─────────────
        seed_services = [
            # FINANCIAL
            ("financial", "Income Tax Return (ITR) Filing", "itr-filing",
             "Professional assistance for accurate and hassle-free ITR filing.",
             "Organized, step-by-step filing process\nProfessional assistance throughout\nGuidance on required documents\nHassle-free experience",
             "Salaried individuals\nSelf-employed professionals\nSmall business owners",
             "Share your requirement\nProvide required information and documents\nInformation is reviewed\nFiling assistance is completed\nConfirmation and follow-up support",
             "file", 1, "images/finance_banner.jpg"),
            ("financial", "Financial Management", "financial-management",
             "Practical support for better organization and management of financial matters.",
             "Clearer view of income and expenses\nBetter organized financial records\nPractical, judgement-free guidance",
             "Individuals managing personal finances\nSmall business owners",
             "Share your current situation\nWe review and discuss options\nPractical action plan is suggested\nOngoing support as needed",
             "chart", 2, "images/finance_banner.jpg"),
            ("financial", "Investment Support", "investment-support",
             "Information and assistance related to investment planning and financial goals, subject to applicable regulations.",
             "Clear information on available options\nHelp aligning choices with your goals\nSupport with paperwork where applicable",
             "Individuals exploring investment options\nProfessionals planning long-term goals",
             "Share your financial goals\nWe explain relevant options\nYou decide with full information\nAssistance with related paperwork",
             "growth", 3, "images/finance_banner.jpg"),
            ("financial", "Tax & Documentation Support", "tax-documentation-support",
             "Assistance with tax-related documentation and business paperwork.",
             "Organized documentation\nReduced paperwork stress\nProfessional review before submission",
             "Individuals and businesses handling tax paperwork",
             "Share the documents you have\nWe review and identify gaps\nAssistance completing the paperwork\nFinal check before submission",
             "doc", 4, "images/finance_banner.jpg"),
            # DIGITAL
            ("digital", "Website Creation & E-Commerce", "website-creation",
             "Professional, responsive, and SEO-friendly websites tailored to showcase your business and drive online sales.",
             "Mobile-friendly, responsive design\nSEO-optimized structure to rank higher\nCustom branding and color themes\nFast loading speeds\nE-commerce and payment gateway setup",
             "Startups needing an online identity\nRetailers moving to e-commerce\nService professionals wanting a portfolio site\nExisting brands refreshing outdated websites",
             "Share your business details, branding, and goals\nWe suggest a design direction and map out the required pages\nWebsite is built, tested, and reviewed with you\nFinal optimizations and SEO setup\nSite goes live with basic training for your team",
             "web", 1, "images/digital_banner.jpg"),
            ("digital", "Social Media Management & Marketing", "social-media-management",
             "End-to-end management of your brand's presence across Facebook, Instagram, LinkedIn, and YouTube to engage your audience.",
             "Consistent, professional posting schedule\nEngaging content aligned with your brand voice\nCommunity management and comment replies\nMonthly performance analytics\nTargeted ad campaigns (optional)",
             "Businesses without the time to manage social media\nBrands wanting to establish authority in their niche\nCompanies seeking consistent engagement and growth",
             "Share your brand guidelines and target audience\nA strategic monthly content plan is prepared\nPosts are designed, created, and scheduled\nCommunity is monitored and engaged\nPerformance is reviewed periodically to optimize strategy",
             "social", 2, "images/digital_banner.jpg"),
            ("digital", "Google Business & SEO Services", "google-business-services",
             "Comprehensive setup and optimization for Google Business Profile, SEO, Ads, and Analytics to dominate local search.",
             "Top ranking on Google Search and Maps\nProfessional business profile setup with reviews management\nClear insight into website traffic and customer behavior\nTargeted Google Ads for immediate lead generation",
             "Local businesses wanting more foot traffic\nService providers needing local leads\nE-commerce sites looking to scale via Google Ads",
             "Audit of your current online visibility\nGoogle Business Profile setup or optimization\nKeyword research and on-page SEO implementation\nGoogle Analytics integration\nOngoing management and ad monitoring",
             "google", 3, "images/digital_banner.jpg"),
            ("digital", "WhatsApp Business Automation", "whatsapp-business-setup",
             "Professional WhatsApp Business setup including catalogs, automated replies, and customer communication workflows.",
             "Professional business profile on WhatsApp\nAutomated quick replies and away messages\nProduct/Service catalog integration\nImproved and faster customer communication",
             "Retailers taking orders via WhatsApp\nService providers handling customer inquiries\nAny business wanting a direct communication channel",
             "Share your business details and logo\nWhatsApp Business account is set up and verified\nProduct Catalog and quick replies are configured\nBasic training on usage and label management",
             "chat", 4, "images/digital_banner.jpg"),
            ("digital", "Digital Payment & QR Solutions", "payment-qr-services",
             "Assistance with setting up merchant accounts and digital payment QR codes for seamless customer transactions.",
             "Faster, convenient customer payments\nProfessional QR standee and display setup\nSupport with related bank/merchant account setup\nZero transaction failure troubleshooting",
             "Retail shops and local businesses\nFreelancers and service professionals\nRestaurants and cafes",
             "Share your business and bank details\nMerchant application is processed\nQR codes are generated and tested\nStandees are delivered and set up at your location",
             "qr", 5, "images/digital_banner.jpg"),
            ("digital", "Professional Business Photography", "business-photography",
             "High-quality, professional photography for your business premises, products, team, and promotional campaigns.",
             "High-resolution, professionally edited images\nContent ready for social media, print, and website\nConsistent visual identity across all platforms\nDrone/aerial photography (where applicable)",
             "Restaurants needing food photography\nReal estate and hotels needing property shots\nE-commerce businesses needing product photos\nCorporate teams needing professional headshots",
             "Discuss the creative vision and required shots\nSchedule the photography shoot at your location\nProfessional shoot execution\nPost-processing and editing\nFinal high-res photos are delivered ready to use",
             "camera", 6, "images/hero2.jpg"),
        ]
        db.executemany(
            "INSERT INTO services (group_name,title,slug,description,benefits,who_for,process_steps,icon,sort_order,image_url) VALUES (?,?,?,?,?,?,?,?,?,?)",
            seed_services,
        )

        seed_faqs = [
            ("Do you help with both tax filing and website design?",
             "Yes — ATULÉRA covers financial/tax services and digital services like websites, social media and Google Business, all under one roof.", 1),
            ("Do you work with individuals or only businesses?",
             "Both. We support individuals with tax and financial needs, and businesses with digital and operational solutions.", 2),
            ("How do I get a quote for my requirement?",
             "Send us a message from the Contact section with a short description, or call/WhatsApp us directly — we'll get back with a practical plan.", 3),
            ("Where is ATULÉRA located?",
             "We're based in Bhilai, Chhattisgarh, and support clients across the region.", 4),
        ]
        db.executemany("INSERT INTO faqs (question,answer,sort_order) VALUES (?,?,?)", seed_faqs)

        seed_testimonials = [
            ("Rajesh Kumar", "Kumar Electronics, Bhilai",
             "ATULÉRA helped us set up our Google Business profile and within weeks we started getting more walk-in customers. Excellent service!", 5),
            ("Priya Sharma", "Self-employed, Raipur",
             "The ITR filing was handled so smoothly. No stress, no confusion. I'll definitely use ATULÉRA again next year.", 5),
            ("Amit Verma", "Verma Traders, Durg",
             "Our website looks very professional. The team understood exactly what we needed and delivered on time. Highly recommended!", 5),
            ("Sunita Patel", "Patel Boutique, Bhilai",
             "WhatsApp Business setup was done quickly and now we can manage customer orders much better. Great support!", 5),
            ("Dinesh Sahu", "Sahu Construction",
             "Very professional team. They helped with all our financial documentation and made the process very simple.", 5),
        ]
        db.executemany(
            "INSERT INTO testimonials (client_name,client_business,review,rating) VALUES (?,?,?,?)",
            seed_testimonials,
        )

        db.execute("INSERT INTO admin_users (username,password) VALUES (?,?)", ("admin", "atulera123"))
        db.commit()
    db.close()


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Determine if ElevenLabs agent is properly configured
# ---------------------------------------------------------------------------
def elevenlabs_agent_active():
    return bool(ELEVENLABS_AGENT_ID and ELEVENLABS_AGENT_ID.strip()
                and ELEVENLABS_AGENT_ID != "your_agent_id_here")


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------
@app.route("/")
def home():
    db = get_db()
    financial    = db.execute("SELECT * FROM services WHERE group_name='financial' AND active=1 ORDER BY sort_order").fetchall()
    digital      = db.execute("SELECT * FROM services WHERE group_name='digital'   AND active=1 ORDER BY sort_order").fetchall()
    faqs         = db.execute("SELECT * FROM faqs ORDER BY sort_order").fetchall()
    testimonials = db.execute("SELECT * FROM testimonials WHERE active=1").fetchall()
    return render_template(
        "index.html",
        financial=financial,
        digital=digital,
        faqs=faqs,
        testimonials=testimonials,
        elevenlabs_agent_id=ELEVENLABS_AGENT_ID,
        elevenlabs_agent_active=elevenlabs_agent_active(),
        supabase_active=bool(supabase),
        admin_photo=get_site_setting(db, "admin_photo"),
        payment_qr=get_site_setting(db, "payment_qr"),
    )


@app.route("/contact", methods=["POST"])
def contact():
    db      = get_db()
    name    = request.form.get("name", "").strip()
    phone   = request.form.get("phone", "").strip()
    email   = request.form.get("email", "").strip()
    message = request.form.get("message", "").strip()

    if not name or not message:
        flash("Please share your name and a short message.", "error")
        return redirect(url_for("home") + "#contact")

    db.execute(
        "INSERT INTO inquiries (name,phone,email,message,created_at) VALUES (?,?,?,?,?)",
        (name, phone, email, message, datetime.now().strftime("%d %b %Y, %I:%M %p")),
    )
    db.commit()
    flash("Thanks! We've received your message and will get back to you soon.", "success")
    return redirect(url_for("home") + "#contact")


@app.route("/services/<slug>")
def service_detail(slug):
    db = get_db()
    service = db.execute("SELECT * FROM services WHERE slug=? AND active=1", (slug,)).fetchone()
    if not service:
        return render_template("404.html"), 404

    gallery = db.execute("SELECT * FROM service_gallery WHERE service_id=?", (service["id"],)).fetchall()

    related = db.execute(
        "SELECT * FROM services WHERE group_name=? AND id!=? AND active=1 ORDER BY sort_order LIMIT 3",
        (service["group_name"], service["id"]),
    ).fetchall()

    return render_template(
        "service_detail.html",
        service=service,
        gallery=gallery,
        benefits=lines_to_list(service["benefits"]),
        who_for=lines_to_list(service["who_for"]),
        steps=lines_to_list(service["process_steps"]),
        related=related,
        elevenlabs_agent_id=ELEVENLABS_AGENT_ID,
        elevenlabs_agent_active=elevenlabs_agent_active(),
        admin_photo=get_site_setting(db, "admin_photo"),
        payment_qr=get_site_setting(db, "payment_qr"),
    )


@app.route("/service-request", methods=["POST"])
def service_request():
    db = get_db()
    name          = request.form.get("name", "").strip()
    service_id    = request.form.get("service_id", "").strip()
    service_title = request.form.get("service_title", "General enquiry").strip()
    slug          = request.form.get("slug", "")

    client_file = request.files.get("client_file")
    file_path = ""
    if client_file:
        file_path = save_upload(client_file, sub="requests") or ""

    if not name:
        flash("Please share your name so we can get back to you.", "error")
        return redirect(url_for("service_detail", slug=slug) if slug else url_for("home"))

    db.execute(
        """INSERT INTO service_requests
           (service_id,service_title,name,phone,email,business_name,message,preferred_contact,status,created_at,client_file)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            service_id or None, service_title, name,
            request.form.get("phone", "").strip(),
            request.form.get("email", "").strip(),
            request.form.get("business_name", "").strip(),
            request.form.get("message", "").strip(),
            request.form.get("preferred_contact", "phone"),
            "New",
            datetime.now().strftime("%d %b %Y, %I:%M %p"),
            file_path,
        ),
    )
    db.commit()
    flash(f'Thank you! Your request for "{service_title}" has been received. ATULÉRA will contact you soon.', "success")
    return redirect(url_for("service_detail", slug=slug) if slug else url_for("home"))


@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip().lower()
    if not q:
        return jsonify({"services": [], "faqs": [], "reply": "Type what you're looking for — e.g. 'website', 'tax filing', 'social media'."})

    db   = get_db()
    like = f"%{q}%"
    services = db.execute(
        "SELECT title,description,group_name,slug FROM services WHERE active=1 AND (lower(title) LIKE ? OR lower(description) LIKE ?) ORDER BY sort_order",
        (like, like),
    ).fetchall()
    faqs = db.execute(
        "SELECT question,answer FROM faqs WHERE lower(question) LIKE ? OR lower(answer) LIKE ?",
        (like, like),
    ).fetchall()

    services_out = [dict(s) for s in services]
    faqs_out     = [dict(f) for f in faqs]

    if services_out:
        reply = f"Found {len(services_out)} service(s) matching '{q}'. Click one to open it."
    elif faqs_out:
        reply = "Here's what might help:"
    else:
        reply = f"No exact match for '{q}' — try 'tax', 'website', 'social media', or send us a message."

    return jsonify({"services": services_out, "faqs": faqs_out, "reply": reply})


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        action   = request.form.get("action", "login")
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        db       = get_db()

        if action == "signup":
            existing_count = db.execute("SELECT COUNT(*) FROM admin_users").fetchone()[0]
            if existing_count > 0:
                access_code = request.form.get("access_code", "").strip()
                if access_code != "ATULERA2024":
                    flash("Invalid access code. Contact the primary admin.", "error")
                    return redirect(url_for("admin_login") + "?tab=signup")
            if not username or len(password) < 4:
                flash("Username required and password must be at least 4 characters.", "error")
                return redirect(url_for("admin_login") + "?tab=signup")
            if db.execute("SELECT id FROM admin_users WHERE username=?", (username,)).fetchone():
                flash(f'Username "{username}" is already taken.', "error")
                return redirect(url_for("admin_login") + "?tab=signup")
            db.execute("INSERT INTO admin_users (username,password) VALUES (?,?)", (username, password))
            db.commit()
            flash(f'Account "{username}" created! Please sign in.', "success")
            return redirect(url_for("admin_login"))
        else:
            user = db.execute(
                "SELECT * FROM admin_users WHERE username=? AND password=?", (username, password)
            ).fetchone()
            if user:
                session["admin_logged_in"] = True
                session["admin_username"]  = username
                session["admin_photo"]     = user["profile_photo"] or ""
                return redirect(url_for("admin_dashboard"))
            flash("Invalid username or password.", "error")

    return render_template("admin_login.html", tab=request.args.get("tab", "login"))


@app.route("/admin/signup", methods=["GET", "POST"])
def admin_signup():
    if not session.get("admin_logged_in"):
        flash("Please log in as admin first.", "error")
        return redirect(url_for("admin_login"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if not username or len(password) < 4:
            flash("Username required and password must be at least 4 characters.", "error")
            return redirect(url_for("admin_signup"))
        db = get_db()
        if db.execute("SELECT id FROM admin_users WHERE username=?", (username,)).fetchone():
            flash(f'Username "{username}" is already taken.', "error")
            return redirect(url_for("admin_signup"))
        db.execute("INSERT INTO admin_users (username,password) VALUES (?,?)", (username, password))
        db.commit()
        flash(f'Admin account "{username}" created.', "success")
        return redirect(url_for("admin_dashboard"))
    return render_template("admin_signup.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


REQUEST_STATUSES = ["New", "Contacted", "In Progress", "Completed", "Cancelled"]


@app.route("/admin")
@login_required
def admin_dashboard():
    db           = get_db()
    services     = db.execute("SELECT * FROM services ORDER BY group_name,sort_order").fetchall()
    
    # Fetch galleries and group by service_id
    galleries_raw = db.execute("SELECT * FROM service_gallery").fetchall()
    galleries = {}
    for g in galleries_raw:
        galleries.setdefault(g["service_id"], []).append(g)

    inquiries    = db.execute("SELECT * FROM inquiries ORDER BY id DESC").fetchall()
    faqs         = db.execute("SELECT * FROM faqs ORDER BY sort_order").fetchall()
    requests_rows= db.execute("SELECT * FROM service_requests ORDER BY id DESC").fetchall()
    testimonials = db.execute("SELECT * FROM testimonials ORDER BY id DESC").fetchall()
    stats = {
        "total_services":    len(services),
        "active_services":   sum(1 for s in services if s["active"]),
        "total_inquiries":   len(inquiries),
        "pending_inquiries": sum(1 for i in inquiries if not i["responded"]),
        "total_requests":    len(requests_rows),
        "new_requests":      sum(1 for r in requests_rows if r["status"] == "New"),
    }
    admin       = db.execute("SELECT * FROM admin_users WHERE username=?", (session.get("admin_username"),)).fetchone()
    admin_photo = admin["profile_photo"] if admin and admin["profile_photo"] else ""
    return render_template(
        "admin_dashboard.html",
        services=services,
        galleries=galleries,
        inquiries=inquiries,
        faqs=faqs,
        service_requests=requests_rows,
        request_statuses=REQUEST_STATUSES,
        stats=stats,
        admin_photo=admin_photo,
        testimonials=testimonials,
        supabase_active=bool(supabase),
        elevenlabs_agent_active=elevenlabs_agent_active(),
    )


@app.route("/admin/site-settings", methods=["POST"])
@login_required
def admin_site_settings():
    db = get_db()
    
    photo_file = request.files.get("admin_photo")
    if photo_file:
        path = save_upload(photo_file, sub="settings")
        if path:
            set_site_setting(db, "admin_photo", path)
            
    qr_file = request.files.get("payment_qr")
    if qr_file:
        path = save_upload(qr_file, sub="settings")
        if path:
            set_site_setting(db, "payment_qr", path)
            
    flash("Site settings updated successfully.", "success")
    return redirect(url_for("admin_dashboard") + "#panel-settings")

@app.route("/admin/upload-photo", methods=["POST"])
@login_required
def admin_upload_photo():
    file = request.files.get("profile_photo")
    if file:
        path = save_upload(file, sub="profiles")
        if path:
            db = get_db()
            db.execute("UPDATE admin_users SET profile_photo=? WHERE username=?", (path, session.get("admin_username")))
            db.commit()
            session["admin_photo"] = path
            flash("Profile photo updated successfully.", "success")
        else:
            flash("Invalid file type.", "error")
    else:
        flash("No file selected.", "error")
    return redirect(url_for("admin_dashboard") + "#panel-settings")


@app.route("/admin/service/image/<int:service_id>", methods=["POST"])
@login_required
def admin_service_image(service_id):
    file = request.files.get("service_image")
    if file:
        path = save_upload(file, sub="services")
        if path:
            db = get_db()
            db.execute("UPDATE services SET image_url=? WHERE id=?", (path, service_id))
            db.commit()
            flash("Service image updated.", "success")
        else:
            flash("Invalid file type.", "error")
    return redirect(url_for("admin_dashboard") + "#panel-services")


@app.route("/admin/service/add", methods=["POST"])
@login_required
def admin_service_add():
    db    = get_db()
    title = request.form["title"]
    slug  = make_slug(db, title)
    db.execute(
        "INSERT INTO services (group_name,title,slug,description,benefits,who_for,process_steps,icon,sort_order) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            request.form["group_name"], title, slug,
            request.form["description"],
            request.form.get("benefits", ""),
            request.form.get("who_for", ""),
            request.form.get("process_steps", ""),
            request.form.get("icon", "spark"),
            int(request.form.get("sort_order", 0) or 0),
        ),
    )
    db.commit()
    flash(f'New service "{title}" added.', "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/service/edit/<int:service_id>", methods=["POST"])
@login_required
def admin_service_edit(service_id):
    db       = get_db()
    title    = request.form["title"]
    existing = db.execute("SELECT title,slug FROM services WHERE id=?", (service_id,)).fetchone()
    slug     = (existing["slug"]
                if existing and existing["title"] == title and existing["slug"]
                else make_slug(db, title, exclude_id=service_id))
    db.execute(
        "UPDATE services SET group_name=?,title=?,slug=?,description=?,benefits=?,who_for=?,process_steps=?,icon=?,sort_order=?,active=? WHERE id=?",
        (
            request.form["group_name"], title, slug,
            request.form["description"],
            request.form.get("benefits", ""),
            request.form.get("who_for", ""),
            request.form.get("process_steps", ""),
            request.form.get("icon", "spark"),
            int(request.form.get("sort_order", 0) or 0),
            1 if request.form.get("active") == "on" else 0,
            service_id,
        ),
    )
    db.commit()
    flash("Service updated.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/service/delete/<int:service_id>", methods=["POST"])
@login_required
def admin_service_delete(service_id):
    db = get_db()
    db.execute("DELETE FROM services WHERE id=?", (service_id,))
    db.commit()
    flash("Service removed.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/service/gallery/add/<int:service_id>", methods=["POST"])
@login_required
def admin_service_gallery_add(service_id):
    files = request.files.getlist("gallery_images")
    db = get_db()
    added = 0
    for file in files:
        if file:
            path = save_upload(file, sub="gallery")
            if path:
                db.execute("INSERT INTO service_gallery (service_id, image_url) VALUES (?, ?)", (service_id, path))
                added += 1
    if added > 0:
        db.commit()
        flash(f"{added} images added to gallery.", "success")
    else:
        flash("No valid images selected.", "error")
    return redirect(url_for("admin_dashboard") + "#panel-services")

@app.route("/admin/service/gallery/delete/<int:image_id>", methods=["POST"])
@login_required
def admin_service_gallery_delete(image_id):
    db = get_db()
    db.execute("DELETE FROM service_gallery WHERE id=?", (image_id,))
    db.commit()
    flash("Gallery image removed.", "success")
    return redirect(url_for("admin_dashboard") + "#panel-services")


@app.route("/admin/faq/add", methods=["POST"])
@login_required
def admin_faq_add():
    db = get_db()
    db.execute(
        "INSERT INTO faqs (question,answer,sort_order) VALUES (?,?,?)",
        (request.form["question"], request.form["answer"], int(request.form.get("sort_order", 0) or 0)),
    )
    db.commit()
    flash("FAQ added.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/faq/delete/<int:faq_id>", methods=["POST"])
@login_required
def admin_faq_delete(faq_id):
    db = get_db()
    db.execute("DELETE FROM faqs WHERE id=?", (faq_id,))
    db.commit()
    flash("FAQ removed.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/inquiry/respond/<int:inquiry_id>", methods=["POST"])
@login_required
def admin_inquiry_respond(inquiry_id):
    db = get_db()
    db.execute(
        "UPDATE inquiries SET responded=1,admin_note=? WHERE id=?",
        (request.form.get("admin_note", ""), inquiry_id),
    )
    db.commit()
    flash("Inquiry marked as responded.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/servicerequest/status/<int:req_id>", methods=["POST"])
@login_required
def admin_servicerequest_status(req_id):
    db         = get_db()
    new_status = request.form.get("status", "New")
    if new_status not in REQUEST_STATUSES:
        new_status = "New"
    db.execute("UPDATE service_requests SET status=? WHERE id=?", (new_status, req_id))
    db.commit()
    flash("Request status updated.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/password", methods=["POST"])
@login_required
def admin_change_password():
    db           = get_db()
    new_password = request.form.get("new_password", "").strip()
    if len(new_password) < 4:
        flash("Password too short.", "error")
        return redirect(url_for("admin_dashboard"))
    db.execute("UPDATE admin_users SET password=? WHERE username=?", (new_password, session.get("admin_username")))
    db.commit()
    flash("Password updated.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/testimonial/add", methods=["POST"])
@login_required
def admin_testimonial_add():
    db = get_db()
    db.execute(
        "INSERT INTO testimonials (client_name,client_business,review,rating) VALUES (?,?,?,?)",
        (
            request.form.get("client_name", "").strip(),
            request.form.get("client_business", "").strip(),
            request.form.get("review", "").strip(),
            int(request.form.get("rating", 5)),
        ),
    )
    db.commit()
    flash("Testimonial added.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/testimonial/delete/<int:t_id>", methods=["POST"])
@login_required
def admin_testimonial_delete(t_id):
    db = get_db()
    db.execute("DELETE FROM testimonials WHERE id=?", (t_id,))
    db.commit()
    flash("Testimonial removed.", "success")
    return redirect(url_for("admin_dashboard"))


# ---------------------------------------------------------------------------
# Supabase status endpoint (for admin info)
# ---------------------------------------------------------------------------
@app.route("/api/status")
def api_status():
    return jsonify({
        "supabase": bool(supabase),
        "elevenlabs_agent": elevenlabs_agent_active(),
        "db": "supabase" if supabase else "sqlite",
    })


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
