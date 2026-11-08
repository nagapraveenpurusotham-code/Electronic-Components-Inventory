from datetime import date, datetime, timedelta
from pathlib import Path
import sqlite3
import os

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "inventory.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-before-production")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, values=(), one=False):
    cursor = get_db().execute(sql, values)
    rows = cursor.fetchall()
    cursor.close()
    return (rows[0] if rows else None) if one else rows


@app.before_request
def require_login():
    """Keep the tracker private, except for account and static-file pages."""
    if request.endpoint not in {"login", "register", "static"} and "user_id" not in session:
        return redirect(url_for("login"))


@app.context_processor
def inject_current_user():
    return {"logged_in_user": session.get("username")}


def init_db():
    db = sqlite3.connect(DATABASE)
    db.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS components (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_number TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0),
            location TEXT,
            supplier TEXT,
            min_stock INTEGER NOT NULL DEFAULT 0 CHECK(min_stock >= 0),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            component_id INTEGER NOT NULL,
            movement_type TEXT NOT NULL CHECK(movement_type IN ('IN', 'OUT')),
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            note TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(component_id) REFERENCES components(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_tag TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            category TEXT,
            location TEXT,
            status TEXT NOT NULL DEFAULT 'Active',
            next_service_date TEXT,
            service_interval_days INTEGER NOT NULL DEFAULT 90,
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS service_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            service_date TEXT NOT NULL,
            technician TEXT,
            description TEXT NOT NULL,
            cost REAL,
            FOREIGN KEY(asset_id) REFERENCES assets(id) ON DELETE CASCADE
        );
        """
    )
    count = db.execute("SELECT COUNT(*) FROM components").fetchone()[0]
    if count == 0:
        db.executemany(
            "INSERT INTO components (part_number, name, category, quantity, location, supplier, min_stock) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("RES-10K-1/4W", "10k Ohm Resistor", "Resistors", 240, "Bin A1", "ElectroHub", 100),
                ("CAP-100UF-25V", "100uF Electrolytic Capacitor", "Capacitors", 8, "Bin B3", "Circuit Supply", 20),
                ("IC-NE555P", "NE555 Timer IC", "Integrated Circuits", 36, "Drawer C2", "ElectroHub", 10),
            ],
        )
        db.executemany(
            "INSERT INTO assets (asset_tag, name, category, location, status, next_service_date, service_interval_days, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("EQ-001", "Soldering Station", "Workshop tool", "Bench 1", "Active", (date.today() + timedelta(days=7)).isoformat(), 90, "Clean tip and inspect power cord."),
                ("EQ-002", "Digital Oscilloscope", "Test equipment", "Lab shelf", "Active", (date.today() - timedelta(days=3)).isoformat(), 180, "Check calibration."),
            ],
        )
    db.commit()
    db.close()


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = query("SELECT * FROM users WHERE username = ?", (username,), one=True)
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for("dashboard"))
        flash("Incorrect username or password.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        try:
            if len(username) < 3 or len(password) < 6:
                raise ValueError("Use a username of at least 3 characters and a password of at least 6 characters.")
            if password != request.form.get("confirm_password", ""):
                raise ValueError("The passwords do not match.")
            db = get_db()
            db.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, generate_password_hash(password)))
            db.commit()
            flash("Account created. Please sign in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("That username is already in use.", "error")
        except ValueError as error:
            flash(str(error), "error")
    return render_template("register.html")


@app.post("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("login"))


@app.route("/")
def dashboard():
    today = date.today().isoformat()
    soon = (date.today() + timedelta(days=14)).isoformat()
    stats = {
        "components": query("SELECT COUNT(*) AS n FROM components", one=True)["n"],
        "units": query("SELECT COALESCE(SUM(quantity), 0) AS n FROM components", one=True)["n"],
        "low_stock": query("SELECT COUNT(*) AS n FROM components WHERE quantity <= min_stock", one=True)["n"],
        "due_service": query("SELECT COUNT(*) AS n FROM assets WHERE next_service_date IS NOT NULL AND next_service_date <= ?", (soon,), one=True)["n"],
    }
    low_stock = query("SELECT * FROM components WHERE quantity <= min_stock ORDER BY quantity ASC LIMIT 5")
    services = query("SELECT * FROM assets WHERE next_service_date IS NOT NULL AND next_service_date <= ? ORDER BY next_service_date", (soon,))
    recent = query("""SELECT t.*, c.part_number, c.name FROM transactions t
                    JOIN components c ON c.id=t.component_id ORDER BY t.created_at DESC LIMIT 6""")
    return render_template("dashboard.html", stats=stats, low_stock=low_stock, services=services, recent=recent, today=today)


@app.route("/components", methods=["GET", "POST"])
def components():
    if request.method == "POST":
        fields = [request.form.get(k, "").strip() for k in ("part_number", "name", "category", "location", "supplier")]
        try:
            quantity, min_stock = int(request.form["quantity"]), int(request.form["min_stock"])
            if not all(fields[:3]) or quantity < 0 or min_stock < 0:
                raise ValueError
            get_db().execute("""INSERT INTO components (part_number, name, category, quantity, location, supplier, min_stock)
                             VALUES (?, ?, ?, ?, ?, ?, ?)""", (*fields[:3], quantity, *fields[3:], min_stock))
            get_db().commit()
            flash("Component saved.", "success")
        except (ValueError, sqlite3.IntegrityError):
            flash("Use a unique part number and valid non-negative quantities.", "error")
        return redirect(url_for("components"))
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    sql, params = "SELECT * FROM components WHERE 1=1", []
    if search:
        sql += " AND (part_number LIKE ? OR name LIKE ? OR supplier LIKE ? OR location LIKE ?)"
        params += [f"%{search}%"] * 4
    if category:
        sql += " AND category = ?"
        params.append(category)
    sql += " ORDER BY name"
    return render_template("components.html", components=query(sql, params), categories=query("SELECT DISTINCT category FROM components ORDER BY category"), search=search, selected_category=category)


@app.post("/components/<int:component_id>/transaction")
def add_transaction(component_id):
    component = query("SELECT * FROM components WHERE id=?", (component_id,), one=True)
    if not component:
        flash("Component not found.", "error")
        return redirect(url_for("components"))
    try:
        quantity = int(request.form["quantity"])
        movement = request.form["movement_type"]
        if quantity <= 0 or movement not in ("IN", "OUT"):
            raise ValueError
        if movement == "OUT" and quantity > component["quantity"]:
            flash("Stock-out quantity is greater than available stock.", "error")
            return redirect(url_for("components"))
        change = quantity if movement == "IN" else -quantity
        db = get_db()
        db.execute("UPDATE components SET quantity = quantity + ? WHERE id=?", (change, component_id))
        db.execute("INSERT INTO transactions (component_id, movement_type, quantity, note) VALUES (?, ?, ?, ?)", (component_id, movement, quantity, request.form.get("note", "").strip()))
        db.commit()
        flash("Stock movement recorded.", "success")
    except ValueError:
        flash("Enter a positive whole number.", "error")
    return redirect(url_for("components"))


@app.post("/components/<int:component_id>/delete")
def delete_component(component_id):
    component = query("SELECT name FROM components WHERE id=?", (component_id,), one=True)
    if not component:
        flash("Component not found.", "error")
    else:
        db = get_db()
        db.execute("DELETE FROM components WHERE id=?", (component_id,))
        db.commit()
        flash(f"{component['name']} and its stock history were deleted.", "success")
    return redirect(url_for("components"))


@app.route("/assets", methods=["GET", "POST"])
def assets():
    if request.method == "POST":
        try:
            interval = int(request.form["service_interval_days"])
            if not request.form["asset_tag"].strip() or not request.form["name"].strip() or interval < 1:
                raise ValueError
            get_db().execute("""INSERT INTO assets (asset_tag,name,category,location,status,next_service_date,service_interval_days,notes)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (request.form["asset_tag"].strip(), request.form["name"].strip(), request.form.get("category", "").strip(), request.form.get("location", "").strip(), request.form.get("status", "Active"), request.form.get("next_service_date") or None, interval, request.form.get("notes", "").strip()))
            get_db().commit(); flash("Equipment saved.", "success")
        except (ValueError, sqlite3.IntegrityError):
            flash("Use a unique asset tag and a service interval of at least one day.", "error")
        return redirect(url_for("assets"))
    return render_template("assets.html", assets=query("SELECT * FROM assets ORDER BY name"), today=date.today().isoformat())


@app.post("/assets/<int:asset_id>/service")
def record_service(asset_id):
    asset = query("SELECT * FROM assets WHERE id=?", (asset_id,), one=True)
    if not asset:
        flash("Equipment not found.", "error")
        return redirect(url_for("assets"))
    service_date = request.form.get("service_date") or date.today().isoformat()
    try:
        cost = float(request.form["cost"]) if request.form.get("cost") else None
        description = request.form["description"].strip()
        if not description:
            raise ValueError
        next_date = (datetime.strptime(service_date, "%Y-%m-%d").date() + timedelta(days=asset["service_interval_days"])).isoformat()
        db = get_db()
        db.execute("INSERT INTO service_history (asset_id,service_date,technician,description,cost) VALUES (?, ?, ?, ?, ?)", (asset_id, service_date, request.form.get("technician", "").strip(), description, cost))
        db.execute("UPDATE assets SET next_service_date=? WHERE id=?", (next_date, asset_id))
        db.commit(); flash("Service history saved and next date updated.", "success")
    except ValueError:
        flash("Add a description and use a valid cost.", "error")
    return redirect(url_for("assets"))


@app.get("/assets/<int:asset_id>/history")
def history(asset_id):
    asset = query("SELECT * FROM assets WHERE id=?", (asset_id,), one=True)
    if not asset:
        return redirect(url_for("assets"))
    return render_template("history.html", asset=asset, history=query("SELECT * FROM service_history WHERE asset_id=? ORDER BY service_date DESC", (asset_id,)))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
