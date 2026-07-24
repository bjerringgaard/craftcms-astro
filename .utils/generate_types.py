import os
import re
import shutil

# Directory where PHP files are located
php_directory = "frontend/modules"

# Output directory for TypeScript files
output_directory = "frontend/vue/@types/backend"

# Regular expression to match PHP class definitions (captures optional parent class name)
class_pattern = r'class\s+(\w+)\s*(?:extends\s+(\w+)\s*)?\{([^}]*)\}'

# Regular expression to match PHP enum class definitions
enum_pattern = r'enum\s+(\w+):\s*(\w+)\s*\{([^}]+)\}'

# PHP to TypeScript type mapping
type_mapping = {
    'int': 'number',
    'integer': 'number',
    'float': 'number',
    'bool': 'boolean',
    'boolean': 'boolean',
    'string': 'string',
    'any': 'any',
    'mixed': 'any',
    'null': 'null',
}

# Standard TypeScript types that should not be imported
standard_ts_types = set(type_mapping.values())

# Default values for standard TypeScript types
default_value_mapping = {
    'number': '0',
    'boolean': 'false',
    'string': "''",
    'any': 'null',
    'null': 'null',
}

# --- Registries ---
class_registry = {}
enum_registry = {}
# Maps original PHP class name → TS type name (only differs for collisions)
name_map = {}


def _get_module_name(file_path):
    """Extract the module name from a file path like frontend/modules/<module>/..."""
    rel = os.path.relpath(file_path, php_directory)
    return rel.split(os.sep)[0].capitalize()


def build_registries():
    """First pass: scan all PHP files and build registries for classes and enums."""
    from collections import defaultdict

    # Collect all class entries before resolving collisions
    all_class_entries = defaultdict(list)

    for root, _, files in os.walk(php_directory):
        for file in files:
            if file.endswith(".php"):
                php_file_path = os.path.join(root, file)
                with open(php_file_path, "r") as f:
                    php_code = f.read()

                for match in re.finditer(class_pattern, php_code):
                    class_name = match.group(1)
                    parent_name = match.group(2)
                    class_body = match.group(3)
                    has_typescript = '@typescript' in class_body
                    properties = re.findall(
                        r'public(?:\s+readonly)?\s+([^\s$]+)\s+\$(\w+)', class_body
                    )
                    all_class_entries[class_name].append({
                        'parent': parent_name or None,
                        'has_typescript': has_typescript,
                        'properties': properties,
                        'class_body': class_body,
                        'file_path': php_file_path,
                    })

                for match in re.finditer(enum_pattern, php_code):
                    enum_name = match.group(1)
                    enum_body = match.group(3)
                    if '@typescript' in enum_body:
                        enum_registry[enum_name] = {
                            'enum_body': enum_body,
                        }

    # Resolve collisions and build final registry
    for class_name, entries in all_class_entries.items():
        ts_entries = [e for e in entries if e['has_typescript']]

        if len(ts_entries) > 1:
            # Multiple @typescript classes with the same name — prefix with module
            for entry in ts_entries:
                module = _get_module_name(entry['file_path'])
                prefixed_name = f"{module}{class_name}"
                class_registry[prefixed_name] = entry
                name_map[class_name] = name_map.get(class_name, []) if isinstance(name_map.get(class_name), list) else []
            # Store all prefixed names so type resolution can warn/pick
            name_map[class_name] = [f"{_get_module_name(e['file_path'])}{class_name}" for e in ts_entries]
            print(f'⚠ Collision: {class_name} found in {len(ts_entries)} modules, generated as: {", ".join(name_map[class_name])}')
        elif len(ts_entries) == 1:
            # Single @typescript entry — use original name
            class_registry[class_name] = ts_entries[0]
            name_map[class_name] = class_name
        else:
            # No @typescript entries — pick the first (for parent resolution)
            class_registry[class_name] = entries[0]
            name_map[class_name] = class_name


def should_generate(class_name, visited=None):
    """Check if a class should have a TS type generated (has @typescript or inherits from one that does)."""
    if visited is None:
        visited = set()
    if class_name in visited or class_name not in class_registry:
        return False
    visited.add(class_name)
    entry = class_registry[class_name]
    if entry['has_typescript']:
        return True
    if entry['parent']:
        return should_generate(entry['parent'], visited)
    return False


def get_all_properties(class_name, visited=None):
    """Get all properties including inherited ones as (type, name, class_body) tuples."""
    if visited is None:
        visited = set()
    if class_name in visited or class_name not in class_registry:
        return []
    visited.add(class_name)
    entry = class_registry[class_name]
    parent_props = []
    if entry['parent']:
        parent_props = get_all_properties(entry['parent'], visited)

    own_props = [(t, n, entry['class_body']) for t, n in entry['properties']]

    # Own properties override parent properties with the same name
    own_names = {n for _, n, _ in own_props}
    merged = [(t, n, cb) for t, n, cb in parent_props if n not in own_names]
    merged.extend(own_props)
    return merged


# --- Import Handling ---

def add_import(imports, source, name):
    """Add an import entry grouped by source file. Skips standard types."""
    if not name or not source:
        return
    if name in standard_ts_types or source in standard_ts_types:
        return
    if source not in imports:
        imports[source] = set()
    imports[source].add(name)


def write_imports(ts_file, imports, class_name):
    """Write grouped import statements, excluding self-imports."""
    for source in sorted(imports.keys()):
        if source == class_name:
            continue
        names = ', '.join(sorted(imports[source]))
        ts_file.write(f"import {{ {names} }} from './{source}';\n")


# --- Type Resolution ---

def resolve_type_name(php_type):
    """Resolve a PHP class name to its TS type name using name_map."""
    mapped = name_map.get(php_type)
    if isinstance(mapped, list):
        # Collision — use first prefixed name
        return mapped[0] if mapped else php_type
    elif isinstance(mapped, str):
        return mapped
    return php_type


def resolve_type_expression(type_expression, imports, class_name):
    """Resolve scalar/custom union type expressions and add imports per member."""
    resolved_parts = []

    for part in type_expression.split('|'):
        part = part.strip()
        if not part:
            continue

        resolved = type_mapping.get(part, part)
        if resolved == 'array':
            resolved_parts.append('Array<any>')
            continue
        if resolved == 'object':
            resolved_parts.append('Record<string, any>')
            continue
        if resolved not in standard_ts_types:
            resolved = resolve_type_name(resolved)
            if resolved != class_name:
                add_import(imports, resolved, resolved)
        resolved_parts.append(resolved)

    return '|'.join(resolved_parts) if resolved_parts else 'any'


def resolve_ts_type(class_name, prop_type, prop_name, class_body, imports):
    """Resolve a PHP type to a TypeScript type string and update imports."""
    # Handle ? prefixes '?MyPhpType'
    if prop_type.startswith('?'):
        base_type = prop_type[1:]
        return resolve_type_expression(base_type, imports, class_name) + '|null'

    # Map PHP types to TypeScript types
    ts_type = type_mapping.get(prop_type, prop_type)

    # Resolve potential name collisions for custom types
    if ts_type not in standard_ts_types and ts_type != 'array' and ts_type != 'object' and not ts_type.endswith('Collection'):
        ts_type = resolve_type_name(ts_type)

    if ts_type.endswith('Model') or ts_type.endswith('Enum'):
        add_import(imports, ts_type, ts_type)
    elif ts_type.endswith('Collection'):
        collection_types = extract_allowed_types(ts_type)
        ts_model = resolve_type_expression(collection_types[0], imports, class_name) if collection_types else 'any'
        ts_type = f"Array<{ts_model}>"
    elif ts_type == 'array':
        ts_model = find_array_type(class_name, prop_name, class_body)
        ts_model = resolve_type_expression(ts_model, imports, class_name)
        ts_type = f"Array<{ts_model}>"
    elif ts_type == 'object':
        ts_model = find_array_type(class_name, prop_name, class_body)
        ts_model = resolve_type_expression(ts_model, imports, class_name)
        ts_type = f"Record<string, {ts_model}>"
    elif ts_type not in standard_ts_types:
        # Handle union types (e.g. TypeA|TypeB) and custom types
        ts_type = resolve_type_expression(ts_type, imports, class_name)

    return ts_type


def get_default_value(ts_type, class_name, imports):
    """Get the default empty value for a TypeScript type and update imports for defaults."""
    # Handle nullable types
    if '|null' in ts_type:
        return 'null'

    # Handle non-null union types - use first type's default
    if '|' in ts_type:
        first_type = ts_type.split('|')[0]
        return get_default_value(first_type, class_name, imports)

    # Handle standard types
    if ts_type in default_value_mapping:
        return default_value_mapping[ts_type]

    # Handle arrays
    if ts_type.startswith('Array<'):
        return '[]'

    # Handle records/objects
    if ts_type.startswith('Record<'):
        return '{}'

    # Custom types (including enums) - call their default factory
    resolved = resolve_type_name(ts_type)
    default_name = f'default{resolved}'
    if resolved != class_name:
        add_import(imports, resolved, default_name)
    return f'{default_name}()'


# --- Helper Functions ---

def extract_allowed_types(collection_class_name):
    """Extract allowed types from a Collection class."""
    for root, _, files in os.walk(php_directory):
        for file in files:
            if file.endswith(".php"):
                php_file_path = os.path.join(root, file)
                with open(php_file_path, "r") as php_file:
                    php_code = php_file.read()
                    if f'class {collection_class_name}' in php_code:
                        match = re.search(r'protected\s+static\s+\$allowedTypes\s*=\s*(\[.+?\]);', php_code)
                        if match:
                            allowed_types_str = match.group(1)
                            allowed_types = re.findall(r'\b(\w+)\s*::\s*class\b', allowed_types_str)
                            return allowed_types
    return None


def find_array_type(class_name, prop_name, class_body):
    """Find the TypeScript type for an array property using @param annotations."""
    class_lines = class_body.split("\n")
    found_param = False

    for line in class_lines:
        if found_param:
            param_pattern = r"@param\s+(\S+)\s+\$" + re.escape(prop_name)
            param_type = re.search(param_pattern, line)

            if param_type:
                param_replaced = param_type.group(1).replace('[]', '')
                match = re.match(r'array<(.+)>', param_replaced)
                if match:
                    inner_type = match.group(1)
                    return type_mapping.get(inner_type, inner_type)
                match = re.match(r'object<(.+)>', param_replaced)
                if match:
                    inner_type = match.group(1)
                    return type_mapping.get(inner_type, inner_type)

                return param_replaced
        elif '@typescript' in line.strip().lower():
            found_param = True

    return 'any'


# --- Generation Functions ---

def generate_class_definition(class_name):
    """Generate TypeScript type definition and default factory for a class."""
    imports = {}
    all_properties = get_all_properties(class_name)

    # Build type definition
    ts_type_code = f"export type {class_name} = {{\n"
    default_entries = []

    for prop_type, prop_name, class_body in all_properties:
        ts_type = resolve_ts_type(class_name, prop_type, prop_name, class_body, imports)
        ts_type_code += f"  {prop_name}: {ts_type};\n"
        default_val = get_default_value(ts_type, class_name, imports)
        default_entries.append((prop_name, default_val))

    ts_type_code += "};"

    # Build default factory
    default_code = f"\n\nexport function default{class_name}(): {class_name} {{\n"
    default_code += "  return {\n"
    for prop_name, default_val in default_entries:
        default_code += f"    {prop_name}: {default_val},\n"
    default_code += "  };\n"
    default_code += "}"

    # Write file
    ts_file_path = os.path.join(output_directory, f"{class_name}.ts")
    with open(ts_file_path, "w") as ts_file:
        write_imports(ts_file, imports, class_name)
        ts_file.write("\n")
        ts_file.write(ts_type_code)
        ts_file.write(default_code)


def generate_enum_definition(enum_name, enum_body):
    """Generate TypeScript enum definition and default factory."""
    ts_code = f"export enum {enum_name} {{\n"
    enum_items = re.findall(r'(\w+)\s*=\s*[\'"]([^\'"]+)[\'"]', enum_body)
    first_item_name = None
    for item_name, item_value in enum_items:
        if first_item_name is None:
            first_item_name = item_name
        ts_code += f"  {item_name} = '{item_value}',\n"
    ts_code += "}"

    # Default is the first enum value
    default_code = ""
    if first_item_name:
        default_code = (
            f"\n\nexport function default{enum_name}(): {enum_name} {{\n"
            f"  return {enum_name}.{first_item_name};\n"
            "}"
        )

    ts_file_path = os.path.join(output_directory, f"{enum_name}.ts")
    with open(ts_file_path, "w") as ts_file:
        ts_file.write("\n")
        ts_file.write(ts_code)
        ts_file.write(default_code)


# --- Main ---

# Clear the output directory to remove deprecated typings
if os.path.exists(output_directory):
    shutil.rmtree(output_directory)

# Ensure the output directory exists
os.makedirs(output_directory, exist_ok=True)

# Phase 1: Build registries of all classes and enums
build_registries()

# Phase 2: Generate TypeScript types for classes (with inheritance)
for class_name in class_registry:
    if should_generate(class_name):
        generate_class_definition(class_name)
        print('✓ Generated: ' + class_name)

# Phase 3: Generate TypeScript enums
for enum_name, enum_data in enum_registry.items():
    generate_enum_definition(enum_name, enum_data['enum_body'])
    print('✓ Generated: ' + enum_name)
