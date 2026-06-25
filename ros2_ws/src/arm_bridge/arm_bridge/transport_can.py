"""CAN transport for the arm bridge. STUB — implement when moving to CAN.

This file is intentionally a placeholder so the migration path is obvious and
the node already knows how to select it. When the arm moves onto the CAN bus
(same step the car will take later), implement these methods using python-can
(SocketCAN) and map the same command vocabulary onto CAN frames:

    ARM,<seq>,<j1>,<j2>,<z>     ->  one CAN frame, arm-command ID
    GRIP,<seq>,<OPEN|CLOSE>     ->  one CAN frame, gripper ID
    feedback frames             ->  decoded back into the same text lines
                                    read_line() returns, so the node does
                                    not change.

Keep the text-line interface (send_line / read_line) even on CAN: encode the
line into a frame on send, decode a frame into the equivalent line on read.
That way the node and the command format stay identical across transports.

Suggested deps when implementing: python-can, a SocketCAN interface
(e.g. can0) brought up from the launch/bringup side, NOT from this node.
"""

from typing import Optional

from .transport_base import ArmTransport


class CanTransport(ArmTransport):
    def __init__(self, channel: str = 'can0', bitrate: int = 500000,
                 arm_tx_id: int = 0x200, arm_rx_id: int = 0x201):
        self._channel = channel
        self._bitrate = int(bitrate)
        self._arm_tx_id = int(arm_tx_id)
        self._arm_rx_id = int(arm_rx_id)
        self._bus = None

    def open(self) -> None:
        raise NotImplementedError(
            'CanTransport is not implemented yet. The arm currently runs on '
            'SerialTransport. Implement this with python-can/SocketCAN when '
            'migrating the arm to CAN, then launch with transport:=can.')

    def close(self) -> None:
        # Safe no-op until implemented.
        if self._bus is not None:
            try:
                self._bus.shutdown()
            except Exception:
                pass
            self._bus = None

    def is_open(self) -> bool:
        return self._bus is not None

    def send_line(self, line: str) -> None:
        raise NotImplementedError('CanTransport.send_line not implemented yet.')

    def read_line(self) -> Optional[str]:
        return None
