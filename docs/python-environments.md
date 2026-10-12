# Prepare Python with uv

Run host installer and evaluation commands from the repository root using
`uv run --locked python …`. `uv` selects the Python version in `.python-version`,
creates `.venv` and installs the dependencies recorded in `uv.lock`. You do not
need to activate the environment. The host is pinned to Python 3.12.12; container
images retain their existing Python versions.

## Install and run

On macOS, install uv with `brew install uv`. On Windows, use
`winget install --id astral-sh.uv -e`, or the
[official installer](https://docs.astral.sh/uv/getting-started/installation/).
Use uv 0.11.21 or later. The image builds use the verified 0.11.21 image digest.

From a clean checkout, after configuring any corporate trust below:

```sh
uv sync --locked
uv run --locked python lab/fresh_install.py --help
```

Expect Python 3.12.12 and a `.venv` environment. Repeat syncs reuse the download
cache and retain the lockfile. `--locked` refuses dependency changes that have
not been recorded. To run notebook tools locally, use `uv sync --locked --group
notebook` and `uv run --locked --group notebook python …`.

After pulling an accepted change, run `uv sync --locked` again. If an old Conda
or virtual environment is active, uv still uses the project's `.venv`; do not
pass `--active`. Keep external `.lab/python-libs` out of `PYTHONPATH` when
verifying this environment, otherwise those packages can shadow locked packages.

## Run unit tests

Run tests from the checkout containing the change. Use `uv run --locked` so the
interpreter and packages come from that checkout's `.venv`. A bare `python` or
the desktop app's bundled interpreter can select a different environment after
a restart. These unit checks use fixtures; Docker and a running lab are not
prerequisites.

For delivery and promotion changes, use PowerShell from the repository root:

```powershell
uv sync --locked
$env:PYTHONPATH = @('lab', 'evaluation', 'judgements') -join [IO.Path]::PathSeparator
$testTemp = Join-Path (Get-Location).Path '.lab/unit-test-temp'
New-Item -ItemType Directory -Force -Path $testTemp | Out-Null
$env:TEMP = $testTemp
$env:TMP = $testTemp
uv run --locked python -m unittest test_delivery_gates test_delivery_operations test_production_release test_release_control test_delivery_feedback test_production_load_gate -q
```

The repository import paths let tests import lab modules directly. They do not
add external dependency folders. The temporary directory keeps fixture files
inside the writable checkout. Expect a final `OK` and exit status zero; tests
of rejected requests can print expected errors before that summary.

On macOS or Linux, run the same checks from the repository root:

```sh
uv sync --locked
PYTHONPATH=lab:evaluation:judgements uv run --locked python -m unittest test_delivery_gates test_delivery_operations test_production_release test_release_control test_delivery_feedback test_production_load_gate -q
```

Choose other test modules for other changes. For the complete lab unit suite,
use `python -m unittest discover -s lab -p 'test_*.py' -q` through the same uv
environment and import paths. Live verification is separate; leave opt-in
settings such as `LAB_VERIFY_REDIS` unset for unit runs.

If imports fail, check the actual interpreter and dependency locations:

```sh
uv run --locked python -c "import sys, azure.storage.blob, yaml; print(sys.executable); print(azure.storage.blob.__file__); print(yaml.__file__)"
```

The paths should point into this checkout's `.venv`. Clear external
`.lab/python-libs` entries from `PYTHONPATH`, then repeat `uv sync --locked`.
Those retained packages can have native extensions for a particular Python
version and may not contain every locked dependency.

If a restricted Windows shell cannot write uv's normal cache, set a writable
cache before syncing:

```powershell
$env:UV_CACHE_DIR = Join-Path (Get-Location).Path '.lab/uv-cache'
uv sync --locked
```

Some unit tests start an isolated HTTP server on loopback. `WinError 10013`
from those fixtures can mean the execution sandbox denied local sockets.
Run that same bounded test command with the required execution permission;
changing package dependencies will not fix a socket denial. Report a blocked
fixture separately from an assertion failure.

## Corporate certificates

Configure trust **before** the first Python or package download. On a Mac whose
corporate CA is already trusted in Keychain, use:

```sh
export UV_SYSTEM_CERTS=true
uv sync --locked
```

On Windows with the corporate CA in the Windows trust store:

```powershell
$env:UV_SYSTEM_CERTS = 'true'
uv sync --locked
```

If your organisation supplies a PEM bundle instead, `SSL_CERT_FILE` must point
to a combined bundle containing public roots **and** the corporate roots. It
replaces uv's default certificate source. On macOS, for example:

```sh
export SSL_CERT_FILE="$HOME/certs/public-and-corporate-ca.pem"
uv sync --locked
```

The path is illustrative; obtain the bundle from your organisation. After an
owned foundation installation, the lab retains a combined bundle that can be
reused from the repository root:

```sh
SSL_CERT_FILE="$PWD/.lab/host-ca-bundle.pem" uv sync --locked
uv run --locked python lab/fresh_install.py --corporate-ca "$HOME/certs/Corporate Root CA.pem"
```

The installer uses the locked certifi public roots plus the supplied corporate
PEM when preparing downloads and child processes. The corporate PEM is not
committed. The generated bundle contains public certificates, not CA private keys.
See [uv certificate support](https://docs.astral.sh/uv/concepts/authentication/certificates/).

Docker Desktop and k3d need their own registry trust. uv does not change their
trust stores or fix a registry's 403 response. Follow [fresh installation](fresh-install.md)
for those prerequisites. Python image builds use the supplied combined CA bundle
before uv downloads packages; source API builds retain their BuildKit `lab_ca`
secret. Certificate verification remains enabled.

## Redis and separate model tooling

The host lock and Search API lock both include `redis==6.4.0`. Redis's server
image uses Docker/k3d registry trust, including corporate CAs during fresh setup.
Its read-only lookup stays on the cluster network, with existing namespace
restrictions and timeouts; no corporate certificate is needed for that internal
Redis connection. This migration does not change its authentication or data bindings.

Container builds use `uv pip` against pinned dependency files. The Search API
file is exported with package hashes from its separate uv lock.
Those files remain owned by their respective service; this avoids adding host
catalogue tooling to a small Search API image. Existing model research packs use
separate uv environments because their NumPy and GPU requirements differ from
the CPU lab. Preserve their frozen dependency files and follow their own guides.

Dependency updates belong in a reviewed batch: edit `pyproject.toml`, run
`uv lock`, then verify with `uv sync --locked`. Do not update the lockfile as part
of a demonstration or an installation retry.
