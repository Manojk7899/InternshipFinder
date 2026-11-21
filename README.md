# Internship Radar

A free fresher internship finder for India and remote internships.

Internship Radar scans public Greenhouse, Lever, and Ashby listings every morning,
filters for fresher-friendly technical internships, and ranks them using:

- Rust
- HTML
- CSS
- JavaScript
- TypeScript and React
- Frontend, full-stack, Node.js, Git, REST APIs, and WebAssembly

No API keys or login are required.

## Run locally

```bash
pip install -r requirements.txt
python radar.py
streamlit run streamlit_app.py
```

## GitHub Actions

Enable workflow read/write permissions in **Settings → Actions → General**.
The workflow runs daily and updates `docs/jobs.json` and `docs/seen.json`.

## Features

- Fresher and internship-only filtering
- Minimum experience and seniority filtering
- Bangalore and Indian-location boosts
- Rust and frontend skill matching
- Search and company filters
- Application status tracker
- Static GitHub Pages fallback
- CSV tracker download and restore

This project only finds and tracks internships. It does not submit applications.
