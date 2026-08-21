import unittest

from scripts.ci.classify_change import classify


class ClassifyTests(unittest.TestCase):
    def test_deploy_workflow_is_production_not_fast(self):
        lane, req, impact = classify([".github/workflows/deploy-runtime-autonomous.yml"])
        self.assertEqual(lane, "PRODUCTION")
        self.assertFalse(req)  # control-plane, no runtime artifacts
        self.assertEqual(impact, "CONTROL_PLANE")

    def test_release_tooling_is_production(self):
        lane, req, _ = classify(["scripts/release/evaluate_production_policy.py"])
        self.assertEqual(lane, "PRODUCTION")
        self.assertFalse(req)

    def test_operations_tooling_is_production(self):
        lane, req, _ = classify(["scripts/operations/verify_runtime.py"])
        self.assertEqual(lane, "PRODUCTION")

    def test_api_is_standard(self):
        lane, req, impact = classify(["api/app/main.py"])
        self.assertEqual(lane, "STANDARD")
        self.assertTrue(req)
        self.assertEqual(impact, "VPS")

    def test_docs_is_fast(self):
        lane, req, impact = classify(["docs/README.md"])
        self.assertEqual(lane, "FAST")
        self.assertFalse(req)
        self.assertEqual(impact, "NONE")

    def test_deploy_vps_is_production_runtime(self):
        lane, req, impact = classify(["deploy/vps/deploy.sh"])
        self.assertEqual(lane, "PRODUCTION")
        self.assertTrue(req)
        self.assertEqual(impact, "VPS")

    def test_mixed_is_production(self):
        lane, req, impact = classify(["api/app/main.py", "worker/hls_motion_yolo_runtime.py"])
        self.assertEqual(lane, "PRODUCTION")
        self.assertTrue(req)
        self.assertEqual(impact, "MIXED")

    def test_canonical_is_production(self):
        lane, req, _ = classify(["contracts/DELIVERY_CANONICAL.md"])
        self.assertEqual(lane, "PRODUCTION")


if __name__ == "__main__":
    unittest.main()
