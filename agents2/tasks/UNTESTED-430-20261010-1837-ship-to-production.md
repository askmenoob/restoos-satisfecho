# Ship to Production (#430)

## GitHub Issues
- **Issue:** https://github.com/satisfecho/pos/issues/430
- **430**

## Status
- **UNTESTED** — Agent 010 finished promote + deploy **2026-10-10T18:42:50Z** UTC. Awaiting tester.
- Preflight: actionable. Local smoke: `http://127.0.0.1:14202/` and `/api/health` → **200**. Front logs (10m): no Angular build failures.
- Version on development: **2.1.183** (menu offer photo crop #429 already in changelog); `[Unreleased]` empty — no bump.
- Divergence at start: `origin/development` **572a9c24d** ahead **4** / behind **1** vs `origin/master` **15ae66b41**. Merged `master` into `development` (**80c359656**), then promoted with `AGENT_PROMOTE=1 AGENT_PROMOTE_FORCE=1 AGENT_PROMOTE_WAIT_DEPLOY=1`.
- **Merge SHA:** `a8f062bcf` (`origin/master`). **Release:** https://github.com/satisfecho/pos/releases/tag/v2.1.183
- **Deploy:** https://github.com/satisfecho/pos/actions/runs/38076648443 — success.

## Problem / goal
Human asks to **ship now** to production (amvara9 / satisfecho.de): promote tested work from **`development`** to **`master`** and confirm deploy. Explicit production request under **`.cursor/rules/git-development-branch-workflow.mdc`** and **`docs/agent-loop.md`** (urgent / deploy-now path).

At planning time (**2026-10-10** UTC): `origin/development` (**572a9c24d**, app version **2.1.183**) is ahead of `origin/master` (**15ae66b41**, **2.1.182**) by about **4** commits and behind by **1** (diverged — not a simple fast-forward). Confirm tip SHAs and ahead/behind counts before merge; do not force-push.

Pending on development includes the menu offer photo crop fix (**#429** / **2.1.183**). `[Unreleased]` is empty at planning time — no further bump expected unless new material lands before promote.

See **`docs/0001-ci-cd-amvara9.md`**, **`scripts/promote-development-to-master.sh`**, **`.cursor/rules/commit-changelog-version.mdc`**. Prior similar work: **#428**, **#426**, **#424**.

## High-level instructions for coder
- Sync **`development`** (`./scripts/git-sync-development.sh`). Confirm local smoke: landing HTTP **200** on HAProxy port; `docker logs --since 10m pos-front` — no Angular build failures.
- **Changelog / version:** If `[Unreleased]` has material user-facing items, cut a new semver section, bump **`front/package.json`** + lockfile, run **`node front/scripts/get-commit-hash.js`**, and commit **`commit-hash.ts`** with the bump on **`development`**. Skip empty churn bumps (current tip already **2.1.183**).
- Because the issue says **ship now**, promote is allowed outside the daily 24h window: use **`AGENT_PROMOTE_FORCE=1 ./scripts/promote-development-to-master.sh`** (or equivalent merge **`development` → `master`** + **`git push origin master`**). Resolve divergence safely (merge **`master` into `development`** first if needed); **never** force-push **`master`**.
- Monitor **Deploy to amvara9**. If GHA fails, use documented manual deploy fallback; do not claim success until production reflects the promoted tip. Watch for CORS/`PRODUCTION=true` pitfalls from the **#424** / **2.1.180** hotfix path.
- Optional: publish a GitHub release matching the shipped semver from **`CHANGELOG.md`** if a version was cut (expect **v2.1.183** if that is the tip being promoted).
- Post-deploy smoke on production: `/` and `/api/health` **200**; landing version/footer hash match the promoted commit.
- This is **release/ops**, not feature coding — fix only blockers that prevent a safe promote. Append **Testing instructions** with merge SHA, workflow/manual deploy evidence, and smoke results.
- Comment on issue **#430** when promote + deploy are done (or if blocked by divergence/conflicts).

## Testing instructions

1. Confirm `origin/master` tip is merge **`a8f062bcf`** (subject includes release through **2.1.183**).
2. Confirm GitHub Actions run **38076648443** (“Deploy to amvara9”) conclusion **success**: https://github.com/satisfecho/pos/actions/runs/38076648443
3. Confirm release **v2.1.183**: https://github.com/satisfecho/pos/releases/tag/v2.1.183
4. Production smoke (already run by coder at **2026-10-10T18:42:50Z** UTC):
   - `curl -s -o /dev/null -w "%{http_code}" https://satisfecho.de/` → **200**
   - `curl -s -o /dev/null -w "%{http_code}" https://satisfecho.de/api/health` → **200**; body `{"status":"ok"}`
   - Landing HTML includes `<meta name="app-version" content="2.1.183">`
5. Optional: open https://satisfecho.de/ and check footer shows **2.1.183**.
