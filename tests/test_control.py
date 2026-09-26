from openalex_review.control import init_control


def test_init_control(tmp_path):
    created = init_control(tmp_path)
    assert len(created) == 5
    assert (tmp_path / "data/control/evidence_matrix.csv").exists()
    assert (tmp_path / "data/control/screening_resolutions.csv").exists()
