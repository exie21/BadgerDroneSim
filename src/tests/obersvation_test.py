def test_centered_valid_target_is_accepted():
    obs = Observation(
        target_id=7,
        capture_time_s=100.00,
        x_error_m=0.06,
        y_error_m=-0.04,
        valid_pose=True,
    )

    result = validate_observation(
        obs,
        expected_target_id=7,
        now_s=100.08,
        last_capture_time_s=99.90,
    )

    assert result.status == "CENTERED"