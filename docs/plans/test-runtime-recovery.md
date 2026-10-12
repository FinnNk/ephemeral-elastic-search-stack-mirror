# Restore repeatable unit-test execution

Use the project's `.venv` through `uv run --locked` for future validation.
The [Python guide](../python-environments.md#run-unit-tests) owns the commands;
`AGENTS.md` directs subsequent agents there before declaring dependencies missing.

## Evidence and corrections

On 12 October 2026, the Windows checkout already contained a working locked
Python 3.12.12 environment. The earlier test attempt selected the desktop app's
bundled interpreter, which did not contain the lab's Azure SDK dependencies.
The retained `.lab/python-libs` folder provided a partial alternative with Python
3.12 native extensions, but lacked PyYAML. It is not the standard test environment.

The locked environment supplied both Azure Blob and PyYAML from `.venv`.
Repository import paths resolved direct lab imports. A writable fixture temporary
directory and execution permission for isolated loopback HTTP fixtures addressed
the Windows sandbox restrictions.

The recovered test run exposed an invalid direct production request that passed
validation before failing in the worker. Validation now directs it to the
existing production candidate/release process. Two production-load fixture
assertions now verify both pinned deployment definitions as well as the target.

The six suites in the guide ran **64 tests, all passed**, in 7.988 seconds on
the corrected code. Expected rejected-request messages appeared in the output.
No live deployment, model inference or performance evaluation was run. This is
Windows unit-test evidence; the equivalent Mac command has not been executed here.

## Next detailed plan

1. Review and accept the runtime documentation and validation correction.
2. Resume the source-to-production walkthrough using the merged per-variant checks.
3. On the Mac, use its native locked uv environment and run the relevant fixtures
   before claiming native verification. Keep any corporate certificate setup from
   the Python guide in place for downloads.
