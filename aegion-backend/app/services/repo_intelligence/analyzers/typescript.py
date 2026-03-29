import re
import hashlib
from typing import List
from ....domain.repo import SymbolRecord
from . import LanguageAnalyzer

class TypeScriptAnalyzer(LanguageAnalyzer):
    """Analyzes TypeScript/JS code using regex heuristics."""

    def extract_symbols(self, content: str, file_path: str) -> List[SymbolRecord]:
        symbols: List[SymbolRecord] = []
        
        # Regex for classes: class ClassName
        # Regex for functions: function funcName, const funcName = () =>, async function...
        
        lines = content.splitlines()
        
        # Simple line-by-line scanning for now (Limit of regex approach)
        # Multi-line signatures will be tricky without a parser
        
        class_pattern = re.compile(r"class\s+(\w+)")
        func_pattern = re.compile(r"(?:async\s+)?function\s+(\w+)")
        const_func_pattern = re.compile(r"(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[^=]+)\s*=>")
        
        for i, line in enumerate(lines):
            line_num = i + 1
            
            # Check Class
            match = class_pattern.search(line)
            if match:
                name = match.group(1)
                self._add_symbol(symbols, name, "class", file_path, line_num)
                continue

            # Check Function
            match = func_pattern.search(line)
            if match:
                name = match.group(1)
                self._add_symbol(symbols, name, "function", file_path, line_num)
                continue
                
            # Check Const Arrow Function
            match = const_func_pattern.search(line)
            if match:
                name = match.group(1)
                self._add_symbol(symbols, name, "function", file_path, line_num)
                continue

        return symbols

    def _add_symbol(self, symbols: List[SymbolRecord], name: str, type_: str, file_path: str, line_start: int):
        symbol_id = hashlib.sha256(f"{file_path}:{name}".encode()).hexdigest()
        symbols.append(SymbolRecord(
            symbol_id=symbol_id,
            name=name,
            type=type_, # type: ignore - literal constraint
            file_path=file_path,
            line_start=line_start,
            line_end=line_start  # Heuristic: single line for now
        ))
