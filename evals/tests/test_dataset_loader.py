import json

from eval_utils.dataset_loader import load_manual_evals, load_textbook_evals


def test_load_manual_evals_maps_base_answer_and_id(tmp_path):
    dataset_root = tmp_path
    dataset_dir = dataset_root / "dataset"
    dataset_dir.mkdir()
    (dataset_dir / "manual_data.json").write_text(
        json.dumps([
            {
                "id": "case-1",
                "question": "What is term insurance?",
                "base_answer": "Temporary life cover.",
            }
        ])
    )

    cases = load_manual_evals(dataset_root)

    assert len(cases) == 1
    assert cases[0].case_id == "case-1"
    assert cases[0].question == "What is term insurance?"
    assert cases[0].expected_output == "Temporary life cover."
    assert cases[0].source == "manual"


def test_load_textbook_evals_returns_empty_when_file_missing(tmp_path):
    assert load_textbook_evals(tmp_path) == []
