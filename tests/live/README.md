# Live Proxmox acceptance test

`test_proxmox_lifecycle.py` is a destructive acceptance test. It uses the
production provider to allocate, clone, start, inspect, stop, and delete a VM,
then verifies the VM is absent during `finally` cleanup.

It is skipped unless both confirmation variables are set:

```bash
LEARNLAB_RUN_LIVE_PROXMOX=1 LEARNLAB_LIVE_PROFILE=<named-profile> \
  python3.13 -m pytest tests/live -q
```

The named profile must exist in the XDG LearnLab configuration and its declared
secret environment variable must already be supplied to the process. Do not put
the token value in this file, test code, TOML, source files, SQLite, or shell
history. Run `python3.13 -m pytest -m 'not live' -q` for the normal offline
suite.
