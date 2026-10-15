# LunaCare Backend

The secure API layer for **LunaCare**, a women's health, wellbeing, and
safety platform. This service is built with FastAPI and is designed to run as
a Vercel Python serverless function while remaining easy to run locally with
Uvicorn.

The backend keeps privileged integrations on the server:

- Firebase Admin SDK for authenticated access to Firestore and Realtime
  Database
- NVIDIA-hosted language models for AViro and the therapy companion
- Razorpay for subscription lifecycle management
- Resend for optional guardian-request email notifications

The frontend should never contain an NVIDIA, Firebase Admin, Razorpay secret,
or other server-side credential.

## What the API provides

### AViro AI

- Conversational AI with usage limits and plan-aware quotas
- Indian legal information search
- Women's health expert and clinic locator
- Short situational-threat analysis from an audio transcript

### Safety and emergency support

- Authenticated or anonymous SOS location telemetry
- AI situational-report storage
- Trusted-guardian invitations and one-time invite codes
- Explicit owner/guardian approval before live location access
- Revocable guardian links and protected ward-location reads

### Wellbeing

- Safety PIN creation and verification
- SOS contact management
- Mood and journal entries
- AI therapy companion with crisis-language guidance and India-specific
  emergency resources

### Accounts and subscriptions

- Firebase ID-token authentication
- User profile synchronization
- Free, Plus, and Max plan limits
- Razorpay monthly/yearly subscriptions, cancellation, and signed webhooks
- Monthly summary cron endpoint for Vercel

## Architecture

```text
LunaCare frontend
        │
        │  HTTPS + Firebase ID token
        ▼
Vercel Python function
  api/index.py → app/main.py
        │
        ├── Firebase Admin SDK
        │     ├── Firebase Authentication
        │     ├── Firestore
        │     └── Realtime Database
        ├── NVIDIA API
        ├── Razorpay API + webhooks
        └── Resend email API (optional)
```

## Repository layout

```text
.
├── api/
│   └── index.py              # Vercel ASGI entrypoint
├── app/
│   ├── main.py               # FastAPI app, CORS, health checks, routers
│   ├── auth_dep.py           # Firebase ID-token dependencies
│   ├── config.py             # Environment-backed settings
│   ├── firebase_setup.py     # Firebase Admin initialization
│   ├── nvidia_client.py      # NVIDIA chat-completions client
│   ├── plans.py              # Effective-plan and quota helpers
│   ├── usage.py              # Daily usage tracking
│   └── routers/
│       ├── aviro.py          # AViro AI endpoints
│       ├── billing.py        # Razorpay subscriptions and webhooks
│       ├── emergency.py      # SOS telemetry
│       ├── guardians.py      # Trusted contacts and live location
│       ├── therapy.py        # Wellbeing companion
│       └── users.py          # Profile, PIN, contacts, moods, journals
├── requirements.txt
└── vercel.json
```

## Requirements

- Python 3.10 or newer
- A Firebase project with Authentication enabled
- Firebase Admin credentials
- An NVIDIA API key for AI features
- A Vercel account for production deployment
- Optional: Razorpay and Resend accounts for billing and email notifications

## Run locally

### 1. Create and activate a virtual environment

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in this directory. Do not commit it.

```dotenv
# AI
NVIDIA_API_KEY=your_nvidia_api_key
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_MODEL=meta/llama-3.3-70b-instruct,meta/llama-3.1-8b-instruct

# Firebase Admin: use either a file path or inline JSON
FIREBASE_CREDENTIALS_PATH=C:\path\to\firebase-service-account.json
# FIREBASE_CREDENTIALS_JSON={"type":"service_account",...}
FIREBASE_DATABASE_URL=https://your-project-default-rtdb.firebaseio.com

# Browser origins, comma separated
ALLOWED_ORIGINS=http://localhost:5500,https://your-production-frontend.example

# Optional email notifications
RESEND_API_KEY=
RESEND_FROM_EMAIL=LunaCare <onboarding@resend.dev>

# Optional Razorpay subscriptions
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=
RAZORPAY_PLAN_MONTHLY=
RAZORPAY_PLAN_YEARLY=

# Required to authorize the monthly-summary cron request
MONTHLY_SUMMARY_CRON_SECRET=
```

For hosted platforms that do not support a credential file, set
`FIREBASE_CREDENTIALS_JSON` to the complete service-account JSON instead of
`FIREBASE_CREDENTIALS_PATH`. Never publish either value.

### 4. Start the development server

```bash
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`.

Useful local URLs:

- Health check: `http://127.0.0.1:8000/api/health`
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Authentication

Protected endpoints expect a Firebase Authentication ID token:

```http
Authorization: Bearer <firebase-id-token>
```

The frontend can obtain the token from the signed-in Firebase user and attach
it to each backend request. The backend verifies the token with Firebase Admin
SDK and uses the verified Firebase UID for database access; it does not trust a
UID supplied in the request body.

The emergency telemetry endpoints also support anonymous device-based writes.
Use a stable client-generated `device_id` for that flow. Anonymous telemetry
is stored under a generated `web_anonymous_<device_id>` identity.

## API reference

All routes are under `/api`. Request and response schemas are available in the
interactive OpenAPI documentation at `/docs`.

| Area | Method | Endpoint | Auth |
|---|---:|---|---|
| Health | GET | `/api/health` | Public |
| Health | GET | `/api/health/ai-models` | Public |
| AViro | POST | `/api/aviro/chat` | Firebase token |
| AViro | POST | `/api/aviro/legal-search` | Firebase token |
| AViro | POST | `/api/aviro/expert-locator` | Firebase token |
| AViro | POST | `/api/aviro/situational-analysis` | Firebase token |
| Usage | GET | `/api/aviro/usage` | Firebase token |
| Therapy | POST | `/api/therapy/chat` | Firebase token |
| Emergency | POST | `/api/emergency/location` | Optional |
| Emergency | POST | `/api/emergency/situational-report` | Optional |
| Users | GET/PUT | `/api/users/me` | Firebase token |
| Users | PUT | `/api/users/me/security-pin` | Firebase token |
| Users | POST | `/api/users/me/security-pin/verify` | Firebase token |
| Users | GET/PUT | `/api/users/me/sos-contacts` | Firebase token |
| Users | GET/POST | `/api/users/me/moods` | Firebase token |
| Users | GET/POST | `/api/users/me/journals` | Firebase token |
| Guardians | POST | `/api/guardians/invite` | Firebase token |
| Guardians | POST | `/api/guardians/invite-code` | Firebase token |
| Guardians | POST | `/api/guardians/redeem-code` | Firebase token |
| Guardians | GET/DELETE | `/api/guardians/my-invites` and `/{link_id}` | Firebase token |
| Guardians | GET/POST | `/api/guardians/pending` and `/{link_id}/approve` | Firebase token |
| Guardians | GET | `/api/guardians/my-wards` | Firebase token |
| Guardians | GET | `/api/guardians/live/{owner_uid}` | Firebase token |
| Billing | POST | `/api/billing/create-subscription` | Firebase token |
| Billing | POST | `/api/billing/cancel` | Firebase token |
| Billing | GET | `/api/billing/status` | Firebase token |
| Billing | POST | `/api/billing/webhook` | Razorpay signature |
| Cron | GET | `/api/users/cron/monthly-summary` | Cron secret |

## Quick API smoke test

```bash
curl http://127.0.0.1:8000/api/health
```

Expected response:

```json
{
  "status": "ok",
  "ai": {
    "key_configured": true,
    "base_url": "https://integrate.api.nvidia.com/v1",
    "models": ["meta/llama-3.3-70b-instruct"]
  }
}
```

To call a protected route, add a Firebase ID token:

```bash
curl http://127.0.0.1:8000/api/aviro/usage \
  -H "Authorization: Bearer YOUR_FIREBASE_ID_TOKEN"
```

## Deploy to Vercel

1. Push this backend directory to a GitHub repository.
2. In Vercel, choose **Add New → Project** and import the repository.
3. Keep the framework preset as **Other**. `vercel.json` routes all requests
   to `api/index.py`.
4. Add the environment variables from the configuration section to the
   Vercel project. Set them for the environments you use.
5. Deploy and verify:

   ```text
   https://YOUR-DEPLOYMENT.vercel.app/api/health
   ```

The repository also configures a monthly Vercel cron for
`/api/users/cron/monthly-summary`. Set `MONTHLY_SUMMARY_CRON_SECRET` and
configure the frontend or cron integration consistently with that secret.

### Connect the frontend

Configure the frontend's API base URL to the deployed backend, for example:

```js
const BACKEND_URL = "https://YOUR-DEPLOYMENT.vercel.app";
```

Use the production frontend origin in `ALLOWED_ORIGINS`. Avoid `*` in
production when credentials or authenticated browser requests are involved.

## Security checklist

- Keep `.env`, Firebase service-account JSON, API keys, and webhook secrets out
  of Git.
- Use Firebase ID tokens, not client-supplied UIDs, for protected requests.
- Restrict `ALLOWED_ORIGINS` to known frontend origins in production.
- Configure and verify `RAZORPAY_WEBHOOK_SECRET` before enabling subscriptions.
- Use HTTPS for every deployed frontend and backend URL.
- Treat AI output as assistance, not medical, legal, or emergency advice.
- Keep emergency escalation messaging visible; the therapy endpoint includes
  crisis guidance, but it is not a replacement for emergency services or a
  licensed professional.
- Review Firebase security rules together with the server authorization model
  before changing database paths or guardian permissions.

## Troubleshooting

### `Firebase credentials are not configured`

Set exactly one of `FIREBASE_CREDENTIALS_JSON` or
`FIREBASE_CREDENTIALS_PATH`, and set `FIREBASE_DATABASE_URL` when using
Realtime Database.

### AI endpoints return a configuration error

Confirm that `NVIDIA_API_KEY` is present and that `NVIDIA_MODEL` contains a
model provisioned for that key. Multiple comma-separated models are tried in
order when a model is unavailable.

### Browser requests fail with CORS errors

Add the exact browser origin, including scheme and port, to
`ALLOWED_ORIGINS`, separated by commas. Restart the local server after
changing `.env`.

### Vercel deployment works but requests time out

Serverless functions have platform execution limits. Check the Vercel
function logs and NVIDIA latency. Keep AI prompts bounded and use a Vercel
plan appropriate for the required execution time.

## Development notes

- The application is intentionally stateless between requests; persistent
  data belongs in Firebase.
- `app/main.py` exposes the FastAPI application as `app`.
- `api/index.py` is the only Vercel adapter and should remain lightweight.
- Run the API locally with Uvicorn before deploying changes.
- Do not log access tokens, service-account JSON, payment secrets, or complete
  user emergency transcripts.

## License and project status

This repository contains the LunaCare application backend. Add the project's
official license and contribution policy before accepting external
contributions or redistributing the code.
