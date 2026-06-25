"""Placeholder test so the package has a test entry point.

Real tests (command formatting, transport line framing, feedback parsing)
go here once the firmware protocol is finalized. Mirrors the role of
stm32_bridge/test/test_odometry.py.
"""


def test_import():
    import arm_bridge  # noqa: F401
    from arm_bridge import transport_base, transport_serial, transport_can  # noqa: F401
    assert hasattr(transport_base, 'ArmTransport')
