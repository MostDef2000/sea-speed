import json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MATRIX=ROOT/"scripts/worker/detector_frequency_matrix_v1.json"
SCHEMA=ROOT/"schemas/detector-frequency-benchmark.schema.json"
class DetectorFrequencyBenchmarkTests(unittest.TestCase):
    def test_matrix_valid(self):
        data=json.loads(MATRIX.read_text(encoding="utf-8"))
        self.assertIn("offered", data)
        self.assertEqual(data["offered"], [5,10,15])
    def test_schema_valid(self):
        data=json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(data["title"], "Sea Speed detector frequency benchmark")
    def test_p95(self):
        from scripts.worker.benchmark_detector_frequency import p95
        self.assertEqual(p95([1,2,3,4,5]), 4)
if __name__=="__main__": unittest.main()
