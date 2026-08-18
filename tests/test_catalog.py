"""Tests for the SimVar catalog loader."""

from msfs_telemetry.catalog import catalog_stats, iter_simvar_specs, load_catalog


def test_catalog_loads():
    catalog = load_catalog()
    assert "VARIABLES" in catalog
    assert len(catalog["VARIABLES"]) > 1000


def test_catalog_expands_indexed_variables():
    specs = list(iter_simvar_specs(max_index=2))
    indexed = [spec for spec in specs if ":1" in spec.name or ":2" in spec.name]
    assert indexed
    assert all(spec.unit for spec in specs)


def test_catalog_stats():
    catalog = load_catalog()
    stats = catalog_stats(catalog)
    assert stats["base_variables"] > 1000
    assert stats["expanded_variables"] > stats["base_variables"]
