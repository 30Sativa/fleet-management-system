"""Transport abstraction for the arm bridge.

The whole point of this file is to keep "what we say to the arm" separate
from "how we send it". The node only ever talks to an ArmTransport. Today
that is Serial (USB CDC). Later it can be CAN, and nothing in the node or
the firmware command vocabulary has to change.

To switch transports you only change the `transport` launch parameter from
`serial` to `can`. Do NOT add transport-specific logic into the node.
"""

from abc import ABC, abstractmethod
from typing import Optional


class ArmTransport(ABC):
    """Common interface every arm transport must implement.

    A transport moves already-formatted command lines/frames to the arm
    controller and returns whatever the controller sends back. It does not
    know what the commands mean — that stays in the node.
    """

    @abstractmethod
    def open(self) -> None:
        """Open the underlying link (serial port, CAN socket, ...)."""

    @abstractmethod
    def close(self) -> None:
        """Close the link. Must be safe to call more than once."""

    @abstractmethod
    def is_open(self) -> bool:
        """Return True if the link is currently usable."""

    @abstractmethod
    def send_line(self, line: str) -> None:
        """Send one command to the arm controller.

        `line` is a complete, human-readable command without the trailing
        terminator (the transport appends what it needs). Example:
        "ARM,0,90.0,45.0,120.0" or "GRIP,1,CLOSE".
        """

    @abstractmethod
    def read_line(self) -> Optional[str]:
        """Return one feedback line from the arm controller, or None.

        Should be non-blocking-ish: return None promptly when no full line
        is available yet, so the node's timer loop stays responsive.
        """
