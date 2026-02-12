"""
sandoc — AI-powered Korean government business plan (사업계획서) generator.

서류 넣고, 대화하고, 완성본 받는다.
"""

__version__ = "0.1.0"

from sandoc.parser import parse_hwp, parse_pdf, parse_any
from sandoc.analyzer import analyze_template, analyze_announcement, classify_documents
from sandoc.style import StyleProfile, extract_style_profile, load_style_profile

__all__ = [
    "parse_hwp",
    "parse_pdf",
    "parse_any",
    "analyze_template",
    "analyze_announcement",
    "classify_documents",
    "StyleProfile",
    "extract_style_profile",
    "load_style_profile",
]
