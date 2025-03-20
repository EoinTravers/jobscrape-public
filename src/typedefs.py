from typing import Callable, Any
from pydantic import BaseModel


class RawPage(BaseModel):
    url: str
    title: str
    html: str
    metadata: dict[str, Any] | None = None


PageSaver = Callable[[RawPage], Any]
