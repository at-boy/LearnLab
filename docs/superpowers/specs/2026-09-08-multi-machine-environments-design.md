# Multi-Machine Environments and Isolated Networking Design

**Status:** Proposed for review

## Purpose

Extend LearnLab from one VM per environment to provider-neutral lab topologies
containing multiple role-named machines, isolated networks, and an explicit SSH
access path, with Proxmox SDN as the first provider implementation.

## Curriculum Model

A VM environment may declare `machines` and `networks`. Machine keys and network
keys are stable IDs local to the environment.

```yaml
environment:
  scope: course
  provider_capability: proxmox.vm-topology
  networks:
    management:
      exposure: controller
    private:
      exposure: isolated
  machines:
    jump:
      guest_capabilities: [os.debian.13, role.ssh-jump]
      networks: [management, private]
      access: direct
    server:
      guest_capabilities: [os.nixos]
      networks: [private]
      access:
        via: jump
```

Curriculum describes intent only. It contains no VMID, node, template, storage,
VNet, subnet, VLAN, address, API URL, or provider profile.

Single-machine syntax remains supported and is normalized internally to one
machine named `default` on one controller-visible network.

## Runtime Model

An environment is an aggregate with child resource records for machines,
networks, provider tasks, addresses, and access routes. Every resource has a
stable LearnLab-generated ownership token and expected provider identity.
Lifecycle operations reconcile recorded and remote state before reuse or
destruction.

Provisioning order is network resources, machine allocation/clone, NIC
attachment/configuration, starts, address discovery, and access-path readiness.
Independent machines may run concurrently only after sequential correctness is
established and tests prove deterministic recovery.

## Partial Failure and Interruption

Provisioning is a durable state machine. Each accepted provider mutation is
recorded before the next mutation. On failure or Ctrl-C, LearnLab retains all
known and uncertain resources, exits with recovery guidance, and never claims
safe resume. Recovery reconciles each child independently. Cleanup proceeds in
dependency order: machines before ephemeral networks.

Destroy requires the existing infrastructure confirmation and a separate
progress policy. Ownership mismatch on any child blocks that child's deletion
without discarding the rest of the recovery record.

## SSH Routing

Remote checks target a machine role. Direct machines use the existing strict
known-host flow. Routed machines use OpenSSH `ProxyJump`/`-J` through a declared
jump role while maintaining isolated, canonical known-host sets for every hop.
No course-authored command controls SSH routing. Timeouts, process groups,
redaction, and bounded cleanup retain current guarantees.

## Proxmox SDN Mapping

The initial provider supports a configured, pre-existing SDN zone and creates
per-environment VNets/subnets only when the profile explicitly permits managed
network creation. A safer first slice may instead allocate from a pool of
operator-created VNets. The profile owns concrete zone, IPAM, DHCP/SNAT, MTU,
and naming settings.

The design begins with a read-only capability/permission probe. It must not
assume `SDN.Use` is sufficient for creating or deleting SDN objects. Permissions
are documented and tested at the narrowest practical paths.

## Validation

Offline validation checks unique roles, network references, reachable access
graphs, exactly one direct controller entry path when remote checks exist, no
access cycles, compatible scopes, and declared machine targets on remote checks.
Profile validation confirms image and topology capabilities without mutation.

## Delivery Slices

1. Normalize the existing single-machine model into aggregate state with no
   behavior change.
2. Support multiple machines on an existing shared network.
3. Add jump-host SSH routing.
4. Add pre-provisioned isolated-network pools.
5. Add LearnLab-managed ephemeral SDN resources only after separate live safety
   acceptance.

Each slice ships independently and retains backward compatibility.

## Testing

- Pure state-machine tests cover every partial-failure and interruption point.
- Fake-provider tests assert exact ordering, ownership checks, and cleanup.
- SSH tests use real local descendant processes and multi-hop argument shaping.
- Schema tests cover access graph and compatibility errors.
- Live tests are explicitly destructive and verify cleanup in `finally` without
  hiding uncertain outcomes.
- Existing single-VM courses and databases migrate additively and remain usable.

## Out of Scope

- Arbitrary routing protocols, EVPN control-plane management, containers,
  Kubernetes orchestration, and cross-provider topologies.
- Automatic repair or deletion of resources not proven to be LearnLab-owned.

## Success Criteria

A course can request a small isolated topology, LearnLab can provision and
record every child resource, checks can reach private machines safely through a
jump host, and interruption or ownership ambiguity never causes unrecorded or
unsafe cleanup.
