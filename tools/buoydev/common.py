"""Shared configuration, isolated inputs, and bounded process supervision."""
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time


def parse_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    def constant(value):
        raise ValueError(f"invalid JSON constant: {value}")

    def validate(value, depth=0):
        if depth > 128:
            raise ValueError("JSON nesting exceeds 128")
        if isinstance(value, str) and any(ord(c) == 0 or 0xD800 <= ord(c) <= 0xDFFF for c in value):
            raise ValueError("NUL and unpaired surrogate escapes are not supported")
        if isinstance(value, dict):
            for key, item in value.items():
                validate(key, depth + 1)
                validate(item, depth + 1)
        elif isinstance(value, list):
            for item in value:
                validate(item, depth + 1)
        elif isinstance(value, float) and not math.isfinite(value):
            raise ValueError("JSON numbers must be finite")

    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except RecursionError as error:
        raise ValueError("JSON nesting exceeds parser limit") from error
    validate(value)
    return value


def load_json(path):
    return parse_json(Path(path).read_text(encoding="utf-8"))


def configuration(path):
    path = Path(path).resolve()
    value = load_json(path)
    if not isinstance(value, dict) or type(value.get("schema")) is not int or value["schema"] != 1:
        raise ValueError("developer configuration requires schema: 1")
    return path.parent, value


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = None
    if path.exists():
        if not path.is_file():
            raise ValueError(f"output is not a regular file: {path}")
        mode = path.stat().st_mode & 0o777
        if not mode & 0o222:
            raise ValueError(f"output is read-only: {path}")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content.encode("utf-8"))
            stream.flush()
            if mode is not None:
                os.chmod(temporary, mode)
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def project_path(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"path leaves project: {relative}")
    return path


def expanded_files(root, patterns):
    if not isinstance(patterns, list) or not all(isinstance(p, str) for p in patterns):
        raise ValueError("file patterns must be an array of strings")
    files = set()
    for pattern in patterns:
        if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
            raise ValueError(f"invalid project glob: {pattern}")
        matches = sorted(root.glob(pattern))
        if not matches:
            raise ValueError(f"no files matched: {pattern}")
        for path in matches:
            project_path(root, path.relative_to(root))
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"expected regular file: {path}")
            files.add(path)
    return sorted(files)


def execute(argv, cwd, timeout=90, log_limit=1048576, environment=None, cancel_file=None):
    """Drain separate pipes with bounded storage; kill descendants at deadline.

    POSIX uses a new session/process group. Windows uses taskkill /T /F on
    timeout. Reader threads continue draining after the retained log limit.
    """
    import threading
    if (type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0
            or type(log_limit) is not int or log_limit < 1):
        raise ValueError("timeout and log limit must be positive and finite")
    start = time.monotonic()
    options = {"start_new_session": True} if os.name != "nt" else {
        "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    process = subprocess.Popen([str(a) for a in argv], cwd=cwd, env=environment,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, **options)
    buffers = [bytearray(), bytearray()]
    truncated = [False, False]

    def drain(pipe, index):
        try:
            while chunk := pipe.read(8192):
                remaining = log_limit - len(buffers[index])
                buffers[index].extend(chunk[:max(remaining, 0)])
                if len(chunk) > remaining:
                    truncated[index] = True
        finally:
            pipe.close()

    readers = [threading.Thread(target=drain, args=(pipe, index), daemon=True)
               for index, pipe in enumerate((process.stdout, process.stderr))]
    for reader in readers:
        reader.start()
    deadline = start + timeout
    timed_out = False
    cancelled = False
    try:
        while process.poll() is None or any(reader.is_alive() for reader in readers):
            if cancel_file and Path(cancel_file).exists():
                cancelled = True
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            time.sleep(min(0.01, remaining))
    finally:
        if os.name != "nt":
            # Also clean up descendants when the direct child exits normally.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        elif timed_out or cancelled:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, timeout=10, check=False)
        if process.poll() is None:
            process.kill()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        for reader in readers:
            reader.join(timeout=2)
    result = {"returncode": process.returncode if process.returncode is not None else -1, "timeout": timed_out,
            "stdout": buffers[0].decode("utf-8", errors="replace"),
            "stderr": buffers[1].decode("utf-8", errors="replace"),
            "truncated": any(truncated), "stdout_truncated": truncated[0], "stderr_truncated": truncated[1],
            "seconds": time.monotonic() - start}
    if cancelled:
        result["cancelled"] = True
    return result
