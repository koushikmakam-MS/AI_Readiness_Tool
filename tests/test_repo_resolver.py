"""Tests for ai_readiness.core.repo_resolver.RepoResolver."""
from __future__ import annotations

import pytest

from ai_readiness.core.repo_resolver import RepoResolver


class TestIsRemote:
    @pytest.mark.parametrize("target", [
        "https://github.com/owner/repo",
        "https://github.com/owner/repo.git",
        "http://github.com/owner/repo",
        "git@github.com:owner/repo.git",
        "ssh://git@github.com/owner/repo.git",
    ])
    def test_urls_are_remote(self, target):
        resolver = RepoResolver(target)
        assert resolver.is_remote is True

    def test_shorthand_owner_repo_is_remote(self):
        resolver = RepoResolver("owner/repo")
        assert resolver.is_remote is True

    @pytest.mark.parametrize("target", [
        ".",
        "..",
        "C:\\some\\local\\path",
    ])
    def test_local_paths_are_not_remote(self, target):
        resolver = RepoResolver(target)
        assert resolver.is_remote is False


class TestResolveLocal:
    def test_existing_dir_resolves(self, tmp_path):
        resolver = RepoResolver(str(tmp_path))
        resolved = resolver.resolve()
        assert resolved == tmp_path.resolve()

    def test_nonexistent_path_raises(self, tmp_path):
        bad_path = str(tmp_path / "does_not_exist")
        resolver = RepoResolver(bad_path)
        with pytest.raises(FileNotFoundError):
            resolver.resolve()

    def test_file_path_raises(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("hi")
        resolver = RepoResolver(str(f))
        with pytest.raises(NotADirectoryError):
            resolver.resolve()


class TestNormalizeUrl:
    def test_shorthand_becomes_github_url(self):
        resolver = RepoResolver("owner/repo")
        assert resolver._normalize_url() == "https://github.com/owner/repo.git"

    def test_https_url_gets_git_suffix(self):
        resolver = RepoResolver("https://github.com/owner/repo")
        assert resolver._normalize_url().endswith(".git")

    def test_already_has_git_suffix(self):
        resolver = RepoResolver("https://github.com/owner/repo.git")
        url = resolver._normalize_url()
        assert url.endswith(".git")
        assert not url.endswith(".git.git")


class TestCleanup:
    def test_cleanup_without_clone_is_safe(self):
        resolver = RepoResolver(".")
        resolver.cleanup()  # Should not raise

    def test_context_manager(self, tmp_path):
        with RepoResolver(str(tmp_path)) as resolver:
            resolved = resolver.resolve()
            assert resolved.exists()
        # cleanup runs on __exit__
