# Eneo Development Setup Guide

This guide covers two approaches to setting up Eneo for development:
- **[DevContainer Setup](#devcontainer-setup-5-steps)** — recommended for VS Code users, handles all dependencies automatically
- **[Manual Setup](#manual-setup-without-devcontainer)** — for those not using VS Code or preferring direct control

> **Production Deployment?** See the [DEPLOYMENT.md](./DEPLOYMENT.md) guide for production setup.

## Quick Overview

- **Development Port**: `8123` (Backend API, DevContainer) / `8000` (manual setup)
- **Frontend Port**: `3000`
- **Recommended Setup**: VS Code DevContainer
- **Time to Setup**: ~10 minutes

## Prerequisites

- **Docker Desktop** - [Download here](https://www.docker.com/products/docker-desktop/)
- **VS Code** - [Download here](https://code.visualstudio.com/)
- **Dev Containers Extension** - Install from VS Code marketplace
- **At least one AI provider API key** (OpenAI, Anthropic, etc.)

## DevContainer Setup (5 Steps)

### Step 1: Clone and Open

```bash
git clone https://github.com/eneo-ai/eneo.git
cd eneo
code .
```

### Step 2: Reopen in Container

When VS Code opens:
1. You'll see a notification: "Folder contains a Dev Container configuration"
2. Click **"Reopen in Container"**
3. Wait 2-3 minutes for initial setup (only first time)

> **Note:** If you don't see the notification, install the "Dev Containers" extension from the VS Code marketplace (`ms-vscode-remote.remote-containers`), then reload VS Code.

### Step 3: Configure Environment

Now edit `backend/.env` and add your AI provider key:

```bash
# Example for OpenAI
OPENAI_API_KEY=sk-proj-your-actual-key-here

# Optional: Enable additional features
USING_ACCESS_MANAGEMENT=True  # Enables Users tab in admin panel
```

### Step 4: Initialize Database

```bash
cd backend
uv run python init_db.py
```

> **Important**: The `init_db.py` script:
> - Creates an example tenant and user (`user@example.com` / `Password1!`)
> - Runs all database migrations automatically
> - Can be re-run after code updates to apply new migrations

### Step 5: Start Services

Open **3 separate terminals** in VS Code:

**Terminal 1 - Backend API:**
```bash
cd backend
uv run start
```

**Terminal 2 - Frontend:**
```bash
cd frontend
bun run dev
```

**Terminal 3 - Worker (Optional, for document processing and for the crawler & apps to work):**
```bash
cd backend
uv run arq src.intric.worker.arq.WorkerSettings
```

## Verify Installation

1. **Access the Application**
   - Frontend: http://localhost:3000
   - Backend API Docs: http://localhost:8123/docs

2. **Login with Default Credentials**
   - Email: `user@example.com`
   - Password: `Password1!`

3. **Change the Default Password** (Important!)
   - Click user menu (top-right corner)
   - Select "Change Password"

## Essential Configuration

### AI Provider Setup

Configure at least one provider in `backend/.env`:

**OpenAI:**
```bash
OPENAI_API_KEY=sk-proj-...
```

**Anthropic:**
```bash
ANTHROPIC_API_KEY=sk-ant-...
```

**Azure OpenAI:**
```bash
AZURE_API_KEY=your-key
AZURE_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_API_VERSION=2024-02-15-preview
AZURE_MODEL_DEPLOYMENT=gpt-4o
USING_AZURE_MODELS=True
```

### Enable Admin Features

Add these to `backend/.env` for full admin capabilities:

```bash
# Enable user management in admin panel
USING_ACCESS_MANAGEMENT=True

# Access to system admin endpoints
ENEO_SUPER_API_KEY=your-secure-api-key

# Access to modules endpoint (higher privilege)
ENEO_SUPER_DUPER_API_KEY=your-other-secure-api-key

# Increase file upload limits (in bytes, 10MB example)
UPLOAD_MAX_FILE_SIZE=10485760
```

## Common Issues & Solutions

### Cannot Access "Users" in Admin Panel

Add to `backend/.env`:
```bash
USING_ACCESS_MANAGEMENT=True
```
Then restart the backend.

### Cannot Create "Apps"

1. Login to admin panel
2. Navigate to **Models** → **Transcription** tab
3. Enable a transcription model (e.g., Whisper)

### File Upload Errors (Large PDFs)

Increase limits in `backend/.env`:
```bash
UPLOAD_MAX_FILE_SIZE=10485760  # 10MB in bytes
```

### Login Issues During Development

The frontend is configured to bind to `0.0.0.0` by default (see `vite.config.ts` line 36), which should work in most development environments including WSL.

If you still experience login issues:
1. Verify the backend is running on port 8123: `curl http://localhost:8123/version`
2. Check that the `JWT_SECRET` in `backend/.env` is set
3. Clear your browser cookies and try again

### Database Issues After Code Updates

Re-run the initialization script to apply new migrations:
```bash
cd backend
uv run python init_db.py
```

This safely applies any new database migrations without losing data.

### Port Conflicts

Check if ports are already in use:
```bash
lsof -i :3000   # Frontend
lsof -i :8123   # Backend (development)
lsof -i :5432   # PostgreSQL
lsof -i :6379   # Redis
```

## Development Workflow

### Daily Development

1. **Start DevContainer** - VS Code automatically reconnects
2. **Pull Latest Changes** - `git pull origin develop`
3. **Update Dependencies** (if needed):
   ```bash
   cd backend && uv sync
   cd frontend && bun install
   ```
4. **Apply Migrations** - `cd backend && uv run python init_db.py`
5. **Start Services** - Run the 3 terminal commands

### Testing Your Changes

**Backend Tests:**
```bash
cd backend
uv run pytest                 # Run all tests
uv run pytest tests/api/ -v   # Specific tests with verbose output
```

**Frontend Tests:**
```bash
cd frontend
bun run test          # Run tests
bun run lint          # Check code style
bun run check         # Type checking
```

### Creating Database Migrations

After modifying database models:
```bash
cd backend
uv run alembic revision --autogenerate -m "describe your changes"
uv run alembic upgrade head
```

## Manual Setup (Without DevContainer)

Use this approach if you're not using VS Code, or prefer to run services directly on your machine.

### Prerequisites

- **Docker** and **Docker Compose** (for PostgreSQL and Redis)
- **Python 3.11+** and **uv** (`pip install uv`)
- **Bun** - [Download here](https://bun.sh/)
- **At least one AI provider API key**

### Step 1: Start Database Services

```bash
cd backend
docker compose up -d
```

This starts PostgreSQL (port `5432`) and Redis (port `6379`).

### Step 2: Configure Environment

Copy the example env file and edit it:

```bash
cd backend
cp .env.example .env  # or create .env manually
```

Key settings to update in `backend/.env`:

```bash
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=postgres

REDIS_HOST=localhost
REDIS_PORT=6379

JWT_SECRET=your-secret-here
URL_SIGNING_KEY=your-signing-key-here

# Set to false for manual setup (important — see note below)
TESTING=false
```

> **Important: The `TESTING` flag**
> When `TESTING=true`, Alembic automatically redirects all migrations to a database named `<POSTGRES_DB>_test` (e.g. `postgres_test`). This keeps your test database separate from your development database. For running the app locally, ensure `TESTING=false`.

### Step 3: Create Databases and Run Migrations

```bash
cd backend

# Create the test database (required for running tests)
docker exec <your-postgres-container> psql -U postgres -c "CREATE DATABASE postgres_test;"

# Run migrations for the development database
TESTING=false uv run alembic upgrade head
```

### Step 4: Initialize with a Default User

The `init_db.py` script creates an initial tenant and admin user. Pass the details via environment variables:

```bash
cd backend
TESTING=false \
DEFAULT_TENANT_NAME=myorg \
DEFAULT_TENANT_QUOTA_LIMIT=1000000 \
DEFAULT_USER_NAME=Admin \
DEFAULT_USER_EMAIL=admin@example.com \
DEFAULT_USER_PASSWORD=yourpassword \
uv run python init_db.py
```

> **Note:** `init_db.py` also runs migrations automatically. If `TESTING` is not explicitly overridden, it reads from `.env`.

### Step 5: Configure the Frontend

```bash
cd frontend/apps/web
```

Create a `.env` file with the following content:

```bash
ENEO_BACKEND_URL="http://localhost:8000"
PUBLIC_ENEO_BACKEND_URL="http://localhost:8000"
JWT_SECRET="your-secret-here"   # Must match JWT_SECRET in backend/.env
PUBLIC_ORIGIN=http://localhost:3000
```

Then install dependencies:

```bash
cd frontend
bun install
```

> **Note on HTTP proxies:** If `HTTP_PROXY` or `HTTPS_PROXY` environment variables are set in your shell, they may cause the frontend's server-side fetch requests to be routed through the proxy, breaking requests to `localhost`. Unset them before starting the frontend dev server: `unset HTTP_PROXY HTTPS_PROXY`.

### Step 6: Start Services

Open separate terminals for each service:

**Terminal 1 — Backend:**
```bash
cd backend
uv run gunicorn src.intric.server.main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend/apps/web
bunx vite dev --host --port 3000
```

**Terminal 3 — Worker (optional, required for document processing):**
```bash
cd backend
uv run arq src.intric.worker.arq.WorkerSettings
```

### Verify Manual Setup

- Frontend: http://localhost:3000
- Backend API Docs: http://localhost:8000/docs
- Login with the credentials you set in Step 4

---

## Next Steps

1. **Explore the API** - Visit http://localhost:8123/docs
2. **Create Your First Assistant** - Use the web interface
3. **Enable Document Processing** - Start the worker service
4. **Configure Additional Models** - Through the admin panel
5. **Review Architecture** - Check [ARCHITECTURE.md](./ARCHITECTURE.md)

## Additional Resources

- **[Deployment Guide](./DEPLOYMENT.md)** - Production setup
- **[API Documentation](http://localhost:8123/docs)** - Interactive API explorer
- **[GitHub Issues](https://github.com/eneo-ai/eneo/issues)** - Report problems
- **[Discussions](https://github.com/eneo-ai/eneo/discussions)** - Get help

---

**Need Help?** Join our [community discussions](https://github.com/eneo-ai/eneo/discussions) or [report an issue](https://github.com/eneo-ai/eneo/issues).