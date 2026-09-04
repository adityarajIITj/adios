#!/usr/bin/env python3
"""
AdiOS Network Subsystem: TCP Congestion Control State Machine (net/tcp_congestion.py)
Implements RFC 5681 TCP Congestion Control:
- Algorithms: TCP Reno and TCP Tahoe
- Phase State Machine:
    - Slow Start (exponential window growth: cwnd += SMSS)
    - Congestion Avoidance (additive linear growth: cwnd += SMSS*SMSS / cwnd)
    - Fast Retransmit (triggered on 3 duplicate ACKs)
    - Fast Recovery (artificial window inflation during out-of-order segment delivery)
- Retransmission Timeout (RTO) penalty: ssthresh collapse and window reset to 1 SMSS

Zero external dependencies. Pure bare-metal networking stack component.
STRICT ZERO EMOJI POLICY.
"""

from enum import Enum
from typing import Optional, Tuple

class CongestionState(Enum):
    SLOW_START           = 1
    CONGESTION_AVOIDANCE = 2
    FAST_RECOVERY        = 3

class TCPCongestionControl:
    """
    Reno Congestion Control Controller for TCP connections.
    """
    def __init__(self, smss: int = 1460, initial_ssthresh: int = 65535):
        self.smss = smss
        self.cwnd = 2 * smss # Initial window: 2 SMSS
        self.ssthresh = initial_ssthresh
        self.state = CongestionState.SLOW_START
        self.dup_acks = 0
        self.last_ack = 0
        self.bytes_in_flight = 0

    def on_ack_received(self, ack_num: int, bytes_acked: int) -> Tuple[CongestionState, bool]:
        """
        Processes an incoming ACK packet.
        Returns (new_state, should_fast_retransmit).
        """
        should_fast_retransmit = False

        if ack_num == self.last_ack:
            # Duplicate ACK
            self.dup_acks += 1

            if self.state == CongestionState.FAST_RECOVERY:
                # In fast recovery, inflate cwnd by 1 SMSS for each additional dup ACK
                self.cwnd += self.smss
            elif self.dup_acks == 3:
                # 3 Duplicate ACKs: Trigger Fast Retransmit & Fast Recovery
                flight = max(self.bytes_in_flight, self.smss * 2)
                self.ssthresh = max(flight // 2, 2 * self.smss)
                self.cwnd = self.ssthresh + 3 * self.smss
                self.state = CongestionState.FAST_RECOVERY
                should_fast_retransmit = True

        else:
            # New ACK
            self.last_ack = ack_num
            self.dup_acks = 0

            if self.state == CongestionState.FAST_RECOVERY:
                # Deflate window back to ssthresh and enter Congestion Avoidance
                self.cwnd = self.ssthresh
                self.state = CongestionState.CONGESTION_AVOIDANCE

            elif self.state == CongestionState.SLOW_START:
                # Exponential growth: add 1 SMSS per ACK
                self.cwnd += self.smss
                if self.cwnd >= self.ssthresh:
                    self.state = CongestionState.CONGESTION_AVOIDANCE

            elif self.state == CongestionState.CONGESTION_AVOIDANCE:
                # Additive increase: approximately 1 SMSS per RTT
                increment = (self.smss * self.smss) // max(self.cwnd, 1)
                self.cwnd += max(1, increment)

        return self.state, should_fast_retransmit

    def on_timeout(self):
        """
        Handles Retransmission Timeout (RTO) event: severe congestion.
        """
        flight = max(self.bytes_in_flight, self.smss * 2)
        self.ssthresh = max(flight // 2, 2 * self.smss)
        self.cwnd = self.smss # Reset to 1 SMSS
        self.dup_acks = 0
        self.state = CongestionState.SLOW_START

    def set_flight_size(self, unacked_bytes: int):
        self.bytes_in_flight = unacked_bytes

    def can_send(self, current_flight: int) -> bool:
        """Checks if congestion window allows transmitting more data."""
        return current_flight < self.cwnd
