"""Offline tests for jlcpcb-parts-cli (fixtures only, no live requests).

The CLI is a single self-contained script; we import it as a module via
importlib so the tests run identically from a checkout or an installed copy.
"""

from __future__ import annotations

import importlib.util
import json
import time
import unittest
from importlib.machinery import SourceFileLoader
from io import StringIO
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "jlcpcb-parts-cli"

loader = SourceFileLoader("jlcpcb_parts_cli", str(SCRIPT))
spec = importlib.util.spec_from_loader("jlcpcb_parts_cli", loader)
client = importlib.util.module_from_spec(spec)
loader.exec_module(client)

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def raw_list(name: str) -> list[dict]:
    return load(name)["data"]["componentPageInfo"]["list"]


def normalized_part(**overrides) -> dict:
    part = {
        "code": "C1",
        "mpn": "PART-1",
        "description": "Synthetic part",
        "manufacturer": "Example",
        "package": "0603",
        "category": "Resistors",
        "stock": 100,
        "tier": client.TIER_BASIC,
        "price_1": 0.01,
        "url": "https://jlcpcb.com/partdetail/example_C1",
        "datasheet": None,
    }
    part.update(overrides)
    return part


class TestNormalize(unittest.TestCase):
    def test_basic_part_c1002(self):
        raw = next(
            c for c in raw_list("basic_page1.json") if c["componentCode"] == "C1002"
        )
        part = client.normalize(raw)
        self.assertEqual(part["code"], "C1002")
        self.assertEqual(part["mpn"], "GZ1608D601TF")
        self.assertEqual(part["tier"], client.TIER_BASIC)
        self.assertEqual(part["manufacturer"], "Sunlord")
        self.assertGreater(part["stock"], 0)
        self.assertTrue(part["url"].startswith("https://jlcpcb.com/partdetail/"))
        self.assertAlmostEqual(part["price_1"], 0.0177)

    def test_promo_extended_c8734(self):
        raw = next(
            c for c in raw_list("search_stm32.json") if c["componentCode"] == "C8734"
        )
        part = client.normalize(raw)
        self.assertEqual(part["mpn"], "STM32F103C8T6")
        self.assertEqual(part["tier"], client.TIER_PROMO)
        self.assertIn("lcsc.com", part["datasheet"])

    def test_extended_part(self):
        raw = {
            "componentCode": "C1550",
            "componentLibraryType": "expand",
            "preferredComponentFlag": False,
            "stockCount": 100,
            "componentModelEn": "0402CG1R0C500NT",
        }
        self.assertEqual(client.normalize(raw)["tier"], client.TIER_EXTENDED)

    def test_missing_fields_degrade(self):
        part = client.normalize({"componentCode": "C1"})
        self.assertIsNone(part["mpn"])
        self.assertIsNone(part["price_1"])
        self.assertEqual(part["stock"], 0)
        self.assertEqual(part["tier"], client.TIER_EXTENDED)

    def test_malformed_prices(self):
        part = client.normalize({"componentCode": "C2", "componentPrices": "junk"})
        self.assertIsNone(part["price_1"])

    def test_price_tiers_are_selected_by_quantity_not_array_order(self):
        part = client.normalize(
            {
                "componentCode": "C4",
                "componentPrices": [
                    {"startNumber": 100, "productPrice": 0.1},
                    {"startNumber": 1, "productPrice": 0.2},
                ],
            }
        )
        self.assertEqual(part["price_1"], 0.2)

    def test_non_finite_prices_are_rejected(self):
        part = client.normalize(
            {
                "componentCode": "C5",
                "componentPrices": [{"startNumber": 1, "productPrice": "NaN"}],
            }
        )
        self.assertIsNone(part["price_1"])

    def test_boolean_stock_is_not_treated_as_one(self):
        client.take_warnings()
        part = client.normalize({"componentCode": "C7", "stockCount": True})

        self.assertEqual(part["stock"], 0)
        self.assertTrue(
            any("stockCount" in warning for warning in client.take_warnings())
        )

    def test_non_finite_stock_degrades_to_zero(self):
        client.take_warnings()
        part = client.normalize({"componentCode": "C8", "stockCount": 1e400})

        self.assertEqual(part["stock"], 0)
        self.assertTrue(
            any("stockCount" in warning for warning in client.take_warnings())
        )

    def test_string_false_is_not_a_truthy_promo_flag(self):
        part = client.normalize(
            {
                "componentCode": "C6",
                "componentLibraryType": "expand",
                "preferredComponentFlag": "false",
            }
        )
        self.assertEqual(part["tier"], client.TIER_EXTENDED)
        part = client.normalize(
            {"componentCode": "C3", "componentPrices": [{"startNumber": 1}]}
        )
        self.assertIsNone(part["price_1"])


class TestSearch(unittest.TestCase):
    def test_search_parses_fixture(self):
        with mock.patch.object(
            client,
            "_request",
            return_value={"total": 25, "list": raw_list("search_stm32.json")},
        ):
            total, parts = client.search("STM32F103C8T6")
        self.assertEqual(total, 25)
        codes = {p["code"] for p in parts}
        self.assertIn("C8734", codes)
        self.assertIn("C393940" if "C393940" in codes else "C2969777", codes)

    def test_basic_only_sets_api_filters(self):
        captured = {}

        def fake_query(body, timeout):
            captured.update(body)
            return {"total": 351, "list": []}

        with mock.patch.object(client, "_request", side_effect=fake_query):
            client.search("", basic_only=True)
        self.assertEqual(captured["componentLibraryType"], "base")
        self.assertEqual(captured["componentProductType"], 1)
        self.assertLessEqual(captured["pageSize"], 100)

    def test_non_object_api_record_is_rejected(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps(
            {
                "code": 200,
                "data": {"componentPageInfo": {"total": 1, "list": [None]}},
            }
        ).encode()
        with (
            mock.patch.object(client.urllib.request, "urlopen", return_value=response),
            self.assertRaisesRegex(client.PayloadError, "non-object"),
        ):
            client._request_once({}, 1)

    def test_non_finite_total_degrades_to_zero(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = (
            b'{"code":200,"data":{"componentPageInfo":{"total":1e400,"list":[]}}}'
        )
        with mock.patch.object(client.urllib.request, "urlopen", return_value=response):
            result = client._request_once({}, 1)

        self.assertEqual(result["total"], 0)

    def test_full_pool_pagination_stops_at_safety_cap(self):
        with mock.patch.object(
            client, "search", return_value=(10**18, [normalized_part()])
        ) as search:
            iterator = client.iter_all()
            with self.assertRaisesRegex(client.PayloadError, "100"):
                for _ in range(101):
                    next(iterator)

        self.assertEqual(search.call_count, 100)


class TestSortKey(unittest.TestCase):
    def test_tier_priority_then_stock(self):
        parts = [
            {"tier": "extended", "stock": 1000},
            {"tier": "promo_extended", "stock": 10},
            {"tier": "basic", "stock": 5},
            {"tier": "basic", "stock": 50},
        ]
        ordered = sorted(parts, key=client.sort_key)
        self.assertEqual(
            [p["tier"] for p in ordered],
            ["basic", "basic", "promo_extended", "extended"],
        )
        self.assertEqual(ordered[0]["stock"], 50)


class TestErrorHandling(unittest.TestCase):
    def test_payload_error_not_retried(self):
        calls = {"n": 0}

        def boom(body, timeout):
            calls["n"] += 1
            raise client.PayloadError("schema changed")

        with (
            mock.patch.object(client, "_request_once", side_effect=boom),
            self.assertRaises(client.PayloadError),
        ):
            client._request({})
        self.assertEqual(calls["n"], 1)

    def test_network_retry_then_success(self):
        responses = [client.NetworkError("t1"), {"total": 0, "list": []}]
        calls = {"n": 0}

        def flaky(body, timeout):
            i = calls["n"]
            calls["n"] += 1
            r = responses[i]
            if isinstance(r, Exception):
                raise r
            return r

        with (
            mock.patch.object(client.time, "sleep"),
            mock.patch.object(client, "_request_once", side_effect=flaky),
        ):
            res = client._request({})
        self.assertEqual(res, {"total": 0, "list": []})
        self.assertEqual(calls["n"], 2)

    def test_network_retries_exhausted(self):
        patcher = mock.patch.object(
            client, "_request_once", side_effect=client.NetworkError("down")
        )
        with (
            mock.patch.object(client.time, "sleep"),
            patcher,
            self.assertRaises(client.NetworkError),
        ):
            client._request({})

    def test_unknown_library_type_warns(self):
        client.take_warnings()
        part = client.normalize(
            {"componentCode": "C9", "componentLibraryType": "weird"}
        )
        warnings = client.take_warnings()
        self.assertEqual(part["tier"], client.TIER_EXTENDED)
        self.assertTrue(any("unknown componentLibraryType" in w for w in warnings))

    def test_missing_mpn_warns(self):
        client.take_warnings()
        client.normalize({"componentCode": "C10"})
        self.assertTrue(any("no MPN" in w for w in client.take_warnings()))

    def test_non_retryable_http_error_is_not_retried(self):
        error = client.urllib.error.HTTPError(client.API_URL, 404, "missing", {}, None)
        self.addCleanup(error.close)
        with (
            mock.patch.object(
                client.urllib.request, "urlopen", side_effect=error
            ) as request,
            self.assertRaises(client.HttpError),
        ):
            client._request({})
        request.assert_called_once()


class TestCanaries(unittest.TestCase):
    def run_canaries_with(self, search_result):
        with mock.patch.object(client, "search", side_effect=search_result):
            return client.run_canaries(timeout=0.1)

    def test_all_pass(self):
        good = (25, [{"code": "C8734", "tier": "promo_extended", "stock": 500}])
        basic = (10, [{"code": "C6186", "tier": "basic", "stock": 100000}])
        status, checks = self.run_canaries_with([good, basic])
        self.assertEqual(status, "PASS")
        self.assertTrue(all(c["ok"] and not c.get("warn") for c in checks))

    def test_tier_drift_is_warn(self):
        drifted = (25, [{"code": "C8734", "tier": "basic", "stock": 500}])
        basic = (10, [{"code": "C6186", "tier": "basic", "stock": 100000}])
        status, checks = self.run_canaries_with([drifted, basic])
        self.assertEqual(status, "WARN")
        self.assertIn("tier changed", checks[0]["warn"])

    def test_stock_drop_is_warn(self):
        low = (10, [{"code": "C6186", "tier": "basic", "stock": 5}])
        ok = (25, [{"code": "C8734", "tier": "promo_extended", "stock": 500}])
        status, checks = self.run_canaries_with([ok, low])
        self.assertEqual(status, "WARN")
        self.assertIn("stock dropped", checks[1]["warn"])

    def test_api_failure_is_fail(self):
        status, checks = self.run_canaries_with(
            [client.ApiError("boom"), client.ApiError("boom")]
        )
        self.assertEqual(status, "FAIL")
        self.assertFalse(any(c["ok"] for c in checks))

    def test_one_missing_canary_is_fail(self):
        good = (25, [{"code": "C8734", "tier": "promo_extended", "stock": 500}])
        status, _ = self.run_canaries_with([good, (0, [])])
        self.assertEqual(status, "FAIL")


class TestCommands(unittest.TestCase):
    def test_search_pages_until_filtered_limit_is_satisfied(self):
        extended = normalized_part(code="C2", tier=client.TIER_EXTENDED)
        basic = normalized_part(code="C3")
        with (
            mock.patch.object(
                client, "search", side_effect=[(100, [extended] * 50), (100, [basic])]
            ) as search,
            mock.patch("sys.stdout", new_callable=StringIO) as output,
        ):
            result = client.main(
                ["--json", "search", "part", "--tier", "basic", "-n", "1"]
            )

        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue())[0]["code"], "C3")
        self.assertEqual(search.call_count, 2)

    def test_info_requires_exact_match_and_keeps_json_valid(self):
        fuzzy = normalized_part(mpn="ABC-123")
        with (
            mock.patch.object(client, "search", return_value=(1, [fuzzy])),
            mock.patch("sys.stdout", new_callable=StringIO) as output,
        ):
            result = client.main(["--json", "info", "ABC"])

        self.assertEqual(result, 1)
        self.assertEqual(json.loads(output.getvalue()), [])

    def test_info_reads_later_pages_for_exact_match(self):
        fuzzy = normalized_part(mpn="ABC-123")
        exact = normalized_part(code="C9", mpn="TARGET-MPN")
        with (
            mock.patch.object(
                client, "search", side_effect=[(101, [fuzzy]), (101, [exact])]
            ) as search,
            mock.patch("sys.stdout", new_callable=StringIO) as output,
        ):
            result = client.main(["--json", "info", "TARGET-MPN"])

        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue())[0]["code"], "C9")
        self.assertEqual(search.call_count, 2)

    def test_info_stops_immediately_when_exact_match_is_found(self):
        exact = normalized_part(code="C9", mpn="TARGET-MPN")
        with (
            mock.patch.object(client, "search", return_value=(1000, [exact])) as search,
            mock.patch("sys.stdout", new_callable=StringIO) as output,
        ):
            result = client.main(["--json", "info", "TARGET-MPN"])

        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue())[0]["code"], "C9")
        self.assertEqual(search.call_count, 1)

    def test_regular_command_surfaces_and_clears_warnings(self):
        raw = {"componentCode": "C9", "componentLibraryType": "surprise"}
        with (
            mock.patch.object(
                client, "_request", return_value={"total": 1, "list": [raw]}
            ),
            mock.patch("sys.stdout", new_callable=StringIO),
            mock.patch("sys.stderr", new_callable=StringIO) as errors,
        ):
            result = client.main(["search", "part", "-n", "1"])

        self.assertEqual(result, 0)
        self.assertIn("warning:", errors.getvalue())
        self.assertEqual(client.take_warnings(), [])

    def test_negative_limit_is_rejected_by_argparse(self):
        with self.assertRaises(SystemExit):
            client.main(["search", "part", "-n", "-1"])


class TestCacheDir(unittest.TestCase):
    def test_cache_dir_is_xdg(self):
        self.assertIn("jlcpcb-parts-cli", str(client.CACHE_DIR))


class TestBasicCache(unittest.TestCase):
    def setUp(self):
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._old_cache_dir = client.CACHE_DIR
        client.CACHE_DIR = Path(self._tmp.name)
        self.addCleanup(setattr, client, "CACHE_DIR", self._old_cache_dir)

    def test_corrupted_cache_refetches_instead_of_crashing(self):
        """Regression: a truncated/corrupt cache file must trigger a refetch,
        never an unhandled JSONDecodeError (reviewer-reported fail-closed bug)."""
        cache = client.CACHE_DIR / "basic_parts.json"
        cache.write_text('{"fetched": 1, "parts": [{"code": "C1"')  # truncated
        with mock.patch.object(
            client, "iter_all", return_value=iter([normalized_part(code="C6186")])
        ) as fetch:
            parts, source = client.load_basic_cache(refresh=False)
        self.assertEqual(parts, [normalized_part(code="C6186")])
        self.assertIn("fresh", source)
        fetch.assert_called_once()
        # and the poisoned cache got replaced with valid JSON
        data = json.loads(cache.read_text())
        self.assertEqual(data["parts"], [normalized_part(code="C6186")])

    def test_wrong_shape_cache_refetches(self):
        cache = client.CACHE_DIR / "basic_parts.json"
        cache.write_text(json.dumps({"fetched": time.time(), "nope": True}))
        with mock.patch.object(
            client, "iter_all", return_value=iter([normalized_part(code="C2")])
        ):
            parts, source = client.load_basic_cache(refresh=False)
        self.assertEqual(parts, [normalized_part(code="C2")])
        self.assertIn("fresh", source)

    def test_fresh_cache_is_used_without_refetch(self):
        cache = client.CACHE_DIR / "basic_parts.json"
        cache.write_text(
            json.dumps(
                {"fetched": time.time(), "parts": [normalized_part(code="C1002")]}
            )
        )
        with mock.patch.object(client, "iter_all") as fetch:
            parts, source = client.load_basic_cache(refresh=False)
        self.assertEqual(parts, [normalized_part(code="C1002")])
        self.assertIn("cache", source)
        fetch.assert_not_called()

    def test_cache_write_is_atomic_shape(self):
        """After a refetch the cache must contain valid JSON under 'parts'."""
        with mock.patch.object(
            client, "iter_all", return_value=iter([normalized_part(code="C3")])
        ):
            client.load_basic_cache(refresh=False)
        cache = client.CACHE_DIR / "basic_parts.json"
        data = json.loads(cache.read_text())  # must not raise
        self.assertEqual(data["parts"], [normalized_part(code="C3")])
        self.assertEqual(list(client.CACHE_DIR.glob("*.tmp")), [])

    def test_schema_poisoned_cache_refetches(self):
        cache = client.CACHE_DIR / "basic_parts.json"
        cache.write_text(json.dumps({"fetched": time.time(), "parts": ["poison"]}))
        with mock.patch.object(
            client, "iter_all", return_value=iter([normalized_part(code="C4")])
        ) as fetch:
            parts, _ = client.load_basic_cache(refresh=False)

        self.assertEqual(parts[0]["code"], "C4")
        fetch.assert_called_once()

    def test_empty_refresh_preserves_existing_cache(self):
        import os

        cache = client.CACHE_DIR / "basic_parts.json"
        old_parts = [normalized_part(code="C6186")]
        cache.write_text(json.dumps({"fetched": 1, "parts": old_parts}))
        stale = time.time() - 25 * 3600
        os.utime(cache, (stale, stale))

        with (
            mock.patch.object(client, "iter_all", return_value=iter(())),
            self.assertRaisesRegex(client.PayloadError, "empty"),
        ):
            client.load_basic_cache(refresh=False)

        self.assertEqual(json.loads(cache.read_text())["parts"], old_parts)


class TestMarkdown(unittest.TestCase):
    def test_table_cells_are_single_line_and_pipe_safe(self):
        self.assertEqual(client._md("x\ny|z"), "x y/z")

    def test_export_counts_sanitized_category(self):
        part = normalized_part(category="A|B")
        with (
            mock.patch.object(
                client, "load_basic_cache", return_value=([part], "test")
            ),
            mock.patch("sys.stdout", new_callable=StringIO) as output,
        ):
            result = client.main(["export"])

        self.assertEqual(result, 0)
        self.assertIn("## A/B (1)", output.getvalue())


if __name__ == "__main__":
    unittest.main()
