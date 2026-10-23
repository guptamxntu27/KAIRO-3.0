# KAIRO — Advanced Anime Discovery & Streaming Starter

A responsive Flask + SQLite web application with a distinctive ink-blue / mint / tangerine visual identity. Includes a discovery homepage, search and genre filters, anime detail/watch pages, episode selection, account registration/login, watch history, and an admin dashboard.

## Run locally
Requires Python 3.10+.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open `http://127.0.0.1:5000`.

## Demo admin login
- Username: `admin`
- Password: `ChangeMe123!`

Change these credentials before deployment. Set environment variables: `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `SECRET_KEY` (long random value), and `PORT` (if required by your host).

## Features
- Original KAIRO design system: ink blue, mint teal and tangerine accents
- Editorial hero banner, responsive anime catalogue and genre discovery
- Search by title and genre filters
- HTML5 video player with selectable episodes
- Signup/login with hashed passwords
- Continue-watching history for signed-in users
- Admin-only anime and episode management
- SQLite database created automatically
- `GET /api/anime` JSON catalogue endpoint and `GET /health` health endpoint
- Gunicorn deployment entrypoint via `Procfile`

## Deploy online
This is a starter application, not a hosted streaming server. To obtain a public URL, deploy it to a Python hosting provider or VPS. The start command is `gunicorn app:app`. Configure HTTPS and persistent storage for `aniverse.db` and `static/uploads`. For a production launch, review CSRF protection, rate limiting, backups, logging, account security and database/storage choices.

## Important streaming note
The included entries use sample/test clips; they are not anime episodes. Add video URLs you own or have permission to distribute. Do not scrape, rehost, or distribute copyrighted anime without authorization. This project does not include a licensed anime catalogue, DRM, or a third-party streaming subscription.

## Multi-server episode player
The watch page includes SUB, DUB, and HSUB server groups with ENMA-1 through ENMA-5 selectors. To configure different streams for an episode, enter a JSON object in the optional **server URLs** field when adding an anime/episode in the admin panel. Example:

```json
{
  "SUB": {"ENMA-1": "https://your-authorized-host/sub-1.m3u8", "ENMA-2": "https://your-authorized-host/sub-2.mp4"},
  "DUB": {"ENMA-1": "https://your-authorized-host/dub-1.mp4"},
  "HSUB": {"ENMA-1": "https://your-authorized-host/hsub-1.mp4"}
}
```

Use only video streams you own or are licensed to distribute. Any server without a configured URL uses the episode's default video URL and is marked accordingly in the player status.
