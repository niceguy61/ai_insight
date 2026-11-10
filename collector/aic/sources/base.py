"""소스 어댑터 공통 인터페이스."""
from abc import ABC, abstractmethod

from aic.models import RawItem


class SourceAdapter(ABC):
    """한 소스에서 항목을 긁어와 RawItem 목록으로 정규화하는 어댑터.

    fetch()는 429 지속 등의 이유로 일부만 수집했을 때도 예외 없이
    지금까지 모은 항목을 반환해야 한다(정상 종료).
    """

    source_name: str = "base"

    @abstractmethod
    def fetch(self) -> list[RawItem]:
        """소스에서 항목을 수집해 RawItem 목록으로 반환."""
