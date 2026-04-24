"""Tests for ai_readiness.utils.language_detect.detect_languages."""
from __future__ import annotations

import pytest

from ai_readiness.utils.language_detect import detect_languages
from tests.conftest import create_file


class TestDetectLanguages:
    def test_python_files(self, tmp_path):
        create_file(tmp_path, "app.py", "print('hi')")
        create_file(tmp_path, "utils.py", "x = 1")
        langs = detect_languages(tmp_path)
        assert "Python" in langs

    def test_javascript_via_package_json(self, tmp_path):
        create_file(tmp_path, "package.json", '{"name": "app"}')
        langs = detect_languages(tmp_path)
        assert "JavaScript" in langs

    def test_typescript_via_tsconfig(self, tmp_path):
        create_file(tmp_path, "tsconfig.json", '{}')
        create_file(tmp_path, "src/app.ts", "const x = 1;")
        langs = detect_languages(tmp_path)
        assert "TypeScript" in langs

    def test_csharp_via_sln(self, tmp_path):
        create_file(tmp_path, "App.sln", "Microsoft Visual Studio Solution")
        langs = detect_languages(tmp_path)
        assert "C#" in langs

    def test_csharp_via_csproj(self, tmp_path):
        create_file(tmp_path, "App.csproj", "<Project></Project>")
        langs = detect_languages(tmp_path)
        assert "C#" in langs

    def test_rust_via_cargo(self, tmp_path):
        create_file(tmp_path, "Cargo.toml", "[package]\n")
        create_file(tmp_path, "src/main.rs", "fn main() {}")
        langs = detect_languages(tmp_path)
        assert "Rust" in langs

    def test_go_via_go_mod(self, tmp_path):
        create_file(tmp_path, "go.mod", "module example.com/app\n")
        langs = detect_languages(tmp_path)
        assert "Go" in langs

    def test_multiple_languages_sorted_by_prevalence(self, tmp_path):
        # Python has manifest + files; JS has only one file
        create_file(tmp_path, "pyproject.toml", "[project]\n")
        for i in range(10):
            create_file(tmp_path, f"src/mod_{i}.py", "x = 1")
        create_file(tmp_path, "util.js", "var x = 1;")

        langs = detect_languages(tmp_path)
        assert "Python" in langs
        assert "JavaScript" in langs
        # Python should come first (manifest weight + file count)
        assert langs.index("Python") < langs.index("JavaScript")

    def test_empty_repo(self, tmp_path):
        langs = detect_languages(tmp_path)
        assert langs == []

    def test_skips_node_modules(self, tmp_path):
        create_file(tmp_path, "node_modules/dep/index.js", "module.exports = {};")
        create_file(tmp_path, "app.py", "pass")
        langs = detect_languages(tmp_path)
        # JS in node_modules should be ignored
        assert "Python" in langs

    def test_java_via_pom(self, tmp_path):
        create_file(tmp_path, "pom.xml", "<project></project>")
        langs = detect_languages(tmp_path)
        assert "Java" in langs

    def test_ruby_via_gemfile(self, tmp_path):
        create_file(tmp_path, "Gemfile", 'source "https://rubygems.org"')
        langs = detect_languages(tmp_path)
        assert "Ruby" in langs
