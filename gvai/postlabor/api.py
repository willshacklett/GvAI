from __future__ import annotations

from flask import Blueprint, jsonify, request

from gvai.postlabor.workers.schema import (
    CareerCandidate,
    CurrentCareerAssessment,
)
from gvai.postlabor.workers.service import (
    run_worker_transition,
)


postlabor_api = Blueprint(
    "postlabor_api",
    __name__,
    url_prefix="/api/postlabor",
)


@postlabor_api.get("/health")
def postlabor_health():
    return jsonify(
        {
            "ok": True,
            "service": "gvai-postlabor",
            "worker_transition": True,
        }
    )


@postlabor_api.post("/worker/transition")
def worker_transition():
    data = request.get_json(silent=True) or {}

    occupation = str(
        data.get("occupation") or ""
    ).strip()

    location = str(
        data.get("location") or ""
    ).strip()

    if not occupation:
        return jsonify(
            {
                "ok": False,
                "error": "occupation is required",
            }
        ), 400

    if not location:
        return jsonify(
            {
                "ok": False,
                "error": "location is required",
            }
        ), 400

    current_data = data.get("current_assessment") or {}

    try:
        current = CurrentCareerAssessment(
            automation_displacement_pressure=float(
                current_data[
                    "automation_displacement_pressure"
                ]
            ),
            augmentation_potential=float(
                current_data[
                    "augmentation_potential"
                ]
            ),
            demand_outlook=float(
                current_data[
                    "demand_outlook"
                ]
            ),
            confidence=float(
                current_data.get(
                    "confidence",
                    0.75,
                )
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify(
            {
                "ok": False,
                "error": (
                    "invalid current_assessment: "
                    f"{exc}"
                ),
            }
        ), 400

    candidates = []

    for item in data.get("candidates") or []:
        try:
            candidates.append(
                CareerCandidate(
                    occupation=str(
                        item["occupation"]
                    ),
                    skill_transferability=float(
                        item["skill_transferability"]
                    ),
                    demand_outlook=float(
                        item["demand_outlook"]
                    ),
                    automation_displacement_pressure=float(
                        item[
                            "automation_displacement_pressure"
                        ]
                    ),
                    retraining_burden=float(
                        item["retraining_burden"]
                    ),
                    wage_retention=float(
                        item["wage_retention"]
                    ),
                    geographic_opportunity=float(
                        item["geographic_opportunity"]
                    ),
                    confidence=float(
                        item.get(
                            "confidence",
                            0.75,
                        )
                    ),
                    notes=str(
                        item.get("notes") or ""
                    ),
                )
            )
        except (
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            return jsonify(
                {
                    "ok": False,
                    "error": (
                        "invalid candidate: "
                        f"{exc}"
                    ),
                }
            ), 400

    result = run_worker_transition(
        occupation=occupation,
        location=location,
        experience_years=float(
            data.get(
                "experience_years",
                0.0,
            )
        ),
        skills=data.get("skills") or [],
        education=data.get("education"),
        licenses=data.get("licenses") or [],
        current_wage=data.get("current_wage"),
        desired_wage=data.get("desired_wage"),
        mobility_radius_miles=data.get(
            "mobility_radius_miles"
        ),
        current_assessment=current,
        candidates=candidates,
    )

    return jsonify(
        {
            "ok": True,
            "result": result.to_dict(),
        }
    )
