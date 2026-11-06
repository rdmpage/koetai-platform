# Deploying to the Hetzner box

**Do not deploy `main`.** `main` is an exact mirror of upstream
(`Koetai/koetai-platform`), and one thing this server uses is still sitting in
an unmerged pull request. Deploy the `deploy/hetzner` branch instead.

## Why this trap exists

Work goes upstream one PR at a time, and Andra merges them when he gets to them.
Between opening a PR and it being merged, that work exists only on its own
branch — so `main` can be perfectly up to date and still be missing a feature
this box runs on.

As of 6 November 2026 (upstream merged most of the list on 5 November):

| Wanted here | Comes from | Upstream yet? |
|---|---|---|
| `scripts/bulk_load.sh` (CLI bulk load) | PR #5 | **yes** |
| Loader agent + **Fast load** button | PR #7 | **yes** |
| `docker-compose.prod.yml`, `Caddyfile.prod` | PR #10 | **yes** |
| First-administrator bootstrap, install/backup docs | PR #12 | **yes** |
| QLever README section | PR #13 | **yes** |
| Saved-example Load button fix | PR #14 | no |
| Federation: accept a query POSTed as the body | PR #15 | **yes** |
| Batched, background dataset delete | PR #16 | **yes** |
| Graph browser (Browse tab) | PR #17 (from `main`) | **yes** |
| Oxigraph open-file limit (`ulimits` on the service) | PR #21 (branch `pr/18-oxigraph-open-files`) | **yes** |
| Same limit for the loader agent's Oxigraph runs | PR #7 (added to it) | **yes** |
| Cross-dataset SPARQL endpoints (`/sparql/<store>`) | PR #23 | **yes** |

Deploying `main` today would only lose the PR #14 fix: saved-example Load
buttons would print their query instead of rendering it. Everything else this
box runs on is upstream.

## Updating the branch

`deploy/hetzner` is upstream plus whatever is still open. It is never PR'd, but
it **is** pushed to `origin`: the box deploys it with `git pull`. So it only ever
moves forward. Bring new work in by merging, then push:

```bash
git fetch upstream
git branch -f main upstream/main             # main is a pure mirror again
git switch deploy/hetzner
git merge --no-edit main                      # and any pr/ branch that gained commits
git push origin deploy/hetzner                # a fast-forward, so the box can pull it
```

`main` can be reset now that PR #17 (opened from `main` itself) is merged. If a
PR is ever opened from `main` again, merge `upstream/main` into it instead until
that PR lands: a reset or rebase would rewrite the PR's commits.

Upstream squash-merges, so a PR that was merged here as its original commits
comes back from `main` as a different commit with the same content. Those
merges conflict on lines that are really identical; take `main`'s side
(`git checkout --theirs <file>`) unless the file has something deploy-only.

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
for b in pr/14-example-buttons; do
  git merge --no-edit "$b" || break      # resolve, commit, then rerun the rest
done
git push --force-with-lease origin deploy/hetzner
```

Drop a branch from the list as soon as its PR is merged: once the work is
upstream, `main` carries it and re-merging only invites conflicts.

### Conflicts seen so far

- **`README.md`, PRs #7 and #13.** Both append a section at the same anchor,
  just before `### Federation datasets (Comunica)`. Keep both, QLever first,
  then "Loading a large file faster". This one recurs.
- **`routes/datasets.py`, PR #16 and `main`.** Keep the `browse` route and drop
  `_remove_upload_dir`, which PR #16 moved into `services/job_runner.py`.
- **`README.md`, `routes/datasets.py`, `services/job_runner.py`, merging
  `main` on 6 November 2026.** The squash-merged copies of #13, #16 and #17
  against the originals already here, plus #25 (command-line dataset replace).
  Took `main`'s side of all three.
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

Once #14 is merged upstream, this branch has no reason to exist: `main` becomes deployable on its own, and `deploy/hetzner` and this file
can go.
