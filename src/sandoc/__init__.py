"""
sandoc — AI-powered Korean government business plan (사업계획서) generator.

서류 넣고, 대화하고, 완성본 받는다.
"""

__version__ = "0.1.0"

from sandoc.parser import parse_hwp, parse_pdf, parse_any
from sandoc.analyzer import analyze_template, analyze_announcement, classify_documents
from sandoc.style import StyleProfile, extract_style_profile, load_style_profile
from sandoc.schema import CompanyInfo, create_sample_company
from sandoc.generator import PlanGenerator, GeneratedSection, GeneratedPlan

__all__ = [
    # parser
    "parse_hwp",
    "parse_pdf",
    "parse_any",
    # analyzer
    "analyze_template",
    "analyze_announcement",
    "classify_documents",
    # style
    "StyleProfile",
    "extract_style_profile",
    "load_style_profile",
    # schema
    "CompanyInfo",
    "create_sample_company",
    # generator
    "PlanGenerator",
    "GeneratedSection",
    "GeneratedPlan",
]
