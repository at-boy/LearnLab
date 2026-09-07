# Interactive Secret Resolution Design

**Status:** Proposed for review

## Purpose

Remove the need to export a Proxmox token secret manually in every shell while
preserving LearnLab's rule that secret values never enter source, curriculum,
TOML, SQLite, logs, exceptions, snapshots, or command history.

## Resolution Order

For a configured `token_secret_env` name:

1. Use a non-empty value already present in the process environment.
2. When attached to an interactive terminal, prompt securely with hidden input
   for this invocation only.
3. In non-interactive mode, fail with a concise message naming the missing
   environment variable and supported input mechanism.

The profile still stores only the environment-variable name. No remember/save
option is provided.

## CLI Behavior

Commands that need a provider call a shared `SecretResolver`. The prompt is
shown only after profile parsing and only when the selected course actually
requires a provider. Pure `none` courses, listing, progress, and offline
validation never prompt.

The prompt identifies the profile and environment-variable name, accepts hidden
input, rejects empty input, and returns the secret in memory. A Ctrl-C or EOF
exits with code 2 before any provider request or state mutation.

For automation, `--token-stdin` is an explicit opt-in on provider-using commands.
It reads one newline-terminated secret from stdin and is mutually exclusive with
interactive prompting. It exists for password-manager pipelines and must never
echo the value. Plain non-TTY stdin is not consumed implicitly.

## Secret Lifetime and Redaction

The resolved value is added immediately to the existing redaction set and is
not cached globally. It lives only for the command process. Errors from prompt,
configuration, HTTP, SSH, and lifecycle paths pass through existing redaction.
Tests use sentinel secrets and assert their absence from all output.

## Security Boundaries

- No `.env` loading and no secret file option.
- No shell command configured in TOML.
- No desktop keyring dependency in this first version.
- No secret is placed in argv, URLs, structured state, or JSON output.
- Environment variables remain the recommended unattended mechanism.
- Documentation may show password-manager piping into `--token-stdin` without
  prescribing one vendor.

## Testing

- Unit tests cover environment, hidden prompt, stdin, empty input, cancellation,
  and non-interactive failure.
- CLI tests prove provider-free paths never invoke the resolver.
- Redaction tests cover provider and unexpected prompt errors.
- Tests prove environment input wins and suppresses all prompting.
- Existing lifecycle interruption and secret tests remain passing.

## Out of Scope

- Persisting secrets or integrating a platform keyring.
- Refreshable OAuth-style credentials.
- Multiple secrets per provider profile.

## Success Criteria

An interactive learner can run a provider command, enter the token once through
a hidden prompt for that process, and proceed without shell exports or secret
persistence; unattended callers retain a deterministic environment/stdin path.
