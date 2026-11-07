#!/usr/bin/env bash
set -euo pipefail

REPO="${REPO:-SKYwalker-0828/broky_data}"
BRANCH="${BRANCH:-main}"

if [[ -z "${GH_TOKEN:-}" ]]; then
  echo "GH_TOKEN is required" >&2
  exit 1
fi

payload=$(cat <<'JSON'
{
  "required_status_checks": null,
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 0
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true,
  "lock_branch": false,
  "allow_fork_syncing": true
}
JSON
)

if gh api -X PUT "repos/${REPO}/branches/${BRANCH}/protection" --input - <<<"$payload" >/dev/null; then
  echo "Branch protection applied to ${REPO}:${BRANCH}"
else
  echo "Failed. Private repos on GitHub Free may require GitHub Pro." >&2
  exit 1
fi
