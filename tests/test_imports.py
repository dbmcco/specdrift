import unittest

from specdrift.contracts import format_default_contract_block
from specdrift.drift import compute_spec_drift
from specdrift.git_tools import WorkingChanges
from specdrift.globmatch import match_any, match_path
from specdrift.specs import SpecdriftSpec, extract_specdrift_spec, parse_specdrift_spec


class TestGlobMatch(unittest.TestCase):
    def test_exact_match(self) -> None:
        self.assertTrue(match_path("foo/bar.py", "foo/bar.py"))

    def test_no_match(self) -> None:
        self.assertFalse(match_path("foo/baz.py", "foo/bar.py"))

    def test_star_matches_within_segment(self) -> None:
        self.assertTrue(match_path("foo/bar.py", "foo/*.py"))

    def test_star_does_not_cross_segment(self) -> None:
        self.assertFalse(match_path("foo/bar/baz.py", "foo/*.py"))

    def test_double_star_matches_zero_segments(self) -> None:
        self.assertTrue(match_path("foo.py", "**/*.py"))

    def test_double_star_matches_multiple_segments(self) -> None:
        self.assertTrue(match_path("a/b/c/foo.py", "**/*.py"))

    def test_double_star_workgraph_prefix(self) -> None:
        self.assertTrue(match_path(".workgraph/foo/bar.json", ".workgraph/**"))

    def test_pattern_not_anchored_to_wrong_root(self) -> None:
        self.assertFalse(match_path("other/docs/spec.md", "docs/**"))


class TestMatchAny(unittest.TestCase):
    def test_matches_first_pattern(self) -> None:
        self.assertTrue(match_any("docs/spec.md", ["docs/**", "**/*.py"]))

    def test_matches_second_pattern(self) -> None:
        self.assertTrue(match_any("src/foo.py", ["docs/**", "**/*.py"]))

    def test_no_match(self) -> None:
        self.assertFalse(match_any("src/foo.py", ["docs/**", "*.md"]))

    def test_empty_patterns(self) -> None:
        self.assertFalse(match_any("src/foo.py", []))


class TestContracts(unittest.TestCase):
    def test_contains_schema(self) -> None:
        block = format_default_contract_block(mode="core", objective="test obj", touch=[])
        self.assertIn("schema = 1", block)

    def test_contains_mode(self) -> None:
        block = format_default_contract_block(mode="core", objective="test obj", touch=[])
        self.assertIn('mode = "core"', block)

    def test_contains_objective(self) -> None:
        block = format_default_contract_block(mode="core", objective="my objective", touch=[])
        self.assertIn('objective = "my objective"', block)

    def test_fenced_wg_contract(self) -> None:
        block = format_default_contract_block(mode="core", objective="test", touch=[])
        self.assertTrue(block.startswith("```wg-contract"))
        self.assertIn("\n```", block)

    def test_touch_paths_present(self) -> None:
        block = format_default_contract_block(mode="core", objective="test", touch=["src/**", "docs/**"])
        self.assertIn('"src/**"', block)
        self.assertIn('"docs/**"', block)

    def test_empty_touch_produces_empty_list(self) -> None:
        block = format_default_contract_block(mode="core", objective="test", touch=[])
        # touch list should appear as an empty TOML array
        self.assertIn("touch =", block)


class TestSpecs(unittest.TestCase):
    _FENCE = '```specdrift\nschema = 1\nspec = ["docs/**"]\n```'

    def test_extract_present(self) -> None:
        result = extract_specdrift_spec(self._FENCE)
        self.assertIsNotNone(result)
        self.assertIn("schema = 1", result)  # type: ignore[arg-type]

    def test_extract_absent(self) -> None:
        self.assertIsNone(extract_specdrift_spec("no fence here"))

    def test_extract_empty_string(self) -> None:
        self.assertIsNone(extract_specdrift_spec(""))

    def test_extract_none_input(self) -> None:
        self.assertIsNone(extract_specdrift_spec(None))  # type: ignore[arg-type]

    def test_parse_returns_dict(self) -> None:
        data = parse_specdrift_spec('schema = 1\nspec = ["docs/**"]')
        self.assertIsInstance(data, dict)
        self.assertEqual(data["schema"], 1)
        self.assertEqual(data["spec"], ["docs/**"])

    def test_from_raw_fields(self) -> None:
        spec = SpecdriftSpec.from_raw({"schema": 1, "spec": ["docs/**"]})
        self.assertEqual(spec.schema, 1)
        self.assertEqual(spec.spec, ["docs/**"])
        self.assertTrue(spec.require_spec_update_when_code_changes)

    def test_from_raw_always_ignores_workgraph(self) -> None:
        spec = SpecdriftSpec.from_raw({"schema": 1, "spec": []})
        self.assertIn(".workgraph/**", spec.ignore)
        self.assertIn(".git/**", spec.ignore)

    def test_from_raw_empty_spec(self) -> None:
        spec = SpecdriftSpec.from_raw({"schema": 1})
        self.assertEqual(spec.spec, [])

    def test_from_raw_opt_out_require_update(self) -> None:
        spec = SpecdriftSpec.from_raw({"schema": 1, "spec": ["docs/**"], "require_spec_update_when_code_changes": False})
        self.assertFalse(spec.require_spec_update_when_code_changes)


class TestComputeSpecDrift(unittest.TestCase):
    @staticmethod
    def _spec(**kwargs: object) -> SpecdriftSpec:
        base: dict = {"schema": 1, "spec": ["docs/**"]}
        base.update(kwargs)
        return SpecdriftSpec.from_raw(base)

    def _run(self, *, changes: WorkingChanges | None = None, **spec_kwargs: object) -> dict:
        return compute_spec_drift(
            task_id="t1",
            task_title="Test task",
            description="",
            spec=self._spec(**spec_kwargs),
            git_root=None,
            changes=changes,
        )

    def test_green_with_no_changes(self) -> None:
        result = self._run()
        self.assertEqual(result["score"], "green")
        self.assertEqual(result["findings"], [])

    def test_green_when_spec_and_code_both_change(self) -> None:
        changes = WorkingChanges(changed_files=["docs/README.md", "src/foo.py"])
        result = self._run(changes=changes)
        self.assertEqual(result["score"], "green")

    def test_yellow_when_code_changes_without_spec(self) -> None:
        changes = WorkingChanges(changed_files=["src/foo.py"])
        result = self._run(changes=changes)
        self.assertEqual(result["score"], "yellow")
        kinds = [f["kind"] for f in result["findings"]]
        self.assertIn("spec_not_updated", kinds)

    def test_green_when_require_update_disabled_and_only_code_changes(self) -> None:
        changes = WorkingChanges(changed_files=["src/foo.py"])
        result = self._run(changes=changes, require_spec_update_when_code_changes=False)
        self.assertEqual(result["score"], "green")

    def test_yellow_when_spec_list_empty(self) -> None:
        result = self._run(spec=[])
        self.assertEqual(result["score"], "yellow")
        kinds = [f["kind"] for f in result["findings"]]
        self.assertIn("invalid_spec_config", kinds)

    def test_yellow_on_unsupported_schema(self) -> None:
        spec = SpecdriftSpec(schema=99, spec=["docs/**"], require_spec_update_when_code_changes=True, ignore=[])
        result = compute_spec_drift(
            task_id="t1", task_title="task", description="", spec=spec, git_root=None, changes=None
        )
        self.assertEqual(result["score"], "yellow")
        kinds = [f["kind"] for f in result["findings"]]
        self.assertIn("unsupported_schema", kinds)

    def test_workgraph_files_excluded_from_telemetry(self) -> None:
        changes = WorkingChanges(changed_files=[".workgraph/foo.txt", "src/bar.py"])
        result = self._run(changes=changes)
        # .workgraph/ is hard-filtered; only src/bar.py counts
        self.assertEqual(result["telemetry"]["files_changed"], 1)

    def test_git_files_excluded_from_telemetry(self) -> None:
        changes = WorkingChanges(changed_files=[".git/ORIG_HEAD", "src/bar.py"])
        result = self._run(changes=changes)
        self.assertEqual(result["telemetry"]["files_changed"], 1)

    def test_output_has_required_keys(self) -> None:
        result = self._run()
        for key in ("task_id", "task_title", "git_root", "score", "spec", "telemetry", "findings", "recommendations"):
            self.assertIn(key, result)

    def test_task_id_and_title_propagated(self) -> None:
        result = compute_spec_drift(
            task_id="my-task-123",
            task_title="My Important Task",
            description="",
            spec=self._spec(),
            git_root="/repo",
            changes=None,
        )
        self.assertEqual(result["task_id"], "my-task-123")
        self.assertEqual(result["task_title"], "My Important Task")
        self.assertEqual(result["git_root"], "/repo")

    def test_telemetry_counts_spec_vs_non_spec(self) -> None:
        changes = WorkingChanges(changed_files=["docs/spec.md", "docs/guide.md", "src/foo.py"])
        result = self._run(changes=changes)
        self.assertEqual(result["telemetry"]["spec_files_changed"], 2)
        self.assertEqual(result["telemetry"]["non_spec_files_changed"], 1)

    def test_recommendations_present_on_finding(self) -> None:
        changes = WorkingChanges(changed_files=["src/foo.py"])
        result = self._run(changes=changes)
        self.assertGreater(len(result["recommendations"]), 0)
        self.assertIn("action", result["recommendations"][0])


if __name__ == "__main__":
    unittest.main()
