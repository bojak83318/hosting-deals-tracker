from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.spec_extractor import MLSpecExtractor


def test_fit_and_extract_one_from_jsonl() -> None:
    data_path = ROOT / "ml" / "training_data.jsonl"

    extractor = MLSpecExtractor().fit(data_path)
    result = extractor.extract_one(
        "Pro VM: 8 vCPU, 32GB RAM, 1TB NVMe storage, 5TB bandwidth, $79/mo"
    )

    assert result["cpu"] == 8
    assert result["ram_gb"] == 32.0
    assert result["storage_gb"] == 1024.0
    assert result["storage_type"] == "nvme"
    assert result["bandwidth_tb"] == 5.0
    assert result["price_monthly"] == 79.0


def test_ml_style_storage_type_inference_when_not_explicit() -> None:
    data_path = ROOT / "ml" / "training_data.jsonl"

    extractor = MLSpecExtractor().fit(data_path)
    result = extractor.predict(
        "Value plan: dual core, 4GB RAM, 120GB solid state storage, 1TB transfer, $10/month"
    )

    assert result["cpu"] == 2
    assert result["ram_gb"] == 4.0
    assert result["storage_gb"] == 120.0
    # "solid state" should normalize to SSD.
    assert result["storage_type"] == "ssd"
    assert result["bandwidth_tb"] == 1.0
    assert result["price_monthly"] == 10.0


def test_extract_many_and_edge_case_unit_conversions() -> None:
    extractor = MLSpecExtractor().fit(
        [
            {
                "text": "2 core, 2GB RAM, 60GB SSD, 1TB bandwidth, $7/mo",
                "storage_type": "ssd",
            }
        ]
    )

    results = extractor.extract_many(
        [
            "CPU: quad core | RAM 8192MB | Disk 102400MB HDD | Bandwidth 500GB | monthly: 9.5",
            "1 vCPU, memory 1GB, 20GB storage, 250GB traffic, $3/month",
        ]
    )

    first = results[0]
    assert first["cpu"] == 4
    assert first["ram_gb"] == 8.0
    assert first["storage_gb"] == 100.0
    assert first["storage_type"] == "hdd"
    assert first["bandwidth_tb"] == round(500 / 1024, 3)
    assert first["price_monthly"] == 9.5

    second = results[1]
    assert second["cpu"] == 1
    assert second["ram_gb"] == 1.0
    assert second["storage_gb"] == 20.0
    assert second["bandwidth_tb"] == round(250 / 1024, 3)
    assert second["price_monthly"] == 3.0
