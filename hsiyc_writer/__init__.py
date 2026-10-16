"""HSIYC article writer.

A small agent that drafts bilingual (Chinese/English) event articles in the exact
style of the HSIYC articles that the HITSZ youth committee has already approved.

Design constraints:
  * No third-party network or LLM SDK - only the Python standard library plus
    Pillow (already present) and python-docx for the .docx deliverable.
  * The style itself is data, not code: it lives in ``spec/`` so the club can
    keep editing it as the reviewers' expectations drift.
"""

__version__ = "0.1.0"
