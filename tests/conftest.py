"""Shared pytest fixtures for DAC tests."""

import pytest
import shutil
import tempfile


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    dirpath = tempfile.mkdtemp()
    yield dirpath
    shutil.rmtree(dirpath)


@pytest.fixture
def single_diagram_xml():
    """A simple drawio XML with a single diagram."""
    return '''<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="Electron" agent="Mozilla/5.0" version="28.2.5" pages="1">
  <diagram id="abc123" name="Test Diagram">
    <mxGraphModel dx="100" dy="100" grid="1">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        <mxCell id="2" value="Hello" style="rounded=1;" vertex="1" parent="1">
          <mxGeometry x="100" y="100" width="80" height="40" as="geometry"/>
        </mxCell>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>'''


@pytest.fixture
def multi_diagram_xml():
    """A drawio XML with multiple diagrams."""
    return '''<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="Electron" agent="Mozilla/5.0" version="28.2.5" pages="3">
  <diagram id="page1" name="First Page">
    <mxGraphModel dx="100" dy="100">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        <mxCell id="2" value="Page 1" vertex="1" parent="1"/>
      </root>
    </mxGraphModel>
  </diagram>
  <diagram id="page2" name="Second Page">
    <mxGraphModel dx="200" dy="200">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        <mxCell id="3" value="Page 2" vertex="1" parent="1"/>
      </root>
    </mxGraphModel>
  </diagram>
  <diagram id="page3" name="Third/Special Page">
    <mxGraphModel dx="300" dy="300">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        <mxCell id="4" value="Page 3" vertex="1" parent="1"/>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>'''
