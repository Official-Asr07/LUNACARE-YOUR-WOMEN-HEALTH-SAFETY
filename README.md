# LunaCare Backend — Vercel Deployment

Same backend, restructured to run as a **Vercel serverless function**
instead of a long-running server (that's the one real difference from the
Render setup — see the note at the bottom on what that changes).

```
lunacare-backend-vercel/
├── api/
│   └── index.py      ← Vercel entrypoint (just imports the FastAPI app)
├── app/               ← unchanged FastAPI app (main.py, routers/, etc.)
├── vercel.json        ← routes all paths to api/index.py
├── requirements.txt
└── .env.example
```

## 1. Push to GitHub

```bash
cd lunacare-backend-vercel
git init
git add .
git commit -m "LunaCare backend for Vercel"
git branch -M main
git remote add origin <your-empty-github-repo-url>
git push -u origin main
```

## 2. Import into Vercel

1. Go to vercel.com → **Add New → Project** → import your GitHub repo.
2. Framework Preset: leave as **Other** (Vercel auto-detects the Python
   function from `vercel.json` + `api/index.py`).
3. Leave Build/Output settings at their defaults — `vercel.json` handles it.
4. Before clicking Deploy, add environment variables (Settings →
   Environment Variables, or the form shown during import):

   | Name | Value |
   |---|---|
   | `NVIDIA_API_KEY` | your NVIDIA API key |
   | `FIREBASE_CREDENTIALS_JSON` | entire service account JSON, one line |
   | `FIREBASE_DATABASE_URL` | `https://YOUR-PROJECT-default-rtdb.firebaseio.com` |
   | `ALLOWED_ORIGINS` | your Firebase Hosting URL, or `*` for now |

5. Click **Deploy**. You'll get a URL like `https://lunacare-backend.vercel.app`.

Test it: open `https://lunacare-backend.vercel.app/api/health` → should
return `{"status":"ok"}`.

## 3. Point index.html at it

Same as before — set:

```js
const BACKEND_URL = "https://lunacare-backend.vercel.app";
```

## 4. What's different from a normal server (Render/VPS)

Vercel runs this as a **stateless serverless function** — each request
spins up (or reuses a warm) isolated instance, runs, and shuts down.
Because this backend doesn't keep anything in memory between requests
(everything goes straight to Firestore/Realtime DB), this works
correctly with **no code changes**. Two practical effects to know about:

- **Cold starts**: the first request after idle time takes ~1-3 seconds
  extra while the function boots and Firebase Admin initializes. Later
  requests within the same warm window are fast.
- **Execution time limit**: Hobby plan caps each request at 10 seconds
  (Pro: 60s+, configurable). All the endpoints here (NVIDIA calls,
  Firestore/RTDB REST calls) normally finish well under that — but if a
  NVIDIA response is unusually slow, a 10s cap could cut it off on Hobby.
  If that happens in practice, upgrade to Pro or move `/api/aviro/chat`
  to Render instead.

Everything else — routes, auth verification, Firestore/RTDB logic — is
byte-for-byte the same code as the Render version.
