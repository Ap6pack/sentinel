# Copyright (c) 2026 Veritas Aequitas Holdings LLC. All rights reserved.

from __future__ import annotations

from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)

# Populated by app.py at startup
decoder_registry: dict = {}


@health_bp.route("/api/v1/health")
def health():
    return jsonify(
        {
            "module": "sentinel-rf",
            "status": "ok",
            "decoders": {
                name: {
                    "running": dec._running,
                    "pid": dec._proc.pid if dec._proc else None,
                }
                for name, dec in decoder_registry.items()
            },
        }
    )
