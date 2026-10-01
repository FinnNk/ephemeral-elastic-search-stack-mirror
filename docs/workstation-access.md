# Connect a workstation to the lab

The lab uses its own certificate authority (CA). Trust its public certificate to verify HTTPS connections to Gitea and the other web services.

## Get the certificate

Ask the lab operator for **`root.pem`**, or copy it from `.lab/https-ingress/root.pem` on the machine hosting the lab. On the current Windows host that is `D:\codex\Ephemeral Elasticsearch\.lab\https-ingress\root.pem`. The CA is created by `python lab/https_ingress.py install`. Only the public `root.pem` is needed; the private key stays on the host.

The examples use a local lab: `gitea.localhost` resolves to your own machine. A remote workstation needs a reachable hostname, DNS and a certificate issued for that hostname; copying the certificate alone does not make a `.localhost` address reach the lab over the LAN.

## Configure Git

You can trust the certificate for just this clone without changing your system trust store. Keep `root.pem` at a permanent absolute path.

**Windows — PowerShell, Git for Windows**

```powershell
$labCa = (Resolve-Path "C:/path/to/root.pem").Path
git -c http.sslBackend=openssl -c http.sslCAInfo="$labCa" clone https://gitea.localhost:34443/elastic-agent/delivery-source.git
cd delivery-source
git config http.sslBackend openssl
git config http.sslCAInfo "$labCa"
git ls-remote origin HEAD
```

The explicit OpenSSL backend avoids dependence on Git for Windows' choice of certificate store. These saved settings apply to this repository only.

**Linux and macOS — shell**

```sh
lab_ca="/absolute/path/to/root.pem"
git -c http.sslCAInfo="$lab_ca" clone https://gitea.localhost:34443/elastic-agent/delivery-source.git
cd delivery-source
git config http.sslCAInfo "$lab_ca"
git ls-remote origin HEAD
```

A successful `ls-remote` prints a commit SHA and `HEAD`. Gitea may also ask you to authenticate; use your own account and a token with repository-read access if required. A certificate verification failure occurs before authentication: check the file path and server hostname rather than disabling verification. Git documents the [CA file setting](https://git-scm.com/docs/git-config#Documentation/git-config.txt-httpsslCAInfo).

## Trust the certificate for a browser

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
