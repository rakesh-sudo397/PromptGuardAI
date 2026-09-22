"""
Master Document Builder:
Integrates styling, audit_monograph, ieee_manuscript_core,
ieee_manuscript_results, and peer_review_report to produce
the complete 10-12+ page Black & White Word Document:
IEEE_PromptGuard_AI_Research_Manuscript_BW.docx
"""

import os
import sys
import time

# Ensure project root is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.manuscript_builder.styling import setup_document
from src.manuscript_builder.audit_monograph import build_audit_monograph
from src.manuscript_builder.ieee_manuscript_core import build_manuscript_core
from src.manuscript_builder.ieee_manuscript_results import build_manuscript_results
from src.manuscript_builder.peer_review_report import build_peer_review_report

def main():
    print("=================================================================")
    print("PROMPTGUARD-AI: GENERATING MASTER IEEE RESEARCH MANUSCRIPT (B&W)")
    print("=================================================================")
    start_time = time.time()
    
    print("[1/5] Initializing document layout and IEEE monochromatic styling...")
    doc = setup_document()
    
    print("[2/5] Compiling Part I: Research Audit Monograph (Phases 0 to 8)...")
    build_audit_monograph(doc)
    
    print("[3/5] Compiling Part II: IEEE Manuscript Core (Phases 9 to 16)...")
    build_manuscript_core(doc)
    
    print("[4/5] Compiling Part II: IEEE Manuscript Results & References (Phases 17 to 24)...")
    build_manuscript_results(doc)
    
    print("[5/5] Compiling Part III: Peer Review Simulation & Readiness (Phases 25 to 27)...")
    build_peer_review_report(doc)
    
    output_filename = "IEEE_PromptGuard_AI_Research_Manuscript_BW.docx"
    output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', output_filename))
    
    print(f"\nSaving master document to: {output_path}...")
    doc.save(output_path)
    
    elapsed = time.time() - start_time
    file_size_kb = os.path.getsize(output_path) / 1024
    
    print("=================================================================")
    print("GENERATION SUCCESSFUL!")
    print(f"File Path: {output_path}")
    print(f"File Size: {file_size_kb:.2f} KB")
    print(f"Time Taken: {elapsed:.2f} seconds")
    print("=================================================================")

if __name__ == "__main__":
    main()
