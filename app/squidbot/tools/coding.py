"""Coding agent tools for Zig and Python with workspace support."""

import asyncio
import logging
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Literal

from ..config import DATA_DIR
from .base import Tool

logger = logging.getLogger(__name__)

# Workspace directory
WORKSPACE_DIR = DATA_DIR / "coding"

# Supported languages
Language = Literal["zig", "python"]


def get_workspace() -> Path:
    """Get or create the coding workspace directory."""
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    return WORKSPACE_DIR


def get_project_dir(project_name: str) -> Path:
    """Get project directory within workspace."""
    project_dir = get_workspace() / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


async def run_command(
    cmd: list[str],
    cwd: Path | None = None,
    timeout: int = 30,
) -> tuple[int, str, str]:
    """Run a command asynchronously with timeout."""
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout,
        )
        return (
            process.returncode or 0,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )
    except asyncio.TimeoutError:
        process.kill()
        return -1, "", f"Command timed out after {timeout}s"
    except Exception as e:
        return -1, "", str(e)


class CodeWriteTool(Tool):
    """Write code to a file in the workspace."""

    @property
    def name(self) -> str:
        return "code_write"

    @property
    def description(self) -> str:
        return (
            "Write code to a file in the coding workspace (.squidbot/coding/). "
            "Supports Zig (.zig) and Python (.py) files. "
            "Creates project directories automatically."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project name (creates subdirectory)",
                },
                "filename": {
                    "type": "string",
                    "description": "Filename with extension (.zig or .py)",
                },
                "code": {
                    "type": "string",
                    "description": "The code to write",
                },
            },
            "required": ["project", "filename", "code"],
        }

    async def execute(self, project: str, filename: str, code: str) -> str:
        project_dir = get_project_dir(project)
        file_path = project_dir / filename

        # Validate extension
        ext = file_path.suffix.lower()
        if ext not in (".zig", ".py"):
            return f"Error: Unsupported file type '{ext}'. Use .zig or .py"

        # Write file
        file_path.write_text(code, encoding="utf-8")
        logger.info(f"Wrote {len(code)} bytes to {file_path}")

        # Try to get relative path, fall back to absolute
        try:
            rel_path = file_path.relative_to(DATA_DIR.parent)
            return f"Written to {rel_path}"
        except ValueError:
            return f"Written to {file_path}"


class CodeReadTool(Tool):
    """Read code from a file in the workspace."""

    @property
    def name(self) -> str:
        return "code_read"

    @property
    def description(self) -> str:
        return "Read code from a file in the coding workspace."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project name",
                },
                "filename": {
                    "type": "string",
                    "description": "Filename to read",
                },
            },
            "required": ["project", "filename"],
        }

    async def execute(self, project: str, filename: str) -> str:
        project_dir = get_project_dir(project)
        file_path = project_dir / filename

        if not file_path.exists():
            return f"Error: File not found: {filename}"

        code = file_path.read_text(encoding="utf-8")
        return f"```{file_path.suffix[1:]}\n{code}\n```"


class CodeRunTool(Tool):
    """Run code in the workspace."""

    @property
    def name(self) -> str:
        return "code_run"

    @property
    def description(self) -> str:
        return (
            "Run code in the workspace. "
            "For Zig: compiles and runs .zig files. "
            "For Python: executes .py files. "
            "Returns stdout, stderr, and exit code."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project name",
                },
                "filename": {
                    "type": "string",
                    "description": "Filename to run",
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Command line arguments (optional)",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default 30)",
                    "default": 30,
                },
            },
            "required": ["project", "filename"],
        }

    async def execute(
        self,
        project: str,
        filename: str,
        args: list[str] | None = None,
        timeout: int = 30,
    ) -> str:
        project_dir = get_project_dir(project)
        file_path = project_dir / filename
        args = args or []

        if not file_path.exists():
            return f"Error: File not found: {filename}"

        ext = file_path.suffix.lower()

        if ext == ".zig":
            return await self._run_zig(file_path, project_dir, args, timeout)
        elif ext == ".py":
            return await self._run_python(file_path, args, timeout)
        else:
            return f"Error: Cannot run '{ext}' files. Use .zig or .py"

    async def _run_zig(
        self,
        file_path: Path,
        project_dir: Path,
        args: list[str],
        timeout: int,
    ) -> str:
        # Check if zig is available
        zig_path = shutil.which("zig")
        if not zig_path:
            return "Error: Zig compiler not found. Please install Zig."

        # Compile and run
        cmd = ["zig", "run", str(file_path)] + args
        code, stdout, stderr = await run_command(cmd, cwd=project_dir, timeout=timeout)

        result = []
        if stdout:
            result.append(f"stdout:\n{stdout}")
        if stderr:
            result.append(f"stderr:\n{stderr}")
        result.append(f"exit code: {code}")

        return "\n".join(result) if result else "No output"

    async def _run_python(
        self,
        file_path: Path,
        args: list[str],
        timeout: int,
    ) -> str:
        # Use same Python interpreter
        import sys

        cmd = [sys.executable, str(file_path)] + args
        code, stdout, stderr = await run_command(
            cmd, cwd=file_path.parent, timeout=timeout
        )

        result = []
        if stdout:
            result.append(f"stdout:\n{stdout}")
        if stderr:
            result.append(f"stderr:\n{stderr}")
        result.append(f"exit code: {code}")

        return "\n".join(result) if result else "No output"


class CodeListTool(Tool):
    """List files in a project."""

    @property
    def name(self) -> str:
        return "code_list"

    @property
    def description(self) -> str:
        return "List files in a project or all projects in the workspace."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project name (optional, lists all projects if omitted)",
                },
            },
            "required": [],
        }

    async def execute(self, project: str | None = None) -> str:
        workspace = get_workspace()

        if project:
            project_dir = workspace / project
            if not project_dir.exists():
                return f"Project '{project}' not found"

            files = sorted(project_dir.rglob("*"))
            if not files:
                return f"Project '{project}' is empty"

            lines = [f"Files in {project}:"]
            for f in files:
                if f.is_file():
                    rel = f.relative_to(project_dir)
                    size = f.stat().st_size
                    lines.append(f"  {rel} ({size} bytes)")
            return "\n".join(lines)
        else:
            # List all projects
            projects = sorted([d for d in workspace.iterdir() if d.is_dir()])
            if not projects:
                return "No projects in workspace"

            lines = ["Projects:"]
            for p in projects:
                file_count = len(list(p.rglob("*")))
                lines.append(f"  {p.name}/ ({file_count} files)")
            return "\n".join(lines)


class CodeDeleteTool(Tool):
    """Delete a file or project."""

    @property
    def name(self) -> str:
        return "code_delete"

    @property
    def description(self) -> str:
        return "Delete a file or entire project from the workspace."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project name",
                },
                "filename": {
                    "type": "string",
                    "description": "Filename to delete (omit to delete entire project)",
                },
            },
            "required": ["project"],
        }

    async def execute(self, project: str, filename: str | None = None) -> str:
        workspace = get_workspace()
        project_dir = workspace / project

        if not project_dir.exists():
            return f"Project '{project}' not found"

        if filename:
            file_path = project_dir / filename
            if not file_path.exists():
                return f"File '{filename}' not found in {project}"
            file_path.unlink()
            return f"Deleted {filename} from {project}"
        else:
            shutil.rmtree(project_dir)
            return f"Deleted project '{project}'"


class ZigBuildTool(Tool):
    """Build a Zig project."""

    @property
    def name(self) -> str:
        return "zig_build"

    @property
    def description(self) -> str:
        return (
            "Build a Zig project. Can create optimized release builds. "
            "For single files, compiles to executable. "
            "For projects with build.zig, runs 'zig build'."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project name",
                },
                "filename": {
                    "type": "string",
                    "description": "Main .zig file (optional if build.zig exists)",
                },
                "release": {
                    "type": "boolean",
                    "description": "Build optimized release (default false)",
                    "default": False,
                },
                "output": {
                    "type": "string",
                    "description": "Output executable name (optional)",
                },
            },
            "required": ["project"],
        }

    async def execute(
        self,
        project: str,
        filename: str | None = None,
        release: bool = False,
        output: str | None = None,
    ) -> str:
        project_dir = get_project_dir(project)

        # Check if zig is available
        zig_path = shutil.which("zig")
        if not zig_path:
            return "Error: Zig compiler not found. Please install Zig."

        build_zig = project_dir / "build.zig"

        if build_zig.exists():
            # Use build.zig
            cmd = ["zig", "build"]
            if release:
                cmd.append("-Doptimize=ReleaseFast")
        elif filename:
            # Single file build
            file_path = project_dir / filename
            if not file_path.exists():
                return f"Error: File not found: {filename}"

            out_name = output or file_path.stem
            cmd = ["zig", "build-exe", str(file_path), f"-femit-bin={out_name}"]
            if release:
                cmd.append("-O")
                cmd.append("ReleaseFast")
        else:
            return "Error: No build.zig found and no filename specified"

        code, stdout, stderr = await run_command(cmd, cwd=project_dir, timeout=120)

        result = []
        if stdout:
            result.append(f"stdout:\n{stdout}")
        if stderr:
            result.append(f"stderr:\n{stderr}")

        if code == 0:
            result.append("Build successful!")
        else:
            result.append(f"Build failed (exit code: {code})")

        return "\n".join(result)


class ZigTestTool(Tool):
    """Run Zig tests."""

    @property
    def name(self) -> str:
        return "zig_test"

    @property
    def description(self) -> str:
        return "Run Zig tests in a file or project."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project name",
                },
                "filename": {
                    "type": "string",
                    "description": ".zig file with tests (optional if build.zig exists)",
                },
            },
            "required": ["project"],
        }

    async def execute(self, project: str, filename: str | None = None) -> str:
        project_dir = get_project_dir(project)

        zig_path = shutil.which("zig")
        if not zig_path:
            return "Error: Zig compiler not found. Please install Zig."

        build_zig = project_dir / "build.zig"

        if build_zig.exists() and not filename:
            cmd = ["zig", "build", "test"]
        elif filename:
            file_path = project_dir / filename
            if not file_path.exists():
                return f"Error: File not found: {filename}"
            cmd = ["zig", "test", str(file_path)]
        else:
            return "Error: No build.zig found and no filename specified"

        code, stdout, stderr = await run_command(cmd, cwd=project_dir, timeout=60)

        result = []
        if stdout:
            result.append(stdout)
        if stderr:
            result.append(stderr)

        if code == 0:
            result.append("All tests passed!")
        else:
            result.append(f"Tests failed (exit code: {code})")

        return "\n".join(result)


class PythonTestTool(Tool):
    """Run Python tests with pytest."""

    @property
    def name(self) -> str:
        return "python_test"

    @property
    def description(self) -> str:
        return "Run Python tests with pytest in a project."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project name",
                },
                "filename": {
                    "type": "string",
                    "description": "Specific test file (optional)",
                },
            },
            "required": ["project"],
        }

    async def execute(self, project: str, filename: str | None = None) -> str:
        import sys

        project_dir = get_project_dir(project)

        cmd = [sys.executable, "-m", "pytest", "-v"]
        if filename:
            file_path = project_dir / filename
            if not file_path.exists():
                return f"Error: File not found: {filename}"
            cmd.append(str(file_path))
        else:
            cmd.append(str(project_dir))

        code, stdout, stderr = await run_command(cmd, cwd=project_dir, timeout=120)

        result = []
        if stdout:
            result.append(stdout)
        if stderr:
            result.append(stderr)

        return "\n".join(result) if result else "No test output"


# Export all coding tools
def get_coding_tools() -> list[Tool]:
    """Get all coding agent tools."""
    return [
        CodeWriteTool(),
        CodeReadTool(),
        CodeRunTool(),
        CodeListTool(),
        CodeDeleteTool(),
        ZigBuildTool(),
        ZigTestTool(),
        PythonTestTool(),
    ]
