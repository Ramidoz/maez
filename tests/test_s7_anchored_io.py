"""core/governance/anchored_io.py — the anchored write/read primitive.

Split out of the migration matrix on review: publication mechanics are a
governance primitive with their own contract, and proving them once here
keeps the migration tests about migration -- classification, fingerprints,
ordering, receipt contents and recovery.

The frozen surface:

    def write_private_file(relative, data, *, root, on_link=None) -> Path
    def read_private_file(relative, *, root, expected_uid) -> bytes
    def read_migration_receipt() -> bytes          # ACTIVATION, takes nothing
    def _read_migration_receipt(*, store_dir_fd: int) -> bytes

`on_link` exists so the exclusive-create race is observable: the winner
links, the loser must fail and re-read rather than replace.

SAFETY: `read_migration_receipt()` opens the ONE canonical directory. No
test here calls it -- only its signature is inspected. Everything else
runs against a tmp_path root.
"""

from __future__ import annotations

import os
import stat as stat_module
from pathlib import Path

import pytest

@pytest.fixture
def anchored():
    """The primitive under test.

    A fixture rather than importorskip: a SKIP is not an alarm. The module
    does not exist yet, so every test here is RED on a named cause -- and
    once it lands each reaches its own assertion.
    """
    import importlib

    try:
        return importlib.import_module("core.governance.anchored_io")
    except ImportError as exc:  # pragma: no cover - the pre-implementation path
        pytest.fail(f"core/governance/anchored_io.py does not exist yet: {exc}")


RECEIPT_NAME = "s7_migration_receipt.json"
SIZE_CAP = 8192


def _write(anchored, root: Path, name: str = RECEIPT_NAME, data: bytes = b"{}"):
    return anchored.write_private_file(name, data, root=root)


class TestTheFrozenSurface:
    def test_the_activation_reader_takes_nothing(self, anchored) -> None:
        """No public or production route accepts a path, a root or a
        descriptor -- asserted from the signature, not from prose."""
        import inspect

        assert not inspect.signature(anchored.read_migration_receipt).parameters

    def test_the_private_reader_takes_only_a_directory_fd(self, anchored) -> None:
        import inspect

        assert set(
            inspect.signature(anchored._read_migration_receipt).parameters
        ) == {"store_dir_fd"}

    def test_the_writer_takes_a_root_and_an_on_link_hook(self, anchored) -> None:
        import inspect

        params = inspect.signature(anchored.write_private_file).parameters
        assert set(params) == {"relative", "data", "root", "on_link"}

    def test_the_reader_requires_an_expected_uid(self, anchored) -> None:
        import inspect

        params = inspect.signature(anchored.read_private_file).parameters
        assert set(params) == {"relative", "root", "expected_uid"}

    def test_no_production_route_accepts_a_path(self, anchored) -> None:
        """A generic reader with a root lets a caller point activation at a
        receipt beside a DIFFERENT store."""
        import inspect

        source = inspect.getsource(anchored.read_migration_receipt)
        assert "root=" not in source


class TestPermissionsAndLinkage:
    def test_the_written_file_is_exactly_0600(self, anchored, tmp_path: Path) -> None:
        """Owner-only is not enough: 0640 and 0644 are owner-only for WRITE
        while still readable by a group or the world."""
        _write(anchored, tmp_path)
        mode = stat_module.S_IMODE(os.stat(tmp_path / RECEIPT_NAME).st_mode)
        assert mode == 0o600, oct(mode)

    def test_the_written_file_is_owned_by_this_user(self, anchored, tmp_path: Path) -> None:
        _write(anchored, tmp_path)
        assert os.stat(tmp_path / RECEIPT_NAME).st_uid == os.getuid()

    def test_the_written_file_has_exactly_one_link(self, anchored, tmp_path: Path) -> None:
        """A second name for the file is a second way to replace it."""
        _write(anchored, tmp_path)
        assert os.stat(tmp_path / RECEIPT_NAME).st_nlink == 1

    def test_it_is_a_regular_file(self, anchored, tmp_path: Path) -> None:
        _write(anchored, tmp_path)
        assert stat_module.S_ISREG(os.stat(tmp_path / RECEIPT_NAME).st_mode)


class TestExclusiveCreate:
    """The winner links; the loser must fail and re-read."""

    def test_a_second_write_refuses_rather_than_replacing(self, anchored, tmp_path: Path) -> None:
        _write(anchored, tmp_path, data=b'{"first":1}')
        with pytest.raises(FileExistsError):
            _write(anchored, tmp_path, data=b'{"second":2}')

    def test_the_loser_leaves_the_winners_bytes_intact(self, anchored, tmp_path: Path) -> None:
        _write(anchored, tmp_path, data=b'{"first":1}')
        with pytest.raises(FileExistsError):
            _write(anchored, tmp_path, data=b'{"second":2}')
        assert (tmp_path / RECEIPT_NAME).read_bytes() == b'{"first":1}'

    def test_the_on_link_hook_observes_the_race(self, anchored, tmp_path: Path) -> None:
        """A competitor publishing between this writer's O_TMPFILE and its
        link must make the link fail -- not silently win."""
        raced: dict[str, bool] = {}

        def publish_a_competitor():
            raced["ran"] = True
            (tmp_path / RECEIPT_NAME).write_bytes(b'{"competitor":1}')
            os.chmod(tmp_path / RECEIPT_NAME, 0o600)

        with pytest.raises(FileExistsError):
            anchored.write_private_file(
                RECEIPT_NAME, b'{"mine":1}', root=tmp_path,
                on_link=publish_a_competitor,
            )
        assert raced.get("ran") is True, "the hook never fired; no race occurred"
        assert (tmp_path / RECEIPT_NAME).read_bytes() == b'{"competitor":1}'

    def test_no_temp_file_is_left_behind(self, anchored, tmp_path: Path) -> None:
        """O_TMPFILE has no name, so a failed publish must leave the
        directory holding only the winner."""
        _write(anchored, tmp_path)
        with pytest.raises(FileExistsError):
            _write(anchored, tmp_path, data=b'{"second":2}')
        assert sorted(p.name for p in tmp_path.iterdir()) == [RECEIPT_NAME]


class TestReadBoundaries:
    def test_a_file_at_the_cap_is_read(self, anchored, tmp_path: Path) -> None:
        """CONTROL: the cap must admit its own boundary, or the refusal
        below proves only that something smaller than the cap fails."""
        payload = b"x" * SIZE_CAP
        _write(anchored, tmp_path, data=payload)
        assert (
            anchored.read_private_file(
                RECEIPT_NAME, root=tmp_path, expected_uid=os.getuid()
            )
            == payload
        )

    def test_one_byte_over_the_cap_refuses(self, anchored, tmp_path: Path) -> None:
        """A bounded read; without it a hostile receipt exhausts memory
        before any validation runs."""
        (tmp_path / RECEIPT_NAME).write_bytes(b"x" * (SIZE_CAP + 1))
        os.chmod(tmp_path / RECEIPT_NAME, 0o600)
        with pytest.raises(ValueError):
            anchored.read_private_file(
                RECEIPT_NAME, root=tmp_path, expected_uid=os.getuid()
            )

    def test_a_short_read_is_completed_not_truncated(
        self, anchored, tmp_path: Path, monkeypatch
    ) -> None:
        """os.read may return fewer bytes than asked. Treating the first
        chunk as the whole file silently truncates the receipt."""
        payload = b"y" * 4096
        _write(anchored, tmp_path, data=payload)
        real_read = os.read

        def dribble(fd, size):
            return real_read(fd, min(size, 17))

        monkeypatch.setattr(os, "read", dribble)
        assert (
            anchored.read_private_file(
                RECEIPT_NAME, root=tmp_path, expected_uid=os.getuid()
            )
            == payload
        )

    def test_a_foreign_owner_refuses(self, anchored, tmp_path: Path) -> None:
        _write(anchored, tmp_path)
        with pytest.raises(PermissionError):
            anchored.read_private_file(
                RECEIPT_NAME, root=tmp_path, expected_uid=os.getuid() + 1
            )


class TestNoFollowAndStatStability:
    def test_a_symlinked_target_refuses(self, anchored, tmp_path: Path) -> None:
        """The planted file is 0600 on purpose: at 0644 the read refuses on
        MODE before ever reaching the no-follow check, and the test passes
        for the wrong reason."""
        elsewhere = tmp_path / "elsewhere.json"
        elsewhere.write_bytes(b'{"foreign":1}')
        os.chmod(elsewhere, 0o600)
        (tmp_path / RECEIPT_NAME).symlink_to(elsewhere)
        with pytest.raises(OSError):
            anchored.read_private_file(
                RECEIPT_NAME, root=tmp_path, expected_uid=os.getuid()
            )

    def test_a_symlinked_root_component_refuses(self, anchored, tmp_path: Path) -> None:
        real = tmp_path / "real"
        real.mkdir()
        _write(anchored, real)
        link = tmp_path / "via_link"
        link.symlink_to(real)
        with pytest.raises(OSError):
            anchored.read_private_file(
                RECEIPT_NAME, root=link, expected_uid=os.getuid()
            )

    def test_the_writer_refuses_a_symlinked_root(
        self, anchored, tmp_path: Path
    ) -> None:
        """The reader's no-follow is only half of it: a writer that resolves
        a symlinked root publishes the receipt into another directory."""
        real = tmp_path / "real"
        real.mkdir()
        link = tmp_path / "via_link"
        link.symlink_to(real)
        with pytest.raises(OSError):
            anchored.write_private_file(RECEIPT_NAME, b"{}", root=link)

    def test_a_fifo_refuses(self, anchored, tmp_path: Path) -> None:
        """A non-regular file can block the reader forever."""
        os.mkfifo(tmp_path / RECEIPT_NAME, 0o600)
        with pytest.raises(OSError):
            anchored.read_private_file(
                RECEIPT_NAME, root=tmp_path, expected_uid=os.getuid()
            )

    def test_the_stat_is_taken_from_the_open_descriptor(self, anchored, tmp_path: Path) -> None:
        """Stat-by-path after opening is a TOCTOU: the name can be replaced
        between the two. The identity must come from the held fd."""
        import ast
        import inspect

        tree = ast.parse(inspect.getsource(anchored.read_private_file))
        calls = {
            ast.unparse(node.func)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        }
        assert "os.fstat" in calls, calls
        assert "os.stat" not in calls, calls


class TestWriteOrderingAndCompleteness:
    """O_TMPFILE -> write ALL -> fsync file -> link -> fsync parent."""

    def _events(self, monkeypatch):
        log: list[tuple[str, str]] = []
        real_fsync, real_link, real_write = os.fsync, os.link, os.write

        def fsync(fd):
            st = os.fstat(fd)
            kind = "dir" if stat_module.S_ISDIR(st.st_mode) else "file"
            log.append(("fsync", kind))
            return real_fsync(fd)

        def link(src, dst, **kw):
            log.append(("link", str(dst)))
            return real_link(src, dst, **kw)

        def write(fd, data):
            log.append(("write", str(len(data))))
            return real_write(fd, data)

        monkeypatch.setattr(os, "fsync", fsync)
        monkeypatch.setattr(os, "link", link)
        monkeypatch.setattr(os, "write", write)
        return log

    def test_the_file_is_fsynced_before_the_link(
        self, anchored, tmp_path: Path, monkeypatch
    ) -> None:
        log = self._events(monkeypatch)
        _write(anchored, tmp_path, data=b'{"a":1}')
        kinds = [f"{k}:{v}" for k, v in log]
        assert "fsync:file" in kinds, kinds
        assert kinds.index("fsync:file") < next(
            i for i, x in enumerate(kinds) if x.startswith("link:")
        ), kinds

    def test_the_parent_is_fsynced_after_the_link(
        self, anchored, tmp_path: Path, monkeypatch
    ) -> None:
        """Without it the directory entry itself is not durable, so a crash
        can lose a receipt whose bytes were safely on disk."""
        log = self._events(monkeypatch)
        _write(anchored, tmp_path, data=b'{"a":1}')
        kinds = [f"{k}:{v}" for k, v in log]
        link_at = next(i for i, x in enumerate(kinds) if x.startswith("link:"))
        assert any(
            x == "fsync:dir" for x in kinds[link_at:]
        ), kinds

    def test_a_partial_write_is_completed(
        self, anchored, tmp_path: Path, monkeypatch
    ) -> None:
        """os.write may accept fewer bytes than offered. Writing once and
        assuming completion truncates the receipt silently."""
        real_write = os.write
        monkeypatch.setattr(
            os, "write", lambda fd, data: real_write(fd, data[:13])
        )
        payload = b"z" * 500
        _write(anchored, tmp_path, data=payload)
        assert (tmp_path / RECEIPT_NAME).read_bytes() == payload


class TestReaderSideInvariants:
    @pytest.mark.parametrize("mode", [0o640, 0o644, 0o400, 0o000, 0o700])
    def test_the_reader_requires_exactly_0600(
        self, anchored, tmp_path: Path, mode: int
    ) -> None:
        """Not merely "no group or other bits": 0400 and 0000 also satisfy
        that and are not the mode the writer produces. Anything but 0600
        means something else has touched the file."""
        _write(anchored, tmp_path)
        os.chmod(tmp_path / RECEIPT_NAME, mode)
        with pytest.raises((PermissionError, OSError)):
            anchored.read_private_file(
                RECEIPT_NAME, root=tmp_path, expected_uid=os.getuid()
            )

    def test_the_reader_refuses_a_multiply_linked_file(
        self, anchored, tmp_path: Path
    ) -> None:
        """A second name is a second way to replace the bytes after the
        reader has checked them."""
        _write(anchored, tmp_path)
        os.link(tmp_path / RECEIPT_NAME, tmp_path / "second_name.json")
        with pytest.raises(OSError):
            anchored.read_private_file(
                RECEIPT_NAME, root=tmp_path, expected_uid=os.getuid()
            )

    def test_a_truncated_read_refuses(
        self, anchored, tmp_path: Path, monkeypatch
    ) -> None:
        """EOF before the stat-declared size means the file changed under
        the reader; returning the short bytes would be silent corruption."""
        _write(anchored, tmp_path, data=b"w" * 400)
        real_read = os.read
        state = {"n": 0}

        def truncating(fd, size):
            state["n"] += 1
            return b"" if state["n"] > 1 else real_read(fd, min(size, 40))

        monkeypatch.setattr(os, "read", truncating)
        with pytest.raises(OSError):
            anchored.read_private_file(
                RECEIPT_NAME, root=tmp_path, expected_uid=os.getuid()
            )

    @pytest.mark.parametrize(
        "field", ["st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns"]
    )
    def test_a_stat_change_across_the_read_refuses(
        self, anchored, tmp_path: Path, monkeypatch, field: str
    ) -> None:
        """BEHAVIOURAL, not shape. Counting two adjacent os.fstat calls
        passes on an implementation that makes both and compares neither.
        Each field is mutated between the pre- and post-read stat, and the
        read must refuse."""
        _write(anchored, tmp_path, data=b"m" * 200)
        real_fstat = os.fstat
        calls = {"n": 0}

        class Shifted:
            def __init__(self, base):
                self._base = base

            def __getattr__(self, name):
                value = getattr(self._base, name)
                if name == field:
                    return value + 1
                return value

        def shifting_fstat(fd):
            calls["n"] += 1
            base = real_fstat(fd)
            return Shifted(base) if calls["n"] > 1 else base

        monkeypatch.setattr(os, "fstat", shifting_fstat)
        with pytest.raises((OSError, ValueError)):
            anchored.read_private_file(
                RECEIPT_NAME, root=tmp_path, expected_uid=os.getuid()
            )
        assert calls["n"] >= 2, (
            "the descriptor was stat'd only once, so no comparison is "
            "possible and the refusal above cannot have come from one"
        )

    def test_a_fifo_is_opened_without_blocking(
        self, anchored, tmp_path: Path
    ) -> None:
        """A FIFO with no writer blocks open() forever unless O_NONBLOCK is
        set, so this must refuse rather than hang."""
        import ast
        import inspect

        os.mkfifo(tmp_path / RECEIPT_NAME, 0o600)
        source = inspect.getsource(anchored.read_private_file)
        assert "O_NONBLOCK" in source, (
            "no O_NONBLOCK: opening a FIFO receipt would hang the reader"
        )
        tree = ast.parse(source)
        assert any(
            isinstance(node, ast.Attribute) and node.attr == "O_NOFOLLOW"
            for node in ast.walk(tree)
        )


class TestTheRootIsInescapable:
    """`relative` is a LEAF NAME, not a path the caller may steer.

    Reproduced before these existed: an absolute `relative` made the
    directory fd irrelevant -- openat ignores it entirely -- and `../`
    walked straight out of the anchored root. Both wrote outside it.
    """

    @pytest.mark.parametrize("escape", ["/tmp/escaped.json", "../sibling.json"])
    def test_the_writer_refuses_an_escaping_name(
        self, anchored, tmp_path: Path, escape: str
    ) -> None:
        root = tmp_path / "root"
        root.mkdir()
        with pytest.raises((ValueError, OSError)):
            anchored.write_private_file(escape, b"{}", root=root)

    @pytest.mark.parametrize("escape", ["/tmp/escaped.json", "../sibling.json"])
    def test_the_reader_refuses_an_escaping_name(
        self, anchored, tmp_path: Path, escape: str
    ) -> None:
        root = tmp_path / "root"
        root.mkdir()
        with pytest.raises((ValueError, OSError)):
            anchored.read_private_file(
                escape, root=root, expected_uid=os.getuid()
            )

    def test_nothing_is_written_outside_the_root(
        self, anchored, tmp_path: Path
    ) -> None:
        """The refusal must also not have created the file on its way out."""
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "outside.json"
        with pytest.raises((ValueError, OSError)):
            anchored.write_private_file(str(outside), b"{}", root=root)
        assert not outside.exists()

    def test_a_plain_nested_path_still_works(
        self, anchored, tmp_path: Path
    ) -> None:
        """CONTROL: rejecting every multi-component path would satisfy the
        escapes above while breaking the legitimate nesting the durability
        tests depend on."""
        root = tmp_path / "root"
        (root / "sub").mkdir(parents=True)
        written = anchored.write_private_file("sub/receipt.json", b"{}", root=root)
        assert Path(written).read_bytes() == b"{}"

    def test_an_intermediate_symlink_component_refuses(
        self, anchored, tmp_path: Path
    ) -> None:
        """O_NOFOLLOW on the final component is not enough: a symlinked
        DIRECTORY partway along redirects the whole walk."""
        root = tmp_path / "root"
        (root / "real").mkdir(parents=True)
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        (root / "hop").symlink_to(elsewhere)
        with pytest.raises((ValueError, OSError)):
            anchored.write_private_file("hop/x.json", b"{}", root=root)

    def test_a_plain_leaf_name_still_works(self, anchored, tmp_path: Path) -> None:
        """CONTROL: refusing everything would satisfy every test above."""
        root = tmp_path / "root"
        root.mkdir()
        anchored.write_private_file("plain.json", b'{"a":1}', root=root)
        assert (root / "plain.json").is_file()


class TestZeroProgressWriteFailsFast:
    def test_a_write_returning_zero_raises_instead_of_looping(
        self, anchored, tmp_path: Path, monkeypatch
    ) -> None:
        """Reproduced as a HANG before this test existed: the write-all loop
        never checked for zero progress, so a device accepting nothing spun
        forever holding an open descriptor."""
        monkeypatch.setattr(os, "write", lambda fd, data: 0)
        with pytest.raises(OSError):
            anchored.write_private_file("x.json", b"abc", root=tmp_path)


class TestActivationBindsTheReceiptToItsStore:
    """The ratified contract: the wrapper opens BOTH leaves under the one
    held directory -- ceremony.sqlite3 for its st_dev/st_ino, and the
    receipt for its bytes -- and the receipt's store_dev/store_ino must
    match. A signature-only test cannot show any of that.

    Exercised through the PRIVATE reader against a tmpdir, never the public
    one, which opens the canonical store.
    """

    def _publish(self, anchored, root: Path, *, dev, ino) -> None:
        import json

        (root / "ceremony.sqlite3").write_bytes(b"")
        os.chmod(root / "ceremony.sqlite3", 0o600)
        anchored.write_private_file(
            RECEIPT_NAME,
            json.dumps({"store_dev": dev, "store_ino": ino}).encode(),
            root=root,
        )

    def _read(self, anchored, root: Path) -> bytes:
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            return anchored._read_migration_receipt(store_dir_fd=fd)
        finally:
            os.close(fd)

    def test_a_matching_receipt_is_returned(
        self, anchored, tmp_path: Path
    ) -> None:
        """CONTROL: without it, refusing everything would pass the rest."""
        store = tmp_path / "ceremony.sqlite3"
        store.write_bytes(b"")
        stat = os.stat(store)
        self._publish(anchored, tmp_path, dev=stat.st_dev, ino=stat.st_ino)
        assert self._read(anchored, tmp_path)

    def test_a_foreign_store_ino_refuses(self, anchored, tmp_path: Path) -> None:
        store = tmp_path / "ceremony.sqlite3"
        store.write_bytes(b"")
        stat = os.stat(store)
        self._publish(anchored, tmp_path, dev=stat.st_dev, ino=stat.st_ino + 1)
        with pytest.raises((ValueError, OSError)):
            self._read(anchored, tmp_path)

    def test_a_foreign_store_dev_refuses(self, anchored, tmp_path: Path) -> None:
        store = tmp_path / "ceremony.sqlite3"
        store.write_bytes(b"")
        stat = os.stat(store)
        self._publish(anchored, tmp_path, dev=stat.st_dev + 1, ino=stat.st_ino)
        with pytest.raises((ValueError, OSError)):
            self._read(anchored, tmp_path)

    def test_a_missing_store_refuses(self, anchored, tmp_path: Path) -> None:
        """A receipt with no store beside it binds nothing."""
        anchored.write_private_file(
            RECEIPT_NAME, b'{"store_dev": 1, "store_ino": 1}', root=tmp_path
        )
        with pytest.raises(OSError):
            self._read(anchored, tmp_path)


STORE_NAME = "ceremony.sqlite3"


class TestTheLinkedEntrysOwnDirectoryIsDurable:
    """A directory entry is not durable until the directory HOLDING it is
    fsynced -- and for a nested leaf that is not the root.

    Reproduced at inode level before this: file fsync yes, root-directory
    fsync yes, the actual nested parent's fsync absent. The bytes were
    safe and the name could still vanish after a crash.
    """

    def _fsynced_inodes(self, monkeypatch) -> list[int]:
        seen: list[int] = []
        real_fsync = os.fsync

        def recording(fd):
            try:
                seen.append(os.fstat(fd).st_ino)
            except OSError:  # pragma: no cover
                pass
            return real_fsync(fd)

        monkeypatch.setattr(os, "fsync", recording)
        return seen

    def test_a_nested_leafs_own_directory_is_fsynced(
        self, anchored, tmp_path: Path, monkeypatch
    ) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        seen = self._fsynced_inodes(monkeypatch)
        anchored.write_private_file("sub/receipt.json", b"{}", root=tmp_path)
        monkeypatch.undo()
        assert os.stat(sub).st_ino in seen, (
            "the directory holding the new entry was never fsynced; only "
            "the root was, so the name is not durable"
        )

    def test_the_root_is_still_fsynced_for_a_top_level_leaf(
        self, anchored, tmp_path: Path, monkeypatch
    ) -> None:
        """CONTROL: syncing only the deepest directory would break the
        ordinary un-nested case this primitive mostly serves."""
        seen = self._fsynced_inodes(monkeypatch)
        anchored.write_private_file(RECEIPT_NAME, b"{}", root=tmp_path)
        monkeypatch.undo()
        assert os.stat(tmp_path).st_ino in seen

    def test_the_file_itself_is_still_fsynced(
        self, anchored, tmp_path: Path, monkeypatch
    ) -> None:
        """CONTROL: directory durability must not have replaced data
        durability."""
        sub = tmp_path / "sub"
        sub.mkdir()
        seen = self._fsynced_inodes(monkeypatch)
        published = anchored.write_private_file(
            "sub/receipt.json", b"{}", root=tmp_path
        )
        monkeypatch.undo()
        assert os.stat(published).st_ino in seen
