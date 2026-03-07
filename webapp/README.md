# Clean Slate PA — Web App

A mobile-first web tool that helps formerly incarcerated people in Pennsylvania check if their record may qualify for sealing or expungement under the Clean Slate Act (as expanded by Act 36 of 2023).

Built for the NYU Tandon hackathon in partnership with [Free Our Vote](https://freeourvote.org).

---

## How it works

1. User enters name + date of birth
2. App searches Pennsylvania UJS public court records via `pa-record-retriever`
3. User confirms their cases (name ambiguity screen if multiple people match)
4. User answers one restitution question
5. App applies Clean Slate eligibility rules and shows plain-language results

---

## Run locally (for events / laptop use)

**Requirements:** Python 3.11+, `uv` or `pip`

```bash
# From the repo root
pip install -r webapp/requirements.txt

# Start the server
uvicorn webapp.main:app --reload

# Open in browser
open http://localhost:8000
```

With `uv` (faster):
```bash
uv pip install -r webapp/requirements.txt
uvicorn webapp.main:app --reload
```

The app runs at `http://localhost:8000`. Share the URL on local WiFi for in-person events.

---

## Deploy to Railway (hosted public URL)

Railway deploys directly from GitHub — no CLI needed.

1. Push this repo to GitHub (if not already there)
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
3. Select this repository
4. Railway auto-detects `railway.json` and deploys
5. Go to **Settings → Networking → Generate Domain** to get a public URL

**Free tier** gives you 500 hours/month — more than enough for events and demos.

To redeploy after changes: just `git push`. Railway deploys automatically.

---

## File structure

```
webapp/
├── main.py           # FastAPI routes (search + check endpoints)
├── eligibility.py    # Clean Slate eligibility engine
├── templates/
│   └── index.html    # Full mobile-first SPA (Tailwind + vanilla JS)
├── static/
│   └── style.css     # Supplemental styles
└── requirements.txt
```

---

## Eligibility rules implemented

**Automatic sealing (no filing required):**
- Non-conviction charges: dismissed, withdrawn, nolle prossed, not guilty
- Summary convictions: 5+ years with no arrests since
- M2/M3 misdemeanors: 7+ years, no subsequent F or M conviction
- Drug felonies (35 § 780-113): 10+ years, qualifying sentence, no subsequent conviction
- Enumerated non-violent felonies (theft, forgery, fraud — F or F3): 10+ years, no subsequent conviction

**Petition-based sealing (must file with Court of Common Pleas):**
- M1 misdemeanors: 7+ years
- Terroristic threats §2706 M1: 10+ years

**Expungement (full destruction of record):**
- Non-conviction dispositions and completed ARD
- Summary convictions: 5+ years, arrest-free
- Age 70+ with 10+ arrest-free years since sentence completion

**Disqualifying:**
- Any restitution owed (flagged UNCLEAR, not ineligible — directed to lawyer)
- Pending/active cases
- Violent felonies, sex offenses (flagged UNCLEAR — needs legal review)
- Drug felonies where sentence was 30+ months minimum or 60+ months maximum
- F1/F2 felonies not in the enumerated list

---

## Legal disclaimer

This tool provides general information only — not legal advice. It uses public court data that may be incomplete or have errors. Always direct users to confirm with a free lawyer before taking any action.

**Sealing a record does NOT restore gun rights. Sealed records are still visible to law enforcement.**
