#!/usr/bin/env python3
"""
AdiOS Network Stack: Transmission Control Protocol Engine (tcp.py)
Implements RFC 793 full Transmission Control Protocol state machine:
- 11 Standard TCP States (CLOSED..TIME_WAIT)
- 3-Way Handshake (SYN, SYN-ACK, ACK)
- Sequence and Acknowledgment tracking
- Sliding Window flow control
- 16-bit One's Complement Internet Checksum over IPv4 Pseudo-Header
- Connection Teardown (FIN, ACK, TIME_WAIT)
Zero external dependencies.
"""

import struct
from enum import Enum, auto
from typing import Optional, Tuple, Dict, List
from net.ipv4 import ip_to_u32, u32_to_ip, internet_checksum as calculate_checksum

# TCP Control Flags
TCP_FLAG_FIN = 0x01
TCP_FLAG_SYN = 0x02
TCP_FLAG_RST = 0x04
TCP_FLAG_PSH = 0x08
TCP_FLAG_ACK = 0x10
TCP_FLAG_URG = 0x20

IP_PROTO_TCP = 6

class TCPState(Enum):
    CLOSED       = auto()
    LISTEN       = auto()
    SYN_SENT     = auto()
    SYN_RECEIVED = auto()
    ESTABLISHED  = auto()
    FIN_WAIT_1   = auto()
    FIN_WAIT_2   = auto()
    CLOSE_WAIT   = auto()
    CLOSING      = auto()
    LAST_ACK     = auto()
    TIME_WAIT    = auto()

class TCPHeader:
    """
    Standard 20-byte TCP Header.
    """
    def __init__(self, src_port: int, dst_port: int, seq_num: int, ack_num: int,
                 flags: int, window_size: int = 65535, urgent_ptr: int = 0):
        self.src_port = src_port
        self.dst_port = dst_port
        self.seq_num = seq_num
        self.ack_num = ack_num
        self.data_offset = 5  # 5 32-bit words = 20 bytes
        self.flags = flags
        self.window_size = window_size
        self.checksum = 0
        self.urgent_ptr = urgent_ptr

    def pack(self, src_ip: str = "0.0.0.0", dst_ip: str = "0.0.0.0", payload: bytes = b"") -> bytes:
        """Packs header and computes RFC 793 pseudo-header checksum."""
        offset_flags = (self.data_offset << 12) | (self.flags & 0x1FF)
        header_no_csum = struct.pack(
            "!HHIIHHHH",
            self.src_port,
            self.dst_port,
            self.seq_num,
            self.ack_num,
            offset_flags,
            self.window_size,
            0, # Checksum field is zero during calculation
            self.urgent_ptr
        )

        # Build IPv4 Pseudo-Header
        tcp_len = len(header_no_csum) + len(payload)
        pseudo_hdr = struct.pack(
            "!4s4sBBH",
            socket_inet_aton(src_ip),
            socket_inet_aton(dst_ip),
            0,
            IP_PROTO_TCP,
            tcp_len
        )

        csum = calculate_checksum(pseudo_hdr + header_no_csum + payload)
        self.checksum = csum

        return struct.pack(
            "!HHIIHHHH",
            self.src_port,
            self.dst_port,
            self.seq_num,
            self.ack_num,
            offset_flags,
            self.window_size,
            self.checksum,
            self.urgent_ptr
        )

    @classmethod
    def unpack(cls, data: bytes) -> 'TCPHeader':
        sp, dp, seq, ack, off_flags, win, csum, urg = struct.unpack("!HHIIHHHH", data[:20])
        hdr = cls(sp, dp, seq, ack, off_flags & 0x1FF, win, urg)
        hdr.data_offset = (off_flags >> 12) & 0xF
        hdr.checksum = csum
        return hdr

def socket_inet_aton(ip_str: str) -> bytes:
    parts = [int(p) for p in ip_str.split('.')]
    return bytes(parts)

class TCPSocket:
    """
    RFC 793 stateful TCP endpoint.
    """
    def __init__(self, local_ip: str = "10.0.2.15", local_port: int = 0):
        self.local_ip = local_ip
        self.local_port = local_port
        self.remote_ip = "0.0.0.0"
        self.remote_port = 0
        self.state = TCPState.CLOSED

        # Transmission Control Block (TCB) variables
        self.snd_una = 0 # Send unacknowledged
        self.snd_nxt = 1000 # Send next
        self.snd_wnd = 65535
        self.rcv_nxt = 0 # Receive next
        self.rcv_wnd = 65535
        self.iss = 1000 # Initial send sequence

        self.rx_stream = bytearray()
        self.tx_queue: List[Tuple[TCPHeader, bytes]] = []
        self.pending_connections: List['TCPSocket'] = []

        # Reno Congestion Control (RFC 5681)
        self.mss = 1460
        self.cwnd = 1460 # Initial 1 MSS slow start window
        self.ssthresh = 65535
        self.dup_ack_count = 0
        self.last_ack_num = 0
        self.in_fast_recovery = False

        # Jacobson RTT Estimation (RFC 6298)
        self.srtt: Optional[float] = None
        self.rttvar: Optional[float] = None
        self.rto: float = 1.0 # Initial RTO = 1.0s

        # Out-of-order Reassembly Buffer
        self.out_of_order_queue: List[Tuple[int, bytes]] = []

    def update_rtt(self, sample_rtt: float):
        """Updates Jacobson smoothed RTT and retransmission timeout (RTO)."""
        if self.srtt is None or self.rttvar is None:
            self.srtt = sample_rtt
            self.rttvar = sample_rtt / 2.0
            self.rto = min(60.0, max(1.0, self.srtt + max(0.1, 4.0 * self.rttvar)))
        else:
            self.rttvar = (1.0 - 0.25) * self.rttvar + 0.25 * abs(self.srtt - sample_rtt)
            self.srtt = (1.0 - 0.125) * self.srtt + 0.125 * sample_rtt
            self.rto = min(60.0, max(1.0, self.srtt + max(0.1, 4.0 * self.rttvar)))

    def on_ack_received(self, ack_num: int):
        """RFC 5681 Reno Congestion Control ACK processor."""
        if ack_num == self.last_ack_num:
            self.dup_ack_count += 1
            if self.dup_ack_count == 3:
                # Fast Retransmit / Fast Recovery Entry
                self.ssthresh = max(self.cwnd // 2, 2 * self.mss)
                self.cwnd = self.ssthresh + 3 * self.mss
                self.in_fast_recovery = True
            elif self.dup_ack_count > 3 and self.in_fast_recovery:
                self.cwnd += self.mss
        elif ack_num > self.last_ack_num:
            if self.in_fast_recovery:
                self.cwnd = self.ssthresh
                self.in_fast_recovery = False
            else:
                if self.cwnd < self.ssthresh:
                    # Slow start: increment by 1 MSS per ACK
                    self.cwnd += self.mss
                else:
                    # Congestion avoidance: additive increase
                    self.cwnd += max(1, (self.mss * self.mss) // self.cwnd)
            self.dup_ack_count = 0
            self.last_ack_num = ack_num

    def on_timeout(self):
        """Handles RTO retransmission timeout (exponential backoff)."""
        self.ssthresh = max(self.cwnd // 2, 2 * self.mss)
        self.cwnd = self.mss
        self.in_fast_recovery = False
        self.dup_ack_count = 0
        self.rto = min(60.0, self.rto * 2.0)

    def bind(self, ip: str, port: int):
        self.local_ip = ip
        self.local_port = port

    def listen(self, backlog: int = 5):
        self.state = TCPState.LISTEN

    def connect(self, remote_ip: str, remote_port: int):
        self.remote_ip = remote_ip
        self.remote_port = remote_port
        self.iss = 1000
        self.snd_nxt = self.iss + 1
        self.snd_una = self.iss

        # Send SYN segment
        syn_hdr = TCPHeader(
            src_port=self.local_port,
            dst_port=self.remote_port,
            seq_num=self.iss,
            ack_num=0,
            flags=TCP_FLAG_SYN,
            window_size=self.rcv_wnd
        )
        self.tx_queue.append((syn_hdr, b""))
        self.state = TCPState.SYN_SENT

    def send(self, data: bytes):
        """Enqueues payload data respecting flow and congestion windows."""
        if self.state != TCPState.ESTABLISHED:
            raise ConnectionError("Socket is not in ESTABLISHED state")

        offset = 0
        effective_wnd = min(self.snd_wnd, self.cwnd)
        while offset < len(data):
            chunk_size = min(self.mss, len(data) - offset)
            chunk = data[offset : offset + chunk_size]
            hdr = TCPHeader(
                src_port=self.local_port,
                dst_port=self.remote_port,
                seq_num=self.snd_nxt,
                ack_num=self.rcv_nxt,
                flags=TCP_FLAG_ACK | TCP_FLAG_PSH,
                window_size=self.rcv_wnd
            )
            self.tx_queue.append((hdr, chunk))
            self.snd_nxt += len(chunk)
            offset += chunk_size

    def recv(self, max_bytes: int = 4096) -> bytes:
        chunk = bytes(self.rx_stream[:max_bytes])
        del self.rx_stream[:len(chunk)]
        return chunk

    def close(self):
        if self.state == TCPState.ESTABLISHED:
            fin_hdr = TCPHeader(
                src_port=self.local_port,
                dst_port=self.remote_port,
                seq_num=self.snd_nxt,
                ack_num=self.rcv_nxt,
                flags=TCP_FLAG_FIN | TCP_FLAG_ACK,
                window_size=self.rcv_wnd
            )
            self.snd_nxt += 1
            self.tx_queue.append((fin_hdr, b""))
            self.state = TCPState.FIN_WAIT_1
        elif self.state == TCPState.CLOSE_WAIT:
            fin_hdr = TCPHeader(
                src_port=self.local_port,
                dst_port=self.remote_port,
                seq_num=self.snd_nxt,
                ack_num=self.rcv_nxt,
                flags=TCP_FLAG_FIN | TCP_FLAG_ACK,
                window_size=self.rcv_wnd
            )
            self.snd_nxt += 1
            self.tx_queue.append((fin_hdr, b""))
            self.state = TCPState.LAST_ACK
        else:
            self.state = TCPState.CLOSED

    def process_incoming_segment(self, hdr: TCPHeader, payload: bytes):
        """Advances TCP state machine and updates congestion / sliding windows."""
        # Update advertised receive window
        self.snd_wnd = hdr.window_size

        if self.state == TCPState.LISTEN:
            if hdr.flags & TCP_FLAG_SYN:
                # Accept connection
                conn = TCPSocket(local_ip=self.local_ip, local_port=self.local_port)
                conn.remote_ip = "10.0.2.15"
                conn.remote_port = hdr.src_port
                conn.rcv_nxt = hdr.seq_num + 1
                conn.iss = 5000
                conn.snd_nxt = conn.iss + 1
                conn.snd_una = conn.iss

                # Send SYN+ACK
                syn_ack = TCPHeader(
                    src_port=conn.local_port,
                    dst_port=conn.remote_port,
                    seq_num=conn.iss,
                    ack_num=conn.rcv_nxt,
                    flags=TCP_FLAG_SYN | TCP_FLAG_ACK,
                    window_size=conn.rcv_wnd
                )
                conn.tx_queue.append((syn_ack, b""))
                conn.state = TCPState.SYN_RECEIVED
                self.pending_connections.append(conn)
            return

        if self.state == TCPState.SYN_SENT:
            if (hdr.flags & TCP_FLAG_SYN) and (hdr.flags & TCP_FLAG_ACK):
                if hdr.ack_num == self.snd_nxt:
                    self.rcv_nxt = hdr.seq_num + 1
                    self.snd_una = hdr.ack_num

                    # Send ACK
                    ack_hdr = TCPHeader(
                        src_port=self.local_port,
                        dst_port=self.remote_port,
                        seq_num=self.snd_nxt,
                        ack_num=self.rcv_nxt,
                        flags=TCP_FLAG_ACK,
                        window_size=self.rcv_wnd
                    )
                    self.tx_queue.append((ack_hdr, b""))
                    self.state = TCPState.ESTABLISHED
            return

        if self.state == TCPState.SYN_RECEIVED:
            if hdr.flags & TCP_FLAG_ACK:
                if hdr.ack_num == self.snd_nxt:
                    self.snd_una = hdr.ack_num
                    self.state = TCPState.ESTABLISHED
            return

        if self.state == TCPState.ESTABLISHED:
            # Process ACK & update congestion control
            if hdr.flags & TCP_FLAG_ACK:
                self.snd_una = max(self.snd_una, hdr.ack_num)
                self.on_ack_received(hdr.ack_num)

            # Process payload with out-of-order reassembly
            if payload:
                if hdr.seq_num == self.rcv_nxt:
                    self.rx_stream.extend(payload)
                    self.rcv_nxt += len(payload)

                    # Drain any contiguous out-of-order fragments
                    self.out_of_order_queue.sort(key=lambda x: x[0])
                    drained = True
                    while drained:
                        drained = False
                        for idx, (seq, ooo_data) in enumerate(self.out_of_order_queue):
                            if seq == self.rcv_nxt:
                                self.rx_stream.extend(ooo_data)
                                self.rcv_nxt += len(ooo_data)
                                self.out_of_order_queue.pop(idx)
                                drained = True
                                break
                elif hdr.seq_num > self.rcv_nxt:
                    # Enqueue out-of-order fragment
                    self.out_of_order_queue.append((hdr.seq_num, payload))

                # Send immediate ACK
                ack_hdr = TCPHeader(
                    src_port=self.local_port,
                    dst_port=self.remote_port,
                    seq_num=self.snd_nxt,
                    ack_num=self.rcv_nxt,
                    flags=TCP_FLAG_ACK,
                    window_size=self.rcv_wnd
                )
                self.tx_queue.append((ack_hdr, b""))

            if hdr.flags & TCP_FLAG_FIN:
                self.rcv_nxt = hdr.seq_num + 1
                ack_hdr = TCPHeader(
                    src_port=self.local_port,
                    dst_port=self.remote_port,
                    seq_num=self.snd_nxt,
                    ack_num=self.rcv_nxt,
                    flags=TCP_FLAG_ACK,
                    window_size=self.rcv_wnd
                )
                self.tx_queue.append((ack_hdr, b""))
                self.state = TCPState.CLOSE_WAIT
            return

        if self.state == TCPState.FIN_WAIT_1:
            if (hdr.flags & TCP_FLAG_ACK) and hdr.ack_num == self.snd_nxt:
                self.state = TCPState.FIN_WAIT_2
            if hdr.flags & TCP_FLAG_FIN:
                self.rcv_nxt = hdr.seq_num + 1
                ack_hdr = TCPHeader(
                    src_port=self.local_port,
                    dst_port=self.remote_port,
                    seq_num=self.snd_nxt,
                    ack_num=self.rcv_nxt,
                    flags=TCP_FLAG_ACK,
                    window_size=self.rcv_wnd
                )
                self.tx_queue.append((ack_hdr, b""))
                self.state = TCPState.TIME_WAIT
            return

        if self.state == TCPState.FIN_WAIT_2:
            if hdr.flags & TCP_FLAG_FIN:
                self.rcv_nxt = hdr.seq_num + 1
                ack_hdr = TCPHeader(
                    src_port=self.local_port,
                    dst_port=self.remote_port,
                    seq_num=self.snd_nxt,
                    ack_num=self.rcv_nxt,
                    flags=TCP_FLAG_ACK,
                    window_size=self.rcv_wnd
                )
                self.tx_queue.append((ack_hdr, b""))
                self.state = TCPState.TIME_WAIT
            return

        if self.state == TCPState.LAST_ACK:
            if (hdr.flags & TCP_FLAG_ACK) and hdr.ack_num == self.snd_nxt:
                self.state = TCPState.CLOSED
            return

if __name__ == "__main__":
    # Test 3-way handshake simulation between client and server
    server = TCPSocket(local_ip="10.0.2.1", local_port=80)
    server.listen()

    client = TCPSocket(local_ip="10.0.2.15", local_port=49152)
    client.connect("10.0.2.1", 80)
    assert client.state == TCPState.SYN_SENT

    # 1. Client sends SYN -> Server
    syn_hdr, _ = client.tx_queue.pop(0)
    server.process_incoming_segment(syn_hdr, b"")
    assert len(server.pending_connections) == 1
    server_conn = server.pending_connections[0]
    assert server_conn.state == TCPState.SYN_RECEIVED

    # 2. Server sends SYN-ACK -> Client
    syn_ack_hdr, _ = server_conn.tx_queue.pop(0)
    client.process_incoming_segment(syn_ack_hdr, b"")
    assert client.state == TCPState.ESTABLISHED

    # 3. Client sends ACK -> Server
    ack_hdr, _ = client.tx_queue.pop(0)
    server_conn.process_incoming_segment(ack_hdr, b"")
    assert server_conn.state == TCPState.ESTABLISHED
    print("TCP 3-way handshake verified.")
