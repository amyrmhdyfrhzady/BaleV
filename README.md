# Cloud Terminal Bot v1.1.1

Cloudflare Worker bot for Telegram and Bale. It provides a simulated terminal, a curl-style HTTP client, a categorized help menu, and an in-chat admin panel backed by Cloudflare D1.

## What is stored

D1 stores only administration/configuration data: allowed users, active status, per-user limits, global defaults, a PBKDF2 password hash, short-lived admin sessions, and a single rolling per-user rate-limit counter. It does **not** store command history, HTTP request bodies, response bodies, or terminal output.

## D1 setup

1. Create a D1 database named `cloud-terminal-config`.
2. Copy its database ID into `wrangler.toml` in place of `REPLACE_WITH_D1_DATABASE_ID`.
3. Bind the database as `DB` if using the Cloudflare Dashboard.
4. Apply the migration:

```bash
npx wrangler d1 migrations apply cloud-terminal-config --remote
```

For local development use `--local`.

## Worker secrets

Set these in Cloudflare Worker > Settings > Variables and Secrets:

- `TELEGRAM_BOT_TOKEN`
- `BALE_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET`
- `BALE_WEBHOOK_SECRET`
- `ADMIN_PASSWORD` (initial password; use at least 12 characters)

Set these non-secret variables:

- `ADMIN_TELEGRAM_IDS`: comma-separated Telegram user IDs allowed to open the admin panel
- `ADMIN_BALE_IDS`: comma-separated Bale user IDs allowed to open the admin panel
- `ALLOWED_TELEGRAM_USER_IDS`: optional legacy allowlist; existing IDs are imported into D1 on first message
- `ALLOWED_BALE_USER_IDS`: optional legacy allowlist; existing IDs are imported into D1 on first message

**Important:** Admin IDs are a separate bootstrap allowlist. A password alone does not grant admin access. Do not leave `ADMIN_*_IDS` empty if you need to use the admin panel. In private chats, use the sender's numeric user ID; the add-user form accepts a private chat ID and stores it as both user ID and chat ID.

On the first successful admin login, `ADMIN_PASSWORD` is PBKDF2-hashed and stored in D1. The admin can later change it from the panel. If the hash is lost or you need to reset the password, delete the `admin_password_hash` row from D1 settings; the Worker will bootstrap again from `ADMIN_PASSWORD`.

## Admin panel

Send `/admin` or tap **🔐 پنل ادمین**. Admin access requires both:

1. Sender ID listed in `ADMIN_TELEGRAM_IDS` or `ADMIN_BALE_IDS` (or a D1 admin role).
2. Correct panel password.

The session expires after 30 minutes. Five failed password attempts lock login for 15 minutes.

Available operations:

- List users and view aggregate counts
- Add/remove Telegram and Bale users
- Enable/disable users
- Set per-user rate limit, request timeout, and maximum response size
- Set defaults for newly added users
- Pause/resume access for ordinary users (admins retain access)
- Change the admin password
- Keep bot API tokens in Cloudflare Secrets; the admin panel never displays or edits them

User command syntax inside the admin prompts:

```text
telegram 123456789
bale 987654321
```

Per-user limits:

```text
telegram 123456789 10 15000 49152
```

Order: platform, chat/user ID, requests per minute, timeout milliseconds, max response bytes.

Default limits:

```text
10 15000 49152
```

## Menus and commands

- `/start`, `/help`, `help`, `?`: full categorized guide
- `menu`: main inline menu
- `curl URL` or `https://...`: HTTP client
- `ping host`: HTTP HEAD connectivity check (not ICMP)
- `nslookup host`: DNS-over-HTTPS lookup
- `wget URL`: response metadata only; does not save a file
- `ipconfig`, `ifconfig`: explains the Worker network limitation
- `tracert`, `traceroute`: explains raw-socket limitation
- Simulated: `clear`, `cls`, `ver`, `version`, `whoami`, `hostname`, `pwd`, `cd`, `date`, `time`, `env`, `history`

curl options supported: `-X/--request`, `-H/--header`, `-d/--data`, `--data-raw`, `--data-binary`, `-I/--head`, `-i/--include`, `-L/--location`, `-s/--silent`, `-u/--user`, `--max-time`.

## Webhooks

Endpoints:

- `GET /` health
- `POST /telegram` Telegram webhook
- `POST /bale` Bale webhook

Telegram requires `X-Telegram-Bot-Api-Secret-Token`. Bale accepts `X-Cloud-Terminal-Secret` or a secret path query parameter.

Telegram webhook example:

```bash
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://YOUR-WORKER.workers.dev/telegram","secret_token":"YOUR_TELEGRAM_WEBHOOK_SECRET"}'
```

Bale webhook example:

```bash
curl -X POST "https://tapi.bale.ai/bot$BALE_BOT_TOKEN/setWebhook" \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://YOUR-WORKER.workers.dev/bale?secret=YOUR_BALE_WEBHOOK_SECRET"}'
```

## Limits and security

- No real Bash, CMD, PowerShell, or OS processes.
- `ping` is HTTP HEAD, not ICMP. `wget` does not persist files.
- Response bodies are capped at the configured per-user limit (maximum 48 KiB); messages are split for delivery.
- Requests/minute, timeout, and response size are configurable per user.
- HTTP/HTTPS only. The URL guard blocks localhost, common private IPv4 literals, IPv6 literals, and metadata hostnames. This hostname validation is not a DNS-pinning egress proxy; keep access restricted to trusted users and do not treat it as a complete SSRF boundary for untrusted users.
- Cloudflare Workers quotas and target server limits apply.
