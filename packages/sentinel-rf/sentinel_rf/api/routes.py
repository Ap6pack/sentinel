# Copyright (c) 2026 Veritas Aequitas Holdings LLC. All rights reserved.

from __future__ import annotations

from flask import Blueprint

routes_bp = Blueprint("routes", __name__)


@routes_bp.route("/api/v1/decoders")
def list_decoders():
    from .health import decoder_registry

    return {
        "decoders": list(decoder_registry.keys()),
    }
