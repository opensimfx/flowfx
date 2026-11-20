"""A .blend is untrusted: body IDs read from it must never let Free Cache delete anything but a FlowFX cache."""
import os

import pytest

from flowfx.core import ids
from flowfx.services import cache

UID = "0123456789ab"


def test_only_generated_ids_are_accepted():
    assert ids.is_uid(ids.new_uid()) and ids.is_uid(UID)
    for bad in ("..", ".", "", "/", "/etc", "../x", "0123456789AB", "0123456789a", "0123456789abc", "01234/6789ab",
                None, 123456789012):
        assert not ids.is_uid(bad)


def test_free_removes_a_real_body_cache(tmp_path):
    body = tmp_path / UID
    (body / "spectral").mkdir(parents=True)
    (body / "spectral" / "flowfx_disp_0001.exr").write_bytes(b"x")
    (body / "report.json").write_text("{}", encoding="utf-8")
    assert cache.free(body, tmp_path) == 2 and not body.exists()


@pytest.mark.parametrize("name", ["..", "victim", "Documents"])
def test_free_refuses_folders_not_named_like_a_body(tmp_path, name):
    root = tmp_path / "cache"
    root.mkdir()
    target = (root / name)
    target.mkdir(exist_ok=True)
    (target / "fluid").mkdir(exist_ok=True)
    with pytest.raises(ValueError):
        cache.free(target, root)
    assert target.exists()


def test_free_refuses_a_folder_holding_other_files(tmp_path):
    body = tmp_path / UID
    (body / "fluid").mkdir(parents=True)
    (body / "thesis.docx").write_bytes(b"keep")
    with pytest.raises(ValueError):
        cache.free(body, tmp_path)
    assert (body / "thesis.docx").exists()


def test_free_refuses_a_folder_outside_the_root(tmp_path):
    root, outside = tmp_path / "cache", tmp_path / "elsewhere" / UID
    root.mkdir()
    (outside / "fluid").mkdir(parents=True)
    with pytest.raises(ValueError):
        cache.free(outside, root)
    assert outside.exists()


def test_free_refuses_a_symlinked_body_folder(tmp_path):
    root, target = tmp_path / "cache", tmp_path / "target"
    root.mkdir()
    (target / "fluid").mkdir(parents=True)
    try:
        os.symlink(target, root / UID, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    with pytest.raises(ValueError):
        cache.free(root / UID, root)
    assert (target / "fluid").exists()
