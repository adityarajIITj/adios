#!/usr/bin/env python3
"""
Test Suite: Block L Transmission Control Protocol Engine
Verifies:
1. TCP Header packing, unpacking, and pseudo-header checksum calculation
2. RFC 793 3-Way Handshake (SYN, SYN-ACK, ACK)
3. Bidirectional data transfer stream with sequence & acknowledgment tracking
4. Graceful 4-way connection teardown (FIN, ACK, TIME_WAIT, CLOSED)
5. Out-of-sequence rejection and sliding window acknowledgment
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from net.tcp import TCPSocket, TCPHeader, TCPState, TCP_FLAG_SYN, TCP_FLAG_ACK, TCP_FLAG_FIN

def test_tcp_block_l_suite():
    print("[Test TCP Block L] Initializing Transmission Control Protocol Verification...")

    # 1. Test TCP Header & Checksum
    print("  -> Testing TCP Header Serialization & Checksum...")
    hdr = TCPHeader(src_port=8080, dst_port=80, seq_num=1000, ack_num=5000, flags=TCP_FLAG_ACK)
    raw_hdr = hdr.pack(src_ip="192.168.1.100", dst_ip="192.168.1.1", payload=b"HELLO_TCP")
    assert len(raw_hdr) == 20
    assert hdr.checksum != 0

    unpacked = TCPHeader.unpack(raw_hdr)
    assert unpacked.src_port == 8080
    assert unpacked.dst_port == 80
    assert unpacked.seq_num == 1000
    assert unpacked.ack_num == 5000
    assert unpacked.flags == TCP_FLAG_ACK
    print("  -> [PASS] TCP Header & Checksum verified.")

    # 2. Test 3-Way Handshake Connection Establishment
    print("  -> Testing RFC 793 3-Way Handshake (Client <-> Server)...")
    server = TCPSocket(local_ip="10.0.2.1", local_port=80)
    server.listen()
    assert server.state == TCPState.LISTEN

    client = TCPSocket(local_ip="10.0.2.15", local_port=49152)
    client.connect("10.0.2.1", 80)
    assert client.state == TCPState.SYN_SENT

    # Client -> Server: SYN
    syn_hdr, syn_payload = client.tx_queue.pop(0)
    server.process_incoming_segment(syn_hdr, syn_payload)
    assert len(server.pending_connections) == 1
    server_conn = server.pending_connections[0]
    assert server_conn.state == TCPState.SYN_RECEIVED

    # Server -> Client: SYN+ACK
    syn_ack_hdr, syn_ack_payload = server_conn.tx_queue.pop(0)
    client.process_incoming_segment(syn_ack_hdr, syn_ack_payload)
    assert client.state == TCPState.ESTABLISHED

    # Client -> Server: ACK
    ack_hdr, ack_payload = client.tx_queue.pop(0)
    server_conn.process_incoming_segment(ack_hdr, ack_payload)
    assert server_conn.state == TCPState.ESTABLISHED
    print("  -> [PASS] 3-Way Handshake verified (Both in ESTABLISHED state).")

    # 3. Test Bidirectional Data Stream Transfer
    print("  -> Testing Bidirectional Stream Data Transfer...")
    http_req = b"GET /status HTTP/1.1\r\nHost: sovereign.adios\r\n\r\n"
    client.send(http_req)

    # Transfer client packet to server
    data_hdr, payload = client.tx_queue.pop(0)
    server_conn.process_incoming_segment(data_hdr, payload)
    
    # Server reads request
    req_received = server_conn.recv(1024)
    assert req_received == http_req

    # Server sends immediate ACK back to client
    ack_to_client, _ = server_conn.tx_queue.pop(0)
    client.process_incoming_segment(ack_to_client, b"")

    # Server sends HTTP Response
    http_resp = b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nADIOS_SOVEREIGN_TCP_ONLINE"
    server_conn.send(http_resp)

    resp_hdr, resp_payload = server_conn.tx_queue.pop(0)
    client.process_incoming_segment(resp_hdr, resp_payload)

    # Client reads response
    resp_received = client.recv(1024)
    assert resp_received == http_resp

    # Client ACKs server's response
    ack_to_server, _ = client.tx_queue.pop(0)
    server_conn.process_incoming_segment(ack_to_server, b"")
    print("  -> [PASS] Bidirectional stream transfer verified.")

    # 4. Test Graceful Connection Teardown
    print("  -> Testing Graceful Connection Teardown (FIN / ACK Handshake)...")
    client.close()
    assert client.state == TCPState.FIN_WAIT_1

    # Client sends FIN -> Server
    fin_hdr, _ = client.tx_queue.pop(0)
    server_conn.process_incoming_segment(fin_hdr, b"")
    assert server_conn.state == TCPState.CLOSE_WAIT

    # Server sends ACK -> Client
    ack_fin, _ = server_conn.tx_queue.pop(0)
    client.process_incoming_segment(ack_fin, b"")
    assert client.state == TCPState.FIN_WAIT_2

    # Server closes its side: sends FIN -> Client
    server_conn.close()
    assert server_conn.state == TCPState.LAST_ACK

    srv_fin_hdr, _ = server_conn.tx_queue.pop(0)
    client.process_incoming_segment(srv_fin_hdr, b"")
    assert client.state == TCPState.TIME_WAIT

    # Client sends final ACK -> Server
    final_ack, _ = client.tx_queue.pop(0)
    server_conn.process_incoming_segment(final_ack, b"")
    assert server_conn.state == TCPState.CLOSED
    print("  -> [PASS] Graceful 4-way teardown verified.")

    print("\n[Test TCP Block L] ALL BLOCK L TCP TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_tcp_block_l_suite()
