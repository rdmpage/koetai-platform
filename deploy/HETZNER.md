# Deploying to the Hetzner box

**Do not deploy `main`.** `main` is upstream (`Koetai/koetai-platform`) plus the
graph browser (PR #17), and several things this server depends on are still
sitting in other unmerged pull requests. Deploy the `deploy/hetzner` branch
instead.

## Why this trap exists

Work goes upstream one PR at a time, and Andra merges them when he gets to them.
Between opening a PR and it being merged, that work exists only on its own
branch — so `main` can be perfectly up to date and still be missing a feature
this box runs on.

As of 1 November 2026 that includes:

| Wanted here | Comes from | Upstream yet? |
|---|---|---|
| `scripts/bulk_load.sh` (CLI bulk load) | PR #5 | **yes** |
| Loader agent + **Fast load** button | PR #7 | no |
| `docker-compose.prod.yml`, `Caddyfile.prod` | PR #10 | no |
| First-administrator bootstrap, install/backup docs | PR #12 | no |
| QLever README section | PR #13 | no |
| Saved-example Load button fix | PR #14 | no |
| Federation: accept a query POSTed as the body | PR #15 | no |
| Batched, background dataset delete | PR #16 | no |
| Graph browser (Browse tab) | PR #17 (from `main`) | no |
| Oxigraph open-file limit (`ulimits` on the service) | PR #21 (branch `pr/18-oxigraph-open-files`) | no |
| Same limit for the loader agent's Oxigraph runs | PR #7 (added to it) | no |

Deploying `main` today would take away the production compose overlay this
server runs on, and the fast loader with it. The command-line `bulk_load.sh`
would survive, since that one is already upstream.

## Updating the branch

`deploy/hetzner` is upstream plus whatever is still open. It is never PR'd, but
it **is** pushed to `origin`: the box deploys it with `git pull`. So it only ever
moves forward. Bring new work in by merging, then push:

```bash
git fetch upstream
git switch main && git merge upstream/main   # not `git branch -f`: see below
git switch deploy/hetzner
git merge --no-edit main                      # and any pr/ branch that gained commits
git push origin deploy/hetzner                # a fast-forward, so the box can pull it
```

`main` is merged into, never reset, because PR #17 (the graph browser) is opened
from `main` itself rather than a `pr/` branch. Until it is merged, `main` is
ahead of `upstream/main`, and `git branch -f main upstream/main` (or a rebase)
would drop or rewrite the PR's commits.

## Regenerating the branch (rarely)

Regenerate only when a PR has landed upstream in a form that conflicts with the
copy merged here, so that the old branch has to come out. This rewrites
history, so it needs a force-push, and the box then needs
`git fetch origin && git reset --hard origin/deploy/hetzner` instead of a pull.

```bash
# Whatever is still open, oldest first. Check with:
#   gh pr list --repo Koetai/koetai-platform --state open
git branch -D deploy/hetzner 2>/dev/null
git switch -c deploy/hetzner upstream/main
for b in pr/10-cloud-install pr/12-docs-first-admin pr/07-bulk-loader \
         pr/13-qlever-docs pr/14-example-buttons pr/15-sparql-post-direct \
         pr/16-batched-delete pr/18-oxigraph-open-files main; do
  git merge --no-edit "$b" || break      # resolve, commit, then rerun the rest
done
git push --force-with-lease origin deploy/hetzner
```

`main` is in the list for PR #17. Drop a branch from it as soon as its PR is
merged: once the work is upstream, `main` carries it and re-merging only
invites conflicts.

### Conflicts seen so far

- **`README.md`, PRs #7 and #13.** Both append a section at the same anchor,
  just before `### Federation datasets (Comunica)`. Keep both, QLever first,
  then "Loading a large file faster". This one recurs.
- **`routes/datasets.py`, PR #16 and `main`.** Keep the `browse` route and drop
  `_remove_upload_dir`, which PR #16 moved into `services/job_runner.py`.
- **`templates/yasgui.html`, PR #14 and upstream (1 November 2026).** Upstream
  fixed the saved-example keyword parsing (issue #18) in the same lines PR #14
  rewrote. Keep PR #14's `exampleKeywords()` and `data-example` Load buttons,
  which also accept the older comma-separated form; upstream's `isUrl()` links
  elsewhere in the file merge cleanly.

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

Once #7, #10, #12, #15, #16, #17 and #21 are all merged upstream, this branch has no reason to
exist: `main` becomes deployable on its own, and `deploy/hetzner` and this file
can go.
