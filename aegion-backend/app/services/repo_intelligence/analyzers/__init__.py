from abc import ABC, abstractmethod
from typing import List
from ....domain.repo import SymbolRecord

class LanguageAnalyzer(ABC):
    """Base class for language-specific symbol extraction."""

    @abstractmethod
    def extract_symbols(self, content: str, file_path: str) -> List[SymbolRecord]:
        """Extract symbols from source code."""
        pass
