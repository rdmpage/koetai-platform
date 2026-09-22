# Deploying to the Hetzner box

**Do not deploy `main`.** `main` mirrors upstream (`Koetai/koetai-platform`), and
several things this server depends on are still sitting in unmerged pull
requests. Deploy the `deploy/hetzner` branch instead.

## Why this trap exists

Work goes upstream one PR at a time, and Andra merges them when he gets to them.
Between opening a PR and it being merged, that work exists only on its own
branch — so `main` can be perfectly up to date and still be missing a feature
this box runs on.

As of 22 September 2026 that includes:

| Wanted here | Comes from | Upstream yet? |
|---|---|---|
| `scripts/bulk_load.sh` (CLI bulk load) | PR #5 | **yes** |
| Loader agent + **Fast load** button | PR #7 | no |
| `docker-compose.prod.yml`, `Caddyfile.prod` | PR #10 | no |
| First-administrator bootstrap, install/backup docs | PR #12 | no |
| QLever README section | PR #13 | no |
| Saved-example Load button fix | PR #14 | no |
| Federation: accept a query POSTed as the body | PR #15 | no |

Deploying `main` today would take away the production compose overlay this
server runs on, and the fast loader with it. The command-line `bulk_load.sh`
would survive, since that one is already upstream.

## Rebuilding the branch

`deploy/hetzner` is a merge of upstream plus whatever is still open. It is
local-only and is never pushed or PR'd — it exists to be thrown away and
regenerated, which is how it stays honest as PRs land.

```bash
git fetch upstream
git branch -f main upstream/main            # main mirrors upstream, always

# Whatever is still open, oldest first. Check with:
#   gh pr list --repo Koetai/koetai-platform --state open
git branch -D deploy/hetzner 2>/dev/null
git switch -c deploy/hetzner main
for b in pr/10-cloud-install pr/12-docs-first-admin pr/07-bulk-loader \
         pr/13-qlever-docs pr/14-example-buttons pr/15-sparql-post-direct; do
  git merge --no-edit "$b" || break      # resolve, commit, then rerun the rest
done
```

Drop a branch from that list as soon as its PR is merged — once the work is
upstream, `main` carries it and re-merging only invites conflicts.

### The one conflict that recurs

PRs #7 and #13 both append a section to `README.md` at the same anchor, just
before `### Federation datasets (Comunica)`. Keep both, QLever first, then
"Loading a large file faster". Nothing else has conflicted so far.

## Deploying

On the box, from the checkout:

```bash
git fetch origin
git checkout deploy/hetzner
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
               --profile oxigraph --profile fastload up -d --build
```

`--build` matters: the app runs from an image built out of this tree, so a bare
`git pull` changes the files on disk and nothing that is serving.

`--profile fastload` is what starts the loader agent. `CLOUD-INSTALL.md` gives
the start command with `--profile oxigraph` alone, so a deployment that followed
that guide has never had the agent running — and without it the app simply does
not offer a fast load. No error, the button is just absent.

The agent finds the store by name, and the defaults assume the compose project
is called `koetai-platform` (compose takes that from the directory name):

```yaml
STORE_CONTAINER=${STORE_CONTAINER:-koetai-platform-oxigraph-1}
STORE_VOLUME=${STORE_VOLUME:-koetai-platform_oxigraph-data}
```

If the checkout directory is named anything else, set both in `.env` to what
these print:

```bash
docker ps --format '{{.Names}}' | grep oxigraph
docker volume ls --format '{{.Name}}' | grep oxigraph
```

Then confirm the agent came up — it writes a heartbeat the app reads, and a
stale directory without a live agent is exactly what that check exists to catch:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs loader | tail
```

Expect `loader-agent: watching /data/bulk-loader/requests for ...`.

## Before you deploy, check it is all there

```bash
git switch deploy/hetzner
for f in scripts/bulk_load.sh services/bulk_loader.py deploy/loader-agent/agent.sh \
         docker-compose.prod.yml deploy/Caddyfile.prod; do
  git cat-file -e HEAD:$f 2>/dev/null && echo "  ok   $f" || echo "  MISSING  $f"
done
grep -c loader-agent docker-compose.yml     # expect 2, not 0
```

If any of those are missing, the merge list above is out of date.

## When everything lands

Once #7, #10, #12 and #15 are all merged upstream, this branch has no reason to
exist: `main` becomes deployable on its own, and `deploy/hetzner` and this file
can go.
