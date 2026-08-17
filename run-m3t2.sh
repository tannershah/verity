#!/usr/bin/env bash
#
# Verity — Phase 3 / M3-T2 (recursive descent)
# Relays the SPRINT.md protocol between one working agent and one red-team agent.
# Prompts are Tanner's, verbatim from SPRINT.md, with M1T2 -> M3T2 substituted.
#
# Usage:  cd /path/to/verity && bash run-m3t2.sh
#
set -uo pipefail

REPO="${REPO:-$PWD}"
LOG="$REPO/runs/phase3-m3t2"
MODEL="opus"
EFFORT="max"          # low | medium | high | xhigh | max | ultracode | auto

cd "$REPO"
mkdir -p "$LOG"
: > "$LOG/cost.log"

# remember the branch we came from, for the commit list at the end
BASE=$(git rev-parse --abbrev-ref HEAD)
if [ "$BASE" = "phase3-m3t2" ]; then
  BASE=$(git branch --format='%(refname:short)' | grep -Ex 'main|master' | head -1)
fi

git rev-parse --verify phase3-m3t2 >/dev/null 2>&1 || git checkout -b phase3-m3t2
git checkout phase3-m3t2

CLAUDE_ARGS=(--model "$MODEL" --output-format json
             --permission-mode acceptEdits --allowedTools "Bash")

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" >&2; }

# Claude Code prints MCP chatter on stdout alongside the JSON result, so keep
# only the single line that is the JSON object.
run() { claude -p "$@" 2>/dev/null | grep -m1 '^{' || true; }

# ask <session_id> <outfile> <prompt>
ask() {
  local sid="$1" out="$2" prompt="$3" json
  json=$(run "$prompt" --resume "$sid" "${CLAUDE_ARGS[@]}")
  if ! jq -e . >/dev/null 2>&1 <<<"$json"; then
    log "FAILED at $out — raw response follows"
    printf '%s\n' "$json" >&2
    exit 1
  fi
  jq -r '.result'         <<<"$json" > "$LOG/$out"
  jq -r '.total_cost_usd' <<<"$json" >> "$LOG/cost.log"
}

# start <slot> <outfile> <prompt>   -> stores session id in the named slot
# A slash command consumes the whole prompt string, so /effort gets its own
# throwaway turn ($0, ~30ms) and the real bootstrap resumes into that session.
start() {
  local slot="$1" out="$2" prompt="$3" json sid
  json=$(run "/effort $EFFORT" "${CLAUDE_ARGS[@]}")
  if ! jq -e . >/dev/null 2>&1 <<<"$json"; then
    log "FAILED setting effort — raw response follows"
    printf '%s\n' "$json" >&2
    exit 1
  fi
  sid=$(jq -r '.session_id' <<<"$json")
  ask "$sid" "$out" "$prompt"
  printf -v "$slot" '%s' "$sid"
}

snap() { git add -A && git commit -q -m "m3t2: $1" || true; }
f()    { cat "$LOG/$1"; }

# ---------------------------------------------------------------- 01 / 02

log "01 working — bootstrap + proposal"
start WORKER 01-working-proposal.md \
"You are working on Verity. Read /.claude/Claude.md, README.md, /docs, and SPRINT.md to get a thorough understanding of the project and its current state. You are going to be working on Phase 3--Integration. This means building out M3T2, the recursive descent. This is a core mechanism that will define our final product, so it is crucial that we get this right on the first try. Carefully read through the current code and scaffolding for it, read through any research, and note any open questions and take your own ruling on them, recording the ruling and your reasoning. Then, give me a detailed proposal in prose for how you want to implement this. Note that a red-team agent will be working in sync with you."

log "02 red-team — bootstrap + test suite design"
start REDTEAM 02-redteam-testdesign.md \
"You are working on Verity. Read /.claude/Claude.md, README.md, /docs, and SPRINT.md to get a thorough understanding of the project and its current state. You are going to be red-teaming Phase 3--Integration. This is the build-out of M3T2, the recursive descent. This is a core mechanism that will define our final product, so it is crucial that we get this right on the first try and identify any potential errors that may arise. Carefully read through the current code and come up a test suite design in prose for me to look at and feed to the working agent to verify its implementation proposal. Note that a working agent will be working in sync with you."

# ---------------------------------------------------------------- 03 - 06

log "03 red-team — cross-reference"
ask "$REDTEAM" 03-redteam-crossref.md \
"Cross reference this design proposal with your red-team flags and report any of conern or any other issues you see: $(f 01-working-proposal.md)"

log "04 working — revise or argue"
ask "$WORKER" 04-working-revision.md \
"Here is what your red-team agent had to say about your proposal: $(f 03-redteam-crossref.md). Carefully read through what it had to say and then revise your proposal or argue why the concern is invalid."

log "05 red-team — green light"
ask "$REDTEAM" 05-redteam-greenlight.md \
"Here is what the working agent has for a response: $(f 04-working-revision.md). Give the green light and build will start--You will be on standby and will do a thorough investigation and edge-case analysis when the build is complete."

log "06 working — BUILD"
ask "$WORKER" 06-working-build.md \
"Here is the green light from red-team to build: $(f 05-redteam-greenlight.md). Start building."
snap "build"

# ---------------------------------------------------------------- 07 - 10

log "07 red-team — try to break it"
ask "$REDTEAM" 07-redteam-break.md \
"build is complete. Here is the summary the working agent gave: $(f 06-working-build.md). Do the thorough red-team analysis and try your best to find a break."

log "08 working — structural fixes"
ask "$WORKER" 08-working-fixes.md \
"This is what the red-team agent found broke in your product: $(f 07-redteam-break.md). Look at each one carefully, determine if it is truly an error, then make the correct structural fix, not a patch. Summarize the repairs/reasons for your actions."
snap "fixes"

log "09 red-team — final sweep"
ask "$REDTEAM" 09-redteam-sweep.md \
"Here is the report the working agent on the bugs you detected earlier: $(f 08-working-fixes.md). Do one last final sweep of the Phase 3 deliverables to ensure everything is in order and will function as expected and necessary."

log "10 working — cleanup + docs"
ask "$WORKER" 10-working-cleanup.md \
"Prepare to terminate this session. Make a sweep through the code you wrote/modified to ensure we have a clean, lean, modular, well-organized codebase that will be maintainable long-term. Make any necessary updates to documentation that have not already been done."
snap "cleanup"

# ---------------------------------------------------------------- report

{
  echo "# M3-T2 run — $(date)"
  echo
  echo "worker session:   $WORKER"
  echo "red-team session: $REDTEAM"
  echo "total cost:       \$$(paste -sd+ "$LOG/cost.log" | bc)"
  echo
  echo '## pytest'
  (cd "$REPO" && python -m pytest -q 2>&1 | tail -20)
  echo
  echo '## ruff'
  (cd "$REPO" && ruff check . 2>&1 | tail -10)
  echo
  echo '## commits'
  git log --oneline "$BASE..phase3-m3t2"
} > "$LOG/REPORT.md" 2>&1

log "done — $LOG/REPORT.md"