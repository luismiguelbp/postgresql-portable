"""Probe how python-dotenv parses WinCC OA passwords containing #."""

from dotenv import dotenv_values
from pathlib import Path
import tempfile

# Passwords with # often need quoting in .env files
password = "p@ss#word"
tests = [
    f"WINCCOA_PASSWORD={password}",
    f'WINCCOA_PASSWORD="{password}"',
    f"WINCCOA_PASSWORD='{password}'",
    rf"WINCCOA_PASSWORD={password.replace('#', r'\#')}",
]
for line in tests:
    p = Path(tempfile.gettempdir()) / "test_dotenv_hash.env"
    p.write_text(line + "\n", encoding="utf-8")
    v = dotenv_values(p).get("WINCCOA_PASSWORD")
    print(repr(line), "->", repr(v))
