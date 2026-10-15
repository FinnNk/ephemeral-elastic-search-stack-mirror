#!/bin/sh
# k3d invokes this before k3s starts. Reconcile in the background so API/DNS
# startup order cannot block the node. Use its existing operator kubeconfig.

reconcile() {
    address=$(timeout 5 nslookup relevance-nexus 2>/dev/null |
        awk '/^Name:/ { answer=1; next } answer && /^Address: / { print $2; exit }')
    if ! printf '%s\n' "$address" | awk -F. '
        NF != 4 { exit 1 }
        { for (i=1; i<=4; i++) if ($i !~ /^[0-9]+$/ || $i > 255) exit 1 }'; then
        echo 'Waiting for the Nexus Docker IPv4 address'
        return 1
    fi
    observed=$(kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml --request-timeout=5s \
        -n platform get endpointslice nexus -o \
        'jsonpath={.metadata.labels.endpointslice\.kubernetes\.io/managed-by}{"|"}{.metadata.labels.kubernetes\.io/service-name}{"|"}{.endpoints[0].addresses[0]}{"|"}{.metadata.resourceVersion}' 2>/dev/null) || {
        echo 'Waiting for the Kubernetes API and Nexus EndpointSlice'
        return 1
    }
    IFS='|' read -r manager service previous revision <<EOF
$observed
EOF
    if [ "$manager" != relevance-lab ] || [ "$service" != nexus ]; then
        echo 'Refusing to change a Nexus EndpointSlice with unexpected ownership'
        return 1
    fi
    [ "$previous" != "$address" ] || return 0
    case "$revision" in ''|*[!0-9]*) echo 'Invalid Nexus EndpointSlice revision'; return 1 ;; esac
    # Optimistic concurrency prevents overwriting a concurrent operator change.
    patch="[{\"op\":\"test\",\"path\":\"/metadata/resourceVersion\",\"value\":\"$revision\"},{\"op\":\"replace\",\"path\":\"/endpoints\",\"value\":[{\"addresses\":[\"$address\"],\"conditions\":{\"ready\":true}}]}]"
    if kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml --request-timeout=5s \
        -n platform patch endpointslice nexus --type=json -p "$patch" >/dev/null 2>&1; then
        echo "Refreshed Nexus cluster route: $previous -> $address"
    else
        echo 'Nexus route changed concurrently or the API is unavailable; retrying'
        return 1
    fi
}

case "${1:-}" in
    --once) reconcile ;;
    --watch)
        last_message=''
        while :; do
            message=$(reconcile)
            # Log transitions, not every poll. There is no output when unchanged.
            if [ -n "$message" ] && [ "$message" != "$last_message" ]; then
                printf '%s %s\n' "$(date -Iseconds)" "$message"
            fi
            last_message=$message
            sleep 15
        done ;;
    *)
        # BusyBox cannot match a shell script reliably with -x alone. Verify
        # both the PID and its command line before treating a watcher as alive.
        pid=$(cat /run/lab-nexus-route.pid 2>/dev/null || true)
        case "$pid" in
            ''|*[!0-9]*) ;;
            *) if kill -0 "$pid" 2>/dev/null &&
                tr '\000' ' ' < "/proc/$pid/cmdline" | grep -F -q "$0 --watch"; then
                    exit 0
               fi ;;
        esac
        start-stop-daemon -S -o -b -m -p /run/lab-nexus-route.pid \
            -x "$0" -O /var/log/lab-nexus-route.log -- --watch ;;
esac
