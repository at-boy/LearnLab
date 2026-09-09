# Course Authoring and Validation Design

**Status:** Implemented and verified offline; no live acceptance claim

## Purpose

Give course authors one reliable workflow for discovering and validating all
curriculum before it is packaged or run. Validation must catch structural,
semantic, packaging, and provider-template compatibility problems without
changing infrastructure.

## Current Problems

- The repository has an authoring tree under `collections/` and a packaged copy
  under `src/learnlab/collections/`; manual copying can drift.
- `CurriculumCatalog` loads one known course path but cannot enumerate a whole
  catalog.
- `requirements` values are parsed but not enforced.
- `proxmox.vm` does not distinguish NixOS, Debian 13, installed tools, or other
  guest-image properties.
- There is no user-facing `learnlab validate` command.
- Existing tests detect packaging drift but do not give authors a consolidated,
  course-oriented report.

## Decisions

### One canonical curriculum tree

`src/learnlab/collections/` becomes the only maintained curriculum tree because
it is already the installed runtime location. The top-level `collections/` tree
is removed after all reviewed content is migrated. Repository tools and tests
must load the same packaged resources that users receive.

### Catalog discovery

`CurriculumCatalog.list_courses()` returns immutable course summaries in stable
collection/course order. Discovery validates directory layout and reports
malformed entries rather than silently skipping them.

### Offline validation

`learnlab validate [COURSE]` validates one course or the entire catalog. It must
not load settings, resolve secrets, open the state database, or contact a
provider. It reports all independent findings in one run and exits:

- `0` when every selected course passes;
- `1` for curriculum findings;
- `2` for invalid command usage;
- `3` for provider/operational failure in online mode.

Checks include strict schema loading, directory/ID consistency, known provider
checks, effective environment compatibility, unique identifiers, regex
compilation, and lightweight authoring lint. Authoring lint flags risky or
likely ineffective commands but does not pretend to prove guest behavior.

### Abstract guest requirements

Environment policy gains an optional, provider-neutral `guest_capabilities`
list for VM scopes, such as `os.nixos`, `os.debian.13`, `tool.curl`, or
`feature.nested-virtualization`. Course YAML never contains a profile name,
template VMID, node, storage, network, URL, or secret.

Each Proxmox profile declares the capabilities its configured template
provides. The initial implementation retains one template per profile; a course
is compatible when all effective guest capabilities are present. This is a
small contract that can later select among profile-local image definitions.

The existing `requirements` field is deprecated in favor of
`guest_capabilities` and rejected after a documented migration. Until removal,
the loader maps it to guest capabilities and warns once per course.

### Provider-aware validation

`learnlab validate [COURSE] --provider PROFILE` performs offline validation
first, then resolves only the named profile and secret. It checks capability
compatibility and invokes the existing read-only provider health check to
verify the configured template, node, storage, and network. It never allocates,
clones, starts, stops, modifies, or deletes resources.

### Reporting

Findings contain severity (`error` or `warning`), course path, source path,
message, and a short remediation. Human output is deterministic. A
`--format json` mode emits a versioned document for automation without secrets
or raw provider responses.

## Authoring Lint Scope

Initial warnings cover:

- unanchored yes/no regular expressions likely to accept unrelated prose;
- `remote-command` strings with interactive or unbounded forms;
- provider-check names absent from the built-in registry;
- manual confirmation used where an objective check is already present;
- VM courses with no OS guest capability;
- commands requiring tools not declared as guest capabilities when a known
  mapping exists.

Warnings never rewrite curriculum and can be promoted to errors later only by a
separate design decision.

## Security and Safety

- Offline validation has no configuration, state, secret, network, or provider
  dependency.
- Online validation is read-only and requires an explicit profile.
- Secret values are redacted from all findings and JSON.
- Provider-specific resource identities remain user configuration.
- Validation never claims that a course has passed live acceptance testing.

## Testing

- Unit tests cover discovery, aggregated findings, exit codes, JSON schema,
  capability migration, and lint rules.
- CLI tests prove offline mode never calls settings, state, secret, or provider
  factories.
- Provider tests prove online mode uses only health/read operations.
- Packaging tests prove the wheel contains the canonical curriculum tree.
- The complete offline suite, Ruff, mypy, wheel installation, and diff checks
  remain required.

## Out of Scope

- Mutating template probes or disposable-VM course execution.
- Multiple templates per profile.
- Multi-machine environment topology.
- Automatic curriculum rewriting.

## Success Criteria

An author can add a course only under `src/learnlab/collections/`, run one
command, receive all actionable static findings, optionally prove that a named
profile exposes a compatible existing template, and build a wheel containing
the exact validated curriculum.
