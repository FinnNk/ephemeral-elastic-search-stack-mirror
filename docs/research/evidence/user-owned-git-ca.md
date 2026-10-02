# User-owned Git CA bundle — 2 October 2026

The Windows host now uses a user-owned OpenSSL bundle for Git. It preserves the
standard roots and adds the public lab CA; Git's installed bundle is unchanged.

| Check | Result |
| --- | --- |
| Bundle installation | 151 distinct CA certificates; global Git OpenSSL/CA settings point to the user-owned file |
| Gitea | `git ls-remote` over HTTPS succeeded with verification enabled and no per-command CA setting; the check used lab-agent authentication |
| Standard roots | HTTPS to GitHub returned 200 using the same bundle |
| Focused tests | Three passed: preserve/deduplicate roots and UTF-8 comments; reject private keys/incomplete PEM; repeat/refresh installation without changing the base, using isolated Git configuration |
| Dependency boundary | The helper ran with `python -S`; no third-party packages are required for setup |

The initial live setup exposed UTF-8 comments in Git's standard bundle. The helper
now validates and retains its PEM certificate blocks, excluding comments, and the
root-preservation test covers that case. The first attempt failed before writing
user files or Git settings; the repaired setup and live checks then passed.

The [verification record](user-owned-git-ca.json) pins the resulting bundle hash
and observed source HEAD. No credentials or private keys are retained in this
record. Your own checkout should authenticate with your own Gitea identity.

Only Windows host behaviour was checked. Browser, Python, Java and container
trust are separate; a working Git command does not establish their trust. The
helper's refresh test used temporary CA certificates and isolated configuration,
not a live CA rotation or a real Git upgrade.

The matching [source README checks](user-owned-git-ca-source-checks.json) passed:
build/release CI and the protected documentation-only relevance decision. The
source application and gate policy are unchanged.
