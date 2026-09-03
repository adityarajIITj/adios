#!/usr/bin/env python3
"""
Test Suite: Block M Layer-7 Network Application Protocol Suite
Verifies:
1. HTTP/1.1 Web Server routing, header parsing, Content-Length, and 404 responses
2. DNS RFC 1035 Query packet packing & A-record resolution
3. DHCP RFC 2131 4-Step DORA (Discover, Offer, Request, Ack) Lease State Machine
"""

import sys
import os
import struct

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from net.protocols import HTTPServer, HTTPResponse, DNSQuery, DNSResolver, DHCPClient, DHCP_MAGIC_COOKIE

def test_net_protocols_block_m_suite():
    print("[Test Protocols Block M] Initializing Application Protocols Verification...")

    # 1. Test HTTP/1.1 Server
    print("  -> Testing HTTP/1.1 Server & Routing...")
    server = HTTPServer()

    @server.route("GET", "/api/v1/system")
    def sys_info(req):
        return HTTPResponse(200, "OK", {"Content-Type": "application/json"}, b'{"os":"AdiOS","arch":"RV32IM"}')

    raw_get = b"GET /api/v1/system HTTP/1.1\r\nHost: node.adios\r\nUser-Agent: AdiOS-Curl\r\n\r\n"
    resp = server.handle_raw_request(raw_get)
    assert b"HTTP/1.1 200 OK" in resp
    assert b"Content-Type: application/json" in resp
    assert b"Content-Length: 30" in resp
    assert b'{"os":"AdiOS","arch":"RV32IM"}' in resp

    # Test 404
    resp_404 = server.handle_raw_request(b"GET /missing/resource HTTP/1.1\r\n\r\n")
    assert b"HTTP/1.1 404 Not Found" in resp_404
    print("  -> [PASS] HTTP/1.1 Server & Routing verified.")

    # 2. Test DNS Query & Response Resolver
    print("  -> Testing RFC 1035 DNS Query & Resolver...")
    dq = DNSQuery(tx_id=0x9ABC).build_query("hyperion.node.adios")
    assert len(dq) > 20
    assert dq[:2] == b"\x9a\xbc"

    # Construct synthetic DNS response for "hyperion.node.adios" -> 192.168.1.42
    # Header: ID 0x9ABC, Flags 0x8180 (Standard response, no error), QD=1, AN=1, NS=0, AR=0
    hdr = struct.pack("!HHHHHH", 0x9ABC, 0x8180, 1, 1, 0, 0)
    # Question copy: \x08hyperion\x04node\x05adios\x00, TYPE A (1), CLASS IN (1)
    qname = b"\x08hyperion\x04node\x05adios\x00"
    q_section = qname + struct.pack("!HH", 1, 1)
    # Answer section: Pointer to QNAME (0xC00C), TYPE A (1), CLASS IN (1), TTL 300, RDLENGTH 4, IP 192.168.1.42
    ans_section = struct.pack("!HHHIH4B", 0xC00C, 1, 1, 300, 4, 192, 168, 1, 42)
    synthetic_dns_resp = hdr + q_section + ans_section

    parsed_dns = DNSResolver.parse_response(synthetic_dns_resp)
    assert parsed_dns["tx_id"] == 0x9ABC
    assert len(parsed_dns["answers"]) == 1
    assert parsed_dns["answers"][0]["ip"] == "192.168.1.42"
    assert parsed_dns["answers"][0]["ttl"] == 300
    print("  -> [PASS] DNS Query & Resolver verified.")

    # 3. Test DHCP 4-Step DORA State Machine
    print("  -> Testing RFC 2131 DHCP DORA Client...")
    client = DHCPClient(mac_bytes=b"\x52\x54\x00\xAA\xBB\xCC")
    assert client.state == "INIT"

    # Step 1: Discover
    disc_pkt = client.build_discover()
    assert client.state == "SELECTING"
    assert len(disc_pkt) >= 240

    # Step 2: Synthetic Server Offer (IP 10.0.2.15, Server 10.0.2.2, Subnet 255.255.255.0, Router 10.0.2.2, DNS 10.0.2.3)
    offer_base = bytearray(236)
    offer_base[0] = 2 # BOOTREPLY
    struct.pack_into("!I", offer_base, 4, client.xid)
    offer_base[16:20] = bytes([10, 0, 2, 15]) # yiaddr
    offer_opts = bytearray(struct.pack("!I", DHCP_MAGIC_COOKIE))
    offer_opts.extend([53, 1, 2]) # DHCP Offer
    offer_opts.extend([54, 4, 10, 0, 2, 2]) # Server ID
    offer_opts.extend([1, 4, 255, 255, 255, 0]) # Subnet Mask
    offer_opts.extend([3, 4, 10, 0, 2, 2]) # Router
    offer_opts.extend([6, 4, 10, 0, 2, 3]) # DNS Server
    offer_opts.append(255)
    synthetic_offer = bytes(offer_base) + bytes(offer_opts)

    req_pkt = client.process_offer(synthetic_offer)
    assert client.state == "REQUESTING"
    assert client.assigned_ip == "10.0.2.15"
    assert client.server_ip == "10.0.2.2"

    # Step 4: Synthetic Server Ack
    ack_base = bytearray(236)
    ack_base[0] = 2
    struct.pack_into("!I", ack_base, 4, client.xid)
    ack_opts = bytearray(struct.pack("!I", DHCP_MAGIC_COOKIE))
    ack_opts.extend([53, 1, 5]) # DHCP Ack
    ack_opts.extend([1, 4, 255, 255, 255, 0])
    ack_opts.extend([3, 4, 10, 0, 2, 2])
    ack_opts.extend([6, 4, 10, 0, 2, 3])
    ack_opts.append(255)
    synthetic_ack = bytes(ack_base) + bytes(ack_opts)

    client.process_ack(synthetic_ack)
    assert client.state == "BOUND"
    assert client.assigned_ip == "10.0.2.15"
    assert client.subnet_mask == "255.255.255.0"
    assert client.router == "10.0.2.2"
    assert client.dns_server == "10.0.2.3"
    print("  -> [PASS] DHCP DORA Lease Acquisition verified (Client BOUND).")

    print("\n[Test Protocols Block M] ALL BLOCK M APPLICATION PROTOCOL TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_net_protocols_block_m_suite()
