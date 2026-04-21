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

        # AI evaluation at creation — store score for reference
        profile = data.get("profile", {})
        score, reason, bonus = evaluate_task_with_ai(task, profile)
        if score is not None:
            task["ai_score"]  = score
            task["ai_reason"] = reason

        data["active_tasks"].append(task)
        save_data(data)

    return redirect(url_for("index"))


@app.route("/preview", methods=["POST"])
def preview():
    """Score a task against the profile without saving it. Returns JSON."""
    from flask import jsonify
    data = load_data()
    profile = data.get("profile", {})

    name        = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    tags_text   = request.form.get("tags", "").strip()
    priority_raw = request.form.get("priority", "1")

    try:
        priority = int(priority_raw)
    except ValueError:
        priority = 1

    if not name:
        return jsonify({"error": "Task name is required"}), 400

    task = {
        "name": name,
        "description": description,
        "tags": parse_tags(tags_text),
        "priority": priority,
        "recurrence": "one_off",
    }

    score, reason, bonus = evaluate_task_with_ai(task, profile)

    if score is None:
        return jsonify({"error": "Could not evaluate — check your profile and AI settings"}), 500

    suggested_priority = 1 if score < 40 else 2 if score < 70 else 3

    return jsonify({
        "score": score,
        "reason": reason,
        "suggested_priority": suggested_priority,
        "suggested_priority_label": ["", "Low", "Medium", "High"][suggested_priority]
    })


def evaluate_task_with_ai(task, profile):
    """
    Calls the configured AI model to score a task against the user's profile.
    Returns (score, reason, bonus) or (None, None, None) on failure.
    """
    ai_model = profile.get("ai_model", "claude")
    likes    = profile.get("likes", [])
    values   = profile.get("values", [])
    believes = profile.get("believes", [])
    goals    = profile.get("goals", [])

    if not likes and not values and not believes and not goals:
        print("[AI] No profile content — skipping")
        return None, None, None

    def fmt(items, prefix):
        if not items: return "  (none set)"
        return "\n".join(f"  - {prefix} {s}" for s in items)

    prompt = f"""You are scoring a completed task against a person's personal profile made up of statements about what they like, value, believe, and want to achieve.

PROFILE
I like...
{fmt(likes, 'I like')}

I value...
{fmt(values, 'I value')}

I believe...
{fmt(believes, 'I believe')}

My goal is...
{fmt(goals, 'My goal is')}

COMPLETED TASK
Name: {task.get('name', '')}
Tags: {', '.join(task.get('tags', [])) or 'none'}
Recurrence: {task.get('recurrence', 'one_off').replace('_', ' ')}
Description: {task.get('description', '') or 'none'}

Score how well completing this task aligns with this person's profile.
Consider all four dimensions — their likes, values, beliefs, and goals.
Reply with a JSON object only — no markdown, no explanation outside the JSON.
Example: {{"score": 72, "reason": "Directly supports their goal of building a business that serves people first."}}
Your response: {{"score": <integer 1-100>, "reason": "<one concise sentence tying the task to a specific part of their profile>"}}"""

    try:
        raw = None

        if ai_model == "claude":
            import anthropic
            api_key = profile.get("api_key") or os.getenv("ANTHROPIC_API_KEY", "")
            if not api_key:
                print("[AI] Claude selected but no API key")
                return None, None, None
            client = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = msg.content[0].text.strip()

        elif ai_model == "openai":
            import openai
            api_key = profile.get("api_key") or os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                print("[AI] OpenAI selected but no API key")
                return None, None, None
            client = openai.OpenAI(api_key=api_key)
            msg = client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = msg.choices[0].message.content.strip()

        elif ai_model == "ollama":
            import urllib.request
            ollama_url   = profile.get("ollama_url", "http://localhost:11434").rstrip("/")
            ollama_model = profile.get("ollama_model", "").strip()
            if not ollama_model:
                print("[AI] Ollama selected but no model name set")
                return None, None, None
            print(f"[AI] Calling Ollama at {ollama_url} with model {ollama_model}")
            payload = json.dumps({
                "model": ollama_model,
                "prompt": prompt,
                "stream": False,
                "think": False
            }).encode()
            req = urllib.request.Request(
                f"{ollama_url}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = json.loads(resp.read())["response"].strip()

            # Strip <think>...</think> block if present (qwen3 thinking mode)
            if "</think>" in raw:
                raw = raw.split("</think>")[-1].strip()
        else:
            print(f"[AI] Unknown model: {ai_model}")
            return None, None, None

        print(f"[AI] Raw response: {raw[:200]}")

        # Strip <think>...</think> block if present (qwen3 thinking mode)
        if "</think>" in raw:
            raw = raw.split("</think>")[-1].strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        # Replace smart/curly quotes with straight quotes
        raw = raw.replace('\u201c', '"').replace('\u201d', '"')
        raw = raw.replace('\u2018', "'").replace('\u2019', "'")
        # Remove zero-width and non-breaking spaces
        raw = raw.replace('\u00a0', ' ').replace('\u200b', '').replace('\ufeff', '')

        # Extract just the JSON object if there's surrounding text
        import re
        json_match = re.search(r'\{[^{}]+\}', raw, re.DOTALL)
        if json_match:
            raw = json_match.group(0)

        print(f"[AI] Parsing: {repr(raw[:100])}")
        result = json.loads(raw)
        score  = max(1, min(100, int(result["score"])))
        reason = str(result["reason"])[:200]
        bonus  = round(score / 100 * 15)

        print(f"[AI] Score={score} Bonus={bonus} Reason={reason}")
        return score, reason, bonus

    except Exception as e:
        print(f"[AI] Error: {e}")
        return None, None, None


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

        # AI evaluation — synchronous
        profile = data.get("profile", {})
        print(f"[AI] Evaluating: {task.get('name')} | model={profile.get('ai_model')} | ollama_model={profile.get('ollama_model')}")
        score, reason, bonus = evaluate_task_with_ai(task, profile)

        if score is not None:
            data = load_data()
            if data["completed_tasks"] and data["completed_tasks"][0].get("name") == task.get("name"):
                data["completed_tasks"][0]["ai_score"]  = score
                data["completed_tasks"][0]["ai_reason"] = reason
                data["completed_tasks"][0]["ai_bonus"]  = bonus
                data["completed_tasks"][0]["earned_xp"] += bonus
                data["xp"]   += bonus
                data["level"] = data["xp"] // 50 + 1
                save_data(data)

    return redirect(url_for("index"))


@app.route("/evaluate_completed/<int:index>")
def evaluate_completed(index):
    """Manually trigger AI evaluation on an already-completed task."""
    data = load_data()
    profile = data.get("profile", {})

    if 0 <= index < len(data["completed_tasks"]):
        task = data["completed_tasks"][index]
        print(f"[AI] Manual evaluate: {task.get('name')}")
        score, reason, bonus = evaluate_task_with_ai(task, profile)

        if score is not None:
            old_bonus = task.get("ai_bonus", 0)
            task["ai_score"]  = score
            task["ai_reason"] = reason
            task["ai_bonus"]  = bonus
            task["earned_xp"] = task.get("earned_xp", 0) - old_bonus + bonus
            data["xp"]        = data["xp"] - old_bonus + bonus
            data["level"]     = data["xp"] // 50 + 1
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


@app.route("/portrait", methods=["POST"])
def portrait():
    from flask import jsonify
    data = load_data()
    prof = data.get("profile", {})

    likes    = prof.get("likes", [])
    values   = prof.get("values", [])
    believes = prof.get("believes", [])
    goals    = prof.get("goals", [])

    if not likes and not values and not believes and not goals:
        return jsonify({"error": "Add some statements first, then generate your portrait."}), 400

    def fmt(items, prefix):
        if not items: return "  (none set)"
        return "\n".join(f"  - {prefix} {s}" for s in items)

    prompt = f"""You are reading a person's self-described profile made up of short personal statements. Produce three things:

1. REFLECTION — 2 sentences in second person that mirror back what they've explicitly shared. Be specific — use their actual words and details. No generic language.

2. EVALUATION — 2 sentences in second person that assess what this combination of traits, values, and goals suggests about how they operate, make decisions, or prioritize. Go beyond what they said — interpret the pattern. What does this profile suggest about how they move through the world?

3. ASSUMPTIONS — 3 inferences this person did NOT explicitly state. Read between the lines. Frame tentatively: "You might...", "There's probably...", "It seems like...". Look for tensions, contradictions, or unspoken motivations. Make them genuinely interesting — not restatements of what they said.

STATEMENTS
I like...
{fmt(likes, 'I like')}

I value...
{fmt(values, 'I value')}

I believe...
{fmt(believes, 'I believe')}

My goal is...
{fmt(goals, 'My goal is')}

Reply with a JSON object only. No markdown, no explanation outside the JSON.
Format: {{"reflection": "2 sentence reflection.", "evaluation": "2 sentence evaluation.", "assumptions": ["assumption one", "assumption two", "assumption three"]}}"""

    try:
        ai_model = prof.get("ai_model", "claude")
        raw = None

        if ai_model == "claude":
            import anthropic
            api_key = prof.get("api_key") or os.getenv("ANTHROPIC_API_KEY", "")
            if not api_key:
                return jsonify({"error": "No Claude API key set — add one in the AI Evaluator section below."}), 400
            client = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = msg.content[0].text.strip()

        elif ai_model == "openai":
            import openai
            api_key = prof.get("api_key") or os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                return jsonify({"error": "No OpenAI API key set — add one in the AI Evaluator section below."}), 400
            client = openai.OpenAI(api_key=api_key)
            msg = client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = msg.choices[0].message.content.strip()

        elif ai_model == "ollama":
            import urllib.request
            ollama_url   = prof.get("ollama_url", "http://localhost:11434").rstrip("/")
            ollama_model = prof.get("ollama_model", "").strip()
            if not ollama_model:
                return jsonify({"error": "No Ollama model set — add one in the AI Evaluator section below."}), 400
            payload = json.dumps({"model": ollama_model, "prompt": prompt, "stream": False}).encode()
            req = urllib.request.Request(
                f"{ollama_url}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = json.loads(resp.read())["response"].strip()
            if "</think>" in raw:
                raw = raw.split("</think>")[-1].strip()

        else:
            return jsonify({"error": "Unknown AI model selected."}), 400

        if not raw:
            return jsonify({"error": "AI returned an empty response."}), 500

        # Parse JSON response
        import re
        raw_clean = raw.strip()
        if raw_clean.startswith("```"):
            raw_clean = raw_clean.split("```")[1]
            if raw_clean.startswith("json"):
                raw_clean = raw_clean[4:]
        raw_clean = raw_clean.strip()
        if "</think>" in raw_clean:
            raw_clean = raw_clean.split("</think>")[-1].strip()
        json_match = re.search(r'\{.*\}', raw_clean, re.DOTALL)
        if json_match:
            raw_clean = json_match.group(0)

        try:
            result = json.loads(raw_clean)
            reflection  = str(result.get("reflection", "")).strip()
            evaluation  = str(result.get("evaluation", "")).strip()
            assumptions = [str(a).strip() for a in result.get("assumptions", []) if str(a).strip()]
        except (json.JSONDecodeError, KeyError):
            # Fallback: treat raw as plain text in reflection
            reflection  = raw_clean
            evaluation  = ""
            assumptions = []

        if not reflection:
            return jsonify({"error": "AI returned an empty response."}), 500

        # Persist back to profile
        data["profile"]["reflection"]  = reflection
        data["profile"]["evaluation"]  = evaluation
        data["profile"]["assumptions"] = assumptions
        save_data(data)

        return jsonify({"reflection": reflection, "evaluation": evaluation, "assumptions": assumptions})

    except Exception as e:
        print(f"[Portrait] Error: {e}")
        return jsonify({"error": "Could not generate portrait — check your API key and try again."}), 500


@app.route("/profile", methods=["GET", "POST"])
def profile():
    data = load_data()
    saved = False

    if request.method == "POST":
        def get_statements(key):
            return [s.strip() for s in request.form.getlist(key) if s.strip()]

        ai_model = request.form.get("ai_model", "claude")
        if ai_model not in ["claude", "openai", "ollama"]:
            ai_model = "claude"

        data["profile"] = {
            "likes":    get_statements("likes[]"),
            "values":   get_statements("values[]"),
            "believes": get_statements("believes[]"),
            "goals":    get_statements("goals[]"),
            "ai_model":     ai_model,
            "api_key":      request.form.get("api_key", "").strip(),
            "ollama_url":   request.form.get("ollama_url", "http://localhost:11434").strip(),
            "ollama_model": request.form.get("ollama_model", "").strip(),
        }
        save_data(data)
        saved = True

    prof = data.get("profile", {})
    return render_template(
        "profile.html",
        profile={
            "likes":    prof.get("likes", []),
            "values":   prof.get("values", []),
            "believes": prof.get("believes", []),
            "goals":    prof.get("goals", []),
            "ai_model":     prof.get("ai_model", "claude"),
            "api_key":      prof.get("api_key", ""),
            "ollama_url":   prof.get("ollama_url", "http://localhost:11434"),
            "ollama_model": prof.get("ollama_model", ""),
            "reflection":   prof.get("reflection", ""),
            "evaluation":   prof.get("evaluation", ""),
            "assumptions":  prof.get("assumptions", []),
        },
        saved=saved
    )


if __name__ == "__main__":
    app.run(debug=True)