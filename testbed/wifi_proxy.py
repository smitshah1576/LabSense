"""Wi-Fi link emulator for the testbed (standard library only).

In the lab, agents and dashboards reach the server over Wi-Fi; in the testbed
they share a perfect virtual bridge. Kernel traffic shaping (tc netem) is not
available everywhere, so this emulates the Wi-Fi hop at the TCP level instead:
it stands where the access point would be (172.28.0.2 on the lab LAN), relays
every connection to the server, and delays the bytes the way a wireless link
does.

TCP never shows an application a lost packet, only a late one: a loss costs a
retransmission timeout (~200-600 ms) and holds back everything behind it. So
each relayed chunk gets the profile's latency and jitter, a lost chunk gets a
retransmission stall, and now and then a whole connection freezes for a few
seconds (interference, roaming between access points) without disconnecting.
Byte order is always preserved, exactly as TCP would.

Profiles (one-way latency +/- jitter, loss, dropouts):
    good     3 ms +/- 2 ms, 0.1 % loss
    campus   15 ms +/- 10 ms, 1 % loss, a 1-4 s dropout every ~30 min per device
    poor     60 ms +/- 40 ms, 4 % loss, a 2-8 s dropout every ~5 min per device
    off      plain relay

Configuration (environment):
    WIFI_PROFILE    one of the profiles above (default campus)
    WIFI_UPSTREAM   server address to relay to (default 172.28.0.1)
    WIFI_PORTS      comma-separated ports to relay (default 9000,8000,5173)

Usage:  WIFI_PROFILE=poor python3 testbed/wifi_proxy.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
from dataclasses import dataclass

logger = logging.getLogger('wifi')


@dataclass(frozen=True)
class Profile:
    latency: float          # one-way base latency, seconds
    jitter: float           # +/- uniform jitter, seconds
    loss: float             # probability a chunk needs a retransmission
    dropout_every: float    # mean seconds between dropouts per connection (0 = never)
    dropout_len: tuple[float, float]  # dropout duration range, seconds


PROFILES = {
    'off': Profile(0.0, 0.0, 0.0, 0, (0, 0)),
    'good': Profile(0.003, 0.002, 0.001, 0, (0, 0)),
    'campus': Profile(0.015, 0.010, 0.01, 1800, (1.0, 4.0)),
    'poor': Profile(0.060, 0.040, 0.04, 300, (2.0, 8.0)),
}

CHUNK = 64 * 1024


class Stats:
    connections = 0
    open = 0
    chunks = 0
    stalls = 0
    dropouts = 0


class Link:
    """One device's Wi-Fi link: both directions share its dropouts."""

    def __init__(self, profile: Profile):
        self.p = profile
        loop = asyncio.get_running_loop()
        self.next_dropout = (loop.time() + random.expovariate(1 / profile.dropout_every)
                             if profile.dropout_every else float('inf'))
        self.dropout_end = 0.0

    def delivery_delay(self, now: float) -> float:
        """Seconds from now until a chunk read now should be delivered."""
        p = self.p
        if now >= self.next_dropout:
            self.dropout_end = now + random.uniform(*p.dropout_len)
            self.next_dropout = self.dropout_end + random.expovariate(1 / p.dropout_every)
            Stats.dropouts += 1
            logger.info('dropout for %.1f s', self.dropout_end - now)
        delay = max(0.0, p.latency + random.uniform(-p.jitter, p.jitter))
        if p.loss and random.random() < p.loss:
            delay += random.uniform(0.2, 0.6)  # retransmission timeout
            Stats.stalls += 1
        return max(delay, self.dropout_end - now)


async def pump(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, link: Link) -> None:
    """Relay one direction, delaying each chunk but never reordering."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue(maxsize=256)

    async def deliver():
        while True:
            due, data = await queue.get()
            if data is None:
                break
            wait = due - loop.time()
            if wait > 0:
                await asyncio.sleep(wait)
            writer.write(data)
            await writer.drain()

    sender = asyncio.create_task(deliver())
    last_due = 0.0
    try:
        while data := await reader.read(CHUNK):
            if sender.done():  # the far side went away
                break
            now = loop.time()
            last_due = max(now + link.delivery_delay(now), last_due)  # keep TCP order
            Stats.chunks += 1
            await queue.put((last_due, data))
        await queue.put((last_due, None))
        await sender
        if writer.can_write_eof():
            writer.write_eof()
    except (ConnectionError, OSError):
        pass
    finally:
        sender.cancel()


async def handle(client_r, client_w, upstream: str, port: int, profile: Profile) -> None:
    Stats.connections += 1
    Stats.open += 1
    try:
        server_r, server_w = await asyncio.open_connection(upstream, port)
    except OSError as exc:
        logger.warning('cannot reach %s:%d: %s', upstream, port, exc)
        client_w.close()
        Stats.open -= 1
        return
    link = Link(profile)
    try:
        await asyncio.gather(pump(client_r, server_w, link), pump(server_r, client_w, link))
    finally:
        for w in (client_w, server_w):
            w.close()
        Stats.open -= 1


async def report(interval: float = 30.0) -> None:
    while True:
        await asyncio.sleep(interval)
        logger.info('open=%d total=%d chunks=%d retransmit-stalls=%d dropouts=%d',
                    Stats.open, Stats.connections, Stats.chunks, Stats.stalls, Stats.dropouts)


async def main() -> None:
    name = os.environ.get('WIFI_PROFILE', 'campus')
    if name not in PROFILES:
        raise SystemExit(f'unknown WIFI_PROFILE {name!r}; choose from {", ".join(PROFILES)}')
    profile = PROFILES[name]
    upstream = os.environ.get('WIFI_UPSTREAM', '172.28.0.1')
    ports = [int(p) for p in os.environ.get('WIFI_PORTS', '9000,8000,5173').split(',')]

    servers = []
    for port in ports:
        servers.append(await asyncio.start_server(
            lambda r, w, port=port: handle(r, w, upstream, port, profile),
            '0.0.0.0', port, backlog=1024))
    logger.info('Wi-Fi profile %r: %s; relaying ports %s to %s',
                name, profile, ', '.join(map(str, ports)), upstream)
    await asyncio.gather(report(), *(s.serve_forever() for s in servers))


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [wifi] %(message)s',
                        datefmt='%H:%M:%S')
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
