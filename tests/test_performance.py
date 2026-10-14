from dataclasses import fields, replace

from shadows_explorer.core.performance import LIMITS, PRESET_DESCRIPTIONS, PRESETS, PerformanceSettings


class FakeSettings(dict):
    def value(self, key, default=None):
        return self.get(key, default)

    def setValue(self, key, value):
        self[key] = value


def test_defaults_are_the_balanced_preset():
    assert PerformanceSettings() == PRESETS["Balanced"]
    assert PerformanceSettings().preset_name() == "Balanced"
    assert set(PRESET_DESCRIPTIONS) == set(PRESETS) | {"Custom"}


def test_round_trip_and_custom():
    settings = FakeSettings()
    custom = replace(PerformanceSettings(), thumbnail_threads=4, preview_pdfs=False)
    custom.save(settings)
    loaded = PerformanceSettings.load(settings)
    assert loaded == custom
    assert loaded.preset_name() == "Custom"
    assert PerformanceSettings.load(FakeSettings()) == PerformanceSettings()


def test_loading_tolerates_strings_and_bad_values():
    # INI-backed QSettings returns strings
    settings = FakeSettings({"performance/thumbnails": "false", "performance/undo_steps": "40",
                             "performance/thumbnail_cache": "lots", "performance/search_threads": "9999",
                             "performance/thumbnail_threads": -3})
    loaded = PerformanceSettings.load(settings)
    assert loaded.thumbnails is False
    assert loaded.undo_steps == 40
    assert loaded.thumbnail_cache == PerformanceSettings().thumbnail_cache  # Invalid: default
    assert loaded.search_threads == LIMITS["search_threads"].high  # Clamped
    assert loaded.thumbnail_threads == LIMITS["thumbnail_threads"].low


def test_presets_are_within_limits_and_distinct():
    for name, preset in PRESETS.items():
        assert preset == preset.clamped(), name
        assert preset.preset_name() == name
    assert len({tuple(getattr(p, f.name) for f in fields(p)) for p in PRESETS.values()}) == len(PRESETS)
    assert PRESETS["Light"].thumbnail_threads < PRESETS["Maximum"].thumbnail_threads


def test_automatic_search_threads():
    assert PerformanceSettings(search_threads=0).effective_search_threads() == PerformanceSettings.cpu_cores()
    assert PerformanceSettings(search_threads=3).effective_search_threads() == 3
