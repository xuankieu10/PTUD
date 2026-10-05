import os
import pytest
import subprocess
from unittest.mock import patch, MagicMock

@patch("backend.main.run_pipeline")
def test_main_cli_valid_args(mock_run, tmp_path):
    import sys
    from backend.main import main
    
    mock_run.return_value = {
        "json_path": "a.json",
        "csv_path": "a.csv",
        "total_subjects": 1,
        "failed_count": 0,
        "passed_count": 1,
        "red_regions_count": 0,
        "annotated_image_path": "a.png",
        "failed_subjects": []
    }
    
    dummy_input = tmp_path / "input.png"
    dummy_input.write_bytes(b"")
    
    test_args = ["main.py", "--input", str(dummy_input), "--output-dir", str(tmp_path)]
    
    with patch.object(sys, "argv", test_args):
        try:
            main()
        except SystemExit as e:
            assert e.code == 0
            
    assert mock_run.called

def test_main_cli_missing_input():
    import sys
    from backend.main import main
    
    test_args = ["main.py"]
    with patch.object(sys, "argv", test_args):
        try:
            main()
        except SystemExit as e:
            assert e.code != 0

