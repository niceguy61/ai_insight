"""공용 데이터 모델."""
from dataclasses import dataclass, field


@dataclass
class RawItem:
    """소스 어댑터가 반환하는 원본 항목. payload에는 소스 고유 필드를 그대로 담는다."""

    source: str
    external_id: str
    payload: dict = field(default_factory=dict)
