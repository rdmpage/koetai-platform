# Deploying to the Hetzner box

**Do not deploy `main`.** `main` mirrors upstream (`Koetai/koetai-platform`), and
several things this server depends on are still sitting in unmerged pull
requests. Deploy the `deploy/hetzner` branch instead.

## Why this trap exists

Work goes upstream one PR at a time, and Andra merges them when he gets to them.
Between opening a PR and it being merged, that work exists only on its own
branch — so `main` can be perfectly up to date and still be missing a feature
this box runs on.

As of 16 September 2026 that includes:

| Wanted here | Comes from | Upstream yet? |
|---|---|---|
| `scripts/bulk_load.sh` (CLI bulk load) | PR #5 | **yes** |
| Loader agent + **Fast load** button | PR #7 | no |
| `docker-compose.prod.yml`, `Caddyfile.prod` | PR #10 | no |
| First-administrator bootstrap, install/backup docs | PR #12 | no |
| QLever README section | PR #13 | no |
| Saved-example Load button fix | PR #14 | no |

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
         pr/13-qlever-docs pr/14-example-buttons; do
  git merge --no-edit "$b" || break      # resolve, commit, then rerun the rest
done
```

Drop a branch from that list as soon as its PR is merged — once the work is
upstream, `main` carries it and re-merging only invites conflicts.

### The one conflict that recurs

PRs #7 and #13 both append a section to `README.md` at the same anchor, just
before `### Federation datasets (Comunica)`. Keep both, QLever first, then
"Loading a large file faster". Nothing else has conflicted so far.

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

Once #7, #10 and #12 are all merged upstream, this branch has no reason to
exist: `main` becomes deployable on its own, and `deploy/hetzner` and this file
can go.
