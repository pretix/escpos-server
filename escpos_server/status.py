from dataclasses import dataclass

TYPE_UNKNOWN = "unknown"
TYPE_OFFLINE = "offline"
TYPE_ONLINE = "online"


@dataclass
class Status:
    type: str = TYPE_UNKNOWN
    paper_end: bool = None
    paper_near_end: bool = None

    @classmethod
    def from_escpos(cls, paper_status):
        return Status(
            type=TYPE_ONLINE,
            paper_near_end=paper_status & 0x0C > 0,
            paper_end=paper_status & 0x60 > 0,
        )