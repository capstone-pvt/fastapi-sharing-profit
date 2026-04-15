from app.domain.fish.bulk import build_bulk_summary


def _det(species: str, weight: float, price_per_kg_min: float = 90, price_per_kg_max: float = 110, in_season: bool = True, confidence: float = 0.8):
    return {
        "species": species,
        "estimatedWeight": weight,
        "confidence": confidence,
        "estimatedPricePerKg": {
            "minPhp": price_per_kg_min,
            "maxPhp": price_per_kg_max,
            "inSeason": in_season,
        },
    }


def test_bulk_summary_empty_list():
    summary = build_bulk_summary([])
    assert summary["totalFish"] == 0
    assert summary["dominantSpecies"] is None
    assert summary["breakdown"] == []
    assert summary["estimatedTotalKg"] == 0.0
    assert summary["estimatedTotalPhp"] == 0.0
    assert summary["warnings"] == []


def test_bulk_summary_single_species():
    dets = [_det("Galunggong", 0.2), _det("Galunggong", 0.3)]
    summary = build_bulk_summary(dets)
    assert summary["totalFish"] == 2
    assert summary["dominantSpecies"] == "Galunggong"
    assert len(summary["breakdown"]) == 1
    row = summary["breakdown"][0]
    assert row["species"] == "Galunggong"
    assert row["count"] == 2
    assert row["totalKg"] == 0.5
    assert row["avgKg"] == 0.25
    assert summary["estimatedTotalKg"] == 0.5
    assert summary["estimatedTotalPhp"] == 50.0


def test_bulk_summary_multiple_species_dominant_by_count():
    dets = [
        _det("Tilapia", 0.2), _det("Tilapia", 0.3),
        _det("Bangus", 1.0),
    ]
    summary = build_bulk_summary(dets)
    assert summary["totalFish"] == 3
    assert summary["dominantSpecies"] == "Tilapia"
    assert [r["species"] for r in summary["breakdown"]] == ["Tilapia", "Bangus"]


def test_bulk_summary_breakdown_sums_match_total():
    dets = [
        _det("Galunggong", 0.2), _det("Galunggong", 0.3),
        _det("Tilapia", 0.4),
    ]
    summary = build_bulk_summary(dets)
    breakdown_total = sum(r["totalKg"] for r in summary["breakdown"])
    assert breakdown_total == summary["estimatedTotalKg"]


def test_bulk_summary_low_confidence_warning():
    dets = [
        _det("Tilapia", 0.2, confidence=0.85),
        _det("Tilapia", 0.2, confidence=0.20),
        _det("Tilapia", 0.2, confidence=0.15),
    ]
    summary = build_bulk_summary(dets)
    assert any("below confidence threshold" in w for w in summary["warnings"])
    assert "2" in summary["warnings"][0]


def test_bulk_summary_uses_offseason_markup_when_present():
    det = _det("Bangus", 1.0, price_per_kg_min=100, price_per_kg_max=100, in_season=False)
    summary = build_bulk_summary([det])
    assert summary["estimatedTotalPhp"] == 100.0
