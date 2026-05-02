from flask import jsonify, request
from gvai.conscience import evaluate_action, gv_conscience_statement


def register_conscience_routes(app):
    if "api_conscience_statement" not in app.view_functions:
        @app.route("/api/conscience", methods=["GET"])
        def api_conscience_statement():
            return jsonify(gv_conscience_statement())

    if "api_conscience_evaluate" not in app.view_functions:
        @app.route("/api/conscience/evaluate", methods=["POST"])
        def api_conscience_evaluate():
            payload = request.get_json(silent=True) or {}
            return jsonify(evaluate_action(
                payload.get("action", ""),
                payload.get("context", "")
            ))

    return app
