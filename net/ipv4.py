#!/usr/bin/env python3
"""
AdiOS Networking Subsystem: Layer 2 Ethernet & Layer 3 IPv4 Engine (ipv4.py)
Features:
- RFC 791 IPv4 header packing, parsing, and RFC 1071 checksum calculation
- RFC 826 Address Resolution Protocol (ARP) Request/Reply generation and table cache
- Ethernet II frame encapsulation and MAC dispatching
"""

import struct
import time

ETHERTYPE_IPV4 = 0x0800
ETHERTYPE_ARP  = 0x0806

ARP_OP_REQUEST = 1
ARP_OP_REPLY   = 2

IP_PROTO_ICMP = 1
IP_PROTO_TCP  = 6
IP_PROTO_UDP  = 17

def internet_checksum(data: bytes) -> int:
    """
    Computes the standard RFC 1071 16-bit one's complement Internet Checksum.
    """
    if len(data) % 2 != 0:
        data += b"\x00"

    total = 0
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i + 1]
        total += word
        total = (total & 0xFFFF) + (total >> 16)

    return (~total) & 0xFFFF

def ip_to_u32(ip_str: str) -> int:
    """Converts dotted-quad IP string (e.g. '192.168.1.10') to 32-bit unsigned int."""
    octets = [int(p) for p in ip_str.split(".")]
    return (octets[0] << 24) | (octets[1] << 16) | (octets[2] << 8) | octets[3]

def u32_to_ip(val: int) -> str:
    """Converts 32-bit unsigned int to dotted-quad IP string."""
    return f"{(val >> 24) & 0xFF}.{(val >> 16) & 0xFF}.{(val >> 8) & 0xFF}.{val & 0xFF}"

def mac_to_bytes(mac_str: str) -> bytes:
    """Converts colon-separated MAC string (e.g. '02:00:00:00:00:01') to 6-byte bytes."""
    return bytes(int(b, 16) for b in mac_str.split(":"))

def bytes_to_mac(b: bytes) -> str:
    """Converts 6-byte bytes to colon-separated MAC string."""
    return ":".join(f"{x:02x}" for x in b)

class EthernetFrame:
    """
    IEEE 802.3 / Ethernet II 14-byte frame header.
    Format: Destination MAC (6B) + Source MAC (6B) + EtherType (2B) + Payload
    """
    def __init__(self, dst_mac="FF:FF:FF:FF:FF:FF", src_mac="02:00:00:00:00:01", ethertype=ETHERTYPE_IPV4, payload=b""):
        self.dst_mac = dst_mac
        self.src_mac = src_mac
        self.ethertype = ethertype
        self.payload = payload

    def pack(self) -> bytes:
        header = struct.pack("!6s6sH", mac_to_bytes(self.dst_mac), mac_to_bytes(self.src_mac), self.ethertype)
        return header + self.payload

    @classmethod
    def unpack(cls, data: bytes):
        if len(data) < 14:
            raise ValueError(f"Ethernet frame too short: {len(data)} bytes")
        dst_b, src_b, ethertype = struct.unpack("!6s6sH", data[:14])
        return cls(bytes_to_mac(dst_b), bytes_to_mac(src_b), ethertype, data[14:])

class ARPPacket:
    """
    RFC 826 Address Resolution Protocol (28 bytes).
    """
    def __init__(self, op=ARP_OP_REQUEST, src_mac="02:00:00:00:00:01", src_ip="192.168.1.1",
                 dst_mac="00:00:00:00:00:00", dst_ip="192.168.1.2"):
        self.hw_type = 1       # Ethernet
        self.proto_type = 0x0800 # IPv4
        self.hw_size = 6
        self.proto_size = 4
        self.op = op
        self.src_mac = src_mac
        self.src_ip = src_ip
        self.dst_mac = dst_mac
        self.dst_ip = dst_ip

    def pack(self) -> bytes:
        return struct.pack(
            "!HHBBH6sI6sI",
            self.hw_type,
            self.proto_type,
            self.hw_size,
            self.proto_size,
            self.op,
            mac_to_bytes(self.src_mac),
            ip_to_u32(self.src_ip),
            mac_to_bytes(self.dst_mac),
            ip_to_u32(self.dst_ip)
        )

    @classmethod
    def unpack(cls, data: bytes):
        if len(data) < 28:
            raise ValueError("ARP packet too short")
        ht, pt, hs, ps, op, sm, si, dm, di = struct.unpack("!HHBBH6sI6sI", data[:28])
        pkt = cls(op, bytes_to_mac(sm), u32_to_ip(si), bytes_to_mac(dm), u32_to_ip(di))
        return pkt

class ARPTable:
    """
    Dynamic cache mapping IP addresses to Ethernet MAC addresses.
    """
    def __init__(self):
        self.table = {} # IP -> (MAC, timestamp)

    def insert(self, ip: str, mac: str):
        self.table[ip] = (mac, time.time())

    def lookup(self, ip: str) -> str:
        entry = self.table.get(ip)
        return entry[0] if entry else None

class IPv4Packet:
    """
    RFC 791 IPv4 20-byte Datagram Header.
    """
    def __init__(self, src_ip="192.168.1.10", dst_ip="192.168.1.1", proto=IP_PROTO_UDP, payload=b"", ttl=64, ident=0):
        self.version = 4
        self.ihl = 5 # 5 words = 20 bytes
        self.tos = 0
        self.ident = ident
        self.flags_frag = 0x4000 # Don't Fragment (DF)
        self.ttl = ttl
        self.proto = proto
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.payload = payload

    def pack(self) -> bytes:
        total_len = 20 + len(self.payload)
        ver_ihl = (self.version << 4) | self.ihl

        # Pack header with 0 checksum first
        header_pre = struct.pack(
            "!BBHHHBBHII",
            ver_ihl,
            self.tos,
            total_len,
            self.ident,
            self.flags_frag,
            self.ttl,
            self.proto,
            0, # Checksum placeholder
            ip_to_u32(self.src_ip),
            ip_to_u32(self.dst_ip)
        )
        chk = internet_checksum(header_pre)

        # Repack with computed checksum
        header = struct.pack(
            "!BBHHHBBHII",
            ver_ihl,
            self.tos,
            total_len,
            self.ident,
            self.flags_frag,
            self.ttl,
            self.proto,
            chk,
            ip_to_u32(self.src_ip),
            ip_to_u32(self.dst_ip)
        )
        return header + self.payload

    @classmethod
    def unpack(cls, data: bytes):
        if len(data) < 20:
            raise ValueError(f"IPv4 packet too short: {len(data)} bytes")
        ver_ihl, tos, tot_len, ident, ff, ttl, proto, chk, src_i, dst_i = struct.unpack("!BBHHHBBHII", data[:20])
        version = ver_ihl >> 4
        ihl = ver_ihl & 0x0F
        if version != 4:
            raise ValueError(f"Unsupported IP version: {version}")
        header_len = ihl * 4
        
        # Verify checksum
        calc_chk = internet_checksum(data[:header_len])
        if calc_chk != 0:
            raise ValueError("IPv4 checksum error")

        payload = data[header_len:tot_len]
        pkt = cls(u32_to_ip(src_i), u32_to_ip(dst_i), proto, payload, ttl, ident)
        return pkt

if __name__ == "__main__":
    pkt = IPv4Packet("10.0.0.1", "10.0.0.2", IP_PROTO_ICMP, b"PING")
    raw = pkt.pack()
    print(f"Packed IPv4 packet: {len(raw)} bytes")
    unpacked = IPv4Packet.unpack(raw)
    assert unpacked.src_ip == "10.0.0.1"
    assert unpacked.dst_ip == "10.0.0.2"
    assert unpacked.payload == b"PING"
    print("IPv4 packet packing and parsing verified.")
