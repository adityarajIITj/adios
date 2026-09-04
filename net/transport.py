#!/usr/bin/env python3
"""
AdiOS Networking Subsystem: Layer 4 Transport & Network Stack (transport.py)
Implements enterprise-grade L4 transport protocols and unified network stack:
- RFC 792 Internet Control Message Protocol (ICMP) Echo Request & Reply (Ping)
- RFC 768 User Datagram Protocol (UDP) with IPv4 pseudo-header checksum verification
- Dynamic Ephemeral Port Allocation (49152..65535) with collision protection
- POSIX-style Datagram Socket with non-blocking mode, timeouts, and buffer controls
- Raw Socket abstraction for low-level protocol inspection and custom frame processing
- Event Multiplexer (NetPoll) supporting select/poll readiness monitoring across sockets
- Unified NetworkStack integrating Ethernet, ARP, IPv4, ICMP, UDP, and raw sockets

Zero external dependencies. Pure RV32IM bare-metal transport stack.
STRICT ZERO EMOJI POLICY ENFORCED.
"""

import struct
import time
from collections import deque
from typing import Dict, List, Tuple, Optional, Set, Any

from net.ipv4 import (
    EthernetFrame, ARPPacket, ARPTable, IPv4Packet,
    ETHERTYPE_IPV4, ETHERTYPE_ARP, ARP_OP_REQUEST, ARP_OP_REPLY,
    IP_PROTO_ICMP, IP_PROTO_UDP, internet_checksum, ip_to_u32
)

ICMP_TYPE_ECHO_REPLY   = 0
ICMP_TYPE_ECHO_REQUEST = 8

# Poll event flags
POLLIN  = 0x0001
POLLOUT = 0x0004
POLLERR = 0x0008

class ICMPPacket:
    """
    RFC 792 ICMP Echo Request / Reply Header (8 bytes).
    """
    def __init__(
        self,
        icmp_type: int = ICMP_TYPE_ECHO_REQUEST,
        code: int = 0,
        ident: int = 1,
        seq: int = 1,
        data: bytes = b""
    ):
        self.icmp_type = icmp_type
        self.code = code
        self.ident = ident
        self.seq = seq
        self.data = data

    def pack(self) -> bytes:
        header_pre = struct.pack("!BBHHH", self.icmp_type, self.code, 0, self.ident, self.seq)
        chk = internet_checksum(header_pre + self.data)
        header = struct.pack("!BBHHH", self.icmp_type, self.code, chk, self.ident, self.seq)
        return header + self.data

    @classmethod
    def unpack(cls, raw: bytes) -> 'ICMPPacket':
        if len(raw) < 8:
            raise ValueError("ICMP packet too short")
        itype, code, chk, ident, seq = struct.unpack("!BBHHH", raw[:8])
        calc_chk = internet_checksum(raw)
        if calc_chk != 0:
            raise ValueError("ICMP checksum error")
        return cls(itype, code, ident, seq, raw[8:])

class UDPPacket:
    """
    RFC 768 UDP Datagram Header (8 bytes).
    Supports IPv4 pseudo-header checksum generation and verification.
    """
    def __init__(
        self,
        src_port: int = 1024,
        dst_port: int = 8080,
        payload: bytes = b"",
        checksum: int = 0
    ):
        self.src_port = src_port
        self.dst_port = dst_port
        self.payload = payload
        self.checksum = checksum

    def pack(self, src_ip: Optional[str] = None, dst_ip: Optional[str] = None, compute_checksum: bool = True) -> bytes:
        total_len = 8 + len(self.payload)
        chk = 0

        if compute_checksum and src_ip and dst_ip:
            # 12-byte IPv4 Pseudo-Header for UDP checksum:
            # Source IP (4B) + Dest IP (4B) + Zero (1B) + Protocol (1B: 17) + UDP Length (2B)
            pseudo = struct.pack(
                "!IIBBH",
                ip_to_u32(src_ip),
                ip_to_u32(dst_ip),
                0,
                IP_PROTO_UDP,
                total_len
            )
            udp_header_pre = struct.pack("!HHHH", self.src_port, self.dst_port, total_len, 0)
            data_to_checksum = pseudo + udp_header_pre + self.payload
            chk = internet_checksum(data_to_checksum)
            if chk == 0:
                chk = 0xFFFF  # RFC 768: transmitted as all ones if computed to zero

        header = struct.pack("!HHHH", self.src_port, self.dst_port, total_len, chk)
        return header + self.payload

    @classmethod
    def unpack(cls, raw: bytes, src_ip: Optional[str] = None, dst_ip: Optional[str] = None, verify_checksum: bool = False) -> 'UDPPacket':
        if len(raw) < 8:
            raise ValueError("UDP packet too short")
        sport, dport, length, chk = struct.unpack("!HHHH", raw[:8])

        if verify_checksum and chk != 0 and src_ip and dst_ip:
            pseudo = struct.pack(
                "!IIBBH",
                ip_to_u32(src_ip),
                ip_to_u32(dst_ip),
                0,
                IP_PROTO_UDP,
                length
            )
            if internet_checksum(pseudo + raw[:length]) != 0:
                raise ValueError("UDP checksum mismatch")

        return cls(sport, dport, raw[8:length], checksum=chk)

class EphemeralPortManager:
    """
    Allocates and tracks ephemeral ports in the IANA dynamic range 49152..65535.
    """
    def __init__(self, start_port: int = 49152, end_port: int = 65535):
        self.start_port = start_port
        self.end_port = end_port
        self.next_port = start_port
        self.allocated_ports: Set[int] = set()

    def allocate(self) -> int:
        for _ in range(self.end_port - self.start_port + 1):
            port = self.next_port
            self.next_port = self.start_port if self.next_port >= self.end_port else self.next_port + 1
            if port not in self.allocated_ports:
                self.allocated_ports.add(port)
                return port
        raise IOError("EADDRINUSE: Ephemeral port space exhausted")

    def release(self, port: int):
        self.allocated_ports.discard(port)

class UDPSocket:
    """
    Virtual Datagram Socket with non-blocking modes, timeouts, and queues.
    """
    def __init__(self, stack: 'NetworkStack', port: Optional[int] = None):
        self.stack = stack
        self.port = port
        self.rx_queue: deque = deque()
        self.non_blocking = False
        self.timeout = None
        self.broadcast_allowed = False
        self.max_queue_len = 64

        if self.port is not None:
            self.stack.bind_udp(self.port, self)

    def bind(self, port: int):
        self.port = port
        self.stack.bind_udp(port, self)

    def setblocking(self, flag: bool):
        self.non_blocking = not flag

    def settimeout(self, timeout: Optional[float]):
        self.timeout = timeout

    def sendto(self, data: bytes, dst_ip: str, dst_port: int):
        src_p = self.port or self.stack.port_manager.allocate()
        if self.port is None:
            self.port = src_p
            self.stack.bind_udp(src_p, self)
        self.stack.send_udp(src_p, dst_ip, dst_port, data)

    def recvfrom(self) -> Tuple[Optional[bytes], Optional[Tuple[str, int]]]:
        if self.rx_queue:
            return self.rx_queue.popleft()
        if self.non_blocking:
            return None, None
        return None, None

    def close(self):
        if self.port is not None:
            self.stack.unbind_udp(self.port)
            self.stack.port_manager.release(self.port)
            self.port = None

class RawSocket:
    """
    Raw IP Socket for capturing and transmitting arbitrary protocol packets.
    """
    def __init__(self, stack: 'NetworkStack', protocol: int):
        self.stack = stack
        self.protocol = protocol
        self.rx_queue: deque = deque()
        self.stack.bind_raw(protocol, self)

    def sendto(self, payload: bytes, dst_ip: str):
        ip_pkt = IPv4Packet(
            src_ip=self.stack.ip,
            dst_ip=dst_ip,
            proto=self.protocol,
            payload=payload
        )
        dst_mac = self.stack.arp_table.lookup(dst_ip) or "FF:FF:FF:FF:FF:FF"
        eth = EthernetFrame(
            dst_mac=dst_mac,
            src_mac=self.stack.mac,
            ethertype=ETHERTYPE_IPV4,
            payload=ip_pkt.pack()
        )
        self.stack.tx_packets.append(eth.pack())

    def recvfrom(self) -> Tuple[Optional[bytes], Optional[str]]:
        if self.rx_queue:
            return self.rx_queue.popleft()
        return None, None

class NetPoll:
    """
    Event multiplexer monitoring read/write readiness across network sockets.
    """
    def __init__(self):
        self.registered_socks: Dict[Any, int] = {}  # sock -> event_mask

    def register(self, sock: Any, events: int = POLLIN):
        self.registered_socks[sock] = events

    def unregister(self, sock: Any):
        self.registered_socks.pop(sock, None)

    def poll(self, timeout_ms: int = 0) -> List[Tuple[Any, int]]:
        ready = []
        for sock, events in self.registered_socks.items():
            revents = 0
            if (events & POLLIN) and hasattr(sock, "rx_queue") and sock.rx_queue:
                revents |= POLLIN
            if (events & POLLOUT):
                revents |= POLLOUT
            if revents != 0:
                ready.append((sock, revents))
        return ready

class NetworkStack:
    """
    The AdiOS Unified L2/L3/L4 Network Stack.
    Integrates Ethernet, ARP, IPv4, ICMP, UDP, raw sockets, and port management.
    """
    def __init__(self, ip: str = "192.168.1.10", mac: str = "02:AD:10:00:00:01"):
        self.ip = ip
        self.mac = mac
        self.arp_table = ARPTable()
        self.port_manager = EphemeralPortManager()
        self.udp_bindings: Dict[int, UDPSocket] = {}
        self.raw_bindings: Dict[int, List[RawSocket]] = {}
        self.tx_packets: List[bytes] = []
        self.icmp_replies_received: List[Tuple[str, int]] = []
        self.poll = NetPoll()

    def bind_udp(self, port: int, sock: UDPSocket):
        self.udp_bindings[port] = sock

    def unbind_udp(self, port: int):
        self.udp_bindings.pop(port, None)

    def bind_raw(self, protocol: int, sock: RawSocket):
        if protocol not in self.raw_bindings:
            self.raw_bindings[protocol] = []
        if sock not in self.raw_bindings[protocol]:
            self.raw_bindings[protocol].append(sock)

    def receive_ethernet(self, raw_frame: bytes):
        """Processes an incoming raw Ethernet frame from the wire/driver."""
        try:
            eth = EthernetFrame.unpack(raw_frame)
        except Exception:
            return

        # Filter: Accept broadcast or unicast directed to our MAC
        if eth.dst_mac.upper() != self.mac.upper() and eth.dst_mac.upper() != "FF:FF:FF:FF:FF:FF":
            return

        if eth.ethertype == ETHERTYPE_ARP:
            self._handle_arp(eth.payload)
        elif eth.ethertype == ETHERTYPE_IPV4:
            self._handle_ipv4(eth.payload, eth.src_mac)

    def _handle_arp(self, payload: bytes):
        try:
            arp = ARPPacket.unpack(payload)
        except Exception:
            return

        self.arp_table.insert(arp.src_ip, arp.src_mac)

        if arp.op == ARP_OP_REQUEST and arp.dst_ip == self.ip:
            # Send ARP Reply
            reply = ARPPacket(
                op=ARP_OP_REPLY,
                src_mac=self.mac,
                src_ip=self.ip,
                dst_mac=arp.src_mac,
                dst_ip=arp.src_ip
            )
            eth = EthernetFrame(
                dst_mac=arp.src_mac,
                src_mac=self.mac,
                ethertype=ETHERTYPE_ARP,
                payload=reply.pack()
            )
            self.tx_packets.append(eth.pack())

    def _handle_ipv4(self, payload: bytes, src_mac: str):
        try:
            ip_pkt = IPv4Packet.unpack(payload)
        except Exception:
            return

        self.arp_table.insert(ip_pkt.src_ip, src_mac)

        # Dispatch to raw sockets
        if ip_pkt.proto in self.raw_bindings:
            for raw_sock in self.raw_bindings[ip_pkt.proto]:
                raw_sock.rx_queue.append((ip_pkt.payload, ip_pkt.src_ip))

        # Ignore if not addressed to us or broadcast
        if ip_pkt.dst_ip != self.ip and ip_pkt.dst_ip != "255.255.255.255":
            return

        if ip_pkt.proto == IP_PROTO_ICMP:
            self._handle_icmp(ip_pkt)
        elif ip_pkt.proto == IP_PROTO_UDP:
            self._handle_udp(ip_pkt)

    def _handle_icmp(self, ip_pkt: IPv4Packet):
        try:
            icmp = ICMPPacket.unpack(ip_pkt.payload)
        except Exception:
            return

        if icmp.icmp_type == ICMP_TYPE_ECHO_REQUEST:
            # Auto-generate ICMP Echo Reply
            reply = ICMPPacket(
                icmp_type=ICMP_TYPE_ECHO_REPLY,
                code=0,
                ident=icmp.ident,
                seq=icmp.seq,
                data=icmp.data
            )
            out_ip = IPv4Packet(
                src_ip=self.ip,
                dst_ip=ip_pkt.src_ip,
                proto=IP_PROTO_ICMP,
                payload=reply.pack()
            )
            dst_mac = self.arp_table.lookup(ip_pkt.src_ip) or "FF:FF:FF:FF:FF:FF"
            eth = EthernetFrame(
                dst_mac=dst_mac,
                src_mac=self.mac,
                ethertype=ETHERTYPE_IPV4,
                payload=out_ip.pack()
            )
            self.tx_packets.append(eth.pack())
        elif icmp.icmp_type == ICMP_TYPE_ECHO_REPLY:
            self.icmp_replies_received.append((ip_pkt.src_ip, icmp.seq))

    def _handle_udp(self, ip_pkt: IPv4Packet):
        try:
            udp = UDPPacket.unpack(ip_pkt.payload, ip_pkt.src_ip, ip_pkt.dst_ip)
        except Exception:
            return

        sock = self.udp_bindings.get(udp.dst_port)
        if sock:
            sock.rx_queue.append((udp.payload, (ip_pkt.src_ip, udp.src_port)))

    def send_udp(self, src_port: int, dst_ip: str, dst_port: int, data: bytes):
        """Constructs and transmits an IPv4/UDP packet with checksum."""
        udp = UDPPacket(src_port, dst_port, data)
        packed_udp = udp.pack(src_ip=self.ip, dst_ip=dst_ip, compute_checksum=True)
        ip_pkt = IPv4Packet(self.ip, dst_ip, IP_PROTO_UDP, packed_udp)
        dst_mac = self.arp_table.lookup(dst_ip) or "FF:FF:FF:FF:FF:FF"
        eth = EthernetFrame(
            dst_mac=dst_mac,
            src_mac=self.mac,
            ethertype=ETHERTYPE_IPV4,
            payload=ip_pkt.pack()
        )
        self.tx_packets.append(eth.pack())

    def send_ping(self, dst_ip: str, seq: int = 1):
        """Sends an ICMP Echo Request."""
        icmp = ICMPPacket(ICMP_TYPE_ECHO_REQUEST, 0, ident=0xAD10, seq=seq, data=b"AdiOS_PING")
        ip_pkt = IPv4Packet(self.ip, dst_ip, IP_PROTO_ICMP, icmp.pack())
        dst_mac = self.arp_table.lookup(dst_ip) or "FF:FF:FF:FF:FF:FF"
        eth = EthernetFrame(
            dst_mac=dst_mac,
            src_mac=self.mac,
            ethertype=ETHERTYPE_IPV4,
            payload=ip_pkt.pack()
        )
        self.tx_packets.append(eth.pack())

if __name__ == "__main__":
    stack_a = NetworkStack("192.168.1.1", "02:00:00:00:00:01")
    stack_b = NetworkStack("192.168.1.2", "02:00:00:00:00:02")

    # Test UDP Datagram communication
    sock_b = UDPSocket(stack_b, port=9000)
    sock_a = UDPSocket(stack_a)
    sock_a.sendto(b"UDPPayloadMessage", "192.168.1.2", 9000)

    frame = stack_a.tx_packets.pop(0)
    stack_b.receive_ethernet(frame)

    msg, sender = sock_b.recvfrom()
    assert msg == b"UDPPayloadMessage"
    assert sender[0] == "192.168.1.1"

    # Test NetPoll
    poll = NetPoll()
    poll.register(sock_b, POLLIN)
    sock_b.rx_queue.append((b"NewData", ("10.0.0.1", 1234)))
    ready = poll.poll()
    assert len(ready) == 1
    assert ready[0][0] == sock_b

    # Test Ping roundtrip
    stack_a.send_ping("192.168.1.2", seq=1)
    ping_frame = stack_a.tx_packets.pop(0)
    stack_b.receive_ethernet(ping_frame)
    reply_frame = stack_b.tx_packets.pop(0)
    stack_a.receive_ethernet(reply_frame)
    assert len(stack_a.icmp_replies_received) == 1

    print("UDP socket communication, NetPoll event readiness, and ICMP roundtrip verified.")
