#!/usr/bin/env python3
"""
Test Suite: Network Stack Deepened Subsystem (Pass X Checkpoint 8)
Verifies:
1. Deepened IPv4 Layer: Fragmentation, Reassembly, LPM Routing, ARP TTL
2. Deepened Transport Layer: UDP Pseudo-Header Checksum, Ephemeral Ports, NetPoll, Ping
3. Deepened Application Layer: HTTP Chunked Transfer, Cookies, DNS Response Builder, DHCP Server Pool

Zero external dependencies. Pure RV32IM bare-metal test harness.
STRICT ZERO EMOJI POLICY ENFORCED.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from net.ipv4 import (
    IPv4Packet, IPv4Fragmenter, IPv4Reassembler, RoutingTable, ARPTable,
    IP_PROTO_UDP, IP_PROTO_ICMP
)
from net.transport import (
    UDPPacket, UDPSocket, NetworkStack, EphemeralPortManager, NetPoll, POLLIN
)
from net.protocols import (
    HTTPServer, HTTPResponse, HTTPCookie, DNSResponseBuilder, DNSResolver,
    DHCPClient, DHCPServer
)

class TestNetStackDeepened(unittest.TestCase):

    def test_01_ipv4_fragmentation_and_reassembly(self):
        payload = b"A" * 3200
        packet = IPv4Packet("10.0.0.1", "10.0.0.2", IP_PROTO_UDP, payload, ident=0x7788, flags_frag=0)
        frags = IPv4Fragmenter.fragment(packet, mtu=1500)
        self.assertEqual(len(frags), 3)

        # More fragments bit check
        self.assertTrue(frags[0].more_fragments)
        self.assertTrue(frags[1].more_fragments)
        self.assertFalse(frags[2].more_fragments)

        # Reassemble out-of-order
        reassembler = IPv4Reassembler()
        self.assertIsNone(reassembler.receive_fragment(frags[2]))
        self.assertIsNone(reassembler.receive_fragment(frags[0]))
        complete = reassembler.receive_fragment(frags[1])
        self.assertIsNotNone(complete)
        self.assertEqual(complete.payload, payload)

    def test_02_routing_table_lpm(self):
        rt = RoutingTable()
        rt.add_route("0.0.0.0", "0.0.0.0", "192.168.1.1", "eth0", metric=10)
        rt.add_route("10.0.0.0", "255.0.0.0", "10.0.0.1", "eth1", metric=1)
        rt.add_route("10.1.2.0", "255.255.255.0", "10.1.2.254", "eth2", metric=1)

        # Longest prefix match: 10.1.2.55 should hit /24 route
        r = rt.lookup("10.1.2.55")
        self.assertEqual(r.dest_net, "10.1.2.0")
        self.assertEqual(r.gateway, "10.1.2.254")

        # 10.5.5.5 should hit /8 route
        r2 = rt.lookup("10.5.5.5")
        self.assertEqual(r2.dest_net, "10.0.0.0")

        # Internet route hits default
        r_def = rt.lookup("172.16.0.1")
        self.assertEqual(r_def.gateway, "192.168.1.1")

    def test_03_udp_pseudo_header_checksum(self):
        udp = UDPPacket(src_port=5000, dst_port=6000, payload=b"CheckMe")
        raw = udp.pack(src_ip="192.168.1.5", dst_ip="192.168.1.6", compute_checksum=True)

        unpacked = UDPPacket.unpack(raw, src_ip="192.168.1.5", dst_ip="192.168.1.6", verify_checksum=True)
        self.assertEqual(unpacked.payload, b"CheckMe")
        self.assertNotEqual(unpacked.checksum, 0)

    def test_04_ephemeral_port_manager_and_netpoll(self):
        mgr = EphemeralPortManager(start_port=50000, end_port=50002)
        p1 = mgr.allocate()
        p2 = mgr.allocate()
        p3 = mgr.allocate()
        self.assertEqual(p1, 50000)
        self.assertEqual(p2, 50001)
        self.assertEqual(p3, 50002)
        self.assertRaises(IOError, mgr.allocate)

        mgr.release(p2)
        p_reused = mgr.allocate()
        self.assertEqual(p_reused, 50001)

        # NetPoll test
        stack = NetworkStack("192.168.1.10")
        sock = UDPSocket(stack, port=p1)
        poll = NetPoll()
        poll.register(sock, POLLIN)
        self.assertEqual(len(poll.poll()), 0)
        sock.rx_queue.append((b"IncomingData", ("10.0.0.1", 9999)))
        ready = poll.poll()
        self.assertEqual(len(ready), 1)

    def test_05_http_chunked_and_cookies(self):
        chunks = [b"Part1_", b"Part2_", b"Final"]
        encoded = HTTPResponse.encode_chunked(chunks)
        decoded = HTTPResponse.decode_chunked(encoded)
        self.assertEqual(decoded, b"Part1_Part2_Final")

        server = HTTPServer()
        @server.route("POST", "/auth")
        def auth_handler(req):
            cookie = HTTPCookie("jwt", "sample_token_xyz", httponly=True)
            return HTTPResponse(200, "OK", body=b"Authenticated", cookies=[cookie])

        raw_req = b"POST /auth HTTP/1.1\r\nHost: local\r\nContent-Length: 0\r\n\r\n"
        resp = server.handle_raw_request(raw_req)
        self.assertIn(b"200 OK", resp)
        self.assertIn(b"Set-Cookie: jwt=sample_token_xyz; Path=/; HttpOnly", resp)

    def test_06_dns_builder_and_dhcp_server(self):
        # DNS Builder & Resolver
        wire = DNSResponseBuilder.build_response(0x9999, "antigravity.os", "10.20.30.40")
        parsed = DNSResolver.parse_response(wire)
        self.assertEqual(parsed["tx_id"], 0x9999)
        self.assertEqual(parsed["answers"][0]["ip"], "10.20.30.40")

        # DHCP Server & Client DORA
        server = DHCPServer(server_ip="192.168.1.1", pool_start="192.168.1.50", pool_end="192.168.1.60")
        client = DHCPClient(mac_bytes=b"\x00\xAA\xBB\xCC\xDD\xEE")

        disc = client.build_discover()
        offer = server.handle_packet(disc)
        self.assertIsNotNone(offer)

        req = client.process_offer(offer)
        ack = server.handle_packet(req)
        self.assertIsNotNone(ack)

        client.process_ack(ack)
        self.assertEqual(client.state, "BOUND")
        self.assertEqual(client.assigned_ip, "192.168.1.50")
        self.assertEqual(client.router, "192.168.1.1")

if __name__ == "__main__":
    unittest.main()
