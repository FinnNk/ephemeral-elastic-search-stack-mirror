#!/bin/sh
# Run in a disposable k3s-image container; Kubernetes and DNS are fixtures.
set -eu
root=$(mktemp -d)
trap 'if [ -f /run/lab-nexus-route.pid ]; then kill "$(cat /run/lab-nexus-route.pid)" 2>/dev/null || true; fi; rm -rf "$root"' EXIT
export TEST_ROOT="$root"
mkdir "$root/bin"
cat > "$root/bin/nslookup" <<'EOF'
#!/bin/sh
printf 'Server: resolver\nAddress: 192.0.2.1:53\n\nName: relevance-nexus\nAddress: %s\n' "$(cat "$TEST_ROOT/address")"
EOF
cat > "$root/bin/kubectl" <<'EOF'
#!/bin/sh
case " $* " in
    *' get '*) [ ! -f "$TEST_ROOT/api-down" ] && cat "$TEST_ROOT/observed" ;;
    *' patch '*)
        [ ! -f "$TEST_ROOT/conflict" ] || exit 1
        printf '%s\n' "$*" > "$TEST_ROOT/patch"
        printf 'relevance-lab|nexus|%s|43' "$(cat "$TEST_ROOT/address")" > "$TEST_ROOT/observed" ;;
    *) exit 1 ;;
esac
EOF
chmod +x "$root/bin/"*
export PATH="$root/bin:$PATH"
script="$root/nexus-node-startup.sh"
sed 's/\r$//' /tests/lab/nexus-node-startup.sh > "$script"
chmod +x "$script"
printf '172.30.0.4' > "$root/address"
printf 'relevance-lab|nexus|172.30.0.9|42' > "$root/observed"
"$script" --once | grep '172.30.0.9 -> 172.30.0.4'
grep -q 'resourceVersion.*42' "$root/patch"
rm "$root/patch"
"$script" --once
[ ! -f "$root/patch" ]
printf 'foreign|nexus|172.30.0.9|42' > "$root/observed"
if "$script" --once; then echo 'Unexpected foreign ownership acceptance'; exit 1; fi
[ ! -f "$root/patch" ]
printf 'relevance-lab|nexus|172.30.0.9|42' > "$root/observed"
printf 'not-an-ip' > "$root/address"
if "$script" --once; then echo 'Unexpected invalid address acceptance'; exit 1; fi
[ ! -f "$root/patch" ]
printf '172.30.0.4' > "$root/address"
touch "$root/api-down"
if "$script" --once; then echo 'Unexpected unavailable API acceptance'; exit 1; fi
rm "$root/api-down"
touch "$root/conflict"
if "$script" --once; then echo 'Unexpected concurrent patch acceptance'; exit 1; fi
rm "$root/conflict"
"$script"
sleep 1
first=$(cat /run/lab-nexus-route.pid)
kill -0 "$first"
"$script"
[ "$(cat /run/lab-nexus-route.pid)" = "$first" ]
kill -0 "$first"
grep -q '172.30.0.4' "$root/observed"
printf '172.30.0.6' > "$root/address"
sleep 16
grep -q '172.30.0.6' "$root/observed"
kill "$first"
# Simulate a stale PID file whose PID has been reused by a different process.
printf '%s' "$$" > /run/lab-nexus-route.pid
"$script"
sleep 1
second=$(cat /run/lab-nexus-route.pid)
[ "$second" != "$$" ]
kill -0 "$second"
echo 'Passed: route changes, ownership, DNS/API failure, concurrency, periodic repair, one watcher and reused PID'
