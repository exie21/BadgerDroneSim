import unittest


class Observation:
    """Represents an observation of a target tag."""
    
    def __init__(self, target_id, expected_target_id, horizontal_error_m, vertical_error_m, status):
        self.target_id = target_id
        self.expected_target_id = expected_target_id
        self.horizontal_error_m = horizontal_error_m
        self.vertical_error_m = vertical_error_m
        self.status = status
    
    @property
    def is_centered(self):
        """Check if observation is centered (status is CENTERED)."""
        return self.status == "CENTERED"


class TestObservation(unittest.TestCase):
    def test_tag_zero_is_valid_when_expected(self):
        """Test that tag ID 0 is valid when it matches the expected target."""
        observation = Observation(
            target_id=0,
            expected_target_id=0,
            horizontal_error_m=0.5,
            vertical_error_m=0.3,
            status="CENTERED"
        )
        self.assertEqual(observation.status, "CENTERED")
        self.assertIsNotNone(observation.horizontal_error_m)

    def test_tag_zero_is_wrong_when_expected_target_differs(self):
        """Test that tag ID 0 is wrong when expected target is different."""
        observation = Observation(
            target_id=0,
            expected_target_id=7,
            horizontal_error_m=None,
            vertical_error_m=None,
            status="WRONG_TARGET"
        )
        self.assertEqual(observation.status, "WRONG_TARGET")
        self.assertIsNone(observation.horizontal_error_m)


if __name__ == '__main__':
    unittest.main()
