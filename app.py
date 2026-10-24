import os, sqlite3, secrets, json
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "aniverse.db")
UPLOAD_DIR = os.path.join(APP_DIR, "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

SEED = [
    ("Black Clover", "Action, Fantasy", 2017, "Hindi Dub", "Asta dreams of becoming the Wizard King in a world where magic is everything.", "https://images.unsplash.com/photo-1578632767115-351597cf2477?auto=format&fit=crop&w=900&q=85", 1),
    ("Ninja Legends", "Action, Adventure", 2024, "Japanese", "A young ninja begins a journey to protect the people he loves.", "https://images.unsplash.com/photo-1614583225154-5fcdda07019e?auto=format&fit=crop&w=900&q=85", 1),
    ("Skybound Academy", "Fantasy, School", 2025, "Hindi Sub", "Students discover mysterious powers at an academy above the clouds.", "https://images.unsplash.com/photo-1578632767115-351597cf2477?auto=format&fit=crop&w=900&q=85", 1),
    ("Mecha Horizon", "Sci-Fi, Action", 2023, "Japanese", "Pilots unite to defend their city from a threat beyond the stars.", "https://images.unsplash.com/photo-1535223289827-42f1e9919769?auto=format&fit=crop&w=900&q=85", 1),
    ("Moonlight Quest", "Adventure, Mystery", 2022, "Hindi Dub", "A group of friends follows a map that appears only at night.", "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=900&q=85", 1),
    ("Spirit Garden", "Fantasy, Drama", 2024, "Hindi Sub", "A quiet village hides a magical garden and an ancient secret.", "https://images.unsplash.com/photo-1511497584788-876760111969?auto=format&fit=crop&w=900&q=85", 1),
]
SAMPLE_VIDEO = "https://storage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL, is_admin INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS anime(
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, genre TEXT NOT NULL,
            year INTEGER, language TEXT, description TEXT, poster TEXT, featured INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS episodes(
            id INTEGER PRIMARY KEY AUTOINCREMENT, anime_id INTEGER NOT NULL,
            episode_number INTEGER NOT NULL, title TEXT NOT NULL, video_url TEXT NOT NULL,
            server_urls TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY(anime_id) REFERENCES anime(id) ON DELETE CASCADE,
            UNIQUE(anime_id, episode_number)
        );
        CREATE TABLE IF NOT EXISTS watch_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            anime_id INTEGER NOT NULL, episode_id INTEGER NOT NULL, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, anime_id), FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(anime_id) REFERENCES anime(id), FOREIGN KEY(episode_id) REFERENCES episodes(id)
        );
        """)
        # Safe migration for databases created by earlier KAIRO versions.
        episode_columns = {row[1] for row in con.execute("PRAGMA table_info(episodes)").fetchall()}
        if "server_urls" not in episode_columns:
            con.execute("ALTER TABLE episodes ADD COLUMN server_urls TEXT NOT NULL DEFAULT '{}' ")
        if con.execute("SELECT COUNT(*) FROM anime").fetchone()[0] == 0:
            for i, item in enumerate(SEED):
                cur = con.execute("INSERT INTO anime(title,genre,year,language,description,poster,featured) VALUES(?,?,?,?,?,?,?)",
                                  (*item[:6], 1 if i == 0 else 0))
                anime_id = cur.lastrowid
                for ep in range(1, 13):
                    con.execute("INSERT INTO episodes(anime_id,episode_number,title,video_url) VALUES(?,?,?,?)",
                                (anime_id, ep, "Episode " + str(ep), SAMPLE_VIDEO))
        admin_user = os.environ.get("ADMIN_USERNAME", "admin")
        admin_pass = os.environ.get("ADMIN_PASSWORD", "ChangeMe123!")
        if con.execute("SELECT COUNT(*) FROM users WHERE is_admin=1").fetchone()[0] == 0:
            con.execute("INSERT OR IGNORE INTO users(username,password_hash,is_admin) VALUES(?,?,1)",
                        (admin_user, generate_password_hash(admin_pass)))

def parse_server_urls(raw):
    """Accept optional JSON mapping of language -> server label -> authorized URL."""
    if not raw or not raw.strip():
        return {}
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            return {}
        clean = {}
        # Accept both the simple Hindi/English format and grouped server mappings.
        for language in ("Hindi", "English"):
            raw_url = value.get(language, "")
            if isinstance(raw_url, str) and raw_url.strip().startswith(("https://", "http://")):
                clean[language] = {language: raw_url.strip()}
            elif isinstance(raw_url, dict):
                servers = {}
                for server, url in raw_url.items():
                    if isinstance(server, str) and isinstance(url, str) and url.strip().startswith(("https://", "http://")):
                        servers[server.strip()[:40]] = url.strip()
                if servers:
                    clean[language] = servers
        return clean
    except (json.JSONDecodeError, TypeError):
        return {}

def current_user():
    if "user_id" not in session:
        return None
    with db() as con:
        return con.execute("SELECT id,username,is_admin FROM users WHERE id=?", (session["user_id"],)).fetchone()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash("Please sign in first.", "error")
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or not user["is_admin"]:
            flash("Admin access required.", "error")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

@app.context_processor
def inject_user():
    return {"logged_user": current_user()}

@app.route("/")
def home():
    q = request.args.get("q", "").strip()
    genre = request.args.get("genre", "").strip()
    with db() as con:
        sql = "SELECT a.*, (SELECT COUNT(*) FROM episodes e WHERE e.anime_id=a.id) AS episode_count FROM anime a WHERE 1=1"
        params = []
        if q:
            sql += " AND (a.title LIKE ? OR a.genre LIKE ? OR a.language LIKE ?)"
            params.extend([f"%{q}%"]*3)
        if genre:
            sql += " AND a.genre LIKE ?"
            params.append(f"%{genre}%")
        sql += " ORDER BY a.featured DESC, a.id DESC"
        shows = con.execute(sql, params).fetchall()
        featured = con.execute("SELECT * FROM anime WHERE featured=1 ORDER BY id DESC LIMIT 1").fetchone()
    return render_template("index.html", anime=shows, featured=featured, q=q, genre=genre)

@app.route("/watch/<int:anime_id>")
def watch(anime_id):
    user = current_user()
    with db() as con:
        show = con.execute("SELECT * FROM anime WHERE id=?", (anime_id,)).fetchone()
        if not show: abort(404)
        eps = con.execute("SELECT * FROM episodes WHERE anime_id=? ORDER BY episode_number", (anime_id,)).fetchall()
        history_episode_id = None
        if user:
            row = con.execute("SELECT episode_id FROM watch_history WHERE user_id=? AND anime_id=?", (user["id"], anime_id)).fetchone()
            if row: history_episode_id = row["episode_id"]
    if not eps: abort(404)
    selected = next((e for e in eps if e["id"] == history_episode_id), eps[0])
    if request.args.get("ep"):
        try:
            selected = next((e for e in eps if e["id"] == int(request.args["ep"])), selected)
        except ValueError:
            pass
    try:
        server_urls = json.loads(selected["server_urls"] or "{}")
    except (KeyError, TypeError, json.JSONDecodeError):
        server_urls = {}
    return render_template("watch.html", show=show, episodes=eps, selected=selected, server_urls=server_urls)

@app.post("/api/history")
@login_required
def save_history():
    data = request.get_json(silent=True) or {}
    try:
        anime_id, episode_id = int(data.get("anime_id")), int(data.get("episode_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid episode"}), 400
    with db() as con:
        ep = con.execute("SELECT id,anime_id FROM episodes WHERE id=?", (episode_id,)).fetchone()
        if not ep or ep["anime_id"] != anime_id:
            return jsonify({"error": "Episode not found"}), 404
        con.execute("""INSERT INTO watch_history(user_id,anime_id,episode_id,updated_at) VALUES(?,?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(user_id,anime_id) DO UPDATE SET episode_id=excluded.episode_id,updated_at=CURRENT_TIMESTAMP""",
                    (session["user_id"], anime_id, episode_id))
    return jsonify({"ok": True})

@app.route("/history")
@login_required
def history():
    with db() as con:
        rows = con.execute("""SELECT a.*, e.id AS episode_id, e.episode_number, h.updated_at
        FROM watch_history h JOIN anime a ON a.id=h.anime_id JOIN episodes e ON e.id=h.episode_id
        WHERE h.user_id=? ORDER BY h.updated_at DESC""", (session["user_id"],)).fetchall()
    return render_template("history.html", rows=rows)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if len(username) < 3 or len(password) < 8:
            flash("Username must be at least 3 characters and password at least 8 characters.", "error")
        else:
            try:
                with db() as con:
                    con.execute("INSERT INTO users(username,password_hash) VALUES(?,?)",
                                (username, generate_password_hash(password)))
                flash("Account created. You can now sign in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("That username is already taken.", "error")
    return render_template("auth.html", mode="signup")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with db() as con:
            user = con.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            flash("Welcome back!", "success")
            dest = request.args.get("next", "")
            return redirect(dest if dest.startswith("/") and not dest.startswith("//") else url_for("home"))
        flash("Incorrect username or password.", "error")
    return render_template("auth.html", mode="login")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have signed out.", "success")
    return redirect(url_for("home"))

@app.route("/admin")
@admin_required
def admin():
    with db() as con:
        shows = con.execute("""SELECT a.*,COUNT(e.id) AS episode_count FROM anime a
        LEFT JOIN episodes e ON e.anime_id=a.id GROUP BY a.id ORDER BY a.id DESC""").fetchall()
    return render_template("admin.html", anime=shows)

@app.route("/admin/anime/new", methods=["GET", "POST"])
@admin_required
def add_anime():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        genre = request.form.get("genre", "").strip()
        year = request.form.get("year", "2026").strip()
        language = request.form.get("language", "Hindi Dub").strip()
        description = request.form.get("description", "").strip()
        poster = request.form.get("poster", "").strip()
        featured = 1 if request.form.get("featured") else 0
        if not title or not genre:
            flash("Title and genre are required.", "error")
            return render_template("anime_form.html", show=None)
        try: year = int(year)
        except ValueError: year = 2026
        file = request.files.get("poster_file")
        if file and file.filename and allowed_image(file.filename):
            filename = secrets.token_hex(8) + "_" + secure_filename(file.filename)
            file.save(os.path.join(UPLOAD_DIR, filename))
            poster = url_for("static", filename="uploads/" + filename)
        with db() as con:
            if featured: con.execute("UPDATE anime SET featured=0")
            cur = con.execute("INSERT INTO anime(title,genre,year,language,description,poster,featured) VALUES(?,?,?,?,?,?,?)",
                              (title,genre,year,language,description,poster or "https://images.unsplash.com/photo-1578632767115-351597cf2477?auto=format&fit=crop&w=900&q=85",featured))
            anime_id = cur.lastrowid
            # Add an initial demo episode; replace the video URL with an authorized stream.
            server_urls = parse_server_urls(request.form.get("server_urls", ""))
            hindi_embed = request.form.get("hindi_embed_url", "").strip()
            english_embed = request.form.get("english_embed_url", "").strip()
            if hindi_embed.startswith(("https://", "http://")): server_urls["Hindi"] = {"Hindi": hindi_embed}
            if english_embed.startswith(("https://", "http://")): server_urls["English"] = {"English": english_embed}
            con.execute("INSERT INTO episodes(anime_id,episode_number,title,video_url,server_urls) VALUES(?,?,?,?,?)",
                        (anime_id,1,"Episode 1",request.form.get("video_url","").strip() or SAMPLE_VIDEO, json.dumps(server_urls)))
        flash("Anime added. Add more episodes from the admin panel.", "success")
        return redirect(url_for("admin"))
    return render_template("anime_form.html", show=None)

@app.route("/admin/anime/<int:anime_id>/episode", methods=["POST"])
@admin_required
def add_episode(anime_id):
    number = request.form.get("episode_number", "1")
    title = request.form.get("episode_title", "").strip()
    video_url = request.form.get("video_url", "").strip()
    try: number = int(number)
    except ValueError: number = 0
    with db() as con:
        exists = con.execute("SELECT id FROM anime WHERE id=?", (anime_id,)).fetchone()
        if not exists: abort(404)
        hindi_embed = request.form.get("hindi_embed_url", "").strip()
        english_embed = request.form.get("english_embed_url", "").strip()
        if number < 1 or not title or not (video_url or hindi_embed.startswith(("https://", "http://")) or english_embed.startswith(("https://", "http://"))):
            flash("Enter an episode number and title, plus a default video URL or at least one embed URL.", "error")
        else:
            try:
                server_urls = parse_server_urls(request.form.get("server_urls", ""))
                if hindi_embed.startswith(("https://", "http://")): server_urls["Hindi"] = {"Hindi": hindi_embed}
                if english_embed.startswith(("https://", "http://")): server_urls["English"] = {"English": english_embed}
                con.execute("INSERT INTO episodes(anime_id,episode_number,title,video_url,server_urls) VALUES(?,?,?,?,?)",
                            (anime_id,number,title,video_url or SAMPLE_VIDEO,json.dumps(server_urls)))
                flash("Episode added.", "success")
            except sqlite3.IntegrityError:
                flash("That episode number already exists for this anime.", "error")
    return redirect(url_for("admin"))

@app.post("/admin/anime/<int:anime_id>/delete")
@admin_required
def delete_anime(anime_id):
    with db() as con:
        con.execute("DELETE FROM watch_history WHERE anime_id=?", (anime_id,))
        con.execute("DELETE FROM episodes WHERE anime_id=?", (anime_id,))
        con.execute("DELETE FROM anime WHERE id=?", (anime_id,))
    flash("Anime deleted.", "success")
    return redirect(url_for("admin"))

@app.route("/api/anime")
def api_anime():
    with db() as con:
        rows = con.execute("""SELECT a.id,a.title,a.genre,a.year,a.language,a.description,a.poster,
        COUNT(e.id) AS episode_count FROM anime a LEFT JOIN episodes e ON e.anime_id=a.id
        GROUP BY a.id ORDER BY a.featured DESC,a.id DESC""").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/health")
def health():
    return jsonify({"status":"ok","app":"AniVerse Advanced"})

@app.errorhandler(404)
def not_found(_):
    return render_template("404.html"), 404

init_db()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("FLASK_DEBUG") == "1")
