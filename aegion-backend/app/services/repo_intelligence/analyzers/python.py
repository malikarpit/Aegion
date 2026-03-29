import ast
import hashlib
from typing import List
from ....domain.repo import SymbolRecord
from . import LanguageAnalyzer

class PythonAnalyzer(LanguageAnalyzer):
    """Analyzes Python code using the `ast` module."""

    def extract_symbols(self, content: str, file_path: str) -> List[SymbolRecord]:
        symbols: List[SymbolRecord] = []
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    symbol_type = "class" if isinstance(node, ast.ClassDef) else "function"
                    
                    # Generate a stable ID
                    # Ideally include parent scope, but for V1 just name+path
                    symbol_id = hashlib.sha256(f"{file_path}:{node.name}".encode()).hexdigest()
                    
                    symbols.append(SymbolRecord(
                        symbol_id=symbol_id,
                        name=node.name,
                        type=symbol_type,
                        file_path=file_path,
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        docstring=ast.get_docstring(node)
                    ))
                    
        except SyntaxError:
            # Code might be invalid or unparsable
            pass
            
        return symbols
