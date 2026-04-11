# ⚔️ Sidequests

### *Living is the Main Quest.*

A gamified to-do list built on a simple idea: your life — the people, the experiences, the moments — that's the main quest. Everything else? Sidequests. Complete them, earn XP, level up, and get back to living.

---

## Why I Built This

I'm not a full-time developer. I'm a maker, a podcaster, a dad, a hobbyist — and I wanted a to-do list that actually felt like *me*. So I built one.

This is a **vibe-coded MVP** — meaning I had an idea, I sat down with AI as my pair programmer, and I shipped something real. It's not perfect. It's not polished. But it works, I use it every day, and it's mine.

That's the whole point.

---

## The Philosophy

> **Imagine → Make → Repeat**

This project lives inside that loop. It started as a sketch, became a working app, and will keep evolving. If you want to follow along, I write about it at [imaginemakerepeat.com](https://imaginemakerepeat.com).

---

## What It Does

- ✅ Add tasks with priority, tags, and recurrence
- ⚔️ Complete tasks to earn XP and level up
- 🔥 See what's due **Today** vs **Later**
- 📅 Weekly completion summary
- 🔁 Recurring tasks (daily, bi-weekly, monthly) auto-regenerate
- 🔍 Full-text search across tasks, tags, and descriptions
- 📦 Archive and restore completed tasks

---

## Stack

No framework. No database. No cloud. Just:

- **Flask** — Python micro web framework
- **Vanilla HTML/CSS** — zero dependencies on the frontend
- **JSON flat file** — your data lives locally, in a single file you can read with your eyes

If you can run Python, you can run this.

---

## Get It Running

```bash
# Clone it
git clone https://github.com/YOUR_USERNAME/sidequests.git
cd sidequests

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install the one dependency
pip install -r requirements.txt

# Set up your data file
cp tasks_data.example.json tasks_data.json

# Launch
python app.py
```

Open [http://localhost:5000](http://localhost:5000) and start your first sidequest.

---

## Project Structure

```
sidequests/
├── app.py                    # All the logic
├── requirements.txt          # Just Flask
├── tasks_data.example.json   # Blank slate to get started
├── tasks_data.json           # Your quests (gitignored — stays on your machine)
└── templates/
    ├── index.html            # The quest board
    └── edit.html             # Edit a quest
```

---

## Roadmap (aka Future Sidequests)

- [ ] AI-assisted XP scoring based on your personal values
- [ ] Mobile-friendly UI
- [ ] Query (my AI character) as in-app quest advisor
- [ ] Raspberry Pi kiosk / always-on quest board
- [ ] Multi-user party mode

---

## This Is a Prototype

And that's okay. Vibe-coded, intentionally scoped, built to be used and improved. If you fork it, break it, or build something better — that's the spirit.

---

## License

MIT — take it, remix it, make it yours.