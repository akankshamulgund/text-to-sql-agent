from eval.run_eval import _summary


def test_ambiguous_questions_are_counted_but_not_scored():
    records = [
        {
            "id": "clarify",
            "difficulty": "easy",
            "completed": True,
            "accuracy": False,
            "planner_category": "ambiguous",
            "llm_calls": 1,
            "seconds": 1.0,
            "failure_category": None,
        },
        {
            "id": "answered",
            "difficulty": "medium",
            "completed": True,
            "accuracy": True,
            "planner_category": "simple",
            "llm_calls": 3,
            "seconds": 3.0,
            "failure_category": None,
        },
    ]

    summary = _summary("v5", records)

    assert summary["accuracy_overall"] == {"correct": 1, "total": 1, "accuracy": 1.0}
    assert summary["ambiguous_question_count"] == 1
    assert summary["routing_categories"]["counts"] == {"ambiguous": 1, "simple": 1}
    assert summary["routing_categories"]["fractions"] == {"ambiguous": 0.5, "simple": 0.5}
    assert summary["average_llm_calls_per_question"] == 2.0
    assert summary["average_seconds_per_question"] == 2.0
    assert summary["accuracy_by_difficulty"]["easy"]["accuracy"] == 0.0
