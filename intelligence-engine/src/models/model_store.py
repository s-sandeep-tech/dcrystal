"""Versioned artifacts from a trusted, application-owned directory only."""
import json
import os
import platform
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4

import joblib


def runtime_versions():
    return {"python": platform.python_version(), **{
        name: version(name) for name in ("numpy", "pandas", "scikit-learn", "joblib")
    }}


class ModelStore:
    def __init__(self, directory):
        self.directory = Path(directory)

    def save(self, bundle):
        self.directory.mkdir(parents=True, exist_ok=True)
        model_id = uuid4().hex
        artifact = self.directory / f"{model_id}.joblib"
        temporary = self.directory / f".{model_id}.tmp"
        pointer = self.directory / f".{model_id}.json"
        try:
            with temporary.open("wb") as stream:
                joblib.dump(bundle, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, artifact)
            with pointer.open("w") as stream:
                json.dump({"artifact": artifact.name, "versions": runtime_versions(),
                           "engine_version": bundle["engine_version"]}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            # The previous active pointer survives any failed write above.
            os.replace(pointer, self.directory / "active.json")
        finally:
            temporary.unlink(missing_ok=True)
            pointer.unlink(missing_ok=True)
        return model_id

    def load(self):
        pointer = self.directory / "active.json"
        if not pointer.exists():
            return None
        manifest = json.loads(pointer.read_text())
        filename = manifest["artifact"]
        if Path(filename).name != filename or not filename.endswith(".joblib"):
            raise ValueError("Invalid model artifact filename")
        if manifest["versions"] != runtime_versions():
            raise ValueError("Model dependency versions changed; restore the training environment or retrain")
        engine, engine_version = manifest["engine_version"]
        if version(engine) != engine_version:
            raise ValueError("Model engine version changed; retrain before serving predictions")
        bundle = joblib.load(self.directory / filename)
        if bundle.get("schema_version") != 1:
            raise ValueError("Unsupported model artifact schema")
        return bundle
