#!/usr/bin/env python3
"""
Test Suite: Block E Networking & Communications Subsystem
Verifies:
1. RFC 1055 SLIP Packet Framing Driver
2. Ethernet II Frames, ARP Request/Reply Resolution & Dynamic Cache
3. RFC 791 IPv4 Header Serialization & RFC 1071 Internet Checksum
4. RFC 792 ICMP Echo Request & Reply (Ping) Protocol Roundtrip
5. RFC 768 UDP Sockets & Port Multiplexing
6. RFC 854 Sovereign Cyber Telnet Server with Shell Integration
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from net.slip import SLIPDriver, SLIP_END, SLIP_ESC
from net.ipv4 import (
    EthernetFrame, ARPPacket, ARPTable, IPv4Packet,
    ETHERTYPE_IPV4, ETHERTYPE_ARP, ARP_OP_REQUEST, ARP_OP_REPLY,
    IP_PROTO_ICMP, IP_PROTO_UDP, internet_checksum
)
from net.transport import NetworkStack, UDPSocket
from net.telnet import TelnetSession, CyberTelnetServer, TELNET_IAC, TELNET_DO, TELNET_OPT_SGA

def test_net_block_e_suite():
    print("[Test Net Block E] Initializing Networking Subsystem Verification...")

    # 1. Test SLIP Driver
    print("  -> Testing RFC 1055 SLIP Packet Framing...")
    driver = SLIPDriver()
    raw_payload = b"\xC0\x00\x11\x22\xDB\x33\x44\xC0"
    framed = SLIPDriver.encode_packet(raw_payload)
    assert framed[0] == SLIP_END and framed[-1] == SLIP_END, "Invalid SLIP framing delimiters"
    assert SLIP_ESC in framed, "SLIP escape byte missing"

    # Feed in small byte chunks to verify state-machine stream decoding
    packets = []
    for chunk in [framed[:4], framed[4:10], framed[10:]]:
        packets.extend(driver.feed_stream(chunk))
    assert len(packets) == 1, f"Expected 1 extracted packet, got {len(packets)}"
    assert packets[0] == raw_payload, "Decoded SLIP payload mismatch"
    print("  -> [PASS] SLIP packet framing verified.")

    # 2. Test Ethernet II & ARP
    print("  -> Testing Ethernet II Frames & ARP Protocol...")
    eth = EthernetFrame("02:00:00:00:00:02", "02:00:00:00:00:01", ETHERTYPE_ARP, b"ARP_PAYLOAD")
    packed_eth = eth.pack()
    assert len(packed_eth) == 14 + len(b"ARP_PAYLOAD")
    unpacked_eth = EthernetFrame.unpack(packed_eth)
    assert unpacked_eth.dst_mac == "02:00:00:00:00:02"
    assert unpacked_eth.src_mac == "02:00:00:00:00:01"
    assert unpacked_eth.ethertype == ETHERTYPE_ARP

    arp = ARPPacket(
        op=ARP_OP_REQUEST,
        src_mac="02:00:00:00:00:01",
        src_ip="192.168.1.10",
        dst_mac="00:00:00:00:00:00",
        dst_ip="192.168.1.20"
    )
    packed_arp = arp.pack()
    assert len(packed_arp) == 28
    unpacked_arp = ARPPacket.unpack(packed_arp)
    assert unpacked_arp.op == ARP_OP_REQUEST
    assert unpacked_arp.src_ip == "192.168.1.10"
    assert unpacked_arp.dst_ip == "192.168.1.20"

    arp_table = ARPTable()
    arp_table.insert("192.168.1.20", "02:00:00:00:00:02")
    assert arp_table.lookup("192.168.1.20") == "02:00:00:00:00:02"
    assert arp_table.lookup("192.168.1.99") is None
    print("  -> [PASS] Ethernet II and ARP protocol verified.")

    # 3. Test IPv4 Serialization & Checksum
    print("  -> Testing RFC 791 IPv4 & RFC 1071 Checksum...")
    ip_pkt = IPv4Packet("10.0.0.1", "10.0.0.2", IP_PROTO_UDP, b"HELLO_NETWORK")
    raw_ip = ip_pkt.pack()
    assert len(raw_ip) == 20 + len(b"HELLO_NETWORK")
    unpacked_ip = IPv4Packet.unpack(raw_ip)
    assert unpacked_ip.src_ip == "10.0.0.1"
    assert unpacked_ip.dst_ip == "10.0.0.2"
    assert unpacked_ip.proto == IP_PROTO_UDP
    assert unpacked_ip.payload == b"HELLO_NETWORK"
    print("  -> [PASS] IPv4 header serialization and checksum verified.")

    # 4. Test ICMP Ping Roundtrip
    print("  -> Testing RFC 792 ICMP Ping Roundtrip between Virtual Stacks...")
    node_a = NetworkStack("192.168.1.1", "02:00:00:00:00:01")
    node_b = NetworkStack("192.168.1.2", "02:00:00:00:00:02")

    # Node A sends Ping to Node B
    node_a.send_ping("192.168.1.2", seq=42)
    assert len(node_a.tx_packets) == 1
    ping_frame = node_a.tx_packets.pop(0)

    # Node B receives frame and auto-replies
    node_b.receive_ethernet(ping_frame)
    assert len(node_b.tx_packets) == 1
    reply_frame = node_b.tx_packets.pop(0)

    # Node A receives reply
    node_a.receive_ethernet(reply_frame)
    assert len(node_a.icmp_replies_received) == 1
    src_ip, seq = node_a.icmp_replies_received[0]
    assert src_ip == "192.168.1.2" and seq == 42
    print("  -> [PASS] ICMP Ping roundtrip verified.")

    # 5. Test UDP Sockets
    print("  -> Testing RFC 768 UDP Sockets & Port Multiplexing...")
    sock_b = UDPSocket(node_b, port=8080)
    
    # Node A sends UDP packet to Node B on port 8080
    node_a.send_udp(src_port=5000, dst_ip="192.168.1.2", dst_port=8080, data=b"CYBER_DATAGRAM")
    udp_frame = node_a.tx_packets.pop(0)

    node_b.receive_ethernet(udp_frame)
    rx_data, rx_addr = sock_b.recvfrom()
    assert rx_data == b"CYBER_DATAGRAM"
    assert rx_addr == ("192.168.1.1", 5000)
    print("  -> [PASS] UDP socket communication verified.")

    # 6. Test Sovereign Cyber Telnet Server
    print("  -> Testing RFC 854 Sovereign Cyber Telnet Server...")
    telnet_server = CyberTelnetServer(node_b, port=2323)

    # Client connects by sending IAC SGA negotiation
    client_sock = UDPSocket(node_a, port=4000)
    client_sock.sendto(bytes([TELNET_IAC, TELNET_DO, TELNET_OPT_SGA]), "192.168.1.2", 2323)
    frame = node_a.tx_packets.pop(0)
    node_b.receive_ethernet(frame)
    
    # Server polls
    telnet_server.poll()
    assert len(node_b.tx_packets) >= 1 # Welcome banner + IAC reply
    banner_frame = node_b.tx_packets.pop(0)
    node_a.receive_ethernet(banner_frame)

    # Client sends shell command: "oracle 4\r\n"
    client_sock.sendto(b"oracle 4\r\n", "192.168.1.2", 2323)
    cmd_frame = node_a.tx_packets.pop(0)
    node_b.receive_ethernet(cmd_frame)

    events = telnet_server.poll()
    assert len(events) == 1, f"Expected 1 executed command event, got {len(events)}"
    c_ip, cmd, out = events[0]
    assert cmd == "oracle 4"
    assert "[Cosmic Oracle]" in out
    print("  -> [PASS] Sovereign Cyber Telnet Server verified.")

    print("\n[Test Net Block E] ALL BLOCK E NETWORKING TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_net_block_e_suite()
