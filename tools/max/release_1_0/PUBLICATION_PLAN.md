# GitHub publication plan — local preparation only

Repository: `karigardarsson/Synthack-OS`, public fork of `Angelo-politek/Synthack-OS`; default branch `main`. Origin/upstream URLs were inspected. Public REST release listing returned `[]`; remote heads are `main`, `syntakt-max`, `syntakt-max2-compat`, `syntakt-upstream-max-fm4`. The requested tag and `syntakt-max-release` branch are absent remotely. Local upstream v0.x tags are unrelated; do not push them with --tags. Authenticated draft-release visibility and write permission were not verified: `gh` was not found in this shell. Recheck both immediately before publication.

Proposed source branch: push the reviewed `codex/max-builder-windows` commit as **syntakt-max-release**, without changing the default branch or existing MAX/MAX2/FM4 branches. Tag exactly that reviewed source commit as **syntakt-max-v1.0**. Keep source history intact; it contains separately labelled FM4 research, which is excluded from the MAX firmware and Windows manifest.

Release title: **Syntakt MAX 1.0**. Proposed classification: **prerelease**, `latest=false`, reflecting experimental community firmware. Final reviewer may choose a normal release; the commands below intentionally use prerelease. Proposed URL: https://github.com/karigardarsson/Synthack-OS/releases/tag/syntakt-max-v1.0 . This URL is a plan, not an existing release.

Asset: `out/release-prep-runtime-rc/Syntakt-MAX-1.0-Windows-x64.zip`, SHA-256 `92d83f258a26d80cbedcaa1ddb5763f61ecbda1df1a06da4e061fe4a12db675d`. Its included SHA256SUMS.txt verifies the contents. Only this ZIP is proposed as an upload; all four fingerprints are in the release body. Keep the complete ZIP's notices. No raw EXE-only upload and no firmware assets.

Release description: [GITHUB_RELEASE.md](GITHUB_RELEASE.md), with absolute tag-specific GitHub links so they work in the release body. Source docs now record Kári's latest successful EXE GUI test. **The validated ZIP was not repacked**: its internal documents remain the earlier validation snapshot, which the release description explicitly explains. New local source docs supersede that earlier statement about pending manual GUI testing. EXE, ZIP, firmware, manifest and builder logic remain unchanged.

## Publication commands — NOT RUN

Run in the WSL checkout with GitHub CLI installed and authenticated for `karigardarsson/Synthack-OS`. No installation or authentication-state changes were made during preparation. Set RELEASE_COMMIT to the exact final documentation commit printed in the preparation report (do not substitute an unrelated later HEAD).

```bash
set -eu
cd /home/kari/Synthack-OS-upstream-max-fm4
REPO=karigardarsson/Synthack-OS
RELEASE_COMMIT='<final preparation commit from report>'
TAG=syntakt-max-v1.0
BRANCH=syntakt-max-release
ASSET=out/release-prep-runtime-rc/Syntakt-MAX-1.0-Windows-x64.zip
gh auth status
gh release list --repo "$REPO" --limit 100
git ls-remote --heads --tags origin
```

Stop if any release/draft/tag already uses TAG; inspect it instead of duplicating. Stop if BRANCH already exists at an unexpected commit. Check the remote URL is the fork and that the working tree is clean. The remaining commands are publication actions and require Kári's final authorization:

```bash
test -z "$(git status --porcelain)" || exit 1
test "$(git rev-parse HEAD)" = "$RELEASE_COMMIT" || exit 1
test "$(git remote get-url --push origin)" = https://github.com/karigardarsson/Synthack-OS.git || exit 1
printf '%s  %s\n' '92d83f258a26d80cbedcaa1ddb5763f61ecbda1df1a06da4e061fe4a12db675d' "$ASSET" | sha256sum -c - || exit 1
git push origin "$RELEASE_COMMIT:refs/heads/$BRANCH"
git tag -a "$TAG" "$RELEASE_COMMIT" -m 'Syntakt MAX 1.0'
git push origin "refs/tags/$TAG"
gh release create "$TAG" "$ASSET" --repo "$REPO" --verify-tag \
  --title 'Syntakt MAX 1.0' \
  --notes-file tools/max/release_1_0/GITHUB_RELEASE.md \
  --prerelease --latest=false
gh release view "$TAG" --repo "$REPO" --json url,tagName,isDraft,isPrerelease,assets
git ls-remote origin "refs/heads/$BRANCH" "refs/tags/$TAG" "refs/tags/$TAG^{}"
```

No force pushes; do not run `git push --tags`, change main, create an upstream PR, or upload other out/ contents. For an interrupted attempt, inspect the remote branch/tag/release before resuming; do not create a second release or overwrite a different tag.

## Preparation checks

Public fork identity/visibility, remote refs, no public release, seven feature groups, explicit credits, hashes, complete licenses, source history filename audit, ZIP allowlist/internal checksums and embedded EXE identity reviewed. Protected files are compared against `03b2eec2aaa2198991a9b327e189769e86864ac2`. Exact archive validation details are kept in the local ignored publication audit. No remote mutation or new tag occurs in this run.
