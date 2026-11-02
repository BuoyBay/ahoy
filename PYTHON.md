# Python policy for ahoy

Python files are ignored by default. New production tooling belongs in Buoy or BuoyScript.

The following exact files remain temporary production compatibility exceptions:

| File | Required capability |
| --- | --- |
| `tools/buoy_build.py` | Compatibility entrypoint for Ahoy recipe planning, execution records and cleanup; deployed by the native Ahoy builder. |
| `tools/buoydev/__init__.py` | Package initializer required by the deployed Ahoy recipe helper imports. |
| `tools/buoydev/build.py` | Existing recipe planner, dependency ordering, locking and build receipts; this feature still needs its native engine port. |
| `tools/buoydev/common.py` | Atomic files and bounded subprocess/configuration helpers imported by the existing Ahoy recipe engine. |

An exception may be removed after its native replacement passes the corresponding build or runtime checks.
Review additions file by file; directory-wide and wildcard Python exceptions are not allowed.
