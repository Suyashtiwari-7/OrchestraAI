"""
OrchestraAI — Local Document Reader Tool
=========================================
Reads and extracts text from local files (code files, TXT, CSV, and PDFs)
so the LLM can analyze or explain them.
"""

import re
import csv
import io
from pathlib import Path
from typing import Dict, Any, List, Optional
from pypdf import PdfReader

# Supported extensions
SUPPORTED_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".html", ".css", ".json", 
    ".csv", ".pdf", ".yaml", ".yml", ".ini", ".toml", ".sh"
}

def extract_file_paths(text: str) -> List[str]:
    """
    Search the text for potential local file paths/references with extensions.
    Matches strings like 'report.pdf', 'c:/Users/Lenovo/index.html', etc.
    """
    # Pattern to match file names/paths with supported extensions
    ext_pattern = "|".join([ext.replace(".", r"\.") for ext in SUPPORTED_EXTENSIONS])
    pattern = r'(?:[a-zA-Z]:[\\/][^\s<>:|?*]*|[\w\-./\\]+)(?:' + ext_pattern + r')\b'
    
    matches = re.findall(pattern, text, re.IGNORECASE)
    # Clean duplicates and normalize slashes
    cleaned = []
    for m in matches:
        m_norm = m.replace("\\", "/").strip()
        if m_norm not in cleaned:
            cleaned.append(m)
    return cleaned

def read_local_file(filepath: Path) -> Dict[str, Any]:
    """
    Read content of a local file based on its extension.
    """
    if not filepath.exists() or not filepath.is_file():
        return {"success": False, "error": f"File '{filepath.name}' not found."}
        
    ext = filepath.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return {"success": False, "error": f"File type '{ext}' is not supported."}
        
    try:
        if ext == ".pdf":
            # PDF Reader extraction
            reader = PdfReader(filepath)
            text = ""
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text += f"--- Page {i+1} ---\n{page_text}\n"
            return {
                "success": True,
                "type": "pdf",
                "filename": filepath.name,
                "content": text.strip()
            }
            
        elif ext == ".csv":
            # CSV Reader formatting
            content = filepath.read_text(encoding="utf-8", errors="ignore")
            reader = csv.reader(io.StringIO(content))
            rows = list(reader)
            # Format as tab-separated values or text block
            csv_text = "\n".join(["\t".join(row) for row in rows[:200]]) # Limit to first 200 rows
            if len(rows) > 200:
                csv_text += f"\n... [Truncated {len(rows) - 200} rows] ..."
            return {
                "success": True,
                "type": "csv",
                "filename": filepath.name,
                "content": csv_text
            }
            
        else:
            # Code and text files
            content = filepath.read_text(encoding="utf-8", errors="ignore")
            # Limit extremely large files
            max_chars = 100000
            is_truncated = False
            if len(content) > max_chars:
                content = content[:max_chars]
                is_truncated = True
                
            file_text = content
            if is_truncated:
                file_text += f"\n\n... [Truncated for length limit of {max_chars} chars] ..."
                
            return {
                "success": True,
                "type": "text",
                "filename": filepath.name,
                "content": file_text
            }
            
    except Exception as e:
        return {"success": False, "error": f"Error reading file: {str(e)}"}

def gather_referenced_documents(prompt: str, base_dir: Path) -> List[Dict[str, Any]]:
    """
    Find file paths in a prompt, resolve them relative to base_dir,
    and read their contents. If not found in base_dir, look in common
    user folders (home, Desktop, Documents, Downloads).
    """
    paths = extract_file_paths(prompt)
    documents = []
    
    for path_str in paths:
        # Try as absolute path first
        file_path = Path(path_str)
        if not file_path.is_absolute():
            # Try resolving relative to base_dir first
            resolved_path = base_dir / path_str
            
            # If not found there, try common user directories
            if not (resolved_path.exists() and resolved_path.is_file()):
                potential_paths = [
                    Path.home() / path_str,
                    Path.home() / "Desktop" / path_str,
                    Path.home() / "Documents" / path_str,
                    Path.home() / "Downloads" / path_str
                ]
                for p in potential_paths:
                    try:
                        if p.exists() and p.is_file():
                            resolved_path = p
                            break
                    except Exception:
                        continue
            file_path = resolved_path
            
        if file_path.exists() and file_path.is_file():
            res = read_local_file(file_path)
            if res["success"]:
                documents.append(res)
                
    return documents
