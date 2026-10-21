import tempfile
import os
import unittest
from unittest.mock import patch

from src.models.predictor import TabularPredictor


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.predictor = TabularPredictor(self.directory.name)
        self.predictor._has_xgboost = False
        self.records = [{"priority": p, "amount": i, "risk": risk}
                        for i in range(10)
                        for p, risk in [("Normal", 10), ("Urgent", 80)]]

    def train(self):
        result = self.predictor.train_or_fit(self.records, target_column="risk")
        self.assertEqual(result["status"], "success", result)

    def test_restart_and_category_batch_stability(self):
        self.train()
        row = {"priority": "Urgent", "amount": 2}
        expected = self.predictor.predict([row])[0]["predicted_value"]
        restored = TabularPredictor(self.directory.name)
        self.assertEqual(expected, restored.predict([row])[0]["predicted_value"])
        self.assertEqual(expected, restored.predict([
            {"priority": "Normal", "amount": 2}, row])[1]["predicted_value"])
        self.assertTrue(restored.predict([{"priority": "Unseen", "amount": 2}]))

    def test_failed_save_preserves_live_and_saved_model(self):
        self.train()
        old = self.predictor.model
        before = self.predictor.predict(self.records)
        with patch("src.models.model_store.os.replace", side_effect=OSError("disk failure")):
            result = self.predictor.train_or_fit(self.records, target_column="risk")
        self.assertEqual(result["status"], "error")
        self.assertIs(self.predictor.model, old)
        self.assertEqual(before, TabularPredictor(self.directory.name).predict(self.records))

    def test_failed_fit_preserves_model(self):
        self.train()
        old = self.predictor.model
        result = self.predictor.train_or_fit(self.records, "risk", ["missing"])
        self.assertEqual(result["status"], "error")
        self.assertIs(self.predictor.model, old)

    def test_failed_activation_preserves_previous_pointer(self):
        self.train()
        pointer = self.predictor.store.directory / "active.json"
        previous = pointer.read_bytes()
        replace = os.replace

        def fail_activation(source, destination):
            if destination.name == "active.json":
                raise OSError("Cannot activate")
            replace(source, destination)

        with patch("src.models.model_store.os.replace", side_effect=fail_activation):
            result = self.predictor.train_or_fit(self.records, "risk")
        self.assertEqual(result["status"], "error")
        self.assertEqual(previous, pointer.read_bytes())
        self.assertIsNotNone(TabularPredictor(self.directory.name).model)

    def test_no_model_uses_existing_heuristic(self):
        self.assertIsNone(self.predictor.model)
        self.assertEqual(self.predictor.predict([{"priority": "Normal"}])[0]["predicted_value"], 15)

    def test_corrupt_manifest_fails_explicitly(self):
        self.train()
        (self.predictor.store.directory / "active.json").write_text("invalid")
        with self.assertRaises(ValueError):
            TabularPredictor(self.directory.name)

    def test_version_mismatch_fails_before_deserialization(self):
        self.train()
        with patch("src.models.model_store.runtime_versions", return_value={}):
            with self.assertRaisesRegex(ValueError, "versions changed"):
                TabularPredictor(self.directory.name)


if __name__ == "__main__":
    unittest.main()
