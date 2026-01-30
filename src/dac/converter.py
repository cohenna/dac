"""Core conversion logic for DAC."""

import xmltodict
import yaml
import re
import os
import sys
from pathlib import Path


def sanitize_filename(name):
    """Convert a diagram name to a safe filename."""
    # Replace characters that are invalid in filenames
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
    # Replace spaces with underscores for easier handling
    sanitized = sanitized.replace(' ', '_')
    return sanitized


def xml_to_yaml_lossless(xml_string):
    """
    Parses XML to a Python dictionary (preserving attributes as @keys),
    then dumps that dictionary to a YAML string.
    """
    data_dict = xmltodict.parse(xml_string)
    return yaml.dump(data_dict, default_flow_style=False, allow_unicode=True)


def yaml_to_xml_lossless(yaml_string):
    """
    Parses YAML to a Python dictionary, then 'unparses' that 
    dictionary back to a valid XML string.
    """
    data_dict = yaml.safe_load(yaml_string)
    return xmltodict.unparse(data_dict, pretty=True)


def diagram_to_code(base_filename):
    """Convert drawio XML to separate YAML files per diagram."""
    drawio_path = f"{base_filename}.drawio"
    output_dir = Path(base_filename)
    
    if not os.path.exists(drawio_path):
        print(f"Error: {drawio_path} not found.")
        sys.exit(1)
    
    with open(drawio_path, 'r') as f:
        xml_content = f.read()
    
    # Parse the XML
    data_dict = xmltodict.parse(xml_content)
    mxfile = data_dict.get('mxfile', {})
    diagrams = mxfile.get('diagram', [])
    
    # Ensure diagrams is a list (single diagram becomes a dict)
    if isinstance(diagrams, dict):
        diagrams = [diagrams]
    
    # Create output directory
    output_dir.mkdir(exist_ok=True)
    
    # Extract mxfile attributes for the manifest
    mxfile_attrs = {k: v for k, v in mxfile.items() if k.startswith('@')}
    manifest = {
        'mxfile': mxfile_attrs,
        'diagrams': []
    }
    
    # Write each diagram to a separate file
    for i, diagram in enumerate(diagrams):
        diagram_name = diagram.get('@name', f'diagram_{i}')
        safe_name = sanitize_filename(diagram_name)
        yaml_path = output_dir / f"{safe_name}.yaml"
        
        # Store diagram data
        diagram_yaml = yaml.dump({'diagram': diagram}, default_flow_style=False, allow_unicode=True)
        
        with open(yaml_path, 'w') as f:
            f.write(diagram_yaml)
        
        manifest['diagrams'].append({
            'name': diagram_name,
            'file': f"{safe_name}.yaml"
        })
        print(f"  ✓ {diagram_name} → {yaml_path}")
    
    # Write manifest file
    manifest_path = output_dir / "_manifest.yaml"
    with open(manifest_path, 'w') as f:
        yaml.dump(manifest, f, default_flow_style=False, allow_unicode=True)
    
    print(f"\n✓ Converted {drawio_path} → {output_dir}/ ({len(diagrams)} diagrams)")


def code_to_diagram(base_filename):
    """Convert separate YAML files back to drawio XML."""
    input_dir = Path(base_filename)
    drawio_path = f"{base_filename}.drawio"
    manifest_path = input_dir / "_manifest.yaml"
    
    if not input_dir.exists():
        print(f"Error: {input_dir}/ directory not found.")
        sys.exit(1)
    
    if not manifest_path.exists():
        print(f"Error: {manifest_path} not found.")
        sys.exit(1)
    
    # Read manifest
    with open(manifest_path, 'r') as f:
        manifest = yaml.safe_load(f)
    
    # Reconstruct mxfile structure
    mxfile = dict(manifest.get('mxfile', {}))
    diagrams = []
    
    # Read each diagram file in order
    for diagram_info in manifest.get('diagrams', []):
        yaml_file = input_dir / diagram_info['file']
        if not yaml_file.exists():
            print(f"Error: {yaml_file} not found.")
            sys.exit(1)
        
        with open(yaml_file, 'r') as f:
            diagram_data = yaml.safe_load(f)
        
        diagrams.append(diagram_data['diagram'])
        print(f"  ✓ {diagram_info['name']} ← {yaml_file}")
    
    # Handle single vs multiple diagrams
    if len(diagrams) == 1:
        mxfile['diagram'] = diagrams[0]
    else:
        mxfile['diagram'] = diagrams
    
    # Convert to XML
    xml_content = xmltodict.unparse({'mxfile': mxfile}, pretty=True)
    
    with open(drawio_path, 'w') as f:
        f.write(xml_content)
    
    print(f"\n✓ Converted {input_dir}/ → {drawio_path} ({len(diagrams)} diagrams)")
