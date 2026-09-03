#!/usr/bin/env python3
"""
AdiOS Networking Subsystem: Layer 4 Transport & Network Stack (transport.py)
Features:
- RFC 792 Internet Control Message Protocol (ICMP) Echo Request & Reply (Ping)
- RFC 768 User Datagram Protocol (UDP) Datagrams & Socket Abstraction
- Unified NetworkStack: Automatic ARP resolution, ICMP auto-reply, and UDP routing
"""

import struct
from collections import deque
from net.ipv4 import (
    EthernetFrame, ARPPacket, ARPTable, IPv4Packet,
    ETHERTYPE_IPV4, ETHERTYPE_ARP, ARP_OP_REQUEST, ARP_OP_REPLY,
    IP_PROTO_ICMP, IP_PROTO_UDP, internet_checksum
)

ICMP_TYPE_ECHO_REPLY   = 0
ICMP_TYPE_ECHO_REQUEST = 8

class ICMPPacket:
    """
    RFC 792 ICMP Echo Request / Reply Header (8 bytes).
    """
    def __init__(self, icmp_type=ICMP_TYPE_ECHO_REQUEST, code=0, ident=1, seq=1, data=b""):
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
    def unpack(cls, raw: bytes):
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
    """
    def __init__(self, src_port=1024, dst_port=8080, payload=b""):
        self.src_port = src_port
        self.dst_port = dst_port
        self.payload = payload

    def pack(self, src_ip=None, dst_ip=None) -> bytes:
        total_len = 8 + len(self.payload)
        # Standard UDP without pseudo-header checksum or checksum = 0
        header = struct.pack("!HHHH", self.src_port, self.dst_port, total_len, 0)
        return header + self.payload

    @classmethod
    def unpack(cls, raw: bytes):
        if len(raw) < 8:
            raise ValueError("UDP packet too short")
        sport, dport, length, chk = struct.unpack("!HHHH", raw[:8])
        return cls(sport, dport, raw[8:length])

class UDPSocket:
    """
    Virtual Datagram Socket for sending and receiving UDP packets.
    """
    def __init__(self, stack, port=None):
        self.stack = stack
        self.port = port
        self.rx_queue = deque()
        if self.port is not None:
            self.stack.bind_udp(self.port, self)

    def bind(self, port: int):
        self.port = port
        self.stack.bind_udp(port, self)

    def sendto(self, data: bytes, dst_ip: str, dst_port: int):
        self.stack.send_udp(self.port or 49152, dst_ip, dst_port, data)

    def recvfrom(self):
        if self.rx_queue:
            return self.rx_queue.popleft() # (data, (src_ip, src_port))
        return None, None

class NetworkStack:
    """
    The AdiOS Unified L2/L3/L4 Network Stack.
    Integrates Ethernet, ARP, IPv4, ICMP, and UDP.
    """
    def __init__(self, ip="192.168.1.10", mac="02:AD:10:00:00:01"):
        self.ip = ip
        self.mac = mac
        self.arp_table = ARPTable()
        self.udp_bindings = {} # port -> UDPSocket
        self.tx_packets = [] # Outgoing raw Ethernet frames
        self.icmp_replies_received = []

    def bind_udp(self, port: int, sock: UDPSocket):
        self.udp_bindings[port] = sock

    def receive_ethernet(self, raw_frame: bytes):
        """Processes an incoming raw Ethernet frame from the wire/driver."""
        try:
            eth = EthernetFrame.unpack(raw_frame)
        except Exception:
            return

        # Filter: Accept broadcast or unicast directed to our MAC
        if eth.dst_mac != self.mac and eth.dst_mac.upper() != "FF:FF:FF:FF:FF:FF":
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
            eth = EthernetFrame(dst_mac=arp.src_mac, src_mac=self.mac, ethertype=ETHERTYPE_ARP, payload=reply.pack())
            self.tx_packets.append(eth.pack())

    def _handle_ipv4(self, payload: bytes, src_mac: str):
        try:
            ip_pkt = IPv4Packet.unpack(payload)
        except Exception:
            return

        self.arp_table.insert(ip_pkt.src_ip, src_mac)

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
            # Auto-generate ICMP Echo Reply (Ping responder)
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
            eth = EthernetFrame(dst_mac=dst_mac, src_mac=self.mac, ethertype=ETHERTYPE_IPV4, payload=out_ip.pack())
            self.tx_packets.append(eth.pack())
        elif icmp.icmp_type == ICMP_TYPE_ECHO_REPLY:
            self.icmp_replies_received.append((ip_pkt.src_ip, icmp.seq))

    def _handle_udp(self, ip_pkt: IPv4Packet):
        try:
            udp = UDPPacket.unpack(ip_pkt.payload)
        except Exception:
            return

        sock = self.udp_bindings.get(udp.dst_port)
        if sock:
            sock.rx_queue.append((udp.payload, (ip_pkt.src_ip, udp.src_port)))

    def send_udp(self, src_port: int, dst_ip: str, dst_port: int, data: bytes):
        """Constructs and transmits an IPv4/UDP packet."""
        udp = UDPPacket(src_port, dst_port, data)
        ip_pkt = IPv4Packet(self.ip, dst_ip, IP_PROTO_UDP, udp.pack())
        dst_mac = self.arp_table.lookup(dst_ip) or "FF:FF:FF:FF:FF:FF"
        eth = EthernetFrame(dst_mac=dst_mac, src_mac=self.mac, ethertype=ETHERTYPE_IPV4, payload=ip_pkt.pack())
        self.tx_packets.append(eth.pack())

    def send_ping(self, dst_ip: str, seq=1):
        """Sends an ICMP Echo Request."""
        icmp = ICMPPacket(ICMP_TYPE_ECHO_REQUEST, 0, ident=0xAD10, seq=seq, data=b"AdiOS_PING")
        ip_pkt = IPv4Packet(self.ip, dst_ip, IP_PROTO_ICMP, icmp.pack())
        dst_mac = self.arp_table.lookup(dst_ip) or "FF:FF:FF:FF:FF:FF"
        eth = EthernetFrame(dst_mac=dst_mac, src_mac=self.mac, ethertype=ETHERTYPE_IPV4, payload=ip_pkt.pack())
        self.tx_packets.append(eth.pack())

if __name__ == "__main__":
    stack_a = NetworkStack("192.168.1.1", "02:00:00:00:00:01")
    stack_b = NetworkStack("192.168.1.2", "02:00:00:00:00:02")

    # Stack A sends Ping to Stack B
    stack_a.send_ping("192.168.1.2", seq=1)
    frame = stack_a.tx_packets.pop(0)

    # Stack B receives and auto-replies
    stack_b.receive_ethernet(frame)
    assert len(stack_b.tx_packets) == 1
    reply_frame = stack_b.tx_packets.pop(0)

    # Stack A receives reply
    stack_a.receive_ethernet(reply_frame)
    assert len(stack_a.icmp_replies_received) == 1
    print("Network ping roundtrip test successful.")
