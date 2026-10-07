# Connect a workstation to the lab

The lab uses its own certificate authority (CA). Trust its public certificate to verify HTTPS connections to Gitea and the other web services.

## Get the certificate

Ask the lab operator for **`root.pem`**, or copy it from `.lab/https-ingress/root.pem` on the machine hosting the lab. On the current Windows host that is `D:\codex\Ephemeral Elasticsearch\.lab\https-ingress\root.pem`. The CA is created by `python lab/https_ingress.py install`. Only the public `root.pem` is needed; the private key stays on the host.

The examples use a lab on your own machine. A remote workstation needs a reachable hostname, DNS and a certificate issued for that hostname; copying the certificate alone does not expose the lab over the LAN.

## Set up lab DNS once

The lab's CoreDNS service resolves the fixed platform names and any
`*.preview.relevance.test` name to `127.0.0.1`. Configure your workstation to send
only those domains to it. No hosts-file changes are needed when previews change.
Ask the operator to [install preview access](preview-access.md#install-on-the-lab-host) first.
For a fresh Mac, complete the `access` stage of [fresh installation](fresh-install.md)
before creating resolver files. Creating a base k3d cluster does not install DNS.

**Windows:** open PowerShell as Administrator, change to this lab repository's
root, then run:

```powershell
.\lab\workstation-dns.ps1 Install
```

The script installs two local name-resolution policy (NRPT) rules, preserves
other rules and clears the DNS cache. It rejects an existing conflicting lab
rule. Expect seven lines ending `-> 127.0.0.1`, including a previously unused preview
name. Check from a normal PowerShell with `.\lab\workstation-dns.ps1 Check`.
To remove just these rules, run the script's `Remove` action as Administrator.
The rules follow [Windows' domain-specific DNS mechanism](https://learn.microsoft.com/en-us/powershell/module/dnsclient/add-dnsclientnrptrule).

**macOS:** configure the two domain-specific resolver files below. If either
file already exists, inspect it and reconcile its settings before replacing it.
Run in a terminal:

```sh
sudo mkdir -p /etc/resolver
printf 'nameserver 127.0.0.1\n' | sudo tee /etc/resolver/localhost
printf 'nameserver 127.0.0.1\n' | sudo tee /etc/resolver/preview.relevance.test
sudo dscacheutil -flushcache
sudo killall -HUP mDNSResponder
python3 -c "import socket; print(socket.gethostbyname('lab-dns-check.preview.relevance.test'))"
```

Expect `127.0.0.1`. To undo these entries, remove the two files you created and
flush the cache again. This procedure has not been checked on a native Mac.

**Linux:** DNS integration depends on your network manager. With NetworkManager's
dnsmasq DNS plugin already enabled, add these domain forwarding lines to
`/etc/NetworkManager/dnsmasq.d/relevance-lab.conf`:

```text
server=/localhost/127.0.0.1
server=/preview.relevance.test/127.0.0.1
```

Run `sudo systemctl reload NetworkManager` to reload its DNS configuration and
test using Python's resolver as above. Remove the two forwarding lines and reload
to undo this setup. Do not replace your primary DNS server with the lab service: it serves
only lab domains. Other Linux resolver setups need equivalent domain forwarding;
native Linux integration remains unverified. See
[NetworkManager's DNS options](https://networkmanager.dev/docs/api/latest/NetworkManager.conf.html).

Name resolution and certificate trust are separate. Continue below to configure
Git and browser trust. If Docker or CoreDNS is stopped, lab names cannot be
resolved through these rules; other domains keep their normal DNS configuration.

## Configure Git once with a user-owned bundle

On macOS, start with Keychain trust and test `git ls-remote` using your installed
Git. Apple Git can use the system trust store. Use the bundle helper below only
with an OpenSSL-backed Git; it explicitly selects that backend. Do not transfer
Windows global Git TLS settings to a Mac. See [Mac setup](mac-setup.md) for the
host prerequisites and native acceptance checks.

On Windows, Git can use a user-owned OpenSSL CA bundle containing its standard
trusted roots and the lab root. After this setup, normal clone commands work
without extra certificate arguments. The settings apply to your Git user account.

With this lab repository available, run from its root in PowerShell. Replace the
example path if you copied `root.pem` elsewhere:

```powershell
python lab/git_ca.py --root "D:/codex/Ephemeral Elasticsearch/.lab/https-ingress/root.pem"
```

The helper uses Python's standard library and Git; it needs no Kubernetes access
or Python packages. It reads the current Git CA file, adds the public lab root,
writes `~/.config/relevance-lab/git-ca-bundle.pem` and sets Git's global
`http.sslBackend=openssl` and `http.sslCAInfo` to that file. It leaves Git's
installed bundle untouched and prints the new bundle path and certificate count.
A small JSON file beside the bundle records the source paths for refresh.

Then, from the folder where you want your application checkout:

```powershell
git clone https://gitea.localhost:34443/elastic-agent/delivery-source.git
cd delivery-source
git ls-remote origin HEAD
```

Gitea may ask you to authenticate; use your own account and a token with
repository-read access if required. A successful `ls-remote` prints a commit SHA
and `HEAD`. Certificate verification happens before authentication; check the
certificate path and server hostname if it fails.

If Git has no configured CA file, supply your standard PEM CA bundle using
`--base-bundle`. You can also use this option to select an existing corporate
bundle explicitly. The helper adds the lab root to those certificates, rather
than replacing them with the lab root alone.

This path was verified on Windows. On Linux or macOS with an OpenSSL-backed Git,
the helper can be run with `python3`; supply `--base-bundle` if neither Git nor
Python identifies the standard CA file. Other Git TLS backends may use their
system certificate store instead. The per-repository alternative below requires
no global Git change.

### Refresh or remove Git trust

Rerun the same helper after a lab CA replacement or an update to the standard
bundle. It reloads the recorded standard bundle and current `root.pem`, replacing
the old lab root rather than accumulating old lab certificates. If Git's standard
bundle moved, pass its new path with `--base-bundle`.

Repository settings and `GIT_SSL_CAINFO` can override the global bundle. To see a
repository's configured CA file, run `git config --show-origin --get http.sslCAInfo`.
An existing per-repository setting is left unchanged; remove it with
`git config --local --unset http.sslCAInfo` if you want that checkout to use the
user-owned bundle.

To return to Git's installation defaults, remove the two global settings:

```powershell
git config --global --unset http.sslCAInfo
git config --global --unset http.sslBackend
```

If you had custom global settings before setup, restore those values instead.
The user-owned files can then be removed if no application uses them.

## Alternative: trust only one checkout

Keep `root.pem` at a permanent absolute path. These commands explicitly trust it
for the clone and save the settings in that checkout only.

**Windows — PowerShell, Git for Windows**

```powershell
$labCa = (Resolve-Path "C:/path/to/root.pem").Path
git -c http.sslBackend=openssl -c http.sslCAInfo="$labCa" clone https://gitea.localhost:34443/elastic-agent/delivery-source.git
cd delivery-source
git config http.sslBackend openssl
git config http.sslCAInfo "$labCa"
git ls-remote origin HEAD
```

**Linux and macOS — shell**

```sh
lab_ca="/absolute/path/to/root.pem"
git -c http.sslCAInfo="$lab_ca" clone https://gitea.localhost:34443/elastic-agent/delivery-source.git
cd delivery-source
git config http.sslCAInfo "$lab_ca"
git ls-remote origin HEAD
```

Git documents the [CA file setting](https://git-scm.com/docs/git-config#Documentation/git-config.txt-httpsslCAInfo)
and TLS backend selection. Neither option disables certificate verification.

## Trust the certificate for a browser

Git's user-owned OpenSSL bundle does not install browser trust. Use this separate
step for browser access; Python, Java and containers may also use their own CA stores.

| Workstation | Action |
| --- | --- |
| Windows | In PowerShell, run `certutil -user -addstore Root "C:\path\to\root.pem"`. This trusts it for the current user. |
| macOS | Run `security add-trusted-cert -d -r trustRoot -k "$HOME/Library/Keychains/login.keychain-db" /absolute/path/to/root.pem`, or import it into the login keychain in Keychain Access and set its SSL trust. macOS may prompt for permission. |
| Ubuntu/Debian | Run the commands below to add it to the system CA store. Other distributions use different trust-store tools. |

```sh
sudo cp /absolute/path/to/root.pem /usr/local/share/ca-certificates/relevance-lab.crt
sudo update-ca-certificates
```

The Linux commands follow [Ubuntu's CA installation guide](https://ubuntu.com/server/docs/how-to/security/install-a-root-ca-certificate-in-the-trust-store/). A browser using its own certificate store, such as some Firefox configurations, may also need the certificate imported under its certificate-authority settings.

Restart the browser if necessary and open `https://gitea.localhost:34443/`. Expect the Gitea sign-in page without a certificate warning. On the host with the reference checkout, `python lab/https_ingress.py trust` automates the Windows or macOS import; Linux import remains manual. [HTTPS ingress](https-ingress.md) documents service addresses and installation.
