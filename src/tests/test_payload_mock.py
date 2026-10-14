"""Tests for the deterministic simulation-only payload mock."""

from dataclasses import FrozenInstanceError, fields
import math
import unittest

from src.badger_core.payload_mock import PayloadResult, PayloadStatus, ScriptedPayloadMock


class TestScriptedPayloadMock(unittest.TestCase):
    def mock(self) -> ScriptedPayloadMock:
        return ScriptedPayloadMock(
            {
                "instant": (0.0, PayloadStatus.SUCCEEDED),
                "success": (1.0, PayloadStatus.SUCCEEDED),
                "failure": (1.0, PayloadStatus.FAILED),
                "unknown": (1.0, PayloadStatus.UNKNOWN),
            }
        )

    def test_public_status_and_result_shapes(self) -> None:
        self.assertEqual(
            {member.name for member in PayloadStatus},
            {"IN_PROGRESS", "SUCCEEDED", "FAILED", "UNKNOWN"},
        )
        self.assertTrue(all(isinstance(member, str) for member in PayloadStatus))
        self.assertEqual([field.name for field in fields(PayloadResult)], ["request_id", "status"])
        result = PayloadResult("request", PayloadStatus.IN_PROGRESS)
        with self.assertRaises(FrozenInstanceError):
            result.status = PayloadStatus.SUCCEEDED

    def test_zero_delay_starts_in_progress_then_polls_succeeded(self) -> None:
        mock = self.mock()

        started = mock.start("instant", now_s=10.0)
        completed = mock.poll("instant", now_s=10.0)

        self.assertEqual(started, PayloadResult("instant", PayloadStatus.IN_PROGRESS))
        self.assertEqual(completed, PayloadResult("instant", PayloadStatus.SUCCEEDED))

    def test_positive_delay_stays_in_progress_until_exact_boundary(self) -> None:
        mock = self.mock()
        mock.start("success", now_s=10.0)

        before = mock.poll("success", now_s=10.999)
        boundary = mock.poll("success", now_s=11.0)

        self.assertEqual(before.status, PayloadStatus.IN_PROGRESS)
        self.assertEqual(boundary.status, PayloadStatus.SUCCEEDED)

    def test_failed_and_unknown_are_distinct_terminal_outcomes(self) -> None:
        mock = self.mock()
        for request_id, expected_status in (
            ("failure", PayloadStatus.FAILED),
            ("unknown", PayloadStatus.UNKNOWN),
        ):
            with self.subTest(request_id=request_id):
                mock.start(request_id, now_s=10.0)
                result = mock.poll(request_id, now_s=11.0)
                self.assertEqual(result, PayloadResult(request_id, expected_status))
                self.assertNotEqual(result.status, PayloadStatus.SUCCEEDED)

    def test_duplicate_start_never_resets_original_completion_time(self) -> None:
        mock = self.mock()
        mock.start("success", now_s=10.0)
        duplicate = mock.start("success", now_s=100.0)

        self.assertEqual(duplicate.status, PayloadStatus.IN_PROGRESS)
        self.assertEqual(mock.poll("success", now_s=10.5).status, PayloadStatus.IN_PROGRESS)
        self.assertEqual(mock.poll("success", now_s=11.0).status, PayloadStatus.SUCCEEDED)

    def test_duplicate_start_after_terminal_result_is_still_in_progress(self) -> None:
        mock = self.mock()
        mock.start("success", now_s=10.0)
        self.assertEqual(mock.poll("success", now_s=11.0).status, PayloadStatus.SUCCEEDED)

        duplicate = mock.start("success", now_s=20.0)

        self.assertEqual(duplicate.status, PayloadStatus.IN_PROGRESS)
        self.assertEqual(mock.poll("success", now_s=11.0).status, PayloadStatus.SUCCEEDED)

    def test_missing_or_not_started_requests_raise_key_error(self) -> None:
        mock = self.mock()

        with self.assertRaises(KeyError):
            mock.start("missing", now_s=10.0)
        with self.assertRaises(KeyError):
            mock.poll("missing", now_s=10.0)
        with self.assertRaises(KeyError):
            mock.poll("success", now_s=10.0)

    def test_invalid_clock_values_and_poll_before_start_are_rejected(self) -> None:
        mock = self.mock()
        for value in (True, "10", math.nan, math.inf):
            with self.subTest(start_now_s=value):
                with self.assertRaises(ValueError):
                    mock.start("success", now_s=value)
            with self.subTest(poll_now_s=value):
                with self.assertRaises(ValueError):
                    mock.poll("success", now_s=value)

        mock.start("success", now_s=10.0)
        with self.assertRaises(ValueError):
            mock.poll("success", now_s=9.99)

    def test_invalid_scripts_are_rejected(self) -> None:
        invalid_scripts = (
            None,
            {"": (0.0, PayloadStatus.SUCCEEDED)},
            {"request": (True, PayloadStatus.SUCCEEDED)},
            {"request": (math.nan, PayloadStatus.SUCCEEDED)},
            {"request": (-0.1, PayloadStatus.SUCCEEDED)},
            {"request": (0.0, PayloadStatus.IN_PROGRESS)},
            {"request": (0.0, "SUCCEEDED")},
            {"request": (0.0,)},
        )
        for script in invalid_scripts:
            with self.subTest(script=script):
                with self.assertRaises(ValueError):
                    ScriptedPayloadMock(script)

    def test_request_ids_have_independent_start_times(self) -> None:
        mock = ScriptedPayloadMock(
            {
                "first": (1.0, PayloadStatus.SUCCEEDED),
                "second": (1.0, PayloadStatus.FAILED),
            }
        )
        mock.start("first", now_s=10.0)
        mock.start("second", now_s=20.0)

        self.assertEqual(mock.poll("first", now_s=11.0).status, PayloadStatus.SUCCEEDED)
        self.assertEqual(mock.poll("second", now_s=20.5).status, PayloadStatus.IN_PROGRESS)
        self.assertEqual(mock.poll("second", now_s=21.0).status, PayloadStatus.FAILED)

    def test_constructor_copies_the_script_mapping(self) -> None:
        script = {"request": (1.0, PayloadStatus.SUCCEEDED)}
        mock = ScriptedPayloadMock(script)
        script["request"] = (0.0, PayloadStatus.FAILED)

        mock.start("request", now_s=10.0)

        self.assertEqual(mock.poll("request", now_s=11.0).status, PayloadStatus.SUCCEEDED)


if __name__ == "__main__":
    unittest.main()
