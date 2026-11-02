import ast
import json
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
PLATFORMS = {"sensor": "sensor.py", "binary_sensor": "binary_sensor.py"}
TRANSLATIONS = [
    ROOT_DIR / "strings.json",
    ROOT_DIR / "translations" / "en.json",
    ROOT_DIR / "translations" / "de.json",
]


def _translation_keys(source: str) -> set[str]:
    """Return every translation_key set in a platform module."""
    keys = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.keyword) and node.arg == "translation_key":
            keys.add(node.value.value)
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Attribute)
            and node.targets[0].attr == "_attr_translation_key"
        ):
            keys.add(node.value.value)
    return keys


class EntityNameTests(unittest.TestCase):
    def test_every_translation_key_has_a_name(self) -> None:
        for path in TRANSLATIONS:
            entity = json.loads(path.read_text(encoding="utf-8"))["entity"]
            for platform, module in PLATFORMS.items():
                source = (ROOT_DIR / module).read_text(encoding="utf-8")
                for key in _translation_keys(source):
                    with self.subTest(file=path.name, platform=platform, key=key):
                        self.assertTrue(entity[platform][key]["name"])

    def test_no_entity_overrides_name(self) -> None:
        # Names come from the translations; a name property would win over them.
        for module in ("sensor.py", "binary_sensor.py", "device_tracker.py"):
            tree = ast.parse((ROOT_DIR / module).read_text(encoding="utf-8"))
            names = [
                node.name
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name == "name"
            ]
            self.assertEqual(names, [], module)


if __name__ == "__main__":
    unittest.main()
