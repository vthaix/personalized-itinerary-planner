import json

import pytest

from itinerary_pipelines import flow
from itinerary_pipelines.config import PipelineConfig


def test_full_order_respects_dependencies():
    order = flow.topo_order()
    assert order == ["fetch", "coverage", "clean", "load", "survey_export", "survey_import"]
    for s in flow.STEPS:
        for d in s.depends_on:
            assert order.index(d) < order.index(s.name)


def test_downstream_from_clean():
    assert flow.downstream("clean") == ["clean", "load", "survey_export", "survey_import"]


def test_downstream_from_survey_export():
    assert flow.downstream("survey_export") == ["survey_export", "survey_import"]


def test_only_keeps_given_steps_in_order():
    assert flow.topo_order(["survey_export", "clean"]) == ["clean", "survey_export"]


def test_unknown_step():
    with pytest.raises(KeyError):
        flow.get("nope")


def test_run_flow_offline_steps(tmp_path):
    """clean → survey_export chạy được từ file thô, không cần mạng hay DB."""
    cfg = PipelineConfig(data_dir=tmp_path, database_url=None)
    cfg.raw_path.parent.mkdir(parents=True)
    cfg.raw_path.write_text(json.dumps({
        "source": "test", "license": "ODbL", "fetched_at": None, "osm_base": None,
        "elements": [
            {"type": "way", "id": 1, "center": {"lat": 12.26, "lon": 109.19},
             "tags": {"name": "Tháp Po Nagar", "historic": "archaeological_site",
                      "wikipedia": "vi:Tháp Po Nagar"}},
            {"type": "node", "id": 2, "lat": 12.25, "lon": 109.19,
             "tags": {"name": "Showroom", "tourism": "museum"}},
        ]}), encoding="utf-8")

    seen = []
    results = flow.run_flow(cfg, only=["clean", "survey_export"], on_result=seen.append)
    assert [r.step for r in results] == ["clean", "survey_export"] == [r.step for r in seen]
    assert results[1].stats == {"rows": 2, "suggested": 1, "flagged": 1, "stale": 0,
                                "rows_with_manual_data_preserved": 0}
    assert cfg.survey_path.exists()
