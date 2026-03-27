# Eneo Frontend

Browser frontend for the Eneo framework, based on SvelteKit.

## Architecture

The frontend consists of two parts, a server that serves the frontend, and the client that runs in the user's browser. The frontend's server handles basic authentication; once authenticated the client can make direct requests to the intric backend, e.g. when uploading files or streaming messages.

```
Intric Backend server <---> Frontend server  <---> Browser / Client
```

## Environment

All deployment specific settings are configured via runtime environment variables. See the sections below (Development, Deployment) to get tips on how to set them for different use cases.

| Variable                        | Description                                                                                                           |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `JWT_SECRET`                    | Secret for signing frontend JWT tokens. **Must match `JWT_SECRET` in the backend `.env`.**                            |
| `ENEO_BACKEND_URL`              | Primary backend URL, exposed to the browser for API calls. Must be reachable from the user's browser.                 |
| `PUBLIC_ENEO_BACKEND_URL`       | Backend URL for unauthenticated client flows (login page, federation discovery). Usually the same as `ENEO_BACKEND_URL`. |
| `ENEO_BACKEND_SERVER_URL`       | _Optional._ Overrides `ENEO_BACKEND_URL` for server-side rendering requests. Useful when frontend and backend share a private network (e.g., `http://backend:8000` in Docker). Defaults to `ENEO_BACKEND_URL`. |
| `PUBLIC_ORIGIN`                 | The public-facing origin of the frontend (e.g. `http://localhost:3000`). Required in production for CSRF protection.  |
| `MOBILITY_GUARD_AUTH`           | _Optional. Required for OIDC/MobilityGuard._ `Authorize` endpoint for the MobilityGuard flow, more info further down. |
| `OIDC_DISCOVERY_ENDPOINT`       | _Optional._ OIDC discovery endpoint for multi-tenant federation login.                                                |
| `OIDC_CLIENT_ID`                | _Optional._ OIDC client ID for federation.                                                                            |
| `OIDC_CLIENT_SECRET`            | _Optional._ OIDC client secret for federation.                                                                        |
| `FEDERATION_PER_TENANT_ENABLED` | _Optional._ Set to `true` to enable per-tenant OIDC federation. Default: `false`.                                     |

> **Note on HTTP proxies (local development):** If `HTTP_PROXY` or `HTTPS_PROXY` are set in your shell, they may cause server-side fetch requests to route through the proxy, breaking requests to `localhost`. Unset them before starting the dev server: `unset HTTP_PROXY HTTPS_PROXY`.

### Example config

For local development, create a `.env` file in this directory (`frontend/apps/web/.env`):

```
JWT_SECRET="your-secret"           # Must match backend JWT_SECRET
ENEO_BACKEND_URL="http://localhost:8000"
PUBLIC_ENEO_BACKEND_URL="http://localhost:8000"
PUBLIC_ORIGIN=http://localhost:3000
FEDERATION_PER_TENANT_ENABLED=false
```

For production:

```
JWT_SECRET="strong-random-secret"
ENEO_BACKEND_URL="https://api.example.com"
PUBLIC_ENEO_BACKEND_URL="https://api.example.com"
PUBLIC_ORIGIN=https://app.example.com
MOBILITY_GUARD_AUTH="https://example.com/mg-local/intric/oauth2/authorize"
```

## Local Development

Use the vite dev server for local development; set up a `.env` file in this directory to configure the required environment variables (see the _Environment_ section above).

```bash
# Prepare everything, install and build dependencies
bun -w run setup

# Start vite dev server
bun run dev
```

If you want to work on the client and the UI library at the same time as developing the Web GUI, you should run `bun -w run dev` to run all dev scripts simultaneously.

## OpenId Connect / MobilityGuard

We do support logging in through MobilityGuard. If the `MOBILITY_GUARD_AUTH` environment variable is set, a new login button will appear on the login screen that will handle the MobilityGuard flow. If the variable does not exist this feature is not enabled. For MobilityGuard to work, a user with the exact matching username and the `"created_with": "mobility_guard"` property needs to exist in the intric user table, otherwise the login will fail. Depending on the setup it is also necessary that the mobilityguard operator whitelists our deployment domains as redirect URIs.

The callback URI will always be in the format `https://<deployment>.<tld>/login/callback`, e.g. `https://app.intric.ai/login/callback`

## Formatting

Prettier is configured for this project, ideally you run format on save, or

```bash
bun run format
```

before comitting a file to git.
