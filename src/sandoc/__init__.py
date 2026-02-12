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
from sandoc.hwpx_engine import HwpxBuilder, StyleMirror, validate_hwpx, edit_hwpx_text
from sandoc.output import OutputPipeline, BuildResult, build_hwpx_from_plan, build_hwpx_from_json
from sandoc.extract import run_extract
from sandoc.assemble import run_assemble
from sandoc.visualize import run_visualize
from sandoc.review import run_review
from sandoc.profile_register import run_profile_register

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
    # hwpx_engine
    "HwpxBuilder",
    "StyleMirror",
    "validate_hwpx",
    "edit_hwpx_text",
    # output
    "OutputPipeline",
    "BuildResult",
    "build_hwpx_from_plan",
    "build_hwpx_from_json",
    # extract
    "run_extract",
    # assemble
    "run_assemble",
    # visualize
    "run_visualize",
    # review
    "run_review",
    # profile_register
    "run_profile_register",
]
