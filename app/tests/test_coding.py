"""Tests for coding agent tools (Zig + Python)."""

import shutil
import tempfile
from pathlib import Path

import pytest

from tools.coding import (CodeDeleteTool, CodeListTool, CodeReadTool,
                          CodeRunTool, CodeWriteTool, PythonTestTool,
                          ZigBuildTool, ZigTestTool, get_coding_tools,
                          get_workspace)


@pytest.fixture
def temp_workspace(monkeypatch, tmp_path):
    """Use temporary workspace for tests."""
    workspace = tmp_path / "coding"
    workspace.mkdir()
    monkeypatch.setattr("tools.coding.WORKSPACE_DIR", workspace)
    return workspace


class TestCodeWriteTool:
    """Test CodeWriteTool."""

    @pytest.fixture
    def tool(self):
        return CodeWriteTool()

    async def test_write_python_file(self, tool, temp_workspace):
        """Test writing a Python file."""
        result = await tool.execute(
            project="test_project",
            filename="hello.py",
            code='print("Hello, World!")',
        )

        assert "Written to" in result
        file_path = temp_workspace / "test_project" / "hello.py"
        assert file_path.exists()
        assert file_path.read_text() == 'print("Hello, World!")'

    async def test_write_zig_file(self, tool, temp_workspace):
        """Test writing a Zig file."""
        code = """
const std = @import("std");

pub fn main() void {
    std.debug.print("Hello, Zig!", .{});
}
"""
        result = await tool.execute(
            project="zig_project",
            filename="main.zig",
            code=code,
        )

        assert "Written to" in result
        file_path = temp_workspace / "zig_project" / "main.zig"
        assert file_path.exists()

    async def test_reject_unsupported_extension(self, tool, temp_workspace):
        """Test that unsupported extensions are rejected."""
        result = await tool.execute(
            project="test",
            filename="script.js",
            code="console.log('hi')",
        )

        assert "Error" in result
        assert "Unsupported" in result


class TestCodeReadTool:
    """Test CodeReadTool."""

    @pytest.fixture
    def tool(self):
        return CodeReadTool()

    async def test_read_existing_file(self, tool, temp_workspace):
        """Test reading an existing file."""
        # Create file first
        project_dir = temp_workspace / "project"
        project_dir.mkdir()
        (project_dir / "test.py").write_text("x = 42")

        result = await tool.execute(project="project", filename="test.py")

        assert "x = 42" in result
        assert "```py" in result

    async def test_read_nonexistent_file(self, tool, temp_workspace):
        """Test reading a nonexistent file."""
        result = await tool.execute(project="project", filename="missing.py")

        assert "Error" in result
        assert "not found" in result


class TestCodeRunTool:
    """Test CodeRunTool."""

    @pytest.fixture
    def tool(self):
        return CodeRunTool()

    async def test_run_python(self, tool, temp_workspace):
        """Test running Python code."""
        # Create file
        project_dir = temp_workspace / "project"
        project_dir.mkdir()
        (project_dir / "hello.py").write_text('print("Hello from Python!")')

        result = await tool.execute(project="project", filename="hello.py")

        assert "Hello from Python!" in result
        assert "exit code: 0" in result

    async def test_run_python_with_args(self, tool, temp_workspace):
        """Test running Python with arguments."""
        project_dir = temp_workspace / "project"
        project_dir.mkdir()
        (project_dir / "args.py").write_text(
            "import sys\nprint(f'Args: {sys.argv[1:]}')"
        )

        result = await tool.execute(
            project="project",
            filename="args.py",
            args=["hello", "world"],
        )

        assert "hello" in result
        assert "world" in result

    async def test_run_python_with_error(self, tool, temp_workspace):
        """Test running Python with runtime error."""
        project_dir = temp_workspace / "project"
        project_dir.mkdir()
        (project_dir / "error.py").write_text("raise ValueError('test error')")

        result = await tool.execute(project="project", filename="error.py")

        assert "exit code:" in result
        assert "0" not in result.split("exit code:")[-1]

    @pytest.mark.skipif(not shutil.which("zig"), reason="Zig not installed")
    async def test_run_zig(self, tool, temp_workspace):
        """Test running Zig code."""
        project_dir = temp_workspace / "zig_project"
        project_dir.mkdir()
        (project_dir / "hello.zig").write_text("""
const std = @import("std");

pub fn main() void {
    std.debug.print("Hello from Zig!\\n", .{});
}
""")

        result = await tool.execute(project="zig_project", filename="hello.zig")

        assert "Hello from Zig!" in result


class TestCodeListTool:
    """Test CodeListTool."""

    @pytest.fixture
    def tool(self):
        return CodeListTool()

    async def test_list_projects(self, tool, temp_workspace):
        """Test listing all projects."""
        (temp_workspace / "project1").mkdir()
        (temp_workspace / "project2").mkdir()
        (temp_workspace / "project1" / "file.py").write_text("")

        result = await tool.execute()

        assert "Projects:" in result
        assert "project1" in result
        assert "project2" in result

    async def test_list_project_files(self, tool, temp_workspace):
        """Test listing files in a project."""
        project_dir = temp_workspace / "myproject"
        project_dir.mkdir()
        (project_dir / "main.py").write_text("x = 1")
        (project_dir / "utils.py").write_text("y = 2")

        result = await tool.execute(project="myproject")

        assert "main.py" in result
        assert "utils.py" in result

    async def test_list_empty_workspace(self, tool, temp_workspace):
        """Test listing empty workspace."""
        result = await tool.execute()

        assert "No projects" in result


class TestCodeDeleteTool:
    """Test CodeDeleteTool."""

    @pytest.fixture
    def tool(self):
        return CodeDeleteTool()

    async def test_delete_file(self, tool, temp_workspace):
        """Test deleting a file."""
        project_dir = temp_workspace / "project"
        project_dir.mkdir()
        file_path = project_dir / "test.py"
        file_path.write_text("delete me")

        result = await tool.execute(project="project", filename="test.py")

        assert "Deleted" in result
        assert not file_path.exists()

    async def test_delete_project(self, tool, temp_workspace):
        """Test deleting entire project."""
        project_dir = temp_workspace / "project"
        project_dir.mkdir()
        (project_dir / "file.py").write_text("")

        result = await tool.execute(project="project")

        assert "Deleted project" in result
        assert not project_dir.exists()


class TestZigBuildTool:
    """Test ZigBuildTool."""

    @pytest.fixture
    def tool(self):
        return ZigBuildTool()

    @pytest.mark.skipif(not shutil.which("zig"), reason="Zig not installed")
    async def test_build_single_file(self, tool, temp_workspace):
        """Test building a single Zig file."""
        project_dir = temp_workspace / "project"
        project_dir.mkdir()
        (project_dir / "main.zig").write_text("""
const std = @import("std");

pub fn main() void {
    std.debug.print("Built!", .{});
}
""")

        result = await tool.execute(project="project", filename="main.zig")

        assert "successful" in result.lower() or "error" not in result.lower()

    async def test_build_no_zig(self, tool, temp_workspace, monkeypatch):
        """Test error when Zig not installed."""
        monkeypatch.setattr(shutil, "which", lambda x: None)

        result = await tool.execute(project="project", filename="main.zig")

        assert "Error" in result
        assert "not found" in result


class TestZigTestTool:
    """Test ZigTestTool."""

    @pytest.fixture
    def tool(self):
        return ZigTestTool()

    @pytest.mark.skipif(not shutil.which("zig"), reason="Zig not installed")
    async def test_run_zig_tests(self, tool, temp_workspace):
        """Test running Zig tests."""
        project_dir = temp_workspace / "project"
        project_dir.mkdir()
        (project_dir / "test.zig").write_text("""
const std = @import("std");
const expect = std.testing.expect;

test "simple test" {
    try expect(1 + 1 == 2);
}
""")

        result = await tool.execute(project="project", filename="test.zig")

        # Should either pass or show test output
        assert "test" in result.lower() or "passed" in result.lower()


class TestPythonTestTool:
    """Test PythonTestTool."""

    @pytest.fixture
    def tool(self):
        return PythonTestTool()

    async def test_run_pytest(self, tool, temp_workspace):
        """Test running pytest."""
        project_dir = temp_workspace / "project"
        project_dir.mkdir()
        (project_dir / "test_example.py").write_text("""
def test_addition():
    assert 1 + 1 == 2

def test_subtraction():
    assert 5 - 3 == 2
""")

        result = await tool.execute(project="project")

        assert "passed" in result.lower()


class TestGetCodingTools:
    """Test get_coding_tools function."""

    def test_returns_all_tools(self):
        """Test that all coding tools are returned."""
        tools = get_coding_tools()

        assert len(tools) == 8
        names = [t.name for t in tools]
        assert "code_write" in names
        assert "code_read" in names
        assert "code_run" in names
        assert "code_list" in names
        assert "code_delete" in names
        assert "zig_build" in names
        assert "zig_test" in names
        assert "python_test" in names


# =============================================================================
# UNIT TESTS - Edge Cases and Validation
# =============================================================================


class TestCodeWriteEdgeCases:
    """Unit tests for CodeWriteTool edge cases."""

    @pytest.fixture
    def tool(self):
        return CodeWriteTool()

    async def test_write_empty_file(self, tool, temp_workspace):
        """Test writing an empty file."""
        result = await tool.execute(project="test", filename="empty.py", code="")
        assert "Written to" in result
        file_path = temp_workspace / "test" / "empty.py"
        assert file_path.exists()
        assert file_path.read_text() == ""

    async def test_write_unicode_content(self, tool, temp_workspace):
        """Test writing unicode content."""
        code = '# 한글 주석\nprint("Hello 世界 🌍")'
        result = await tool.execute(project="unicode", filename="hello.py", code=code)
        assert "Written to" in result
        file_path = temp_workspace / "unicode" / "hello.py"
        assert file_path.read_text() == code

    async def test_write_large_file(self, tool, temp_workspace):
        """Test writing a large file."""
        code = "x = 1\n" * 10000  # 60KB+
        result = await tool.execute(project="large", filename="big.py", code=code)
        assert "Written to" in result
        file_path = temp_workspace / "large" / "big.py"
        assert file_path.stat().st_size > 50000

    async def test_overwrite_existing_file(self, tool, temp_workspace):
        """Test overwriting an existing file."""
        project_dir = temp_workspace / "overwrite"
        project_dir.mkdir()
        (project_dir / "file.py").write_text("old content")

        result = await tool.execute(
            project="overwrite", filename="file.py", code="new content"
        )
        assert "Written to" in result
        assert (project_dir / "file.py").read_text() == "new content"

    async def test_write_nested_directory(self, tool, temp_workspace):
        """Test writing to nested directory path."""
        result = await tool.execute(
            project="nested/sub/dir", filename="file.py", code="x = 1"
        )
        assert "Written to" in result
        file_path = temp_workspace / "nested/sub/dir" / "file.py"
        assert file_path.exists()

    async def test_reject_shell_extension(self, tool, temp_workspace):
        """Test rejection of shell scripts."""
        result = await tool.execute(
            project="test", filename="script.sh", code="echo hi"
        )
        assert "Error" in result
        assert "Unsupported" in result

    async def test_reject_binary_extension(self, tool, temp_workspace):
        """Test rejection of binary files."""
        result = await tool.execute(project="test", filename="data.bin", code="bytes")
        assert "Error" in result

    async def test_write_with_special_chars_in_project(self, tool, temp_workspace):
        """Test project name with special characters."""
        result = await tool.execute(
            project="my-project_v2", filename="main.py", code="x = 1"
        )
        assert "Written to" in result


class TestCodeReadEdgeCases:
    """Unit tests for CodeReadTool edge cases."""

    @pytest.fixture
    def tool(self):
        return CodeReadTool()

    async def test_read_empty_file(self, tool, temp_workspace):
        """Test reading an empty file."""
        project_dir = temp_workspace / "project"
        project_dir.mkdir()
        (project_dir / "empty.py").write_text("")

        result = await tool.execute(project="project", filename="empty.py")
        assert "```py" in result

    async def test_read_unicode_file(self, tool, temp_workspace):
        """Test reading unicode content."""
        project_dir = temp_workspace / "project"
        project_dir.mkdir()
        (project_dir / "unicode.py").write_text('print("世界")')

        result = await tool.execute(project="project", filename="unicode.py")
        assert "世界" in result

    async def test_read_zig_file_syntax(self, tool, temp_workspace):
        """Test reading Zig file returns correct syntax hint."""
        project_dir = temp_workspace / "project"
        project_dir.mkdir()
        (project_dir / "main.zig").write_text("const x = 1;")

        result = await tool.execute(project="project", filename="main.zig")
        assert "```zig" in result

    async def test_read_nonexistent_project(self, tool, temp_workspace):
        """Test reading from nonexistent project."""
        result = await tool.execute(project="nonexistent", filename="file.py")
        assert "Error" in result


class TestCodeRunEdgeCases:
    """Unit tests for CodeRunTool edge cases."""

    @pytest.fixture
    def tool(self):
        return CodeRunTool()

    async def test_run_nonexistent_file(self, tool, temp_workspace):
        """Test running a nonexistent file."""
        project_dir = temp_workspace / "project"
        project_dir.mkdir()

        result = await tool.execute(project="project", filename="missing.py")
        assert "Error" in result
        assert "not found" in result

    async def test_run_unsupported_extension(self, tool, temp_workspace):
        """Test running unsupported file type."""
        project_dir = temp_workspace / "project"
        project_dir.mkdir()
        (project_dir / "script.rb").write_text("puts 'hi'")

        result = await tool.execute(project="project", filename="script.rb")
        assert "Error" in result
        assert "Cannot run" in result

    async def test_run_python_syntax_error(self, tool, temp_workspace):
        """Test running Python with syntax error."""
        project_dir = temp_workspace / "project"
        project_dir.mkdir()
        (project_dir / "bad.py").write_text("def broken(")

        result = await tool.execute(project="project", filename="bad.py")
        assert "exit code:" in result
        # Should have non-zero exit code
        assert "SyntaxError" in result or "exit code: 1" in result

    async def test_run_python_with_stdin(self, tool, temp_workspace):
        """Test Python script that doesn't wait for input."""
        project_dir = temp_workspace / "project"
        project_dir.mkdir()
        (project_dir / "quick.py").write_text("print('done')")

        result = await tool.execute(project="project", filename="quick.py", timeout=5)
        assert "done" in result
        assert "exit code: 0" in result

    async def test_run_python_imports(self, tool, temp_workspace):
        """Test Python with standard library imports."""
        project_dir = temp_workspace / "project"
        project_dir.mkdir()
        (project_dir / "imports.py").write_text(
            "import json\nimport os\nprint(json.dumps({'status': 'ok'}))"
        )

        result = await tool.execute(project="project", filename="imports.py")
        assert "ok" in result
        assert "exit code: 0" in result

    @pytest.mark.skipif(not shutil.which("zig"), reason="Zig not installed")
    async def test_run_zig_compile_error(self, tool, temp_workspace):
        """Test running Zig with compile error."""
        project_dir = temp_workspace / "project"
        project_dir.mkdir()
        (project_dir / "bad.zig").write_text("const x = undefined_var;")

        result = await tool.execute(project="project", filename="bad.zig")
        # Should fail with compile error
        assert "error" in result.lower()


class TestCodeListEdgeCases:
    """Unit tests for CodeListTool edge cases."""

    @pytest.fixture
    def tool(self):
        return CodeListTool()

    async def test_list_nonexistent_project(self, tool, temp_workspace):
        """Test listing nonexistent project."""
        result = await tool.execute(project="nonexistent")
        assert "not found" in result

    async def test_list_empty_project(self, tool, temp_workspace):
        """Test listing empty project."""
        project_dir = temp_workspace / "empty_project"
        project_dir.mkdir()

        result = await tool.execute(project="empty_project")
        assert "empty" in result.lower()

    async def test_list_shows_file_sizes(self, tool, temp_workspace):
        """Test that listing shows file sizes."""
        project_dir = temp_workspace / "project"
        project_dir.mkdir()
        (project_dir / "small.py").write_text("x = 1")
        (project_dir / "bigger.py").write_text("x = 1\n" * 100)

        result = await tool.execute(project="project")
        assert "bytes" in result

    async def test_list_nested_files(self, tool, temp_workspace):
        """Test listing nested directory structure."""
        project_dir = temp_workspace / "nested"
        project_dir.mkdir()
        (project_dir / "src").mkdir()
        (project_dir / "src" / "main.py").write_text("")
        (project_dir / "tests").mkdir()
        (project_dir / "tests" / "test_main.py").write_text("")

        result = await tool.execute(project="nested")
        assert "main.py" in result
        assert "test_main.py" in result


class TestCodeDeleteEdgeCases:
    """Unit tests for CodeDeleteTool edge cases."""

    @pytest.fixture
    def tool(self):
        return CodeDeleteTool()

    async def test_delete_nonexistent_file(self, tool, temp_workspace):
        """Test deleting a nonexistent file."""
        project_dir = temp_workspace / "project"
        project_dir.mkdir()

        result = await tool.execute(project="project", filename="missing.py")
        assert "not found" in result

    async def test_delete_nonexistent_project(self, tool, temp_workspace):
        """Test deleting a nonexistent project."""
        result = await tool.execute(project="nonexistent")
        assert "not found" in result

    async def test_delete_project_with_files(self, tool, temp_workspace):
        """Test deleting project with multiple files."""
        project_dir = temp_workspace / "project"
        project_dir.mkdir()
        (project_dir / "file1.py").write_text("")
        (project_dir / "file2.py").write_text("")
        (project_dir / "subdir").mkdir()
        (project_dir / "subdir" / "file3.py").write_text("")

        result = await tool.execute(project="project")
        assert "Deleted project" in result
        assert not project_dir.exists()


class TestZigToolsEdgeCases:
    """Unit tests for Zig tools edge cases."""

    @pytest.fixture
    def build_tool(self):
        return ZigBuildTool()

    @pytest.fixture
    def test_tool(self):
        return ZigTestTool()

    async def test_build_no_filename_no_buildzig(self, build_tool, temp_workspace):
        """Test build without filename or build.zig."""
        project_dir = temp_workspace / "project"
        project_dir.mkdir()

        result = await build_tool.execute(project="project")
        assert "Error" in result
        assert "No build.zig" in result

    async def test_test_no_filename_no_buildzig(self, test_tool, temp_workspace):
        """Test running tests without filename or build.zig."""
        project_dir = temp_workspace / "project"
        project_dir.mkdir()

        result = await test_tool.execute(project="project")
        assert "Error" in result

    @pytest.mark.skipif(not shutil.which("zig"), reason="Zig not installed")
    async def test_build_with_release_flag(self, build_tool, temp_workspace):
        """Test building with release optimization."""
        project_dir = temp_workspace / "project"
        project_dir.mkdir()
        (project_dir / "main.zig").write_text("""
const std = @import("std");
pub fn main() void {
    std.debug.print("Release!", .{});
}
""")

        result = await build_tool.execute(
            project="project", filename="main.zig", release=True
        )
        # Should complete (may succeed or fail based on env)
        assert "Build" in result


class TestPythonTestEdgeCases:
    """Unit tests for PythonTestTool edge cases."""

    @pytest.fixture
    def tool(self):
        return PythonTestTool()

    async def test_run_specific_test_file(self, tool, temp_workspace):
        """Test running specific test file."""
        project_dir = temp_workspace / "project"
        project_dir.mkdir()
        (project_dir / "test_one.py").write_text("def test_a(): assert True")
        (project_dir / "test_two.py").write_text("def test_b(): assert False")

        result = await tool.execute(project="project", filename="test_one.py")
        assert "passed" in result.lower()

    async def test_run_failing_tests(self, tool, temp_workspace):
        """Test running failing tests."""
        project_dir = temp_workspace / "project"
        project_dir.mkdir()
        (project_dir / "test_fail.py").write_text("""
def test_will_fail():
    assert 1 == 2, "Expected failure"
""")

        result = await tool.execute(project="project")
        assert "failed" in result.lower() or "FAILED" in result

    async def test_run_tests_no_tests_found(self, tool, temp_workspace):
        """Test running when no tests exist."""
        project_dir = temp_workspace / "project"
        project_dir.mkdir()
        (project_dir / "not_a_test.py").write_text("x = 1")

        result = await tool.execute(project="project")
        # pytest should report no tests
        assert (
            "no tests" in result.lower()
            or "0 passed" in result.lower()
            or "collected 0" in result.lower()
        )


# =============================================================================
# INTEGRATION TESTS - Full Workflows
# =============================================================================


class TestPythonIntegration:
    """Integration tests for Python coding workflow."""

    @pytest.fixture
    def write_tool(self):
        return CodeWriteTool()

    @pytest.fixture
    def read_tool(self):
        return CodeReadTool()

    @pytest.fixture
    def run_tool(self):
        return CodeRunTool()

    @pytest.fixture
    def list_tool(self):
        return CodeListTool()

    @pytest.fixture
    def delete_tool(self):
        return CodeDeleteTool()

    @pytest.fixture
    def test_tool(self):
        return PythonTestTool()

    async def test_write_read_run_workflow(
        self, write_tool, read_tool, run_tool, temp_workspace
    ):
        """Test complete write -> read -> run workflow."""
        # Write
        code = 'print("Integration test passed!")'
        write_result = await write_tool.execute(
            project="integration", filename="main.py", code=code
        )
        assert "Written to" in write_result

        # Read
        read_result = await read_tool.execute(project="integration", filename="main.py")
        assert "Integration test passed!" in read_result

        # Run
        run_result = await run_tool.execute(project="integration", filename="main.py")
        assert "Integration test passed!" in run_result
        assert "exit code: 0" in run_result

    async def test_multi_file_project(
        self, write_tool, run_tool, list_tool, temp_workspace
    ):
        """Test creating and running multi-file project."""
        # Create module
        await write_tool.execute(
            project="multifile",
            filename="utils.py",
            code="""
def greet(name):
    return f"Hello, {name}!"

def add(a, b):
    return a + b
""",
        )

        # Create main that imports module
        await write_tool.execute(
            project="multifile",
            filename="main.py",
            code="""
from utils import greet, add

print(greet("World"))
print(f"Sum: {add(10, 20)}")
""",
        )

        # List files
        list_result = await list_tool.execute(project="multifile")
        assert "utils.py" in list_result
        assert "main.py" in list_result

        # Run main
        run_result = await run_tool.execute(project="multifile", filename="main.py")
        assert "Hello, World!" in run_result
        assert "Sum: 30" in run_result

    async def test_write_test_workflow(self, write_tool, test_tool, temp_workspace):
        """Test writing code and tests, then running tests."""
        # Write module
        await write_tool.execute(
            project="tested",
            filename="calculator.py",
            code="""
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b
""",
        )

        # Write tests
        await write_tool.execute(
            project="tested",
            filename="test_calculator.py",
            code="""
from calculator import add, subtract, multiply

def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0

def test_subtract():
    assert subtract(5, 3) == 2
    assert subtract(0, 5) == -5

def test_multiply():
    assert multiply(3, 4) == 12
    assert multiply(0, 100) == 0
""",
        )

        # Run tests
        test_result = await test_tool.execute(project="tested")
        assert "passed" in test_result.lower()
        assert "3 passed" in test_result

    async def test_create_modify_delete_workflow(
        self, write_tool, read_tool, delete_tool, list_tool, temp_workspace
    ):
        """Test full lifecycle: create -> modify -> delete."""
        # Create
        await write_tool.execute(
            project="lifecycle", filename="app.py", code="version = 1"
        )

        # Verify
        read_result = await read_tool.execute(project="lifecycle", filename="app.py")
        assert "version = 1" in read_result

        # Modify
        await write_tool.execute(
            project="lifecycle", filename="app.py", code="version = 2"
        )
        read_result = await read_tool.execute(project="lifecycle", filename="app.py")
        assert "version = 2" in read_result

        # Delete file
        await delete_tool.execute(project="lifecycle", filename="app.py")
        list_result = await list_tool.execute(project="lifecycle")
        assert "app.py" not in list_result or "empty" in list_result.lower()

    async def test_complex_python_project(
        self, write_tool, run_tool, test_tool, temp_workspace
    ):
        """Test a more complex Python project structure."""
        # Create package structure
        await write_tool.execute(
            project="myapp",
            filename="__init__.py",
            code="",
        )

        await write_tool.execute(
            project="myapp",
            filename="models.py",
            code="""
class User:
    def __init__(self, name, email):
        self.name = name
        self.email = email

    def __repr__(self):
        return f"User({self.name}, {self.email})"

class Product:
    def __init__(self, name, price):
        self.name = name
        self.price = price

    def discounted_price(self, percent):
        return self.price * (1 - percent / 100)
""",
        )

        await write_tool.execute(
            project="myapp",
            filename="main.py",
            code="""
from models import User, Product

user = User("Alice", "alice@example.com")
product = Product("Widget", 100.0)

print(f"User: {user}")
print(f"Product: {product.name} at ${product.price}")
print(f"Discounted: ${product.discounted_price(20):.2f}")
""",
        )

        await write_tool.execute(
            project="myapp",
            filename="test_models.py",
            code="""
from models import User, Product

def test_user_creation():
    user = User("Test", "test@test.com")
    assert user.name == "Test"
    assert user.email == "test@test.com"

def test_product_discount():
    product = Product("Item", 100.0)
    assert product.discounted_price(10) == 90.0
    assert product.discounted_price(50) == 50.0
""",
        )

        # Run main
        run_result = await run_tool.execute(project="myapp", filename="main.py")
        assert "User: User(Alice" in run_result
        assert "Discounted: $80.00" in run_result

        # Run tests
        test_result = await test_tool.execute(project="myapp")
        assert "passed" in test_result.lower()


@pytest.mark.skipif(not shutil.which("zig"), reason="Zig not installed")
class TestZigIntegration:
    """Integration tests for Zig coding workflow."""

    @pytest.fixture
    def write_tool(self):
        return CodeWriteTool()

    @pytest.fixture
    def read_tool(self):
        return CodeReadTool()

    @pytest.fixture
    def run_tool(self):
        return CodeRunTool()

    @pytest.fixture
    def build_tool(self):
        return ZigBuildTool()

    @pytest.fixture
    def test_tool(self):
        return ZigTestTool()

    @pytest.fixture
    def delete_tool(self):
        return CodeDeleteTool()

    async def test_write_read_run_workflow(
        self, write_tool, read_tool, run_tool, temp_workspace
    ):
        """Test complete Zig write -> read -> run workflow."""
        code = """
const std = @import("std");

pub fn main() void {
    std.debug.print("Zig integration test!\\n", .{});
}
"""
        # Write
        write_result = await write_tool.execute(
            project="zig_integration", filename="main.zig", code=code
        )
        assert "Written to" in write_result

        # Read
        read_result = await read_tool.execute(
            project="zig_integration", filename="main.zig"
        )
        assert "Zig integration test!" in read_result
        assert "```zig" in read_result

        # Run
        run_result = await run_tool.execute(
            project="zig_integration", filename="main.zig"
        )
        assert "Zig integration test!" in run_result

    async def test_zig_with_tests(self, write_tool, test_tool, temp_workspace):
        """Test writing Zig code with tests."""
        code = """
const std = @import("std");
const expect = std.testing.expect;

fn add(a: i32, b: i32) i32 {
    return a + b;
}

fn multiply(a: i32, b: i32) i32 {
    return a * b;
}

test "add works" {
    try expect(add(2, 3) == 5);
    try expect(add(-1, 1) == 0);
}

test "multiply works" {
    try expect(multiply(3, 4) == 12);
    try expect(multiply(0, 100) == 0);
}

pub fn main() void {
    std.debug.print("Result: {}\\n", .{add(10, 20)});
}
"""
        await write_tool.execute(project="zig_tested", filename="math.zig", code=code)

        # Run tests
        test_result = await test_tool.execute(project="zig_tested", filename="math.zig")
        assert "passed" in test_result.lower() or "All tests passed" in test_result

    async def test_zig_build_workflow(self, write_tool, build_tool, temp_workspace):
        """Test Zig build workflow."""
        code = """
const std = @import("std");

pub fn main() void {
    std.debug.print("Built successfully!\\n", .{});
}
"""
        await write_tool.execute(project="zig_build", filename="app.zig", code=code)

        # Build
        build_result = await build_tool.execute(project="zig_build", filename="app.zig")
        assert "successful" in build_result.lower() or "Build" in build_result

    async def test_zig_algorithm_implementation(
        self, write_tool, run_tool, test_tool, temp_workspace
    ):
        """Test implementing an algorithm in Zig."""
        code = """
const std = @import("std");
const expect = std.testing.expect;

fn fibonacci(n: u32) u64 {
    if (n <= 1) return n;
    var a: u64 = 0;
    var b: u64 = 1;
    var i: u32 = 2;
    while (i <= n) : (i += 1) {
        const temp = a + b;
        a = b;
        b = temp;
    }
    return b;
}

fn factorial(n: u32) u64 {
    if (n <= 1) return 1;
    var result: u64 = 1;
    var i: u32 = 2;
    while (i <= n) : (i += 1) {
        result *= i;
    }
    return result;
}

test "fibonacci" {
    try expect(fibonacci(0) == 0);
    try expect(fibonacci(1) == 1);
    try expect(fibonacci(10) == 55);
    try expect(fibonacci(20) == 6765);
}

test "factorial" {
    try expect(factorial(0) == 1);
    try expect(factorial(1) == 1);
    try expect(factorial(5) == 120);
    try expect(factorial(10) == 3628800);
}

pub fn main() void {
    std.debug.print("fib(10) = {}\\n", .{fibonacci(10)});
    std.debug.print("fact(5) = {}\\n", .{factorial(5)});
}
"""
        await write_tool.execute(
            project="zig_algo", filename="algorithms.zig", code=code
        )

        # Run
        run_result = await run_tool.execute(
            project="zig_algo", filename="algorithms.zig"
        )
        assert "fib(10) = 55" in run_result
        assert "fact(5) = 120" in run_result

        # Test
        test_result = await test_tool.execute(
            project="zig_algo", filename="algorithms.zig"
        )
        assert "passed" in test_result.lower() or "All tests passed" in test_result


class TestCrossLanguageIntegration:
    """Integration tests for mixed Zig and Python projects."""

    @pytest.fixture
    def write_tool(self):
        return CodeWriteTool()

    @pytest.fixture
    def run_tool(self):
        return CodeRunTool()

    @pytest.fixture
    def list_tool(self):
        return CodeListTool()

    @pytest.fixture
    def delete_tool(self):
        return CodeDeleteTool()

    async def test_mixed_language_project(self, write_tool, list_tool, temp_workspace):
        """Test project with both Zig and Python files."""
        # Write Python
        await write_tool.execute(
            project="mixed",
            filename="process.py",
            code="print('Python processing')",
        )

        # Write Zig
        await write_tool.execute(
            project="mixed",
            filename="compute.zig",
            code="""
const std = @import("std");
pub fn main() void {
    std.debug.print("Zig computing", .{});
}
""",
        )

        # List should show both
        list_result = await list_tool.execute(project="mixed")
        assert "process.py" in list_result
        assert "compute.zig" in list_result

    async def test_separate_language_projects(
        self, write_tool, list_tool, temp_workspace
    ):
        """Test managing separate Python and Zig projects."""
        # Python project
        await write_tool.execute(
            project="py_project", filename="main.py", code="print('Python')"
        )
        await write_tool.execute(
            project="py_project", filename="utils.py", code="def helper(): pass"
        )

        # Zig project
        await write_tool.execute(
            project="zig_project",
            filename="main.zig",
            code='const std = @import("std"); pub fn main() void {}',
        )

        # List all projects
        list_result = await list_tool.execute()
        assert "py_project" in list_result
        assert "zig_project" in list_result

    async def test_cleanup_multiple_projects(
        self, write_tool, delete_tool, list_tool, temp_workspace
    ):
        """Test cleaning up multiple projects."""
        # Create projects
        await write_tool.execute(project="temp1", filename="a.py", code="")
        await write_tool.execute(project="temp2", filename="b.py", code="")
        await write_tool.execute(project="temp3", filename="c.zig", code="")

        # Verify
        list_result = await list_tool.execute()
        assert "temp1" in list_result
        assert "temp2" in list_result
        assert "temp3" in list_result

        # Delete all
        await delete_tool.execute(project="temp1")
        await delete_tool.execute(project="temp2")
        await delete_tool.execute(project="temp3")

        # Verify cleanup
        list_result = await list_tool.execute()
        assert "No projects" in list_result


class TestToolParameterValidation:
    """Test tool parameter validation."""

    def test_code_write_tool_parameters(self):
        """Test CodeWriteTool parameter schema."""
        tool = CodeWriteTool()
        params = tool.parameters
        assert params["type"] == "object"
        assert "project" in params["properties"]
        assert "filename" in params["properties"]
        assert "code" in params["properties"]
        assert set(params["required"]) == {"project", "filename", "code"}

    def test_code_run_tool_parameters(self):
        """Test CodeRunTool parameter schema."""
        tool = CodeRunTool()
        params = tool.parameters
        assert "args" in params["properties"]
        assert "timeout" in params["properties"]
        assert params["properties"]["timeout"]["default"] == 30

    def test_zig_build_tool_parameters(self):
        """Test ZigBuildTool parameter schema."""
        tool = ZigBuildTool()
        params = tool.parameters
        assert "release" in params["properties"]
        assert "output" in params["properties"]
        assert params["properties"]["release"]["default"] is False

    def test_all_tools_have_descriptions(self):
        """Test all tools have descriptions."""
        tools = get_coding_tools()
        for tool in tools:
            assert tool.description, f"{tool.name} missing description"
            assert len(tool.description) > 10, f"{tool.name} description too short"

    def test_all_tools_have_to_openai_tool(self):
        """Test all tools can be converted to OpenAI format."""
        tools = get_coding_tools()
        for tool in tools:
            openai_format = tool.to_openai_tool()
            assert "type" in openai_format
            assert "function" in openai_format
            assert openai_format["function"]["name"] == tool.name
