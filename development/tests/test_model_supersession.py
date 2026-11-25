"""Table-local classification and semantic-color attenuation, without pricing changes."""
from __future__ import annotations

import unittest

from src.presentation.model_supersession import model_version, superseded_rows


class SupersessionTests(unittest.TestCase):
    def test_numeric_versions_and_equal_trailing_zeros(self):
        groups = (("OpenAI", ("GPT-5.6 Sol", "GPT-6 Sol", "GPT-6.1 Sol")),
                  ("Anthropic", ("Claude Opus 4.8", "Claude Opus 5", "Claude Opus 5.5")),
                  ("Google", ("Gemini 3.7 Flash", "Gemini 3.8 Flash")),
                  ("Google", ("Gemini 3.9 Pro", "Gemini 3.10 Pro")),
                  ("xAI", ("Grok 4.5", "Grok 4.6", "Grok 4.7")),
                  ("xAI", ("Grok 4.9", "Grok 4.10")))
        for publisher, names in groups:
            with self.subTest(publisher=publisher):
                self.assertEqual(tuple(range(len(names) - 1)), superseded_rows([(publisher, n) for n in names]))
        self.assertEqual((), superseded_rows([("OpenAI", "GPT-6"), ("OpenAI", "GPT-6.0")]))
        self.assertEqual((0, 1), superseded_rows([("OpenAI", n) for n in ("GPT-6", "GPT-6.0", "GPT-6.0.1")]))

    def test_grok_matching_is_numeric_table_local_and_conservative(self):
        old, new = ("xAI", "Grok 4.6"), ("xAI", "Grok 4.7")
        self.assertEqual((), superseded_rows([old]))
        self.assertEqual((1,), superseded_rows([new, old]))
        self.assertEqual((), superseded_rows([("xAI", "Grok 4"), ("xAI", "Grok 4.0")]))
        self.assertEqual(model_version("xAI", "Grok 4.7"), model_version(" XAI ", " GROK 4.7 "))
        for publisher, name in (
            ("Other", "Grok 5"), ("OpenAI", "Grok 5"), ("xAI", "GPT-5"),
            ("xAI", "Grok 5 Preview"), ("xAI", "Grok 5 Experimental"),
            ("xAI", "Grok 5 Fast"), ("xAI", "Grok 5 Mini"),
            ("xAI", "Grok 5 (fast mode)"), ("xAI", "Grok 5-2026-10-01"),
        ):
            with self.subTest(publisher=publisher, name=name):
                self.assertIsNone(model_version(publisher, name))
                self.assertEqual((), superseded_rows([old, (publisher, name)]))

    def test_named_tiers_and_new_families_are_recognized_generically(self):
        self.assertEqual((0,), superseded_rows([("OpenAI", "GPT-5.6 Luna"), ("OpenAI", "GPT-6 Luna")]))
        self.assertEqual((0,), superseded_rows([("Anthropic", "Claude Fable 5"), ("Anthropic", "Claude Fable 5.1")]))
        self.assertEqual((1,), superseded_rows([("OpenAI", "GPT-6 Codex"), ("OpenAI", "GPT-5.3-Codex")]))
        self.assertEqual((0,), superseded_rows([("Anthropic", "Claude 3.5 Sonnet"), ("Anthropic", "Claude Sonnet 4")]))
        self.assertEqual(model_version("OpenAI", "GPT-6 Luna"), model_version("Open AI", "gpt‑6  \tLUNA"))
        self.assertEqual(model_version("Google", "Gemini 3 Flash Lite"), model_version("Google", "Gemini 3 Flash-Lite"))
        for publisher, name in (("OpenAI", "GPT-6 Luna Preview"), ("OpenAI", "GPT-6 Fast"),
                                ("Anthropic", "Claude Opus 4.8 (fast mode) (preview)"),
                                ("Anthropic", "Claude Fable 5 Experimental"), ("Google", "Gemini 4 Flash Preview"),
                                ("Google", "Gemini 4 Exp"), ("OpenAI", "GPT-6 Luna-2026-10-01"), ("OpenAI", "GPT-4o")):
            with self.subTest(name=name):
                self.assertIsNone(model_version(publisher, name))

    def test_live_catalog_names_fade_every_older_same_variant_row(self):
        rows = [("OpenAI", n) for n in ("GPT-6 Astra", "GPT-5.5", "GPT-5.6 Sol", "GPT-5.4", "GPT-5.6 Terra",
                                        "GPT-6 Sol", "GPT-5.3-Codex", "GPT-6.1 Sol", "GPT-5.4 mini", "GPT-5 mini",
                                        "GPT-5.6 Luna", "GPT-5.4 nano", "GPT-6 Luna")]
        rows += [("Anthropic", n) for n in ("Claude Fable 5", "Claude Opus 4.8 (fast mode) (preview)", "Claude Fable 5.1",
                                            "Claude Opus 4.8", "Claude Opus 5", "Claude Sonnet 4", "Claude Sonnet 4.6",
                                            "Claude Opus 5.5", "Claude Sonnet 5", "Claude Sonnet 5.5",
                                            "Claude Haiku 4.5", "Claude Haiku 5.5")]
        faded = {rows[index][1] for index in superseded_rows(rows)}
        self.assertEqual({"GPT-5.4", "GPT-5.6 Sol", "GPT-6 Sol", "GPT-5 mini", "GPT-5.6 Luna",
                          "Claude Fable 5", "Claude Opus 4.8", "Claude Opus 5", "Claude Sonnet 4",
                          "Claude Sonnet 4.6", "Claude Sonnet 5", "Claude Haiku 4.5"}, faded)

    def test_families_variants_channels_and_publishers_remain_separate(self):
        rows = [("Anthropic", "Claude Opus 4"), ("Anthropic", "Claude Sonnet 5"),
                ("Google", "Gemini 3 Flash"), ("Google", "Gemini 4 Pro"),
                ("OpenAI", "GPT-5 Sol"), ("OpenAI", "GPT-6 Mini"),
                ("OpenAI", "GPT-7 Sol (fast mode)"), ("OpenAI", "GPT-8 Sol Preview"),
                ("OpenAI", "GPT-9 Sol Experimental"), ("Other", "GPT-10 Sol"),
                ("OpenAI", "GPT-11 Mystery"), ("OpenAI", "GPT-13 Luna"), ("Other", "Version 3.10"),
                ("Anthropic", "GPT-12 Sol"), ("Google", "Gemini 3 Flash Lite")]
        self.assertEqual((), superseded_rows(rows))
        self.assertIsNone(model_version("Other", "Version 3.9"))

    def test_only_displayed_models_count_even_after_availability_filtering(self):
        old, newer = ("OpenAI", "GPT-6 Sol"), ("OpenAI", "GPT-6.1 Sol")
        self.assertEqual((), superseded_rows([old]))
        self.assertEqual((0,), superseded_rows([old, newer]))


if __name__ == "__main__":
    unittest.main()
