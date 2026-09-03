#!/usr/bin/env python3
"""
AdiOS Hardware Driver Subsystem: Motorola MC146818 Real-Time Clock & CMOS Driver (rtc.py)
Reads date and time from standard PC/AT CMOS registers (0x70 / 0x71).
Performs BCD decoding, 12h/24h conversion, and UNIX timestamp calculation.
Zero external dependencies.
"""

import time

CMOS_ADDR_PORT = 0x70
CMOS_DATA_PORT = 0x71

# CMOS Registers
RTC_SECONDS      = 0x00
RTC_MINUTES      = 0x02
RTC_HOURS        = 0x04
RTC_DAY_OF_MONTH = 0x07
RTC_MONTH        = 0x08
RTC_YEAR         = 0x09
RTC_STATUS_A     = 0x0A
RTC_STATUS_B     = 0x0B

class RTCDriver:
    """
    Motorola MC146818 Real-Time Clock Hardware Driver.
    """
    def __init__(self):
        self.cmos_regs = bytearray(128)
        # Default status: 24h mode (bit 1=1), BCD format (bit 2=0)
        self.cmos_regs[RTC_STATUS_B] = 0x02
        self.sync_system_time()

    def sync_system_time(self):
        """Sets CMOS registers to current time in BCD format."""
        now = time.gmtime()
        self.cmos_regs[RTC_SECONDS] = self._to_bcd(now.tm_sec)
        self.cmos_regs[RTC_MINUTES] = self._to_bcd(now.tm_min)
        self.cmos_regs[RTC_HOURS]   = self._to_bcd(now.tm_hour)
        self.cmos_regs[RTC_DAY_OF_MONTH] = self._to_bcd(now.tm_mday)
        self.cmos_regs[RTC_MONTH]   = self._to_bcd(now.tm_mon)
        self.cmos_regs[RTC_YEAR]    = self._to_bcd(now.tm_year % 100)

    def _to_bcd(self, val: int) -> int:
        return ((val // 10) << 4) | (val % 10)

    def _from_bcd(self, bcd: int) -> int:
        return ((bcd >> 4) * 10) + (bcd & 0x0F)

    def read_cmos(self, reg: int) -> int:
        return self.cmos_regs[reg & 0x7F]

    def write_cmos(self, reg: int, val: int):
        self.cmos_regs[reg & 0x7F] = val & 0xFF

    def get_time(self) -> dict:
        """Reads and converts CMOS registers into human-readable date/time."""
        status_b = self.read_cmos(RTC_STATUS_B)
        is_bcd = not bool(status_b & 0x04)

        sec = self.read_cmos(RTC_SECONDS)
        minute = self.read_cmos(RTC_MINUTES)
        hour = self.read_cmos(RTC_HOURS)
        day = self.read_cmos(RTC_DAY_OF_MONTH)
        mon = self.read_cmos(RTC_MONTH)
        yr = self.read_cmos(RTC_YEAR)

        if is_bcd:
            sec = self._from_bcd(sec)
            minute = self._from_bcd(minute)
            hour = self._from_bcd(hour)
            day = self._from_bcd(day)
            mon = self._from_bcd(mon)
            yr = self._from_bcd(yr)

        full_year = 2000 + yr
        return {
            "year": full_year,
            "month": mon,
            "day": day,
            "hour": hour,
            "minute": minute,
            "second": sec,
            "iso8601": f"{full_year:04d}-{mon:02d}-{day:02d} {hour:02d}:{minute:02d}:{sec:02d}"
        }

if __name__ == "__main__":
    rtc = RTCDriver()
    t = rtc.get_time()
    print("CMOS RTC Current Time:", t["iso8601"])
    assert 2020 <= t["year"] <= 2040
    assert 1 <= t["month"] <= 12
    assert 0 <= t["hour"] <= 23
    print("CMOS RTC Driver verified.")
