"""Check implementation-pack contracts; does not exercise unimplemented HTTP handlers."""
from pathlib import Path
import json
import re
import yaml
from openapi_spec_validator import validate_spec
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
spec = yaml.safe_load((ROOT / 'contracts/openapi.yaml').read_text())
validate_spec(spec)
operations = {op['operationId']: op for methods in spec['paths'].values() for op in methods.values()}
assert len(operations) == sum(len(methods) for methods in spec['paths'].values())
for path, methods in spec['paths'].items():
    for method, op in methods.items():
        if method in ('post', 'patch', 'delete', 'put'):
            assert any(p.get('$ref', '').endswith('/IdempotencyKey') for p in op.get('parameters', [])), path
        assert 'default' in op['responses']

examples = sorted((ROOT / 'contracts/examples').glob('*.json'))
assert examples, 'HTTP examples must not be empty'
for f in examples:
    case = json.loads(f.read_text())
    assert case['operation_id'] in operations
    reference = '#/components/schemas/' + case['schema']
    assert reference in json.dumps(operations[case['operation_id']]), (f, 'schema not a direct request/response')
    schema = {'$ref': reference, 'components': spec['components']}
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(case['data']))
    assert bool(errors) == (case.get('valid', True) is False), (f, [e.message for e in errors])
assert any(not json.loads(f.read_text())['valid'] for f in examples), 'Need negative examples'

ai_schemas = {p.name: json.loads(p.read_text()) for p in (ROOT / 'contracts/ai').glob('*.schema.json')}
assert len(ai_schemas) == 3
for schema in ai_schemas.values():
    Draft202012Validator.check_schema(schema)
ai_examples = sorted((ROOT / 'contracts/ai/examples').glob('*.json'))
covered_ai = set()
for f in ai_examples:
    case = json.loads(f.read_text())
    covered_ai.add(case['schema'])
    errors = list(Draft202012Validator(ai_schemas[case['schema']]).iter_errors(case['data']))
    assert bool(errors) == (case['valid'] is False), (f, [e.message for e in errors])
assert covered_ai == set(ai_schemas)

schemas = spec['components']['schemas']
eras = json.loads((ROOT / 'contracts/fixtures/eras.json').read_text())
assert [e['id'] for e in eras] == schemas['EraId']['enum']
assert len(eras) == 10 and len({e['sort_order'] for e in eras}) == 10
frontend = (ROOT / 'mobile/src/mocks/fixtures.ts').read_text()
assert set(re.findall(r"id: '(ERA_[A-Z_]+)'", frontend)) == set(schemas['EraId']['enum'])
for era in eras:
    assert era['fragment_goal'] == 3 
config = json.loads((ROOT / 'contracts/fixtures/config.json').read_text())
assert config['version'] == spec['info']['version']
assert config['mission_xp'] == schemas['Mission']['properties']['xp']['const']
assert config['free_xp'] in schemas['Discovery']['properties']['xp_awarded']['enum']
assert config['max_evidence_images'] == schemas['Submission']['properties']['evidence_count']['maximum']
assert config['max_upload_bytes'] == schemas['Asset']['properties']['byte_size']['maximum']
assert config['max_caption_chars'] == schemas['PostInput']['properties']['caption']['maxLength']
assert config['max_direct_recipients'] == schemas['PostInput']['properties']['friend_ids']['x-max-distinct-items']
assert config['max_group_recipients'] == schemas['PostInput']['properties']['group_ids']['x-max-distinct-items']
assert config['max_group_members'] == schemas['GroupInput']['properties']['member_ids']['x-max-distinct-items'] + 1

flow = json.loads((ROOT / 'contracts/acceptance.json').read_text())
covered = {op for case in flow['cases'] for op in case['operations']}
assert set(operations) == covered, (set(operations) - covered, covered - set(operations))
assert len({case['id'] for case in flow['cases']}) == len(flow['cases'])
assert all(case['given'] and case['when'] and case['then'] for case in flow['cases'])
md_files = [*(ROOT / 'docs').rglob('*.md'), *(ROOT / 'contracts').rglob('*.md'), ROOT / 'firebase/README.md', ROOT / 'README.md', ROOT / 'mobile/README.md']
for path in md_files:
    for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', path.read_text()):
        if target.startswith(('http:', 'https:', '#', 'mailto:')):
            continue
        dest = target.split('#')[0]
        assert not dest or (path.parent / dest).exists(), (path, target)
print(f'PASS: {len(operations)} operations; {len(examples)} HTTP + {len(ai_examples)} AI examples; '
      f'{len(flow["cases"])} acceptance cases; catalog/config and {len(md_files)} Markdown files')
