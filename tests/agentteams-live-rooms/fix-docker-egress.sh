#!/usr/bin/env bash
# Allow AgentTeams docker bridge (172.18.0.0/16) to reach the public internet.
# Nested Cloud VMs often have iptables-legacy FORWARD policy DROP while docker
# writes the matching ACCEPT rules only to iptables-nft. Higress then cannot
# call the LLM upstream (api.deepseek.com) and Manager chat hangs.
set -euo pipefail

BRIDGE="${AGENTTEAMS_DOCKER_BRIDGE:-br-8b0a57af09b5}"
CIDR="${AGENTTEAMS_DOCKER_CIDR:-172.18.0.0/16}"

if ! command -v iptables-legacy >/dev/null 2>&1; then
  echo "iptables-legacy not found" >&2
  exit 1
fi

if ! ip link show "$BRIDGE" >/dev/null 2>&1; then
  echo "bridge $BRIDGE not found; set AGENTTEAMS_DOCKER_BRIDGE" >&2
  exit 1
fi

run() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  else
    sudo -n "$@"
  fi
}

insert_if_missing() {
  local table="$1"
  shift
  local -a check=("$@")
  # Drop the insert index from the check (FORWARD 1 <rule> → FORWARD <rule>).
  if [ "${check[0]}" = "FORWARD" ] || [ "${check[0]}" = "POSTROUTING" ]; then
    local chain="${check[0]}"
    unset "check[0]"
    local rest=("${check[@]}")
    if [ "${rest[0]}" = "1" ]; then
      rest=("${rest[@]:1}")
    fi
    if [ -n "$table" ]; then
      if run iptables-legacy -t "$table" -C "$chain" "${rest[@]}" 2>/dev/null; then
        return 0
      fi
      run iptables-legacy -t "$table" -I "$chain" 1 "${rest[@]}"
    else
      if run iptables-legacy -C "$chain" "${rest[@]}" 2>/dev/null; then
        return 0
      fi
      run iptables-legacy -I "$chain" 1 "${rest[@]}"
    fi
    return 0
  fi
  echo "unexpected rule: $*" >&2
  exit 1
}

insert_if_missing "" FORWARD 1 -i "$BRIDGE" -j ACCEPT
insert_if_missing "" FORWARD 1 -o "$BRIDGE" -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
insert_if_missing nat POSTROUTING 1 -s "$CIDR" ! -o "$BRIDGE" -j MASQUERADE

echo "legacy FORWARD/MASQUERADE installed for $CIDR via $BRIDGE"
