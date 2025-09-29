#!/usr/bin/env python3
"""
Widgets package initializer.

Re-exports:
- widgets_bp: Flask Blueprint with routes:
  - GET /widgets
  - GET /widget/<name>
  - GET /widget/<name>.json
"""

from .routes import widgets_bp

__all__ = ["widgets_bp"]