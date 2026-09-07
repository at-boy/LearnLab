# Multi-Machine Environments and Isolated Networking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provision, access, reconcile, and safely destroy role-named multi-VM lab environments, then add isolated Proxmox networking in controlled slices.

**Architecture:** Normalize single-VM environments into aggregate resource state, extend the provider protocol with explicit machine/network primitives, and drive provisioning through a durable state machine. Add shared-network multi-VM support first, then jump routing, operator-managed isolated pools, and finally optional managed SDN resources.

**Tech Stack:** Python 3.13, SQLite, httpx, OpenSSH, Proxmox VE REST API/SDN, pytest.

**Spec:** `docs/superpowers/specs/2026-09-08-multi-machine-environments-design.md`

## Global Constraints

- Complete guest-capability validation before this plan.
- Preserve all current single-VM course and database behavior through additive migration.
- Record every accepted mutation before issuing the next mutation.
- Never delete a child resource without complete ownership reconciliation.
- Interruption retains known and uncertain state and exits with recovery guidance.
- Curriculum contains only abstract roles, capabilities, networks, and access paths.
- Managed SDN mutation requires a separate explicit live-test authorization.
- Use an isolated worktree and TDD; do not push or merge implicitly.

---

### Task 1: Topology Curriculum Model and Single-Machine Normalization

**Files:**
- Modify: `src/learnlab/curriculum.py`
- Create: `src/learnlab/topology.py`
- Modify: `tests/test_curriculum.py`
- Create: `tests/test_topology.py`

**Interfaces:**
- Produces: `MachineSpec`, `NetworkSpec`, `AccessSpec`, `EnvironmentTopology`.
- Produces: `normalize_topology(policy) -> EnvironmentTopology`.
- Existing VM policy normalizes to machine `default` and network `management`.

- [ ] **Step 1: Write normalization and strict-schema tests**

```python
def test_legacy_vm_policy_normalizes_to_default_machine(policy):
    topology = normalize_topology(policy)
    assert tuple(topology.machines) == ("default",)
    assert topology.machines["default"].access.direct is True

def test_topology_rejects_access_cycle(builder):
    builder.machine("a", via="b").machine("b", via="a")
    with pytest.raises(CurriculumError, match="access cycle"):
        builder.load()
```

- [ ] **Step 2: Verify RED and implement immutable graph validation**

Run: `.venv/bin/python -m pytest tests/test_curriculum.py tests/test_topology.py -q`

Validate stable unique role/network IDs, all references, no access cycles, at
least one direct controller path when remote checks exist, and explicit machine
targets for multi-machine remote/provider checks.

- [ ] **Step 3: Verify and commit**

```bash
git add src/learnlab/curriculum.py src/learnlab/topology.py tests/test_curriculum.py tests/test_topology.py
git commit -m "feat: model multi-machine course topologies"
```

---

### Task 2: Additive Aggregate Resource State

**Files:**
- Modify: `src/learnlab/state.py`
- Modify: `tests/test_state.py`

**Interfaces:**
- Produces: `EnvironmentAggregate`, `MachineResource`, `NetworkResource`, `ResourcePhase`.
- Adds `environment_resources`, `machine_resources`, and `network_resources` tables.
- Migrates each legacy environment into aggregate `default` without deleting the legacy ownership evidence during migration.

- [ ] **Step 1: Write a legacy migration preservation test**

```python
def test_single_vm_row_migrates_to_owned_default_machine(legacy_store):
    legacy = seed_owned_environment(legacy_store)
    legacy_store.initialize()
    aggregate = legacy_store.environment_aggregate(legacy.scope_key)
    assert aggregate.machines["default"].vmid == legacy.vmid
    assert aggregate.machines["default"].expected_name == legacy.expected_vm_name
```

- [ ] **Step 2: Verify RED and add transactional schema migration**

Run: `.venv/bin/python -m pytest tests/test_state.py -k aggregate -q`

Use additive tables and checked phases. Resource mutations require compare-and-
set phase transitions. Preserve retired-database fencing and every old row.

- [ ] **Step 3: Add partial/uncertain transition tests and implement methods**

Cover requested, accepted-with-UPID, complete, uncertain, ready, destroying, and
destroyed for each child. Each write is one explicit transaction.

- [ ] **Step 4: Verify and commit**

```bash
git add src/learnlab/state.py tests/test_state.py
git commit -m "feat: persist aggregate environment resources"
```

---

### Task 3: Provider Machine Primitives and Shared-Network Provisioning

**Files:**
- Modify: `src/learnlab/providers/base.py`
- Modify: `src/learnlab/providers/proxmox.py`
- Modify: `src/learnlab/lifecycle.py`
- Modify: `tests/providers/fake_proxmox.py`
- Modify: `tests/providers/test_proxmox.py`
- Modify: `tests/test_lifecycle.py`

**Interfaces:**
- Adds provider methods `allocate_machine`, `clone_machine`, `start_machine`, `locate_machine`, `delete_machine` using opaque resource IDs.
- Produces: `TopologyLifecycle.ensure_environment(request, topology)`.

- [ ] **Step 1: Write exact two-machine lifecycle-order test**

```python
def test_two_machine_shared_network_records_each_mutation(lifecycle, provider, store):
    lifecycle.ensure_environment(request, two_machine_topology())
    assert provider.calls == [
        "allocate:jump", "clone:jump", "wait-clone:jump",
        "allocate:server", "clone:server", "wait-clone:server",
        "start:jump", "wait-start:jump", "address:jump",
        "start:server", "wait-start:server", "address:server",
    ]
    assert all(x.phase == "ready" for x in store.aggregate().machines.values())
```

- [ ] **Step 2: Verify RED and adapt the Proxmox API without behavior drift**

Run focused provider/lifecycle tests. Wrap existing VM methods behind role-aware
primitives; do not change proven HTTP verbs or task polling.

- [ ] **Step 3: Add failure at every mutation boundary**

Parameterize failures and KeyboardInterrupt after each accepted clone/start.
Assert durable known/uncertain state, exit-130 guidance, and no optimistic resume.

- [ ] **Step 4: Implement dependency-ordered reconciliation and destruction**

Reconcile expected name, profile fingerprint, API origin, node, and provider
identity per machine. Destroy machines in reverse dependency order; retain any
blocked child and continue only where deletion remains independently safe.

- [ ] **Step 5: Verify and commit**

```bash
git add src/learnlab/providers src/learnlab/lifecycle.py tests/providers tests/test_lifecycle.py
git commit -m "feat: provision multi-machine shared-network labs"
```

---

### Task 4: Machine-Targeted Validation and Jump-Host SSH

**Files:**
- Modify: `src/learnlab/validation.py`
- Modify: `src/learnlab/ssh.py`
- Modify: `src/learnlab/session.py`
- Modify: `tests/test_validation.py`
- Modify: `tests/test_ssh.py`
- Modify: `tests/test_session.py`

**Interfaces:**
- Adds `Verification.machine: str | None`; normalized single-machine checks target `default`.
- Adds `SshRoute(target, hops)` and `SshExecutor.run(..., route: SshRoute)`.

- [ ] **Step 1: Write target resolution and ProxyJump argv tests**

```python
def test_private_machine_uses_declared_jump_route(executor, topology):
    executor.run(profile, aggregate, "hostname", 30, route=route_to("server"))
    argv = executor.last_argv
    assert "-J" in argv
    assert argv[argv.index("-J") + 1] == "student@jump-address"
    assert argv[-2] == "student@server-private-address"
```

- [ ] **Step 2: Verify RED and implement routing without a local shell**

Run SSH/validation/session tests. Build argv elements directly, preserve batch
mode, strict host-key checking, timeouts, raw pipes, process groups, and one final
curriculum-authored remote command argument.

- [ ] **Step 3: Add canonical host-key tests for every hop**

Enroll and compare complete sorted host-key sets separately for jump and target.
Use isolated aggregate paths; never mutate normal user known_hosts.

- [ ] **Step 4: Add real descendant-held-pipe multi-hop cleanup regression**

Use the existing POSIX real-process strategy and assert TERM/KILL escalation and
bounded completion after cancellation.

- [ ] **Step 5: Verify and commit**

```bash
git add src/learnlab/validation.py src/learnlab/ssh.py src/learnlab/session.py tests/test_validation.py tests/test_ssh.py tests/test_session.py
git commit -m "feat: validate private machines through jump hosts"
```

---

### Task 5: Operator-Managed Isolated Network Pool

**Files:**
- Modify: `src/learnlab/config.py`
- Modify: `src/learnlab/providers/base.py`
- Modify: `src/learnlab/providers/proxmox.py`
- Modify: `src/learnlab/lifecycle.py`
- Modify: `tests/test_config.py`
- Modify: `tests/providers/test_proxmox.py`
- Modify: `tests/test_lifecycle.py`

**Interfaces:**
- Adds profile `network_pools.<capability> = ["vnet-a", "vnet-b"]`.
- Produces provider `reserve_network`, `attach_machine_network`, `release_network` with read-only remote discovery and local durable reservation.

- [ ] **Step 1: Write deterministic reservation and collision tests**

```python
def test_reservation_chooses_first_free_configured_network(pool, store):
    store.reserve("vnet-a", owner="other")
    assert pool.reserve("isolated.l2", owner="env-2") == "vnet-b"
```

- [ ] **Step 2: Verify RED and implement pool mapping**

Network names exist only in profile configuration/state, never curriculum.
Validate existence/read permission before reservation. Use SQLite uniqueness to
fence concurrent local LearnLab processes.

- [ ] **Step 3: Integrate attachment, readiness, and release**

Attach NICs through proven Proxmox configuration endpoints, record task/outcome
before proceeding, and release local reservation only after all attached machines
are safely deleted. Treat remote mismatch as blocked.

- [ ] **Step 4: Verify and commit**

```bash
git add src/learnlab/config.py src/learnlab/providers src/learnlab/lifecycle.py tests/test_config.py tests/providers/test_proxmox.py tests/test_lifecycle.py
git commit -m "feat: allocate operator-managed isolated networks"
```

---

### Task 6: Managed Proxmox SDN Resources

**Files:**
- Create: `src/learnlab/providers/proxmox_sdn.py`
- Modify: `src/learnlab/providers/proxmox.py`
- Modify: `src/learnlab/config.py`
- Modify: `src/learnlab/lifecycle.py`
- Create: `tests/providers/test_proxmox_sdn.py`
- Modify: `tests/test_lifecycle.py`
- Create: `tests/live/test_proxmox_sdn_topology.py`

**Interfaces:**
- Produces: `ProxmoxSdnManager.discover_capabilities()`, `create_network()`, `apply()`, `delete_network()`.
- Adds explicit profile mode `sdn_management = "disabled" | "managed"`, default `disabled`.

- [ ] **Step 1: Write exact HTTP contract and permission-failure tests**

Assert create/apply/delete paths and verbs against captured Proxmox documentation
for the target installed version. Redact responses and classify authentication,
authorization, task failure, timeout, and uncertain mutation separately.

- [ ] **Step 2: Verify RED and implement the disabled-by-default manager**

Generate collision-resistant provider names from LearnLab ownership IDs within
Proxmox length/character constraints. Persist accepted mutations and expected
object properties before applying SDN configuration.

- [ ] **Step 3: Add failure matrix and reverse cleanup**

Cover VNet created/subnet failed, apply uncertain, machines partly attached,
machine deletion blocked, and network deletion blocked. Never delete a network
until all owned child attachments are absent.

- [ ] **Step 4: Stop for explicit destructive live-test authorization**

Present the exact profile, configured zone, intended objects, permissions, and
cleanup path. Do not run the live test until approved.

- [ ] **Step 5: Run one isolated topology acceptance test**

Provision jump and private server, prove controller-to-jump and jump-to-server
SSH, prove intended isolation, destroy machines, remove SDN children, apply, and
verify absence. Preserve records if any outcome is uncertain.

- [ ] **Step 6: Verify offline suite and commit**

```bash
git add src/learnlab/providers/proxmox_sdn.py src/learnlab/providers/proxmox.py src/learnlab/config.py src/learnlab/lifecycle.py tests/providers/test_proxmox_sdn.py tests/test_lifecycle.py tests/live/test_proxmox_sdn_topology.py
git commit -m "feat: manage isolated Proxmox SDN labs"
```

---

### Task 7: Documentation, Migration, and Full Gate

**Files:**
- Modify: `README.md`
- Modify: `docs/LearnLab-Course-Authoring-Guide.md`
- Create: `docs/proxmox-multi-machine-operations.md`
- Modify: `tests/test_packaging.py`

- [ ] **Step 1: Document topology schema and operator recovery**

Include single-machine compatibility, role targeting, jump access, pool versus
managed SDN modes, least-privilege notes, resource-state inspection, and exact
manual reconciliation rules. Use generic values only.

- [ ] **Step 2: Run complete non-live verification**

Run offline pytest, Ruff, `mypy src`, packaging/wheel installation, and diff
check. Confirm existing single-VM course integration tests remain unchanged.

- [ ] **Step 3: Commit documentation**

```bash
git add README.md docs/LearnLab-Course-Authoring-Guide.md docs/proxmox-multi-machine-operations.md tests/test_packaging.py
git commit -m "docs: explain multi-machine lab operations"
```
