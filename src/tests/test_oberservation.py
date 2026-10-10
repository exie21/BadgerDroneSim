import unittest
from src.badger_core.oberservation import Observation, ObservationStatus, validate_observation


class TestObservationValidation(unittest.TestCase):
    
    def test_centered_valid_target_is_accepted(self):
        """Test that a centered observation is accepted with CENTERED status."""
        obs = Observation(
            target_id=7,
            capture_time_s=100.00,
            received_time_s=100.08,
            x_error_m=0.06,
            y_error_m=-0.04,
            valid_pose=True,
            calibration_version="v1",
        )

        result = validate_observation(
            obs,
            expected_target_id=7,
            now_s=100.08,
            last_capture_time_s=99.90,
        )

        self.assertEqual(result.status, ObservationStatus.CENTERED)
    
    def test_valid_non_centered_returns_valid(self):
        """Test that a valid observation outside tolerance returns VALID status."""
        obs = Observation(
            target_id=7,
            capture_time_s=100.00,
            received_time_s=100.08,
            x_error_m=0.20,
            y_error_m=0.00,
            valid_pose=True,
            calibration_version="v1",
        )

        result = validate_observation(
            obs,
            expected_target_id=7,
            now_s=100.08,
            last_capture_time_s=99.90,
        )

        self.assertEqual(result.status, ObservationStatus.VALID)
        self.assertIsNotNone(result.horizontal_error_m)


if __name__ == '__main__':
    unittest.main()
