import os
from datetime import datetime, timedelta, time
from typing import Optional, Tuple, List
from functools import wraps
from bson.objectid import ObjectId
from flask import Flask, render_template_string, request, redirect, url_for, flash,session
from flask_pymongo import PyMongo
from dotenv import load_dotenv
from jinja2 import DictLoader

# ---------------------------
# Config
# ---------------------------
load_dotenv()  # auto-load variables from .env file in project folder

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI", "mongodb://localhost:27017/squash_booking")

mongo = PyMongo(app)

db = mongo.db

# ---------------------------
# Simple HTML templates (Jinja in-strings for MVP)
# ---------------------------
base_tpl = """
<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Squash Booking MVP</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 2rem; }
    header { display:flex; gap: 1rem; align-items: baseline; }
    nav a { margin-right: 1rem; }
    form { display: grid; gap: .75rem; max-width: 640px; }
    input, select { padding: .5rem; }
    .grid { display: grid; gap: .5rem; }
    .row { display: grid; grid-template-columns: repeat(4, 1fr); gap: .5rem; }
    .card { border: 1px solid #ddd; border-radius: 10px; padding: 1rem; }
    .pill { padding: .2rem .5rem; border-radius: 999px; background: #eee; }
    .ok { background:#d1fae5 }
    .warn { background:#fef3c7 }
    .bad { background:#fee2e2 }
    .muted { color:#666 }
    .btn { display:inline-block; padding:.5rem .8rem; border-radius:8px; border:1px solid #ccc; text-decoration:none; }
    .btn.primary { background:#111; color:white; border-color:#111 }
    .btn.danger { background:#b91c1c; color:white; border-color:#b91c1c }
    .btn.link { border-color:transparent; background:transparent; color:#0366d6; }
  </style>
</head>
<body>
  <header>
    <h2>Squash Roma Booking Proto</h2>
    <nav>
      <a href=\"{{ url_for('home') }}\">Home</a>
      <a href=\"{{ url_for('new_request') }}\">New Request</a>
      <a href=\"{{ url_for('admin_dashboard') }}\">Admin</a>
      <a href=\"{{ url_for('calendar_day') }}\">Court Bookings Calendar</a>
      {% if session.get('is_admin') %}
        <span class="pill ok">Admin</span>
        <a class="btn" href="{{ url_for('admin_logout') }}">Logout</a>
      {% else %}
         <a class="btn" href="{{ url_for('admin_login', next=request.path) }}">Admin Login</a>
      {% endif %}
    </nav>
  </header>
  {% with messages = get_flashed_messages() %}
    {% if messages %}
      <ul>
        {% for m in messages %}<li>{{ m }}</li>{% endfor %}
      </ul>
    {% endif %}
  {% endwith %}
  {% block content %}{% endblock %}
</body>
</html>
"""

home_tpl = """
{% extends 'base.html' %}
{% block content %}
  <div style="text-align:center;margin-bottom:2rem;">
    <img src="{{ url_for('static', filename='images/roma_squash_logo.jpeg') }}"
         alt="Roma Squash Club Logo"
         style="max-width:300px;border-radius:10px;box-shadow:0 0 10px rgba(0,0,0,0.2);">
  </div>

  <p>Minimal web app to collect member availability, auto-match by level and time overlap, and let Carlos approve.</p>

  <div class="grid">
    <div class="card">
      <h3>Create a Play Request</h3>
      <p>Members submit date, time window and level. System proposes a match automatically.</p>
      <a class="btn primary" href="{{ url_for('new_request') }}">New Request</a>
    </div>

    <div class="card">
      <h3>Admin</h3>
      <p>Review pending proposals and approve/decline. See open requests. Create manual bookings.</p>
      <a class="btn" href="{{ url_for('admin_dashboard') }}">Go to Admin</a>
    </div>

    <div class="card">
      <h3>Calendar</h3>
      <p>See confirmed bookings per court and change court assignments.</p>
      <a class="btn" href="{{ url_for('calendar_day') }}">Today</a>
    </div>
  </div>
{% endblock %}
"""

new_request_tpl = """
{% extends 'base.html' %}
{% block content %}
  <h3>New Play Request</h3>
  <form method=\"post\">
    <label>Member Name <input required name=\"name\" placeholder=\"e.g., Marco Rossi\"></label>
    <label>Level
      <select name=\"level\" required>
        {% for L in [1,2,3,4,5] %}
          <option value=\"{{L}}\">Level {{L}}</option>
        {% endfor %}
      </select>
    </label>
    <label>Date <input required type=\"date\" name=\"date\" value=\"{{ default_date }}\"></label>
    <div class=\"row\">
      <label>Start <input required type=\"time\" name=\"start\" value=\"18:00\"></label>
      <label>End <input required type=\"time\" name=\"end\" value=\"20:00\"></label>
      <label>Duration (minutes)
        <select name=\"duration\">
          {% for d in [45, 60] %}
            <option value=\"{{d}}\">{{d}}</option>
          {% endfor %}
        </select>
      </label>
      <label>Notes <input name=\"notes\" placeholder=\"optional\"></label>
    </div>
    <button class=\"btn primary\" type=\"submit\">Submit Request</button>
  </form>
{% endblock %}
"""

edit_request_tpl = """
{% extends 'base.html' %}
{% block content %}
  <h3>Edit Request — {{ r.name }}</h3>
  <form method=\"post\">
    <label>Member Name <input required name=\"name\" value=\"{{ r.name }}\"></label>
    <label>Level
      <select name=\"level\" required>
        {% for L in [1,2,3,4,5] %}
          <option value=\"{{L}}\" {% if r.level == L %}selected{% endif %}>Level {{L}}</option>
        {% endfor %}
      </select>
    </label>
    <label>Date <input required type=\"date\" name=\"date\" value=\"{{ r.date }}\"></label>
    <div class=\"row\">
      <label>Start <input required type=\"time\" name=\"start\" value=\"{{ r.start }}\"></label>
      <label>End <input required type=\"time\" name=\"end\" value=\"{{ r.end }}\"></label>
      <label>Duration (minutes)
        <select name=\"duration\"> 
          {% for d in [45, 60] %}
            <option value=\"{{d}}\" {% if r.duration == d %}selected{% endif %}>{{d}}</option>
          {% endfor %}
        </select>
      </label>
      <label>Notes <input name=\"notes\" value=\"{{ r.notes or '' }}\"></label>
    </div>
    <button class=\"btn primary\" type=\"submit\">Save Changes</button>
    <a class=\"btn\" href=\"{{ url_for('admin_dashboard') }}\">Cancel</a>
  </form>
{% endblock %}
"""

edit_booking_tpl = """
{% extends 'base.html' %}
{% block content %}
  <h3>Edit Booking</h3>
  <form method="post">
    <div class="row">
      <label>Player A <input name="player_a" value="{{ b.player_a or '' }}" placeholder="Name (optional)"></label>
      <label>Player B <input name="player_b" value="{{ b.player_b or '' }}" placeholder="Name (optional)"></label>
      <label>Date <input required type="date" name="date" value="{{ b.date }}"></label>
      <label>Court
        <select name="court_id">
          {% for c in courts %}
            <option value="{{ c.court_id }}" {% if c.court_id == b.court_id %}selected{% endif %}>Court {{ c.court_id }}</option>
          {% endfor %}
        </select>
      </label>
    </div>
    <div class="row">
      <label>Start <input required type="time" name="start" value="{{ b.start }}"></label>
      <label>End <input required type="time" name="end" value="{{ b.end }}"></label>
      <label>Notes <input name="notes" value="{{ b.notes or '' }}" placeholder="optional"></label>
    </div>
    <button class="btn primary" type="submit">Save</button>
    <a class="btn" href="{{ url_for('calendar_day', date_str=b.date) }}">Cancel</a>
  </form>
{% endblock %}
"""

admin_login_tpl = """
{% extends 'base.html' %}
{% block content %}
  <h3>Admin Login</h3>
  <form method="post" action="{{ url_for('admin_login', next=request.args.get('next') or request.args.get('next') ) }}">
    <label>Password
      <input type="password" name="password" required>
    </label>
    <button class="btn primary" type="submit">Login</button>
    <a class="btn" href="{{ url_for('home') }}">Cancel</a>
  </form>
{% endblock %}
"""

admin_tpl = """
{% extends 'base.html' %}
{% block content %}
  <h3>Admin Dashboard</h3>

  <div class=\"card\">
    <h4>Create Manual Booking</h4>
    <form method=\"post\" action=\"{{ url_for('create_manual_booking') }}\">
      <div class=\"row\">
        <label>Player A <input required name=\"player_a\" placeholder=\"Name\"></label>
        <label>Player B <input required name=\"player_b\" placeholder=\"Name\"></label>
        <label>Date <input required type=\"date\" name=\"date\" value=\"{{ today }}\"></label>
        <label>Court
          <select name=\"court_id\">{% for c in courts %}<option value=\"{{ c.court_id }}\">Court {{ c.court_id }}</option>{% endfor %}</select>
        </label>
      </div>
      <div class=\"row\">
        <label>Start <input required type=\"time\" name=\"start\" value=\"18:00\"></label>
        <label>End <input required type=\"time\" name=\"end\" value=\"19:00\"></label>
        <label>Notes <input name=\"notes\" placeholder=\"optional\"></label>
      </div>
      <button class=\"btn primary\" type=\"submit\">Add Booking</button>
    </form>
  </div>

  <h4>Pending Proposals</h4>
  {% if proposals %}
    {% for p in proposals %}
      <div class=\"card\">
        <div>
          <b>Pair:</b> {{ p.request_a.name }} (L{{p.level_a}}) vs {{ p.request_b.name }} (L{{p.level_b}})
          <span class=\"pill\">{{ p.date }}</span>
          <div class=\"muted\">Suggested slot: {{ p.slot_start }} - {{ p.slot_end }} on Court {{ p.court_id }}</div>
        </div>
        <div style=\"margin-top:.5rem;\">
          <a class=\"btn primary\" href=\"{{ url_for('approve_proposal', proposal_id=p.id_str) }}\">Approve</a>
          <a class=\"btn danger\" href=\"{{ url_for('reject_proposal', proposal_id=p.id_str) }}\">Reject</a>
        </div>
      </div>
    {% endfor %}
  {% else %}
    <p class=\"muted\">No pending proposals.</p>
  {% endif %}

  <h4 style=\"margin-top:1.5rem;\">Open Requests</h4>
  {% if open_requests %}
    {% for r in open_requests %}
      <div class=\"card\">
        <b>{{ r.name }}</b> (L{{ r.level }}) — {{ r.date }}
        <div class=\"muted\">Available: {{ r.start }}–{{ r.end }} | {{ r.notes or '' }}</div>
        <div style=\"margin-top:.5rem;\">
          <a class=\"btn\" href=\"{{ url_for('edit_request', request_id=r.id_str) }}\">Edit</a>
          <a class=\"btn danger\" href=\"{{ url_for('delete_request', request_id=r.id_str) }}\" onclick=\"return confirm('Delete this request?');\">Delete</a>
        </div>
      </div>
    {% endfor %}
  {% else %}
    <p class=\"muted\">No open requests.</p>
  {% endif %}
{% endblock %}
"""

calendar_tpl = """
{% extends 'base.html' %}
{% block content %}
  <h3>Calendar — {{ date }}</h3>

  <form method="get" action="{{ url_for('calendar_day') }}" style="margin-bottom:1rem;">
    <label>Go to date:
      <input type="date" name="date" value="{{ date }}" />
    </label>
    <button class="btn" type="submit">Go</button>
  </form>

  <div class="grid">
  {% for court in courts %}
    <div class="card">
      <h4>Court {{ court.court_id }}</h4>
      {% set bookings = by_court.get(court.court_id, []) %}
      {% if bookings %}
        {% for b in bookings %}
          <div style="display:flex;align-items:center;justify-content:space-between;gap:.5rem;">
            <div>
              <b>{{ b.start }}–{{ b.end }}</b>
              <div class="muted">{{ b.player_a }} vs {{ b.player_b }}</div>
            </div>

            {% if session.get('is_admin') %}
            <div style="display:flex;gap:.5rem;align-items:center;">
              <a class="btn" href="{{ url_for('edit_booking', booking_id=b.id_str) }}">Edit</a>

              <form method="post" action="{{ url_for('change_booking_court', booking_id=b.id_str) }}">
                <select name="court_id">
                  {% for c2 in courts %}
                    <option value="{{ c2.court_id }}" {% if c2.court_id == b.court_id %}selected{% endif %}>
                      Court {{ c2.court_id }}
                    </option>
                  {% endfor %}
                </select>
                <button class="btn" type="submit">Move</button>
              </form>

              <form method="post" action="{{ url_for('delete_booking', booking_id=b.id_str) }}"
                    onsubmit="return confirm('Delete this booking?');">
                <button class="btn danger" type="submit">Delete</button>
              </form>
            </div>
            {% endif %}
          </div>
        {% endfor %}
      {% else %}
        <div class="muted">No bookings</div>
      {% endif %}
    </div>
  {% endfor %}
  </div>
{% endblock %}
"""

# Register templates in-memory (Flask 3.x compatible)
app.jinja_loader = DictLoader({
    'base.html': base_tpl,
    'home.html': home_tpl,
    'new_request.html': new_request_tpl,
    'edit_request.html': edit_request_tpl,
    'admin.html': admin_tpl,
    'calendar.html': calendar_tpl,
    'edit_booking.html': edit_booking_tpl,   # <-- add this
    'admin_login.html': admin_login_tpl,  # <-- add this
})

# ---------------------------
# Utilities
# ---------------------------

def parse_hhmm(s: str) -> time:
    return datetime.strptime(s, "%H:%M").time()


def minutes_overlap(a_start: time, a_end: time, b_start: time, b_end: time) -> Tuple[int, Optional[time], Optional[time]]:
    start = max(a_start, b_start)
    end = min(a_end, b_end)
    if start >= end:
        return 0, None, None
    delta = datetime.combine(datetime.today(), end) - datetime.combine(datetime.today(), start)
    mins = int(delta.total_seconds() // 60)
    return mins, start, end


def discrete_slots(start: time, end: time, duration_min: int = 60, step_min: int = 15) -> List[Tuple[time, time]]:
    slots = []
    dt = datetime.combine(datetime.today(), start)
    end_dt = datetime.combine(datetime.today(), end)
    while dt + timedelta(minutes=duration_min) <= end_dt:
        slots.append((dt.time(), (dt + timedelta(minutes=duration_min)).time()))
        dt += timedelta(minutes=step_min)
    return slots


def court_is_free(date_str: str, court_id: int, slot_start: time, slot_end: time) -> bool:
    existing = list(db.bookings.find({
        "date": date_str,
        "court_id": court_id,
        "status": {"$in": ["tentative", "confirmed"]}
    }))
    for b in existing:
        if not (slot_end <= parse_hhmm(b["start"]) or slot_start >= parse_hhmm(b["end"])):
            return False
    return True


def court_is_free_excluding(date_str: str, court_id: int, slot_start: time, slot_end: time, exclude_id: ObjectId) -> bool:
    """
    Like court_is_free, but ignores the booking with _id = exclude_id.
    Uses efficient Mongo-side overlap filter:
      overlap if existing.start < slot_end AND existing.end > slot_start
    """
    s_start = slot_start.strftime("%H:%M")
    s_end = slot_end.strftime("%H:%M")
    conflict = db.bookings.find_one({
        "_id": {"$ne": exclude_id},
        "date": date_str,
        "court_id": court_id,
        "status": {"$in": ["tentative", "confirmed"]},
        "start": {"$lt": s_end},
        "end": {"$gt": s_start},
    })
    return conflict is None

def seed_courts_if_needed():
    if db.courts.count_documents({}) == 0:
        db.courts.insert_many([{ "court_id": i+1 } for i in range(4)])



# --- Club hours helpers ---

WEEKDAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

def seed_default_hours():
    """
    Seed default club hours if none exist:
      Mon–Sat open 10:00–22:00, Sun closed
    Collection: availability_rules
    Doc shape: { weekday: 0..6, is_open: bool, open: "HH:MM", close: "HH:MM" }
    """
    if db.availability_rules.count_documents({}) == 0:
        docs = []
        for wd in range(7):
            if wd <= 5:  # Mon..Sat
                docs.append({"weekday": wd, "is_open": True,  "open": "10:00", "close": "22:00"})
            else:        # Sun
                docs.append({"weekday": wd, "is_open": False, "open": "00:00", "close": "00:00"})
        db.availability_rules.insert_many(docs)

def get_club_hours(date_str: str):
    """
    Return (open_time, close_time, is_open) for the given YYYY-MM-DD date.
    Falls back to defaults if a rule for that weekday is missing.
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    wd = dt.weekday()  # 0=Mon..6=Sun
    rule = db.availability_rules.find_one({"weekday": wd})
    if not rule:
        # Fallback defaults if not seeded yet
        if wd <= 5:
            return parse_hhmm("10:00"), parse_hhmm("22:00"), True
        return parse_hhmm("00:00"), parse_hhmm("00:00"), False
    if not rule.get("is_open", True):
        return parse_hhmm("00:00"), parse_hhmm("00:00"), False
    return parse_hhmm(rule.get("open", "10:00")), parse_hhmm(rule.get("close", "22:00")), True

def clamp_to_hours(date_str: str, start: time, end: time):
    """
    Clamp [start, end) to club hours for the given date.
    Returns: (clamped_start, clamped_end, is_open)
      - If the club is closed or no overlap remains after clamping, returns (None, None, False).
    """
    open_t, close_t, is_open = get_club_hours(date_str)
    if not is_open:
        return None, None, False
    s = max(start, open_t)
    e = min(end, close_t)
    if s >= e:
        return None, None, False
    return s, e, True


# ---------------------------
# Matching logic (simple greedy)
# ---------------------------

def try_autopair(new_request_id: ObjectId):
    r = db.play_requests.find_one({"_id": new_request_id})
    if not r or r["status"] != "open":
        return

    # Candidates: same date, open, not the same requester, level within ±1
    candidates = list(db.play_requests.find({
        "_id": {"$ne": r["_id"]},
        "date": r["date"],
        "status": "open",
        "level": {"$gte": r["level"] - 1, "$lte": r["level"] + 1},
    }))

    best = None
    best_score = -10**9
    for c in candidates:
        overlap_mins, ov_start, ov_end = minutes_overlap(
            parse_hhmm(r["start"]), parse_hhmm(r["end"]),
            parse_hhmm(c["start"]), parse_hhmm(c["end"])
        )
        if overlap_mins <= 0:
            continue

        # Clamp the overlap window to club hours for that date
        s_c, e_c, is_open = clamp_to_hours(r["date"], ov_start, ov_end)
        if not is_open or s_c is None:
            continue

        # Score: overlap + level closeness
        level_pen = -abs(r["level"] - c["level"])  # 0 is best
        score = overlap_mins + 5 * level_pen
        if score > best_score:
            best = (c, s_c, e_c)
            best_score = score

    if not best:
        return  # no candidate yet

    c, ov_start, ov_end = best

    # Find a feasible slot & a free court within club hours
    duration = r.get("duration", 45)
    for s_start, s_end in discrete_slots(ov_start, ov_end, duration_min=duration, step_min=15):
        for court in db.courts.find({}).sort("court_id"):
            court_id = court["court_id"]
            if court_is_free(r["date"], court_id, s_start, s_end):
                # Create tentative booking + proposal
                booking_id = db.bookings.insert_one({
                    "date": r["date"],
                    "court_id": court_id,
                    "start": s_start.strftime("%H:%M"),
                    "end": s_end.strftime("%H:%M"),
                    "status": "tentative"
                }).inserted_id

                proposal = {
                    "request_a_id": r["_id"],
                    "request_b_id": c["_id"],
                    "date": r["date"],
                    "slot_start": s_start.strftime("%H:%M"),
                    "slot_end": s_end.strftime("%H:%M"),
                    "court_id": court_id,
                    "status": "pending_admin",
                    "level_a": r["level"],
                    "level_b": c["level"],
                    "booking_id": booking_id,
                    "created_at": datetime.utcnow(),
                }
                db.match_proposals.insert_one(proposal)
                return
    # If we reach here, no courts free within overlap/hours; do nothing.

# ---------------------------
# Routes
# ---------------------------
@app.route("/")
def home():
    seed_courts_if_needed()
    return render_template_string(home_tpl)


@app.route("/member/request", methods=["GET", "POST"])
def new_request():
    seed_courts_if_needed()
    if request.method == "POST":
        name = request.form.get("name").strip()
        level = int(request.form.get("level"))
        date_str = request.form.get("date")  # YYYY-MM-DD
        start = request.form.get("start")
        end = request.form.get("end")
        duration = int(request.form.get("duration", 45))
        notes = request.form.get("notes")

        # Basic validation
        if parse_hhmm(end) <= parse_hhmm(start):
            flash("End time must be after start time.")
            return redirect(url_for('new_request'))

        # Enforce club hours: clamp to hours and refuse if no overlap
        s_clamped, e_clamped, is_open = clamp_to_hours(date_str, parse_hhmm(start), parse_hhmm(end))
        if not is_open:
            flash("Club is closed on the selected day.")
            return redirect(url_for('new_request'))
        if s_clamped is None:
            flash("Selected time window is outside club hours.")
            return redirect(url_for('new_request'))

        req_doc = {
            "name": name,
            "level": level,
            "date": date_str,
            "start": s_clamped.strftime("%H:%M"),
            "end": e_clamped.strftime("%H:%M"),
            "duration": duration,
            "notes": notes,
            "status": "open",
            "created_at": datetime.utcnow(),
        }
        rid = db.play_requests.insert_one(req_doc).inserted_id

        # Try to auto-pair right away
        try_autopair(rid)

        flash("Request submitted. If a compatible opponent is found, Carlos will review the proposal.")
        return redirect(url_for('home'))

    return render_template_string(new_request_tpl, default_date=datetime.now().strftime("%Y-%m-%d"))


# -------- Minimal admin guard --------
def require_admin(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        # If already logged in, proceed
        if session.get("is_admin"):
            return view(*args, **kwargs)
        # Otherwise, send to login with 'next' redirect back here
        return redirect(url_for("admin_login", next=request.path))
    return wrapped

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        pwd = request.form.get("password", "")
        if pwd == os.environ.get("ADMIN_PASS", ""):
            session["is_admin"] = True
            flash("Logged in as admin.")
            return redirect(request.args.get("next") or url_for("admin_dashboard"))
        flash("Incorrect password.")
    return render_template_string(admin_login_tpl)



@app.route("/admin")
@require_admin
def admin_dashboard():
    seed_courts_if_needed()

    proposals = []
    for p in db.match_proposals.find({"status": "pending_admin"}).sort("created_at", -1):
        ra = db.play_requests.find_one({"_id": p["request_a_id"]})
        rb = db.play_requests.find_one({"_id": p["request_b_id"]})
        p["request_a"] = ra
        p["request_b"] = rb
        p["id_str"] = str(p["_id"])  # for links in template
        proposals.append(p)

    open_requests = list(db.play_requests.find({"status": "open"}).sort("created_at", -1))
    for r in open_requests:
        r["id_str"] = str(r["_id"])  # for edit/delete links
    courts = list(db.courts.find({}).sort("court_id"))

    return render_template_string(admin_tpl, proposals=proposals, open_requests=open_requests, courts=courts, today=datetime.now().strftime("%Y-%m-%d"))

@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    flash("Logged out.")
    return redirect(url_for("home"))

@app.route("/admin/proposals/<proposal_id>/approve")
@require_admin
def approve_proposal(proposal_id):
    p = db.match_proposals.find_one({"_id": ObjectId(proposal_id)})
    if not p or p["status"] != "pending_admin":
        flash("Proposal not found or already processed.")
        return redirect(url_for('admin_dashboard'))

    # Confirm booking
    db.bookings.update_one({"_id": p["booking_id"]}, {"$set": {"status": "confirmed"}})
    # Mark requests as matched
    db.play_requests.update_one({"_id": p["request_a_id"]}, {"$set": {"status": "matched"}})
    db.play_requests.update_one({"_id": p["request_b_id"]}, {"$set": {"status": "matched"}})

    db.match_proposals.update_one({"_id": p["_id"]}, {"$set": {"status": "approved"}})

    flash("Proposal approved and booking confirmed.")
    return redirect(url_for('admin_dashboard'))


@app.route("/admin/proposals/<proposal_id>/reject")
@require_admin
def reject_proposal(proposal_id):
    p = db.match_proposals.find_one({"_id": ObjectId(proposal_id)})
    if not p or p["status"] != "pending_admin":
        flash("Proposal not found or already processed.")
        return redirect(url_for('admin_dashboard'))

    # Free tentative booking
    db.bookings.update_one({"_id": p["booking_id"]}, {"$set": {"status": "cancelled"}})
    # Keep requests open so they can be re-matched
    db.match_proposals.update_one({"_id": p["_id"]}, {"$set": {"status": "rejected"}})

    flash("Proposal rejected; requests remain open.")
    return redirect(url_for('admin_dashboard'))


# ---- New: Edit & Delete Requests ----
@app.route("/admin/requests/<request_id>/edit", methods=["GET", "POST"])
@require_admin
def edit_request(request_id):
    r = db.play_requests.find_one({"_id": ObjectId(request_id)})
    if not r:
        flash("Request not found.")
        return redirect(url_for('admin_dashboard'))
    if r.get("status") != "open":
        flash("Only OPEN requests can be edited.")
        return redirect(url_for('admin_dashboard'))

    if request.method == "POST":
        name = request.form.get("name").strip()
        level = int(request.form.get("level"))
        date_str = request.form.get("date")
        start = request.form.get("start")
        end = request.form.get("end")
        duration = int(request.form.get("duration", 60))
        notes = request.form.get("notes")
        if parse_hhmm(end) <= parse_hhmm(start):
            flash("End time must be after start time.")
            return redirect(url_for('edit_request', request_id=request_id))

        db.play_requests.update_one({"_id": r["_id"]}, {"$set": {
            "name": name,
            "level": level,
            "date": date_str,
            "start": start,
            "end": end,
            "duration": duration,
            "notes": notes,
        }})
        flash("Request updated.")
        # attempt re-matching
        try_autopair(r["_id"])
        return redirect(url_for('admin_dashboard'))

    # GET
    return render_template_string(edit_request_tpl, r=r)


@app.route("/admin/requests/<request_id>/delete")
@require_admin
def delete_request(request_id):
    r = db.play_requests.find_one({"_id": ObjectId(request_id)})
    if not r:
        flash("Request not found.")
        return redirect(url_for('admin_dashboard'))
    if r.get("status") != "open":
        flash("Only OPEN requests can be deleted.")
        return redirect(url_for('admin_dashboard'))

    # remove any pending proposals involving this request
    db.match_proposals.delete_many({"$or": [{"request_a_id": r["_id"]}, {"request_b_id": r["_id"]}], "status": "pending_admin"})
    db.play_requests.delete_one({"_id": r["_id"]})
    flash("Request deleted.")
    return redirect(url_for('admin_dashboard'))


# ---- New: Manual Booking ----
@app.route("/admin/bookings/new", methods=["POST"])  # form is on admin page
@require_admin
def create_manual_booking():
    player_a = request.form.get("player_a").strip()
    player_b = request.form.get("player_b").strip()
    date_str = request.form.get("date")
    start = request.form.get("start")
    end = request.form.get("end")
    court_id = int(request.form.get("court_id"))

    if parse_hhmm(end) <= parse_hhmm(start):
        flash("End time must be after start time.")
        return redirect(url_for('admin_dashboard'))

    # Enforce club hours for manual bookings
    s_clamped, e_clamped, is_open = clamp_to_hours(date_str, parse_hhmm(start), parse_hhmm(end))
    if not is_open:
        flash("Club is closed on the selected day.")
        return redirect(url_for('admin_dashboard'))
    if s_clamped is None:
        flash("Selected time is outside club hours.")
        return redirect(url_for('admin_dashboard'))

    # Check court availability
    if not court_is_free(date_str, court_id, s_clamped, e_clamped):
        flash(f"Court {court_id} is not free for the selected time.")
        return redirect(url_for('admin_dashboard'))

    db.bookings.insert_one({
        "date": date_str,
        "court_id": court_id,
        "start": s_clamped.strftime("%H:%M"),
        "end": e_clamped.strftime("%H:%M"),
        "status": "confirmed",
        "player_a": player_a,
        "player_b": player_b,
        "created_at": datetime.utcnow(),
    })
    flash("Manual booking created.")
    return redirect(url_for('admin_dashboard'))


# ---- Calendar & change booking court & delete ----
@app.route("/calendar")
@app.route("/calendar/<date_str>")
def calendar_day(date_str: Optional[str] = None):
    seed_courts_if_needed()
    # Allow choosing date via query param too
    q_date = request.args.get("date")
    if q_date:
        date_str = q_date
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    courts = list(db.courts.find({}).sort("court_id"))
    bookings = list(db.bookings.find({"date": date_str, "status": "confirmed"}).sort([("court_id", 1), ("start", 1)]))

    # decorate with player names
    by_court = {}
    for b in bookings:
        # Try to fetch proposal for context (optional)
        p = db.match_proposals.find_one({"booking_id": b["_id"]})
        ra = rb = None
        if p:
            ra = db.play_requests.find_one({"_id": p.get("request_a_id")})
            rb = db.play_requests.find_one({"_id": p.get("request_b_id")})

        # Prefer names stored on the booking; fall back to requests; then to placeholders
        player_a = b.get("player_a") or (ra["name"] if ra and "name" in ra else "Player A")
        player_b = b.get("player_b") or (rb["name"] if rb and "name" in rb else "Player B")

        entry = {
            "id_str": str(b["_id"]),
            "start": b["start"],
            "end": b["end"],
            "player_a": player_a,
            "player_b": player_b,
            "court_id": b["court_id"],
        }
        by_court.setdefault(b["court_id"], []).append(entry)

    return render_template_string(calendar_tpl, date=date_str, courts=courts, by_court=by_court)


@app.route("/admin/bookings/<booking_id>/edit", methods=["GET", "POST"])
@require_admin
def edit_booking(booking_id):
    b = db.bookings.find_one({"_id": ObjectId(booking_id)})
    if not b:
        flash("Booking not found.")
        return redirect(url_for('calendar_day'))

    if request.method == "POST":
        player_a = (request.form.get("player_a") or "").strip() or None
        player_b = (request.form.get("player_b") or "").strip() or None
        date_str = request.form.get("date")
        start_s = request.form.get("start")
        end_s   = request.form.get("end")
        court_id = int(request.form.get("court_id") or b.get("court_id", 1))
        notes = (request.form.get("notes") or "").strip() or None

        # Basic validation
        if parse_hhmm(end_s) <= parse_hhmm(start_s):
            flash("End time must be after start time.")
            return redirect(url_for('edit_booking', booking_id=booking_id))

        # Enforce club hours
        s_clamped, e_clamped, is_open = clamp_to_hours(date_str, parse_hhmm(start_s), parse_hhmm(end_s))
        if not is_open:
            flash("Club is closed on the selected day.")
            return redirect(url_for('edit_booking', booking_id=booking_id))
        if s_clamped is None:
            flash("Selected time window is outside club hours.")
            return redirect(url_for('edit_booking', booking_id=booking_id))

        # Check court availability excluding this booking
        if not court_is_free_excluding(date_str, court_id, s_clamped, e_clamped, b["_id"]):
            flash(f"Court {court_id} is not free for the selected time.")
            return redirect(url_for('edit_booking', booking_id=booking_id))

        # Persist changes
        db.bookings.update_one({"_id": b["_id"]}, {"$set": {
            "date": date_str,
            "court_id": court_id,
            "start": s_clamped.strftime("%H:%M"),
            "end": e_clamped.strftime("%H:%M"),
            "player_a": player_a,   # can be None if you leave blank
            "player_b": player_b,
            "notes": notes,
        }})
        flash("Booking updated.")
        # Redirect to the new date’s calendar view if the date changed
        return redirect(url_for('calendar_day', date_str=date_str))

    # GET → render form
    courts = list(db.courts.find({}).sort("court_id"))
    return render_template_string(edit_booking_tpl, b=b, courts=courts)



@app.route("/admin/bookings/<booking_id>/change_court", methods=["POST"])
@require_admin
def change_booking_court(booking_id):
    b = db.bookings.find_one({"_id": ObjectId(booking_id)})
    if not b:
        flash("Booking not found.")
        return redirect(url_for('calendar_day'))

    new_court = int(request.form.get("court_id"))
    if new_court == b.get("court_id"):
        flash("No change to court.")
        return redirect(url_for('calendar_day', date_str=b["date"]))

    # Check availability on new court
    if not court_is_free(b["date"], new_court, parse_hhmm(b["start"]), parse_hhmm(b["end"])):
        flash(f"Court {new_court} is not free for that time.")
        return redirect(url_for('calendar_day', date_str=b["date"]))

    db.bookings.update_one({"_id": b["_id"]}, {"$set": {"court_id": new_court}})
    flash("Booking moved to new court.")
    return redirect(url_for('calendar_day', date_str=b["date"]))


@app.route("/admin/bookings/<booking_id>/delete", methods=["POST"])
@require_admin
def delete_booking(booking_id):
    b = db.bookings.find_one({"_id": ObjectId(booking_id)})
    if not b:
        flash("Booking not found.")
        return redirect(url_for('calendar_day'))

    # If booking came from a proposal, mark that proposal as cancelled (optional)
    db.match_proposals.update_one({"booking_id": b["_id"]}, {"$set": {"status": "cancelled"}})

    db.bookings.delete_one({"_id": b["_id"]})
    flash("Booking deleted.")
    return redirect(url_for('calendar_day', date_str=b["date"]))

    # Check availability on new court
    if not court_is_free(b["date"], new_court, parse_hhmm(b["start"]), parse_hhmm(b["end"])):
        flash(f"Court {new_court} is not free for that time.")
        return redirect(url_for('calendar_day', date_str=b["date"]))

    db.bookings.update_one({"_id": b["_id"]}, {"$set": {"court_id": new_court}})
    flash("Booking moved to new court.")
    return redirect(url_for('calendar_day', date_str=b["date"]))


# ---------------------------
# Startup helpers (Flask 3.x safe)
# ---------------------------

def ensure_indexes():
    db.play_requests.create_index([("date", 1), ("status", 1), ("level", 1)])
    db.bookings.create_index([("date", 1), ("court_id", 1), ("start", 1), ("end", 1)])
    db.match_proposals.create_index([("status", 1), ("created_at", -1)])

# Run once at startup
with app.app_context():
    seed_courts_if_needed()
    seed_default_hours()            # <-- add this
    ensure_indexes()

@app.route("/admin/hours", methods=["POST"])  # update hours per weekday
@require_admin
def update_hours():
    # Expect fields like is_open_0, open_0, close_0 ... is_open_6, open_6, close_6
    for wd in range(7):
        is_open = request.form.get(f"is_open_{wd}") == "1"
        open_v = request.form.get(f"open_{wd}") or "10:00"
        close_v = request.form.get(f"close_{wd}") or "22:00"
        db.availability_rules.update_one(
            {"weekday": wd},
            {"$set": {"weekday": wd, "is_open": is_open, "open": open_v, "close": close_v}},
            upsert=True,
        )
    flash("Club hours saved.")
    return redirect(url_for('admin_dashboard'))

if __name__ == "__main__":
    app.run(debug=True)
