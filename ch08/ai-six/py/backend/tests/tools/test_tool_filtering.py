import unittest
from unittest.mock import MagicMock

from backend.agent.config import ToolConfig, Config
from backend.agent.tool_manager import _filter_tools, get_tool_dict
from backend.object_model.tool import Tool


class MockTool(Tool):
    def __init__(self, name: str):
        self.name = name
        self.description = f"Mock tool {name}"
        self.parameters = {}
        self.required = set()
    
    def run(self, **kwargs):
        return f"Mock result from {self.name}"


class TestToolFiltering(unittest.TestCase):
    
    def setUp(self):
        # Create mock tools
        self.tool_a = MockTool("tool_a")
        self.tool_b = MockTool("tool_b")
        self.tool_c = MockTool("tool_c")
        self.all_tools = [self.tool_a, self.tool_b, self.tool_c]
    
    def test_filter_tools_no_filtering(self):
        """Test that when both enabled_tools and disabled_tools are None, all tools are returned."""
        result = _filter_tools(self.all_tools, enabled_tools=None, disabled_tools=None)
        self.assertEqual(len(result), 3)
        self.assertIn(self.tool_a, result)
        self.assertIn(self.tool_b, result)
        self.assertIn(self.tool_c, result)
    
    def test_filter_tools_enabled_only(self):
        """Test filtering with enabled_tools."""
        enabled_tools = ["tool_a", "tool_c"]
        result = _filter_tools(self.all_tools, enabled_tools=enabled_tools, disabled_tools=None)
        
        self.assertEqual(len(result), 2)
        self.assertIn(self.tool_a, result)
        self.assertNotIn(self.tool_b, result)
        self.assertIn(self.tool_c, result)
    
    def test_filter_tools_disabled_only(self):
        """Test filtering with disabled_tools."""
        disabled_tools = ["tool_b"]
        result = _filter_tools(self.all_tools, enabled_tools=None, disabled_tools=disabled_tools)
        
        self.assertEqual(len(result), 2)
        self.assertIn(self.tool_a, result)
        self.assertNotIn(self.tool_b, result)
        self.assertIn(self.tool_c, result)
    
    def test_filter_tools_enabled_empty_list(self):
        """Test filtering with empty enabled_tools list."""
        enabled_tools = []
        result = _filter_tools(self.all_tools, enabled_tools=enabled_tools, disabled_tools=None)
        
        self.assertEqual(len(result), 0)
    
    def test_filter_tools_disabled_empty_list(self):
        """Test filtering with empty disabled_tools list."""
        disabled_tools = []
        result = _filter_tools(self.all_tools, enabled_tools=None, disabled_tools=disabled_tools)
        
        self.assertEqual(len(result), 3)
        self.assertIn(self.tool_a, result)
        self.assertIn(self.tool_b, result)
        self.assertIn(self.tool_c, result)
    
    def test_filter_tools_nonexistent_enabled(self):
        """Test filtering with enabled_tools containing nonexistent tools."""
        enabled_tools = ["tool_a", "nonexistent_tool"]
        result = _filter_tools(self.all_tools, enabled_tools=enabled_tools, disabled_tools=None)
        
        self.assertEqual(len(result), 1)
        self.assertIn(self.tool_a, result)
    
    def test_filter_tools_nonexistent_disabled(self):
        """Test filtering with disabled_tools containing nonexistent tools."""
        disabled_tools = ["nonexistent_tool"]
        result = _filter_tools(self.all_tools, enabled_tools=None, disabled_tools=disabled_tools)
        
        self.assertEqual(len(result), 3)
        self.assertIn(self.tool_a, result)
        self.assertIn(self.tool_b, result)
        self.assertIn(self.tool_c, result)


class TestToolConfigValidation(unittest.TestCase):
    
    def test_tool_config_valid_none_none(self):
        """Test ToolConfig with both enabled_tools and disabled_tools as None."""
        config = ToolConfig(
            tools_dirs=["/test/tools"],
            mcp_tools_dirs=["/test/mcp"],
            enabled_tools=None,
            disabled_tools=None
        )
        # Should not raise any exception
        self.assertIsNone(config.enabled_tools)
        self.assertIsNone(config.disabled_tools)
    
    def test_tool_config_valid_enabled_none(self):
        """Test ToolConfig with enabled_tools set and disabled_tools as None."""
        config = ToolConfig(
            tools_dirs=["/test/tools"],
            mcp_tools_dirs=["/test/mcp"],
            enabled_tools=["tool_a", "tool_b"],
            disabled_tools=None
        )
        # Should not raise any exception
        self.assertEqual(config.enabled_tools, ["tool_a", "tool_b"])
        self.assertIsNone(config.disabled_tools)
    
    def test_tool_config_valid_none_disabled(self):
        """Test ToolConfig with enabled_tools as None and disabled_tools set."""
        config = ToolConfig(
            tools_dirs=["/test/tools"],
            mcp_tools_dirs=["/test/mcp"],
            enabled_tools=None,
            disabled_tools=["tool_c"]
        )
        # Should not raise any exception
        self.assertIsNone(config.enabled_tools)
        self.assertEqual(config.disabled_tools, ["tool_c"])
    
    def test_tool_config_invalid_both_set(self):
        """Test ToolConfig with both enabled_tools and disabled_tools set."""
        with self.assertRaises(ValueError) as context:
            ToolConfig(
                tools_dirs=["/test/tools"],
                mcp_tools_dirs=["/test/mcp"],
                enabled_tools=["tool_a"],
                disabled_tools=["tool_b"]
            )
        self.assertIn("You can only have one of enabled_tools or disabled_tools", str(context.exception))


class TestConfigValidation(unittest.TestCase):
    
    def test_config_valid_none_none(self):
        """Test Config with both enabled_tools and disabled_tools as None."""
        config = Config(
            default_model_id="test-model",
            tools_dirs=["/test/tools"],
            mcp_tools_dirs=["/test/mcp"],
            memory_dir="/test/memory",
            enabled_tools=None,
            disabled_tools=None
        )
        
        with unittest.mock.patch('os.path.isdir', return_value=True):
            config.invariant()  # Should not raise any exception
        
        self.assertIsNone(config.enabled_tools)
        self.assertIsNone(config.disabled_tools)
    
    def test_config_valid_enabled_none(self):
        """Test Config with enabled_tools set and disabled_tools as None."""
        config = Config(
            default_model_id="test-model",
            tools_dirs=["/test/tools"],
            mcp_tools_dirs=["/test/mcp"],
            memory_dir="/test/memory",
            enabled_tools=["tool_a", "tool_b"],
            disabled_tools=None
        )
        
        with unittest.mock.patch('os.path.isdir', return_value=True):
            config.invariant()  # Should not raise any exception
        
        self.assertEqual(config.enabled_tools, ["tool_a", "tool_b"])
        self.assertIsNone(config.disabled_tools)
    
    def test_config_valid_none_disabled(self):
        """Test Config with enabled_tools as None and disabled_tools set."""
        config = Config(
            default_model_id="test-model",
            tools_dirs=["/test/tools"],
            mcp_tools_dirs=["/test/mcp"],
            memory_dir="/test/memory",
            enabled_tools=None,
            disabled_tools=["tool_c"]
        )
        
        with unittest.mock.patch('os.path.isdir', return_value=True):
            config.invariant()  # Should not raise any exception
        
        self.assertIsNone(config.enabled_tools)
        self.assertEqual(config.disabled_tools, ["tool_c"])
    
    def test_config_invalid_both_set(self):
        """Test Config with both enabled_tools and disabled_tools set."""
        config = Config(
            default_model_id="test-model",
            tools_dirs=["/test/tools"],
            mcp_tools_dirs=["/test/mcp"],
            memory_dir="/test/memory",
            enabled_tools=["tool_a"],
            disabled_tools=["tool_b"]
        )
        
        with unittest.mock.patch('os.path.isdir', return_value=True):
            with self.assertRaises(ValueError) as context:
                config.invariant()
            self.assertIn("You can only have one of enabled_tools or disabled_tools", str(context.exception))


if __name__ == '__main__':
    unittest.main()