# Deploying Parchi to PythonAnywhere

This guide walks through pushing Parchi to GitHub and then deploying it on PythonAnywhere from scratch. Follow it top to bottom on first deploy; skip to **Updating after the first deploy** for every deploy after that.

---

## 0. Before you start

You'll need:
- A GitHub account and a new (empty) repository to hold this code.
- A PythonAnywhere account (a free "Beginner" account is enough to start).
- This project working locally (it already is).

---

## 1. Push the code to GitHub

Run these from the project root on your own machine:

```bash
git init
git add .
git commit -m "Initial commit: Parchi inventory + billing app"
```

Create a new empty repository on GitHub (via the website, or `gh repo create parchi --private --source=. --remote=origin`), then:

```bash
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

> `venv/`, `db.sqlite3`, `media/`, `staticfiles/`, and `.env` are already excluded via `.gitignore` — don't remove those entries, they contain your local secrets/DB and don't belong in git.

---

## 2. Create the PythonAnywhere web app

1. Log in to [www.pythonanywhere.com](https://www.pythonanywhere.com) and open a **Bash console** (Dashboard → New console → Bash).
2. Clone your repo:
   ```bash
   git clone https://github.com/<your-username>/<your-repo>.git parchi
   cd parchi
   ```
3. Create a virtualenv (PythonAnywhere ships several Python versions — pick 3.10+):
   ```bash
   mkvirtualenv --python=/usr/bin/python3.10 parchi-venv
   pip install -r requirements.txt
   ```
   (`mkvirtualenv` activates it automatically. If you open a new console later, reactivate with `workon parchi-venv`.)

4. Go to the **Web** tab → **Add a new web app** → choose **Manual configuration** (not the Django wizard) → pick the same Python version as your virtualenv.

---

## 3. Configure environment variables

Still on the **Web** tab, scroll to **Environment variables** and add:

| Name | Value |
|---|---|
| `DJANGO_SECRET_KEY` | a long random string — generate one with `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_ALLOWED_HOSTS` | `<your-username>.pythonanywhere.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://<your-username>.pythonanywhere.com` |

These map directly to the `os.environ.get(...)` calls in `parchi/settings.py` — no code changes needed.

---

## 4. Point PythonAnywhere at the virtualenv and the code

On the **Web** tab:
- **Virtualenv** section → enter: `/home/<your-username>/.virtualenvs/parchi-venv`
- **Code** section → **Source code**: `/home/<your-username>/parchi`
- **Working directory**: `/home/<your-username>/parchi`

### Edit the WSGI file

Click the WSGI configuration file link (something like `/var/www/<your-username>_pythonanywhere_com_wsgi.py`), delete its contents, and replace with:

```python
import sys
import os

path = '/home/<your-username>/parchi'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'parchi.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

Replace `<your-username>` in both places above with your actual PythonAnywhere username.

---

## 5. Static and media files

Still on the **Web** tab, under **Static files**, add two mappings:

| URL | Directory |
|---|---|
| `/static/` | `/home/<your-username>/parchi/staticfiles` |
| `/media/` | `/home/<your-username>/parchi/media` |

This lets PythonAnywhere's front end serve CSS/JS and bill PDFs directly, without going through Django — faster, and required for the public (unauthenticated) bill-PDF links to work smoothly.

---

## 6. Run migrations and collect static files

Back in the Bash console (with the virtualenv active — `workon parchi-venv` if needed):

```bash
cd ~/parchi
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

The superuser account you create here is your **platform admin** login — use it to sign in and reach the in-app dashboard at `/accounts/superadmin/` to see all businesses and impersonate an owner for support.

---

## 7. Go live

Back on the **Web** tab, click the big green **Reload** button.

Visit `https://<your-username>.pythonanywhere.com/` — you should land on the product list, which redirects to login/signup since nothing's created yet. Sign up a test business and run through: add a product → create a bill → download the PDF → open the WhatsApp link, to confirm everything works on the real domain (some things, like the `wa.me` link opening WhatsApp, are only truly testable from a phone).

---

## 8. A few things specific to PythonAnywhere

- **Database**: this guide keeps SQLite (fine for one or a handful of small businesses). If you outgrow it, PythonAnywhere gives you a free/paid MySQL database — only the `DATABASES` block in `parchi/settings.py` needs to change; none of the app code does.
- **No background workers**: PDF generation happens synchronously when a bill is created — there's nothing here that needs Celery or a queue, which matters because PythonAnywhere's free tier doesn't support long-running background processes.
- **Free tier outbound restrictions**: the WhatsApp integration is just a `wa.me` link opened on the customer's own phone — Parchi's server never makes an outbound call to WhatsApp, so this isn't affected by PythonAnywhere's free-tier allowlist.
- **HTTPS**: PythonAnywhere serves your app over HTTPS by default (`https://<username>.pythonanywhere.com`) — that's why `DJANGO_CSRF_TRUSTED_ORIGINS` above uses `https://`.
- **Disk space**: bill PDFs accumulate in `media/bills/`. The free tier has limited disk space; if you approach the limit, it's safe to delete old PDFs for bills that have already been sent (`Bill.objects.filter(created_at__lt=some_date)` in a Django shell) — the bill records themselves stay intact, only the stored PDF file goes.

---

## Updating after the first deploy

Every time you push new changes to GitHub, redeploy with:

```bash
cd ~/parchi
git pull
workon parchi-venv
pip install -r requirements.txt   # only needed if requirements.txt changed
python manage.py migrate           # only needed if there are new migrations
python manage.py collectstatic --noinput
```

Then go to the **Web** tab and click **Reload** again.
