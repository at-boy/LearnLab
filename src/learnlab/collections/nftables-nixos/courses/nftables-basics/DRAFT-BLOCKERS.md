# Draft nftables course blockers

Both the ordered course and retained NAT lesson are unverified on live guests.
No certification record is claimed. Run the design's full live acceptance and
cleanup checklist before promotion. NAT is excluded from ordering pending a
multi-machine ingress client and objective redirect verification, including
listener identity and fresh request evidence. Logging uses a same-VM disposable
namespace; its veth packet path and kernel journal evidence still require live
acceptance on each declared OS. Automatic snapshot recovery needs console-backed
live acceptance. No lockout drill should break the LearnLab SSH control channel.

Primary references used for corrections:
- https://wiki.nftables.org/wiki-nftables/index.php/Netfilter_hooks
- https://netfilter.org/projects/nftables/manpage.html
- https://wiki.nixos.org/wiki/Nixos-rebuild

Capabilities are requirements for the guest template, not packages installed by
LearnLab. Use static guest networking in this draft: IPv6 neighbor discovery and
DHCP-specific allowances are not taught by the minimal ruleset.
