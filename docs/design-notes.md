# Design notes

I wanted a lab where a routing failure has an observable consequence, not just a set of routers that can ping each other.

The first cut uses six FRR nodes:

- two backbone routers in AS65000
- two Dublin edge routers in AS65100
- two London edge routers in AS65200

Each site has two independent exits to the backbone. The site pair runs OSPF on the internal link so the router loopbacks stay reachable, and iBGP is built over those loopbacks. The backbone pair uses iBGP over a direct point-to-point link. Site-to-backbone sessions are eBGP.

That gives me a useful failure case later: if a site loses one external BGP session, the affected router should still be able to use the other site router as its path out. It also means I can break OSPF separately and see whether the iBGP session over loopbacks follows it.

The first live failure test exposed an important design mistake: I was using the same /32 addresses as both iBGP router IDs/update-sources and as the BGP payload prefixes used for traffic tests. When `core1-dub1` failed, `dub2` could still reach `dub1`'s router loopback through OSPF, but the iBGP path for that same /32 was marked invalid and never propagated upstream. I split those roles instead of hiding the failure: 10.100/10.200 loopbacks are infrastructure for OSPF+iBGP, while 10.110/10.210 are the prefixes advertised and probed end to end.

## Addressing

| Link / role | Prefix |
| --- | --- |
| core1-core2 | 10.0.0.0/31 |
| core1-dub1 | 10.0.10.0/31 |
| core2-dub2 | 10.0.11.0/31 |
| core1-lon1 | 10.0.20.0/31 |
| core2-lon2 | 10.0.21.0/31 |
| Dublin internal | 10.1.0.0/31 |
| London internal | 10.2.0.0/31 |
| Dublin router loopbacks | 10.100.0.1/32, 10.100.0.2/32 |
| Dublin service prefixes | 10.110.0.1/32, 10.110.0.2/32 |
| London router loopbacks | 10.200.0.1/32, 10.200.0.2/32 |
| London service prefixes | 10.210.0.1/32, 10.210.0.2/32 |
| Core loopbacks | 10.255.0.1/32, 10.255.0.2/32 |

## Things I am deliberately not adding yet

No EVPN, MPLS, route reflectors, or vendor-specific NOS images in the first version. They would make the topology look busier without helping answer the initial reliability questions.

The immediate goals are:

1. bring up the routing cleanly and capture the expected control-plane state;
2. make that expected state executable as checks rather than notes in a README;
3. introduce failures one at a time and measure what changes.
