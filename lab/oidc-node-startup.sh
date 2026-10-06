#!/bin/sh
# Docker regenerates /etc/hosts on restart. k3d runs this hook before k3s.
set -eu
read -r address hostname < /etc/rancher/k3s/lab-oidc-host
[ -n "$address" ] && [ "$hostname" = "identity.localhost" ]
temporary=$(mktemp)
trap 'rm -f "$temporary"' EXIT HUP INT TERM
awk '$0 !~ /# relevance-lab-oidc$/ { print }' /etc/hosts > "$temporary"
printf '%s %s # relevance-lab-oidc\n' "$address" "$hostname" >> "$temporary"
# /etc/hosts is a Docker-managed mount; replace its contents, not the file.
cat "$temporary" > /etc/hosts
echo "Restored lab OIDC issuer resolution before k3s startup"
