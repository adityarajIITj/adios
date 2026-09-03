#!/usr/bin/env python3
"""
Test Suite: Block K Hardware Device Drivers & VirtIO Bus
Verifies:
1. drivers/virtio_ring: VirtIO v1.0 standard split virtqueue descriptor chains
2. drivers/virtio_blk: VirtIO block storage sector I/O operations
3. drivers/virtio_net: VirtIO network packet transmission and reception
4. drivers/pci: PCI Bus Controller, configuration space, and BAR mapping
5. drivers/rtc: Motorola MC146818 Real-Time Clock CMOS decoding
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from drivers.virtio_ring import Virtqueue, VRingDesc
from drivers.virtio_blk import VirtioBlkDevice, SECTOR_SIZE
from drivers.virtio_net import VirtioNetDevice
from drivers.pci import PCIBusController, PCIDevice, PCI_VENDOR_REDHAT
from drivers.rtc import RTCDriver

def test_drivers_block_k_suite():
    print("[Test Drivers Block K] Initializing Hardware Drivers & VirtIO Verification...")

    # 1. Test Virtqueue Split Ring Architecture
    print("  -> Testing VirtIO Split Virtqueue Architecture...")
    vq = Virtqueue(queue_size=32)
    assert vq.num_free == 32
    head = vq.add_buffer([(0x80001000, 128, False), (0x80002000, 256, True)])
    assert vq.num_free == 30
    assert vq.avail.idx == 1
    assert vq.avail.ring[0] == head

    # Hardware device marks completed
    vq.device_complete(head, 384)
    res = vq.get_completed()
    assert res == (head, 384)
    assert vq.get_completed() is None # No more completed buffers

    vq.free_chain(head)
    assert vq.num_free == 32
    print("  -> [PASS] VirtIO Split Virtqueue verified.")

    # 2. Test VirtIO Block Storage Device
    print("  -> Testing VirtIO Block Storage Driver...")
    blk = VirtioBlkDevice(num_sectors=128)
    sample_sector = b"SOVEREIGN_VIRTIO_BLOCK_SECTOR_DATA_" * 10
    blk.write_sector(12, sample_sector)
    read_back = blk.read_sector(12)
    assert len(read_back) == SECTOR_SIZE
    assert read_back.startswith(sample_sector)
    print("  -> [PASS] VirtIO Block device driver verified.")

    # 3. Test VirtIO Network Adapter
    print("  -> Testing VirtIO Network Adapter Driver...")
    net = VirtioNetDevice(mac_addr="52:54:00:AB:CD:EF")
    test_frame = b"\xFF\xFF\xFF\xFF\xFF\xFF\x52\x54\x00\xAB\xCD\xEF\x08\x00" + b"TEST_PAYLOAD"
    bytes_sent = net.transmit_packet(test_frame)
    assert bytes_sent == len(test_frame)

    net.receive_packet(test_frame)
    rx_frame = net.poll_rx()
    assert rx_frame == test_frame
    assert net.poll_rx() is None
    print("  -> [PASS] VirtIO Network adapter verified.")

    # 4. Test PCI Bus Controller & Config Space
    print("  -> Testing PCI Bus Controller & Configuration Space...")
    pci = PCIBusController()
    dev_net = PCIDevice(bus=0, slot=3, fn=0, vendor_id=PCI_VENDOR_REDHAT, device_id=0x1000, class_code=0x02, subclass=0x00)
    dev_net.set_bar(0, 0x10000000, 4096)
    pci.register_device(dev_net)

    dev_blk = PCIDevice(bus=0, slot=4, fn=0, vendor_id=PCI_VENDOR_REDHAT, device_id=0x1001, class_code=0x01, subclass=0x00)
    dev_blk.set_bar(0, 0x10001000, 4096)
    pci.register_device(dev_blk)

    all_devs = pci.enumerate_bus()
    assert len(all_devs) == 2
    # Verify 32-bit register read
    v_id = dev_net.read_config_32(0x00) & 0xFFFF
    assert v_id == PCI_VENDOR_REDHAT
    print("  -> [PASS] PCI Bus Controller verified.")

    # 5. Test Motorola MC146818 CMOS RTC Driver
    print("  -> Testing CMOS Real-Time Clock Driver...")
    rtc = RTCDriver()
    t = rtc.get_time()
    assert 2020 <= t["year"] <= 2040
    assert 1 <= t["month"] <= 12
    assert 0 <= t["hour"] <= 23
    assert len(t["iso8601"]) == 19
    print("  -> [PASS] CMOS Real-Time Clock verified.")

    print("\n[Test Drivers Block K] ALL BLOCK K HARDWARE DRIVER TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_drivers_block_k_suite()
