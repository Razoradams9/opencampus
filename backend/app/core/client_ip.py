"""Client IP resolution for rate limiting.

The direct TCP peer is the client unless that peer is listed in
OPENCAMPUS_TRUSTED_PROXIES. Only then is X-Forwarded-For consulted, read from
the right: each trusted hop is skipped and the first untrusted address is the
client. Entries to the left of it were written by the client and are ignored,
so a client can never choose its own rate-limit identity.

Run uvicorn with --no-proxy-headers so this is the only layer interpreting
forwarding headers (uvicorn otherwise trusts them from 127.0.0.1 by default).
"""

import ipaddress

from starlette.requests import Request

from app.core.config import IPNetwork

UNKNOWN = "unknown"


def _parse(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    value = value.strip()
    if value.startswith("[") and "]" in value:  # "[2001:db8::1]:443"
        value = value[1 : value.index("]")]
    elif value.count(":") == 1:  # "203.0.113.7:1234"
        value = value.split(":", 1)[0]
    try:
        return ipaddress.ip_address(value)
    except ValueError:
        return None


def _trusted(address: ipaddress.IPv4Address | ipaddress.IPv6Address, proxies: tuple[IPNetwork, ...]) -> bool:
    return any(address in network for network in proxies)


def _bucket_identity(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str:
    """IPv4 per address; IPv6 per /64, the smallest block an end site usually controls."""
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped:
            return str(address.ipv4_mapped)
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)


def client_ip(request: Request, trusted_proxies: tuple[IPNetwork, ...]) -> str:
    peer_text = request.client.host if request.client else ""
    peer = _parse(peer_text)
    if peer is None:
        return peer_text or UNKNOWN  # e.g. a test client or unix socket: an opaque, stable label

    if trusted_proxies and _trusted(peer, trusted_proxies):
        hops = [hop for header in request.headers.getlist("x-forwarded-for") for hop in header.split(",")]
        for hop in reversed(hops):
            address = _parse(hop)
            if address is None:
                break  # malformed chain: stop and fall back to the last trusted hop
            if not _trusted(address, trusted_proxies):
                return _bucket_identity(address)
            peer = address
    return _bucket_identity(peer)
