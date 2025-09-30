#!/usr/bin/env python3
"""
Widgets Blueprint Routes (Phase 0)
- GET /widgets -> list all registered widgets
- GET /widget/<name> -> HTML page suitable for iframe embedding
- GET /widget/<name>.json -> JSON figure data (fig.to_dict())
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from flask import Blueprint, render_template, request, abort, make_response, jsonify

from .registry import REGISTRY, get_widget_and_meta, normalize_params

widgets_bp = Blueprint("widgets", __name__)

def _parse_widget_params(name: str, args) -> Dict[str, Any]:
    """
    Normalize query args according to a widget's declared schema.
    Unknown/invalid values fall back to defaults.
    Theme/width/height are handled by the HTML route, not passed to the builder.
    """
    entry = REGISTRY.get(name)
    if not entry:
        return {}
    meta = entry.get("meta", {})
    schema = meta.get("params", {}) or {}

    # Build raw param dict; ignore common presentation params
    raw = {}
    try:
        raw = args.to_dict(flat=True)
    except Exception:
        try:
            raw = dict(args)  # fallback if already a dict-like
        except Exception:
            raw = {}

    # Remove presentation-only params if present
    for k in ("theme", "width", "height"):
        raw.pop(k, None)

    return normalize_params(raw, schema)

def _apply_widget_headers(response):
    """
    Apply minimal framing/CSP headers for widget responses.
    Global app.after_request also sets these, but we include here for extra safety.
    """
    xfo = os.environ.get("WIDGETS_XFO", "SAMEORIGIN")
    frame_ancestors = os.environ.get("WIDGETS_FRAME_ANCESTORS", "'self' https://*.hubspot.com")
    script_src = os.environ.get(
        "WIDGETS_SCRIPT_SRC",
        "'self' 'unsafe-inline' 'unsafe-eval' https://cdn.plot.ly data: blob:"
    )
    response.headers["X-Frame-Options"] = xfo
    directives = []
    if frame_ancestors:
        directives.append(f"frame-ancestors {frame_ancestors}")
    if script_src:
        directives.append(f"script-src {script_src}")
    if directives:
        response.headers["Content-Security-Policy"] = "; ".join(directives)
    return response


@widgets_bp.route("/widgets", methods=["GET"])
def widgets_index():
    """List all registered widgets with links to HTML/JSON and example params (if provided)."""
    items: List[Dict[str, Any]] = []
    for name, entry in REGISTRY.items():
        meta = entry.get("meta", {}) if isinstance(entry, dict) else {}
        title = meta.get("title", name.replace("_", " ").title())
        base_html = f"/widget/{name}"
        base_json = f"/widget/{name}.json"

        # Build example links if meta["examples"] is present:
        examples_meta = meta.get("examples", []) or []
        example_links: List[Dict[str, str]] = []
        for ex in examples_meta:
            label = ex.get("label", "Example")
            query = (ex.get("query") or "").replace("&", "&")  # sanitize if stored HTML-encoded
            if query and not query.startswith("?"):
                html_url = f"{base_html}?{query}"
                json_url = f"{base_json}?{query}"
            elif query:
                html_url = f"{base_html}{query}"
                json_url = f"{base_json}{query}"
            else:
                html_url = base_html
                json_url = base_json
            example_links.append({"label": label, "html_url": html_url, "json_url": json_url})

        items.append(
            {
                "name": name,
                "title": title,
                "html_url": base_html,
                "json_url": base_json,
                "examples": example_links,
            }
        )

    resp = make_response(render_template("widgets/index.html", widgets=items))
    return _apply_widget_headers(resp)


@widgets_bp.route("/widget/<name>", methods=["GET"])
def render_widget_html(name: str):
    """
    Render a single widget as a minimal HTML snippet suitable for iframe embedding.
    Query params:
      - theme: dark (default) | light
      - width: integer px (optional; defaults to 100% via CSS)
      - height: integer px (optional; default 420)
    """
    # Parse and lightly validate params
    theme = (request.args.get("theme", "dark") or "dark").lower()
    theme = "light" if theme == "light" else "dark"

    width_raw = request.args.get("width")
    height_raw = request.args.get("height")

    width_css = "100%"  # default
    if width_raw:
        try:
            width_css = f"{int(width_raw)}px"
        except (TypeError, ValueError):
            width_css = "100%"

    height_css = "420px"
    if height_raw:
        try:
            height_css = f"{int(height_raw)}px"
        except (TypeError, ValueError):
            height_css = "420px"

    # Resolve widget
    try:
        builder, meta = get_widget_and_meta(name)
    except KeyError:
        abort(404, f"Unknown widget: {name}")

    # Parse chart-specific params per widget schema then build the figure
    chart_params = _parse_widget_params(name, request.args)
    fig = builder(chart_params if chart_params is not None else {})

    # Apply theme at layout level (simple and safe)
    if theme == "light":
        fig.update_layout(template="plotly_white")
    else:
        fig.update_layout(template="plotly_dark")

    # Server-side embed using CDN for plotly
    chart_html = fig.to_html(full_html=False, include_plotlyjs="cdn")

    # Render base template
    resp = make_response(
        render_template(
            "widgets/widget_base.html",
            chart_html=chart_html,
            theme=theme,
            width=width_css,
            height=height_css,
            title=meta.get("title", name.replace("_", " ").title()),
        )
    )
    return _apply_widget_headers(resp)


@widgets_bp.route("/widget/<name>.json", methods=["GET"])
def render_widget_json(name: str):
    """
    Return the widget's Plotly figure data as JSON (fig.to_dict()).
    """
    try:
        builder, meta = get_widget_and_meta(name)
    except KeyError:
        abort(404, f"Unknown widget: {name}")

    chart_params = _parse_widget_params(name, request.args)
    fig = builder(chart_params if chart_params is not None else {})
    resp = jsonify(fig.to_dict())
    return _apply_widget_headers(resp)
