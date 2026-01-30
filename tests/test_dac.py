"""Tests for Diagrams As Code (DAC) converter."""

import pytest
import os
import shutil
import yaml
from pathlib import Path

from dac import (
    sanitize_filename,
    xml_to_yaml_lossless,
    yaml_to_xml_lossless,
    diagram_to_code,
    code_to_diagram,
)


# =============================================================================
# Test: sanitize_filename
# =============================================================================

class TestSanitizeFilename:
    """Tests for the sanitize_filename function."""

    def test_simple_name(self):
        """Simple names should pass through with spaces replaced."""
        assert sanitize_filename("Global Workflow") == "Global_Workflow"

    def test_name_with_slash(self):
        """Forward slashes should be replaced with underscores."""
        assert sanitize_filename("Newton/CAN") == "Newton_CAN"

    def test_name_with_special_chars(self):
        """Various special characters should be sanitized."""
        assert sanitize_filename('Test<>:"/\\|?*Name') == "Test_________Name"

    def test_already_safe_name(self):
        """Names that are already safe should not change (except spaces)."""
        assert sanitize_filename("Simple-Name_123") == "Simple-Name_123"

    def test_empty_name(self):
        """Empty string should remain empty."""
        assert sanitize_filename("") == ""

    def test_unicode_name(self):
        """Unicode characters should be preserved."""
        assert sanitize_filename("Diagramme Français") == "Diagramme_Français"


# =============================================================================
# Test: xml_to_yaml_lossless
# =============================================================================

class TestXmlToYaml:
    """Tests for XML to YAML conversion."""

    def test_basic_conversion(self, single_diagram_xml):
        """Basic XML should convert to valid YAML."""
        yaml_output = xml_to_yaml_lossless(single_diagram_xml)
        assert "mxfile:" in yaml_output
        assert "'@host': Electron" in yaml_output
        assert "diagram:" in yaml_output

    def test_preserves_attributes(self, single_diagram_xml):
        """XML attributes should be preserved as @-prefixed keys."""
        yaml_output = xml_to_yaml_lossless(single_diagram_xml)
        assert "'@id': abc123" in yaml_output
        assert "'@name': Test Diagram" in yaml_output

    def test_preserves_nested_structure(self, single_diagram_xml):
        """Nested elements should be preserved."""
        yaml_output = xml_to_yaml_lossless(single_diagram_xml)
        assert "mxGraphModel:" in yaml_output
        assert "root:" in yaml_output
        assert "mxCell:" in yaml_output


# =============================================================================
# Test: yaml_to_xml_lossless
# =============================================================================

class TestYamlToXml:
    """Tests for YAML to XML conversion."""

    def test_basic_conversion(self):
        """Basic YAML should convert to valid XML."""
        yaml_input = """
mxfile:
  '@host': Electron
  diagram:
    '@id': test123
    '@name': Test
"""
        xml_output = yaml_to_xml_lossless(yaml_input)
        assert '<?xml version="1.0" encoding="utf-8"?>' in xml_output
        assert '<mxfile' in xml_output
        assert 'host="Electron"' in xml_output

    def test_preserves_attributes(self):
        """YAML @-prefixed keys should become XML attributes."""
        yaml_input = """
mxfile:
  '@version': '1.0'
  diagram:
    '@id': abc
    '@name': My Diagram
"""
        xml_output = yaml_to_xml_lossless(yaml_input)
        assert 'version="1.0"' in xml_output
        assert 'id="abc"' in xml_output
        assert 'name="My Diagram"' in xml_output


# =============================================================================
# Test: Round-trip conversion
# =============================================================================

class TestRoundTrip:
    """Tests for XML -> YAML -> XML round-trip consistency."""

    def test_single_diagram_roundtrip(self, single_diagram_xml):
        """Single diagram XML should survive round-trip."""
        yaml_output = xml_to_yaml_lossless(single_diagram_xml)
        xml_output = yaml_to_xml_lossless(yaml_output)
        
        # Key elements should be preserved
        assert '<mxfile' in xml_output
        assert 'host="Electron"' in xml_output
        assert 'id="abc123"' in xml_output
        assert 'name="Test Diagram"' in xml_output
        assert 'value="Hello"' in xml_output

    def test_multi_diagram_roundtrip(self, multi_diagram_xml):
        """Multiple diagrams should survive round-trip."""
        yaml_output = xml_to_yaml_lossless(multi_diagram_xml)
        xml_output = yaml_to_xml_lossless(yaml_output)
        
        # All diagrams should be preserved
        assert 'name="First Page"' in xml_output
        assert 'name="Second Page"' in xml_output
        assert 'name="Third/Special Page"' in xml_output


# =============================================================================
# Test: diagram_to_code (d2c)
# =============================================================================

class TestDiagramToCode:
    """Tests for converting drawio files to YAML files."""

    def test_creates_output_directory(self, temp_dir, single_diagram_xml):
        """Should create output directory for YAML files."""
        drawio_path = Path(temp_dir) / "test.drawio"
        drawio_path.write_text(single_diagram_xml)
        
        os.chdir(temp_dir)
        diagram_to_code("test")
        
        assert (Path(temp_dir) / "test").is_dir()

    def test_creates_manifest(self, temp_dir, single_diagram_xml):
        """Should create _manifest.yaml file."""
        drawio_path = Path(temp_dir) / "test.drawio"
        drawio_path.write_text(single_diagram_xml)
        
        os.chdir(temp_dir)
        diagram_to_code("test")
        
        manifest_path = Path(temp_dir) / "test" / "_manifest.yaml"
        assert manifest_path.exists()

    def test_single_diagram_creates_one_file(self, temp_dir, single_diagram_xml):
        """Single diagram should create one YAML file."""
        drawio_path = Path(temp_dir) / "test.drawio"
        drawio_path.write_text(single_diagram_xml)
        
        os.chdir(temp_dir)
        diagram_to_code("test")
        
        yaml_path = Path(temp_dir) / "test" / "Test_Diagram.yaml"
        assert yaml_path.exists()

    def test_multi_diagram_creates_multiple_files(self, temp_dir, multi_diagram_xml):
        """Multiple diagrams should create multiple YAML files."""
        drawio_path = Path(temp_dir) / "test.drawio"
        drawio_path.write_text(multi_diagram_xml)
        
        os.chdir(temp_dir)
        diagram_to_code("test")
        
        output_dir = Path(temp_dir) / "test"
        assert (output_dir / "First_Page.yaml").exists()
        assert (output_dir / "Second_Page.yaml").exists()
        assert (output_dir / "Third_Special_Page.yaml").exists()

    def test_manifest_contains_diagram_order(self, temp_dir, multi_diagram_xml):
        """Manifest should preserve diagram order."""
        drawio_path = Path(temp_dir) / "test.drawio"
        drawio_path.write_text(multi_diagram_xml)
        
        os.chdir(temp_dir)
        diagram_to_code("test")
        
        manifest_path = Path(temp_dir) / "test" / "_manifest.yaml"
        with open(manifest_path) as f:
            manifest = yaml.safe_load(f)
        
        diagrams = manifest['diagrams']
        assert len(diagrams) == 3
        assert diagrams[0]['name'] == "First Page"
        assert diagrams[1]['name'] == "Second Page"
        assert diagrams[2]['name'] == "Third/Special Page"

    def test_missing_drawio_file_exits(self, temp_dir):
        """Should exit with error if drawio file doesn't exist."""
        os.chdir(temp_dir)
        
        with pytest.raises(SystemExit) as exc_info:
            diagram_to_code("nonexistent")
        
        assert exc_info.value.code == 1


# =============================================================================
# Test: code_to_diagram (c2d)
# =============================================================================

class TestCodeToDiagram:
    """Tests for converting YAML files back to drawio."""

    def test_creates_drawio_file(self, temp_dir, single_diagram_xml):
        """Should create drawio file from YAML files."""
        # First create the YAML files
        drawio_path = Path(temp_dir) / "test.drawio"
        drawio_path.write_text(single_diagram_xml)
        
        os.chdir(temp_dir)
        diagram_to_code("test")
        
        # Remove original and recreate
        drawio_path.unlink()
        code_to_diagram("test")
        
        assert drawio_path.exists()

    def test_preserves_all_diagrams(self, temp_dir, multi_diagram_xml):
        """Should preserve all diagrams in round-trip."""
        drawio_path = Path(temp_dir) / "test.drawio"
        drawio_path.write_text(multi_diagram_xml)
        
        os.chdir(temp_dir)
        diagram_to_code("test")
        
        # Remove original and recreate
        drawio_path.unlink()
        code_to_diagram("test")
        
        content = drawio_path.read_text()
        assert 'name="First Page"' in content
        assert 'name="Second Page"' in content
        assert 'name="Third/Special Page"' in content

    def test_missing_directory_exits(self, temp_dir):
        """Should exit with error if YAML directory doesn't exist."""
        os.chdir(temp_dir)
        
        with pytest.raises(SystemExit) as exc_info:
            code_to_diagram("nonexistent")
        
        assert exc_info.value.code == 1

    def test_missing_manifest_exits(self, temp_dir):
        """Should exit with error if manifest doesn't exist."""
        yaml_dir = Path(temp_dir) / "test"
        yaml_dir.mkdir()
        
        os.chdir(temp_dir)
        
        with pytest.raises(SystemExit) as exc_info:
            code_to_diagram("test")
        
        assert exc_info.value.code == 1

    def test_missing_diagram_file_exits(self, temp_dir, single_diagram_xml):
        """Should exit with error if a diagram file is missing."""
        drawio_path = Path(temp_dir) / "test.drawio"
        drawio_path.write_text(single_diagram_xml)
        
        os.chdir(temp_dir)
        diagram_to_code("test")
        
        # Delete one of the diagram files
        (Path(temp_dir) / "test" / "Test_Diagram.yaml").unlink()
        
        with pytest.raises(SystemExit) as exc_info:
            code_to_diagram("test")
        
        assert exc_info.value.code == 1


# =============================================================================
# Test: Full integration
# =============================================================================

class TestFullIntegration:
    """End-to-end integration tests."""

    def test_full_roundtrip_single_diagram(self, temp_dir, single_diagram_xml):
        """Complete roundtrip for single diagram file."""
        drawio_path = Path(temp_dir) / "test.drawio"
        drawio_path.write_text(single_diagram_xml)
        
        os.chdir(temp_dir)
        
        # Convert to YAML
        diagram_to_code("test")
        
        # Backup and remove original
        backup_path = Path(temp_dir) / "test.drawio.bak"
        shutil.move(drawio_path, backup_path)
        
        # Convert back to drawio
        code_to_diagram("test")
        
        # Verify key content is preserved
        new_content = drawio_path.read_text()
        assert 'host="Electron"' in new_content
        assert 'id="abc123"' in new_content
        assert 'name="Test Diagram"' in new_content
        assert 'value="Hello"' in new_content

    def test_full_roundtrip_multi_diagram(self, temp_dir, multi_diagram_xml):
        """Complete roundtrip for multi-diagram file."""
        drawio_path = Path(temp_dir) / "test.drawio"
        drawio_path.write_text(multi_diagram_xml)
        
        os.chdir(temp_dir)
        
        # Convert to YAML
        diagram_to_code("test")
        
        # Verify correct number of files
        yaml_dir = Path(temp_dir) / "test"
        yaml_files = list(yaml_dir.glob("*.yaml"))
        assert len(yaml_files) == 4  # 3 diagrams + manifest
        
        # Remove original and convert back
        drawio_path.unlink()
        code_to_diagram("test")
        
        # Verify all pages preserved
        new_content = drawio_path.read_text()
        assert 'pages="3"' in new_content or new_content.count('<diagram') == 3
        assert 'name="First Page"' in new_content
        assert 'name="Second Page"' in new_content
        assert 'name="Third/Special Page"' in new_content

    def test_modify_single_diagram_preserves_others(self, temp_dir, multi_diagram_xml):
        """Modifying one diagram file should preserve others."""
        drawio_path = Path(temp_dir) / "test.drawio"
        drawio_path.write_text(multi_diagram_xml)
        
        os.chdir(temp_dir)
        diagram_to_code("test")
        
        # Modify one diagram
        first_page_path = Path(temp_dir) / "test" / "First_Page.yaml"
        with open(first_page_path) as f:
            diagram_data = yaml.safe_load(f)
        
        # Change a value
        diagram_data['diagram']['@name'] = "Modified First Page"
        
        with open(first_page_path, 'w') as f:
            yaml.dump(diagram_data, f)
        
        # Also update manifest
        manifest_path = Path(temp_dir) / "test" / "_manifest.yaml"
        with open(manifest_path) as f:
            manifest = yaml.safe_load(f)
        manifest['diagrams'][0]['name'] = "Modified First Page"
        with open(manifest_path, 'w') as f:
            yaml.dump(manifest, f)
        
        # Convert back
        drawio_path.unlink()
        code_to_diagram("test")
        
        # Verify modification and preservation
        new_content = drawio_path.read_text()
        assert 'name="Modified First Page"' in new_content
        assert 'name="Second Page"' in new_content
        assert 'name="Third/Special Page"' in new_content


# =============================================================================
# Test: Edge cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_diagram_with_special_characters_in_content(self, temp_dir):
        """Diagrams with special characters in content should be preserved."""
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="Test" version="1.0" pages="1">
  <diagram id="test" name="Special Chars">
    <mxGraphModel>
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        <mxCell id="2" value="&lt;b&gt;Bold&lt;/b&gt; &amp; &quot;quoted&quot;" vertex="1" parent="1"/>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>'''
        
        drawio_path = Path(temp_dir) / "test.drawio"
        drawio_path.write_text(xml_content)
        
        os.chdir(temp_dir)
        diagram_to_code("test")
        drawio_path.unlink()
        code_to_diagram("test")
        
        new_content = drawio_path.read_text()
        # The HTML entities should be preserved in some form
        assert 'Bold' in new_content

    def test_empty_diagram(self, temp_dir):
        """Empty diagram (minimal content) should be handled."""
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="Test" version="1.0" pages="1">
  <diagram id="empty" name="Empty Diagram">
    <mxGraphModel>
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>'''
        
        drawio_path = Path(temp_dir) / "test.drawio"
        drawio_path.write_text(xml_content)
        
        os.chdir(temp_dir)
        diagram_to_code("test")
        drawio_path.unlink()
        code_to_diagram("test")
        
        assert drawio_path.exists()
        content = drawio_path.read_text()
        assert 'name="Empty Diagram"' in content

    def test_diagram_name_with_numbers(self, temp_dir):
        """Diagram names with numbers should be handled correctly."""
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="Test" version="1.0" pages="1">
  <diagram id="test" name="Page-123">
    <mxGraphModel>
      <root>
        <mxCell id="0"/>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>'''
        
        drawio_path = Path(temp_dir) / "test.drawio"
        drawio_path.write_text(xml_content)
        
        os.chdir(temp_dir)
        diagram_to_code("test")
        
        assert (Path(temp_dir) / "test" / "Page-123.yaml").exists()
