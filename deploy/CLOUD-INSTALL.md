# Installing Koetai on a cloud server

A start-to-finish install on a fresh Linux host, ending with an HTTPS site you
sign into with your ORCID. Written against Hetzner Cloud because that is what it
was tested on; nothing here is Hetzner-specific beyond the sizing note.

Budget about half an hour, most of it waiting for DNS.

## Before you start

You need three things, and two of them take time to arrange, so do them first:

1. **A domain name** you can add a DNS record to.
2. **An ORCID application** — register at
   <https://orcid.org/developer-tools>. It gives you a client ID and secret, and
   asks for a redirect URI: use `https://YOUR-DOMAIN/auth/callback`. This has to
   match exactly, including the scheme.
3. **Your own ORCID iD.** You will be the first administrator, and on a new
   install nothing else can make one — registration is invitation-only,
   invitations are issued by an administrator, so without this the instance
   cannot be signed into at all.

## 1. Pick a server

The store is what grows. Measured on a real instance: **115 million triples took
21.8 GB**, or roughly 190 bytes per triple. Estimate from the triples you expect,
then leave room — a load expands its source file on disk, and deleted data does
not return space to the filesystem until the store is compacted.

| Triples | Store | Suggested disk |
|---|---|---|
| 100 M | ~19 GB | 40 GB |
| 300 M | ~57 GB | 100 GB |
| 500 M | ~95 GB | 160 GB |

**Attach a volume rather than relying on the server's own disk**, which is
fixed at whatever the plan includes. A volume can be enlarged later without
rebuilding the machine, and this is the resource you will run out of first.

**Memory matters less than you would expect.** Oxigraph answers queries from
disk: a full aggregate over 102 million triples ran in 29 seconds while the
process held under 300 MB. RAM buys page cache, which makes queries quicker, and
headroom for loading. 8 GB is workable, 16 GB comfortable.

**Processor: ARM is the better buy.** Hetzner's ARM (CAX) instances cost
substantially less per core than the x86 lines, and Oxigraph ships multi-arch
images that run natively. Two things to know before choosing ARM: the Fuseki
image in `docker-compose.yml` is x86-only (use a multi-arch one, or leave Fuseki
alone — Oxigraph is the default), and RUDOF, which shape *validation* uses, has
no ARM build. Shape *inference* is unaffected; it is a Python package.

A CAX31-sized machine — 8 vCPU, 16 GB — with a 100 GB volume is a reasonable
starting point for a few hundred million triples.

## 2. Point DNS at the server

Add an `A` record for your domain to the server's IPv4 address, and an `AAAA`
for IPv6 if you have one. **Do this before starting the stack.** Caddy asks
Let's Encrypt for a certificate on first run, and that only works once the name
resolves to this host — otherwise it fails, retries with backoff, and you spend a
while wondering why the site will not load.

Check it has propagated:

```bash
dig +short YOUR-DOMAIN
```

## 3. Install Docker and get the code

```bash
curl -fsSL https://get.docker.com | sh
git clone https://github.com/Koetai/koetai-platform.git
cd koetai-platform
```

If you attached a volume, mount it and put Docker's data on it, so the stores
land on the big disk rather than the small one. Hetzner mounts volumes under
`/mnt/HC_Volume_NNNNN`.

## 4. Write the configuration

Everything the production overlay needs comes from a `.env` file beside the
compose files. It refuses to start rather than guess, so a missing value is an
error at the point of typing rather than a puzzle later.

```bash
cat > .env <<'EOF'
KOETAI_DOMAIN=koetai.example.org
BASE_URL=https://koetai.example.org

# Anything long and random. Sessions are signed with it; changing it later
# signs everyone out.
SECRET_KEY=CHANGE-ME

# From https://orcid.org/developer-tools. The redirect URI must match exactly.
ORCID_CLIENT_ID=APP-XXXXXXXXXXXXXXXX
ORCID_CLIENT_SECRET=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
ORCID_REDIRECT_URI=https://koetai.example.org/auth/callback

# You. Without this nobody can sign in — see "Before you start".
KOETAI_ADMIN_ORCIDS=0000-0000-0000-0000

# Only read in internal mode; harmless otherwise.
# KOETAI_MODE=internal
# INTERNAL_ALLOWED_ORCIDS=0000-0001-1111-1111
# INTERNAL_ALLOWED_DOMAINS=your-institute.org

FUSEKI_ADMIN_PASSWORD=CHANGE-ME-TOO
EOF
chmod 600 .env
```

`BASE_URL` deserves a moment. It becomes part of every dataset's graph URIs, and
those are written into the store when a dataset is created. Changing it later
does not rewrite them, so decide the final hostname **before** loading anything.

### Which mode?

- **`community`** (the default) — anyone with an ORCID may join, but only with an
  invitation. Invitations are issued from the Admin menu. This is the public
  model.
- **`internal`** — no invitations; instead an allowlist of ORCIDs, or of email
  domains for people who have made an email public on ORCID. Better for a group
  hosting for its own members.

Both sign in with ORCID. The third mode, `local`, signs *every visitor* in as the
same user and must not be used on a public host.

## 5. Start it

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
               --profile oxigraph up -d
```

The first start takes a few minutes: it builds the app image and Caddy fetches a
certificate. Watch it happen:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f caddy
```

Then open `https://YOUR-DOMAIN` and sign in with the ORCID you listed as an
administrator. You should arrive at an empty dashboard with an Admin menu.

## 6. Check it over

- **Admin → Storage** reports host memory and disk. Worth a look after a large
  load: memory is what decides whether one survives.
- **My Datasets → New Dataset** lists the triplestores this install actually has
  running; Oxigraph should be selectable and Fuseki not, unless you started it.
- Uploads up to `MAX_UPLOAD_MB` (4 GB by default) go through the browser.
  Anything larger is better fetched by the dataset's **Web** tab, which pulls
  from a URL server-side and has no such limit.

## What this does not set up

- **Backups.** Nothing here backs anything up. What matters is the `koetai-data`
  volume — it holds the SQLite database, which is the only copy of your users,
  datasets and shapes. The triplestore volumes hold data that can be reloaded
  from sources; the database cannot be reconstructed.
- **The fast loader.** `docker-compose.yml` has an optional `loader` service,
  behind the `fastload` profile, that makes large imports several times quicker.
  It mounts the Docker socket, which is root on the host. On a machine only you
  use that may be a fair trade; on a shared instance think harder, and read
  `deploy/loader-agent/agent.sh` first — it is deliberately short. Over SSH,
  `scripts/bulk_load.sh` gives the same speed with no daemon holding the socket.
- **A firewall.** Only 80 and 443 need to be open. Nothing else in the stack
  publishes a port — the app, the stores and the agent all talk over the compose
  network.
- **Fuseki.** Started only if you ask for it (`--profile fuseki` is not needed;
  it is in the base file, so it starts by default — remove it if unwanted).

## If something goes wrong

**The certificate never arrives.** Almost always DNS: check `dig +short
YOUR-DOMAIN` matches the server, and that 80 and 443 are reachable from outside.
Let's Encrypt validates over port 80.

**"Your ORCID is not permitted on this instance."** In `community` mode you
needed an invitation, or to be listed in `KOETAI_ADMIN_ORCIDS`. In `internal`
mode you are not on the allowlist. Both are in `.env`; restart after editing.

**Sign-in loops back to the front page.** Usually `ORCID_REDIRECT_URI` not
matching what is registered with ORCID — including `https` versus `http`.

**A large upload fails with a dropped connection.** Historically this was the
store running out of memory; loads are now sent in batches, which bounds it.
Check Admin → Storage for headroom, and `dmesg | grep -i "killed process"` on
the host for a definitive answer.
