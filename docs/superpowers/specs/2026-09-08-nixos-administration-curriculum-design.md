# NixOS Administration Curriculum Design

**Status:** Proposed for review

## Purpose and Audience

Implement the original hands-on NixOS learning path for an experienced Debian
administrator who is new to NixOS. The course emphasizes the declarative mental
model, precise early instructions, meaningful failure guidance, safe
experimentation, and gradually reduced scaffolding.

## Curriculum Shape

Create a `nixos` collection with three ordered courses rather than one oversized
course:

1. `nixos/administration-foundations`
2. `nixos/nix-language-and-store`
3. `nixos/flakes-and-fleet`

All use a course-scoped disposable NixOS environment. Later courses declare the
earlier course as a learning prerequisite through course metadata; completion is
recommended and displayed, not used as an irreversible lockout.

## Course 1: Administration Foundations

Lessons cover first contact and system inspection; `configuration.nix`; options
and modules; declarative packages; `nixos-rebuild dry-build`, `test`, `boot`,
and `switch`; generations and rollback; users and SSH; services and logs;
networking and the firewall; upgrades, garbage collection, and recovery.

Early lessons provide exact commands, explain expected output, and give layered
hints. Later lessons describe outcomes and require the learner to choose more of
the implementation.

## Course 2: Nix Language and Store

Lessons cover values and types, lists and attribute sets, functions, `let` and
`with`, imports, module merging and priority, evaluation versus realization,
store paths and derivations, profiles, shells, builds, and binary caches. Work
stays administration-oriented rather than becoming a general programming
course.

## Course 3: Flakes and Fleet

Lessons introduce flake inputs/outputs, `flake.lock`, updating and rollback,
one flake describing multiple `nixosConfigurations`, shared modules, host roles,
checks, Git workflow, and a small multi-host design exercise. Flakes are taught
after the learner understands the underlying NixOS and Nix concepts.

## Authoring Features Required

Before authoring, the schema must support:

- course summary, audience, prerequisites, learning objectives, estimated time,
  and maturity status;
- guest capabilities including `os.nixos` and required tools;
- optional expected-output prose and progressive hints on a verification;
- curriculum revision metadata so changed checks do not silently conflict with
  saved completion.

Hints are static curriculum text. LearnLab reveals them one at a time after a
failed check or explicit request. They never include personal provider values.

## Verification Philosophy

- Prefer objective remote checks for machine state.
- Use text evidence for mental-model questions with precise, anchored patterns.
- Use manual confirmation only for genuine observation or recovery drills.
- Every destructive or connectivity-sensitive exercise has a tested recovery
  path before the risky action.
- Checks validate outcomes, not brittle formatting of `configuration.nix`, when
  runtime or evaluated state can be inspected instead.
- Commands are idempotent, non-interactive, bounded, and safe on resume.

## Template Contract

The course requires an abstract NixOS base capability, SSH access for the
configured learner, passwordless privilege escalation for the documented lab
commands, QEMU guest agent support, and a writable classic
`/etc/nixos/configuration.nix` starting point. Concrete template identity and
cluster placement remain in the user's provider profile.

## Testing and Certification

- Every YAML file passes offline and profile-aware validation.
- Content tests assert course/lesson order, required readiness gates, unique
  IDs, hint presence in early lessons, and no provider-specific values.
- Nix snippets are evaluated or built in a disposable NixOS test environment
  where practical.
- Each course is played from a fresh template, including deliberate failure,
  save/resume, rollback, and cleanup.
- A course is ready only when its digest has a matching live certification.

## Out of Scope

- Home Manager, desktop configuration, custom package derivation deep dives,
  secrets deployment, and production fleet rollout.
- Building the NixOS template itself as an ordinary learner lesson. Template
  bootstrap remains operator documentation until LearnLab supports image builds.

## Success Criteria

An experienced Linux administrator can progress from zero NixOS experience to
understanding declarative system management, the Nix machinery beneath it, and
flakes/multi-host modules through reproducible hands-on exercises with honest
validation and safe recovery.
