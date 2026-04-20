from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime, timedelta
import json
import os
import calendar
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, template_folder="templates")

DATA_FILE = "tasks_data.json"

DEFAULT_DATA = {
    "active_tasks": [],
    "completed_tasks": [],
    "archived_tasks": [],
    "xp": 0,
    "level": 1
}


def load_data():
    if not os.path.exists(DATA_FILE):
        save_data(DEFAULT_DATA)
        return json.loads(json.dumps(DEFAULT_DATA))

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        return {
            "active_tasks": data.get("active_tasks", []),
            "completed_tasks": data.get("completed_tasks", []),
            "archived_tasks": data.get("archived_tasks", []),
            "xp": data.get("xp", 0),
            "level": data.get("level", 1),
            "profile": data.get("profile", {}),
        }
    except (json.JSONDecodeError, OSError):
        save_data(DEFAULT_DATA)
        return json.loads(json.dumps(DEFAULT_DATA))


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def xp_for_priority(priority):
    return {1: 5, 2: 10, 3: 15}.get(priority, 0)


def current_dt():
    return datetime.now()


def format_timestamp(dt):
    return dt.strftime("%Y-%m-%d %I:%M %p")


def current_timestamp():
    return format_timestamp(current_dt())


def current_date_string():
    return current_dt().strftime("%Y-%m-%d")


def calculate_daily_xp(completed_tasks):
    today = current_date_string()
    total = 0

    for task in completed_tasks:
        completed_at = task.get("completed_at", "")
        earned_xp = task.get("earned_xp", 0)

        if completed_at.startswith(today):
            total += earned_xp

    return total


def start_of_day(dt):
    return datetime(dt.year, dt.month, dt.day)


def get_completed_this_week_summary(completed_tasks):
    now = current_dt()
    today_start = start_of_day(now)
    week_start = today_start - timedelta(days=6)

    summary = {}

    # Prefill all 7 days so empty days still appear.
    for i in range(7):
        day_dt = week_start + timedelta(days=i)
        day_key = day_dt.strftime("%Y-%m-%d")
        summary[day_key] = {
            "label": day_dt.strftime("%A, %b %d"),
            "count": 0,
            "xp": 0,
            "tasks": []
        }

    for task in completed_tasks:
        completed_at = task.get("completed_at", "")
        completed_dt = parse_datetime_safe(completed_at)
        if not completed_dt:
            continue

        completed_day = start_of_day(completed_dt)
        if completed_day < week_start or completed_day > today_start:
            continue

        day_key = completed_day.strftime("%Y-%m-%d")
        summary[day_key]["count"] += 1
        summary[day_key]["xp"] += task.get("earned_xp", 0)
        summary[day_key]["tasks"].append(task.get("name", "Untitled task"))

    ordered_keys = sorted(summary.keys(), reverse=True)
    return [(key, summary[key]) for key in ordered_keys]


def parse_tags(tags_text):
    if not tags_text:
        return []

    tags = []
    for tag in tags_text.split(","):
        cleaned = tag.strip()
        if cleaned and cleaned.lower() not in [t.lower() for t in tags]:
            tags.append(cleaned)

    return tags


def tags_to_text(tags):
    if not tags:
        return ""
    return ", ".join(tags)


def normalize_tasks(data):
    for section in ["active_tasks", "completed_tasks", "archived_tasks"]:
        for task in data.get(section, []):
            if "tags" not in task:
                task["tags"] = []
            if "recurrence" not in task:
                task["recurrence"] = "one_off"


def filter_tasks(tasks, query):
    if not query:
        return tasks

    query = query.lower().strip()
    words = query.split()

    filtered = []

    for task in tasks:
        name = task.get("name", "").lower()
        description = task.get("description", "").lower()
        tags = [t.lower() for t in task.get("tags", [])]
        recurrence = task.get("recurrence", "").lower()

        searchable_text = f"{name} {description} {' '.join(tags)} {recurrence}"

        if all(word in searchable_text for word in words):
            filtered.append(task)

    return filtered


def parse_recurrence(value):
    allowed = ["one_off", "daily", "weekly", "bi_weekly", "monthly"]
    if value in allowed:
        return value
    return "one_off"


def recurrence_label(value):
    labels = {
        "one_off": "One-off",
        "daily": "Daily",
        "weekly": "Weekly",
        "bi_weekly": "Bi-weekly",
        "monthly": "Monthly"
    }
    return labels.get(value, "One-off")


def add_one_month(dt):
    year = dt.year
    month = dt.month + 1

    if month > 12:
        month = 1
        year += 1

    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def next_due_datetime(recurrence, base_dt=None):
    if base_dt is None:
        base_dt = current_dt()

    recurrence = parse_recurrence(recurrence)

    if recurrence == "daily":
        return base_dt + timedelta(days=1)
    if recurrence == "weekly":
        return base_dt + timedelta(days=7)
    if recurrence == "bi_weekly":
        return base_dt + timedelta(days=14)
    if recurrence == "monthly":
        return add_one_month(base_dt)

    return None


def create_recurring_copy(task, completed_dt):
    recurrence = parse_recurrence(task.get("recurrence", "one_off"))
    if recurrence == "one_off":
        return None

    next_due = next_due_datetime(recurrence, completed_dt)

    recurring_task = {
        "name": task.get("name", ""),
        "description": task.get("description", ""),
        "tags": list(task.get("tags", [])),
        "priority": task.get("priority", 1),
        "recurrence": recurrence,
        "created_at": format_timestamp(completed_dt),
    }

    if next_due:
        recurring_task["next_due_at"] = format_timestamp(next_due)

    return recurring_task


def parse_datetime_safe(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d %I:%M %p")
    except (TypeError, ValueError):
        return None


def sort_tasks(tasks):
    def task_sort_key(task):
        recurrence = task.get("recurrence", "one_off")
        priority_order = -task.get("priority", 1)  # negate so high (3) sorts first

        if recurrence == "one_off":
            return (0, 0, priority_order)

        next_due_str = task.get("next_due_at")

        if next_due_str:
            dt = parse_datetime_safe(next_due_str)
            if dt:
                return (1, dt.timestamp(), priority_order)

        return (2, float("inf"), priority_order)

    return sorted(tasks, key=task_sort_key)


def is_due_today(task):
    next_due = task.get("next_due_at")

    if not next_due:
        return True

    dt = parse_datetime_safe(next_due)
    if not dt:
        return False

    return dt.date() <= current_dt().date()


@app.route("/")
def index():
    data = load_data()
    normalize_tasks(data)

    search_query = request.args.get("q", "").strip()
    daily_xp = calculate_daily_xp(data["completed_tasks"])
    weekly_completed = get_completed_this_week_summary(data["completed_tasks"])

    indexed_active_tasks = [
        {**task, "_index": i}
        for i, task in enumerate(data["active_tasks"])
    ]

    filtered_active = filter_tasks(indexed_active_tasks, search_query)
    filtered_active = sort_tasks(filtered_active)

    today_tasks = []
    later_tasks = []

    for task in filtered_active:
        if is_due_today(task):
            today_tasks.append(task)
        else:
            later_tasks.append(task)

    filtered_completed = filter_tasks(data["completed_tasks"], search_query)
    filtered_archived = filter_tasks(data["archived_tasks"], search_query)

    return render_template(
        "index.html",
        today_tasks=today_tasks,
        later_tasks=later_tasks,
        completed_tasks=filtered_completed,
        archived_tasks=filtered_archived,
        weekly_completed=weekly_completed,
        xp=data["xp"],
        daily_xp=daily_xp,
        level=data["level"],
        search_query=search_query,
        recurrence_label=recurrence_label
    )


@app.route("/add", methods=["POST"])
def add():
    data = load_data()
    normalize_tasks(data)

    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    tags_text = request.form.get("tags", "").strip()
    recurrence = parse_recurrence(request.form.get("recurrence", "one_off"))
    priority_raw = request.form.get("priority", "1")

    try:
        priority = int(priority_raw)
    except ValueError:
        priority = 1

    if priority not in [1, 2, 3]:
        priority = 1

    if name:
        task = {
            "name": name,
            "description": description,
            "tags": parse_tags(tags_text),
            "priority": priority,
            "recurrence": recurrence,
            "created_at": current_timestamp()
        }

        next_due = next_due_datetime(recurrence)
        if next_due:
            task["next_due_at"] = format_timestamp(next_due)

        data["active_tasks"].append(task)
        save_data(data)

    return redirect(url_for("index"))


@app.route("/complete/<int:index>")
def complete(index):
    data = load_data()
    normalize_tasks(data)

    if 0 <= index < len(data["active_tasks"]):
        task = data["active_tasks"].pop(index)
        earned = xp_for_priority(task["priority"])
        data["xp"] += earned

        new_level = data["xp"] // 50 + 1
        if new_level > data["level"]:
            data["level"] = new_level

        completed_dt = current_dt()

        task["completed_at"] = format_timestamp(completed_dt)
        task["earned_xp"] = earned
        data["completed_tasks"].insert(0, task)

        recurring_copy = create_recurring_copy(task, completed_dt)
        if recurring_copy:
            data["active_tasks"].insert(0, recurring_copy)

        save_data(data)

    return redirect(url_for("index"))


@app.route("/delete/<int:index>")
def delete(index):
    data = load_data()
    normalize_tasks(data)

    if 0 <= index < len(data["active_tasks"]):
        data["active_tasks"].pop(index)
        save_data(data)

    return redirect(url_for("index"))


@app.route("/edit/<int:index>", methods=["GET", "POST"])
def edit(index):
    data = load_data()
    normalize_tasks(data)

    if not (0 <= index < len(data["active_tasks"])):
        return redirect(url_for("index"))

    task = data["active_tasks"][index]

    if request.method == "POST":
        new_name = request.form.get("name", "").strip()
        new_description = request.form.get("description", "").strip()
        new_tags_text = request.form.get("tags", "").strip()
        new_recurrence = parse_recurrence(request.form.get("recurrence", "one_off"))
        priority_raw = request.form.get("priority", "1")

        try:
            new_priority = int(priority_raw)
        except ValueError:
            new_priority = 1

        if new_priority not in [1, 2, 3]:
            new_priority = 1

        if new_name:
            task["name"] = new_name
            task["description"] = new_description
            task["tags"] = parse_tags(new_tags_text)
            task["priority"] = new_priority
            task["recurrence"] = new_recurrence

            next_due = next_due_datetime(new_recurrence)
            if next_due:
                task["next_due_at"] = format_timestamp(next_due)
            else:
                task.pop("next_due_at", None)

            save_data(data)

        return redirect(url_for("index"))

    task_for_template = dict(task)
    task_for_template["tags_text"] = tags_to_text(task.get("tags", []))

    return render_template(
        "edit.html",
        task=task_for_template,
        index=index
    )


@app.route("/archive_completed/<int:index>")
def archive_completed(index):
    data = load_data()
    normalize_tasks(data)

    if 0 <= index < len(data["completed_tasks"]):
        task = data["completed_tasks"].pop(index)
        task["archived_at"] = current_timestamp()
        data["archived_tasks"].insert(0, task)
        save_data(data)

    return redirect(url_for("index"))


@app.route("/restore_archived/<int:index>")
def restore_archived(index):
    data = load_data()
    normalize_tasks(data)

    if 0 <= index < len(data["archived_tasks"]):
        task = data["archived_tasks"].pop(index)
        task.pop("archived_at", None)
        data["active_tasks"].insert(0, task)
        save_data(data)

    return redirect(url_for("index"))


@app.route("/delete_completed/<int:index>")
def delete_completed(index):
    data = load_data()
    normalize_tasks(data)

    if 0 <= index < len(data["completed_tasks"]):
        data["completed_tasks"].pop(index)
        save_data(data)

    return redirect(url_for("index"))


@app.route("/delete_archived/<int:index>")
def delete_archived(index):
    data = load_data()
    normalize_tasks(data)

    if 0 <= index < len(data["archived_tasks"]):
        data["archived_tasks"].pop(index)
        save_data(data)

    return redirect(url_for("index"))


@app.route("/profile", methods=["GET", "POST"])
def profile():
    data = load_data()
    saved = False

    if request.method == "POST":
        mission = request.form.get("mission", "").strip()[:300]
        values_raw = request.form.get("values", "").strip()
        values = [v.strip().lower() for v in values_raw.split(",") if v.strip()]
        goals = [g.strip() for g in request.form.getlist("goals[]") if g.strip()]
        ai_model = request.form.get("ai_model", "claude")
        if ai_model not in ["claude", "openai", "ollama"]:
            ai_model = "claude"
        api_key = request.form.get("api_key", "").strip()
        ollama_url = request.form.get("ollama_url", "http://localhost:11434").strip()
        ollama_model = request.form.get("ollama_model", "").strip()

        data["profile"] = {
            "mission": mission,
            "user_values": values,
            "goals": goals,
            "ai_model": ai_model,
            "api_key": api_key,
            "ollama_url": ollama_url,
            "ollama_model": ollama_model,
        }
        save_data(data)
        saved = True

    prof = data.get("profile", {})
    return render_template(
        "profile.html",
        profile={
            "mission": prof.get("mission", ""),
            "user_values": prof.get("user_values", prof.get("values", [])),
            "goals": prof.get("goals", []),
            "ai_model": prof.get("ai_model", "claude"),
            "api_key": prof.get("api_key", ""),
            "ollama_url": prof.get("ollama_url", "http://localhost:11434"),
            "ollama_model": prof.get("ollama_model", ""),
        },
        saved=saved
    )


if __name__ == "__main__":
    app.run(debug=True)