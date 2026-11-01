"""Versioned build recipes. Planning is read-only; ahoy executes the plan.

No shell, scheduler, cache or implicit dependency-install hooks live here.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import subprocess
import socket
import time
import fnmatch
import uuid
import hashlib
import itertools

import build_support as support
from buoy_executables import resolve_compiler, resolve_packager
from .common import atomic_write, load_json


def need(condition, message):
    if not condition:
        raise ValueError(message)


def strings(value, label):
    need(isinstance(value, list) and all(isinstance(x, str) and x and '\x00' not in x for x in value),
         f'{label} must be an array of nonempty strings')
    return value


def path_in(root, relative):
    need(isinstance(relative, str) and relative and not Path(relative).is_absolute()
         and '..' not in Path(relative).parts and '\\' not in relative, f'invalid project path: {relative}')
    path = root / relative
    for parent in (path, *path.parents):
        if parent == root:
            break
        need(not parent.is_symlink() and not (hasattr(parent, 'is_junction') and parent.is_junction()), f'linked build path: {parent}')
    need(path.resolve().is_relative_to(root) and path.resolve() != root, f'path leaves project: {relative}')
    return path


def inputs(root, patterns):
    found = set()
    for pattern in strings(patterns, 'inputs'):
        path_in(root, pattern)
        matches = sorted(root.glob(pattern))
        need(matches, f'no inputs matched: {pattern}')
        for path in matches:
            path_in(root, path.relative_to(root).as_posix())
            need(path.is_file(), f'input is not a regular file: {path}')
            found.add(str(path))
    return sorted(found)


def render(text, values):
    need(isinstance(text, str), 'command arguments must be strings')
    def replace(match):
        if match[0] == '{{':
            return '{'
        if match[0] == '}}':
            return '}'
        need(match[1] in values, f'unknown placeholder: {match[0]}')
        return values[match[1]]
    return re.sub(r'\{\{|\}\}|\{([a-z][a-z0-9_-]*)\}', replace, text)


def snapshot(root, paths, allow_missing=False):
    records = {}
    for relative in paths:
        path = path_in(root, relative)
        if not path.exists():
            need(allow_missing, f'missing declared output: {relative}')
            records[relative] = {'kind': 'missing'}
            continue
        need(path.is_file() or path.is_dir(), f'unsupported output type: {relative}')
        children = [path] if path.is_file() else sorted(path.rglob('*'))
        if path.is_dir():
            records[relative] = {'kind': 'directory'}
        for child in children:
            path_in(root, child.relative_to(root).as_posix())
            key = child.relative_to(root).as_posix()
            if child.is_file():
                records[key] = {'kind': 'file', 'sha256': support.file_hash(child)}
            elif child.is_dir():
                records[key] = {'kind': 'directory'}
            else:
                raise ValueError(f'unsupported output type: {key}')
    return records


def artifact_suffix(outputs):
    return '-' + hashlib.sha256('\0'.join(sorted(outputs)).encode()).hexdigest()[:16] if outputs is not None else ''


def receipt_path(root, name, target, profile, outputs=None):
    return path_in(root, f'.buoy/build/receipts/{name}-{target}-{profile}{artifact_suffix(outputs)}.json')


def owner_path(root, name, target, profile, outputs=None):
    return path_in(root, f'.buoy/build/owners/{name}-{target}-{profile}{artifact_suffix(outputs)}.json')


def previous_owner(root, name, target, profile, outputs):
    for path in (receipt_path(root, name, target, profile, outputs), owner_path(root, name, target, profile, outputs),
                 receipt_path(root, name, target, profile), owner_path(root, name, target, profile)):
        if path.exists():
            value = load_json(path)
            if path in (receipt_path(root, name, target, profile), owner_path(root, name, target, profile)) and sorted(value.get('outputs', [])) != sorted(outputs):
                continue
            return validate_owner(value, name, target, profile, outputs)
    return None


def retire_legacy_records(root, name, target, profile, outputs):
    for path in (receipt_path(root, name, target, profile), owner_path(root, name, target, profile)):
        if path.exists() and sorted(load_json(path).get('outputs', [])) == sorted(outputs):
            path.unlink()


def file_state(path):
    if not path.exists():
        return None
    state = path.stat()
    return [state.st_dev, state.st_ino, state.st_size, state.st_mtime_ns, state.st_ctime_ns]


def metadata(root, name, target, profile, outputs):
    nodes = snapshot(root, outputs, allow_missing=True)
    return dict(schema=2, name=name, target=target, profile=profile, outputs=outputs, nodes=nodes,
                stats={p: file_state(path_in(root, p)) for p in nodes},
                roots={p: file_state(path_in(root, p)) for p in outputs})


def owned_nodes(previous, value):
    return {p: bool(previous.get('owned_nodes', {}).get(p, False)
                    or previous.get('stats', {}).get(p) != value['stats'].get(p)) for p in value['nodes']}


def validate_owner(value, name, target, profile, outputs):
    need(isinstance(value, dict) and value.get('schema') in (1, 2)
         and value.get('name') == name and value.get('target') == target
         and value.get('profile') == profile and sorted(value.get('outputs', [])) == sorted(outputs),
         f'{name}: ownership record does not match recipe')
    if value['schema'] == 1:
        # Legacy receipts omitted directories. Infer only parents of known files;
        # unknown empty directories remain protected during migration.
        nodes = {p: {'kind': 'file', 'sha256': h} for p, h in value.get('hashes', {}).items()}
        for filename in list(nodes):
            for parent in Path(filename).parents:
                text = parent.as_posix()
                if any(text == p or text.startswith(p + '/') for p in outputs):
                    nodes[text] = {'kind': 'directory'}
        value = dict(value, nodes=nodes)
    return value


def record(root, name, target, profile, outputs):
    previous = validate_owner(load_json(owner_path(root, name, target, profile, outputs)), name, target, profile, outputs)
    value = metadata(root, name, target, profile, outputs)
    snapshot(root, outputs)  # All declared outputs must actually exist.
    value['owned_nodes'] = owned_nodes(previous, value)
    need(all(value['owned_nodes'].values()), f'{name}: pre-existing output was not produced by this build')
    value['state'] = 'complete'
    atomic_write(owner_path(root, name, target, profile, outputs), json.dumps(value, indent=2) + '\n')
    atomic_write(receipt_path(root, name, target, profile, outputs), json.dumps(value, indent=2) + '\n')


def failed(root, name, target, profile, outputs):
    previous = validate_owner(load_json(owner_path(root, name, target, profile, outputs)), name, target, profile, outputs)
    value = metadata(root, name, target, profile, outputs)
    value['state'] = 'failed'
    value['owned_nodes'] = owned_nodes(previous, value)
    atomic_write(owner_path(root, name, target, profile, outputs), json.dumps(value, indent=2) + '\n')
    receipt_path(root, name, target, profile, outputs).unlink(missing_ok=True)


def clean(root, name, target, profile, outputs):
    disposable = [p for p in outputs if not p.startswith('packages/')]
    if not disposable:
        print(f'{name}: published package archives retained; no disposable outputs')
        return
    receipt = receipt_path(root, name, target, profile, outputs)
    owner = owner_path(root, name, target, profile, outputs)
    value = previous_owner(root, name, target, profile, outputs)
    if value is None:
        print(f'{name}: no owned outputs to clean')
        return
    selected_nodes = {p: node for p, node in value['nodes'].items() if any(p == d or p.startswith(d + '/') for d in disposable)}
    need(all(node['kind'] == 'missing' or value.get('owned_nodes', {}).get(p, value['schema'] == 1) for p, node in selected_nodes.items()),
         f'{name}: refusing to clean pre-existing, unowned outputs')
    # Committed archives and any tracked descendants are shared project inputs.
    git = shutil.which('git')
    in_repository = any((p / '.git').exists() for p in (root, *root.parents))
    need(git or not in_repository, 'git is required to protect version-controlled outputs during clean')
    if git:
        tracked = subprocess.run([git, '-C', str(root), 'ls-files', '-z', '--', *disposable], capture_output=True)
        need(tracked.returncode == 0 or not in_repository, 'cannot verify version-controlled outputs')
        need(not tracked.stdout, f'{name}: refusing to clean version-controlled outputs')
    # Validate the entire set before removing anything. Preserve changed outputs.
    need(snapshot(root, disposable, allow_missing=True) == selected_nodes, f'{name}: outputs changed since build; refusing clean')
    for relative in disposable:
        path = path_in(root, relative)
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    receipt.unlink(missing_ok=True)
    if len(disposable) != len(outputs):
        retained = metadata(root, name, target, profile, outputs)
        retained['state'] = 'cleaned'
        retained['owned_nodes'] = {p: value.get('owned_nodes', {}).get(p, value['schema'] == 1) for p in retained['nodes']}
        atomic_write(owner, json.dumps(retained, indent=2) + '\n')
    else:
        owner.unlink(missing_ok=True)
    retire_legacy_records(root, name, target, profile, outputs)


def invalidate(root, name, target, profile, outputs):
    receipt = receipt_path(root, name, target, profile, outputs)
    owner = owner_path(root, name, target, profile, outputs)
    previous = previous_owner(root, name, target, profile, outputs)
    value = metadata(root, name, target, profile, outputs)
    value['state'] = 'pending'
    value['owned_nodes'] = {p: bool(previous and previous.get('owned_nodes', {}).get(p, previous['schema'] == 1)
                                   and previous.get('nodes', {}).get(p) == node) for p, node in value['nodes'].items()}
    for relative in outputs:
        path = path_in(root, relative)
        if path.is_dir():
            need(previous and previous.get('owned_nodes', {}).get(relative, previous['schema'] == 1),
                 f'{name}: existing output directory has no matching ownership receipt: {relative}')
            current = snapshot(root, [relative])
            need(set(current) <= set(previous.get('nodes', {})),
                 f'{name}: output directory contains unrecorded files: {relative}')
            if previous.get('roots', {}).get(relative):
                need(file_state(path)[:2] == previous['roots'][relative][:2], f'{name}: output directory was replaced: {relative}')
    atomic_write(owner, json.dumps(value, indent=2) + '\n')
    receipt.unlink(missing_ok=True)
    retire_legacy_records(root, name, target, profile, outputs)


def hold_lock(root, owner_pid):
    """Hold a kernel lock until the native owner's pipe closes.

    Abrupt process death releases the lock in the OS. The directory remains a
    compatibility marker for older executors; a dead protocol-2 marker can be
    reclaimed only while holding the exclusive kernel lock.
    """
    marker = path_in(root, '.buoy/build-writer')
    filename = path_in(root, '.buoy/build.lock')
    filename.parent.mkdir(parents=True, exist_ok=True)
    with filename.open('a+b') as stream:
        if os.name == 'nt':
            import msvcrt
            stream.seek(0, 2)
            if not stream.tell():
                stream.write(b'\0')
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if marker.exists():
            record_file = marker / 'owner.json'
            previous = load_json(record_file) if record_file.is_file() else {}
            need(previous.get('protocol') == 2 and previous.get('host') == socket.gethostname(),
                 f'legacy or unknown build claim at {marker}; confirm its processes stopped before removing it')
            shutil.rmtree(marker)
        marker.mkdir()
        token = uuid.uuid4().hex
        try:
            atomic_write(marker / 'owner.json', json.dumps(dict(protocol=2, pid=owner_pid, helper_pid=os.getpid(),
                          host=socket.gethostname(), started_at=time.time(), token=token)))
            print('BUOY_BUILD_LOCKED', flush=True)
            sys.stdin.buffer.read(1)
        finally:
            if marker.exists() and load_json(marker / 'owner.json').get('token') == token:
                shutil.rmtree(marker)


def plan(args):
    config_path = Path(args.config).resolve()
    root = config_path.parent
    config = load_json(config_path)
    need(isinstance(config, dict) and type(config.get('schema')) is int and config['schema'] == 1,
         'build configuration requires schema: 1')
    need(set(config) <= {'schema', 'compiler', 'packager', 'recipes'}, 'unknown build configuration field')
    recipes = config.get('recipes')
    need(isinstance(recipes, dict) and recipes, 'recipes must be a nonempty object')
    for name, recipe in recipes.items():
        need(re.fullmatch(r'[a-z][a-z0-9_-]*', name), f'invalid recipe name: {name}')
        need(isinstance(recipe, dict), f'{name}: recipe must be an object')
        need(set(recipe) <= {'kind', 'needs', 'path', 'inputs', 'outputs', 'checks', 'bundled_packages', 'argv', 'check_argv', 'check_all_targets', 'targets', 'profiles', 'timeout'}, f'{name}: unknown recipe field')
        need(recipe.get('kind') in ('package', 'command', 'group'), f'{name}: unknown recipe kind')
        common = {'kind', 'needs', 'inputs', 'targets', 'profiles', 'timeout'}
        fields = {'package': {'path', 'checks', 'bundled_packages'},
                  'command': {'argv', 'check_argv', 'check_all_targets', 'outputs'}, 'group': set()}
        need(set(recipe) <= common | fields[recipe['kind']], f'{name}: fields do not match recipe kind')
        if 'check_all_targets' in recipe:
            need(type(recipe['check_all_targets']) is bool, f'{name}: check_all_targets must be Boolean')
        for dependency in strings(recipe.get('needs', []), 'needs'):
            need(dependency in recipes, f'{name}: missing dependency {dependency}')
    # Validate all graph references and cycles, including unselected recipes.
    ordered, visiting = [], []
    def visit(name):
        need(name in recipes, f'unknown build recipe: {name}')
        need(name not in visiting, 'build dependency cycle: ' + ' -> '.join(visiting + [name]))
        if name in ordered:
            return
        visiting.append(name)
        for dependency in recipes[name].get('needs', []):
            visit(dependency)
        visiting.pop()
        ordered.append(name)
    for name in recipes:
        visit(name)
    selected = args.names
    need(args.list or selected, 'build requires a recipe name or --list')
    need(not args.list or not selected, '--list does not accept recipe names')
    need(not (args.plan and args.list), '--list and --plan are mutually exclusive')
    if args.deadline is not None:
        seconds = float(args.deadline)
        need(math.isfinite(seconds) and seconds > 0, 'deadline must be positive and finite')
    target = args.target or support.host_target()
    need(target in support.TARGETS, f'unknown target: {target}')
    need(re.fullmatch(r'[a-z][a-z0-9_-]*', args.profile), 'invalid profile')
    need(not args.all_targets or args.command == 'check', '--all-targets requires check')
    report = dict(schema=1, command=args.command, root=root.as_posix(), target=target, profile=args.profile,
                  recipes=sorted(recipes), actions=[], complete=False)
    if args.list:
        return report
    ordered = []
    for name in selected:
        visit(name)
    if args.command == 'clean':
        ordered = []
        def select_clean(name):
            if recipes[name]['kind'] == 'group':
                for child in recipes[name].get('needs', []):
                    select_clean(child)
            elif name not in ordered:
                ordered.append(name)
        for name in selected:
            select_clean(name)
    python = sys.executable
    helper = str(Path(__file__).resolve().parents[1] / 'buoy_build.py')
    base = [python, '-B', helper]
    suffix = '.app' if target.endswith('darwin') else '.exe' if target.endswith('windows') else ''
    values = {'python': python, 'root': str(root), 'target': target, 'profile': args.profile, 'application-suffix': suffix}
    compiler = None
    packager = None
    needs_tool = any('{compiler}' in arg or '{packager}' in arg
                     for name in ordered if recipes[name]['kind'] == 'command'
                     for arg in recipes[name].get('check_argv' if args.command == 'check' else 'argv', []))
    if args.command != 'clean' and (needs_tool or args.compiler or args.packager or config.get('compiler') or config.get('packager')
                                     or os.environ.get('BUOY') or os.environ.get('BPM_PACKAGER')):
        compiler = resolve_compiler(args.compiler or config.get('compiler'), cwd=Path.cwd() if args.compiler else root)
        packager = resolve_packager(args.packager or config.get('packager'), compiler=compiler, cwd=Path.cwd() if args.packager else root)
        values.update(compiler=compiler, packager=packager)
    outputs_seen = []
    # Producer uniqueness is a property of the configuration, not of which
    # roots happen to be selected together in one invocation.
    producers = []
    for producer, recipe in recipes.items():
        produced = recipe.get('outputs', [])
        if recipe['kind'] == 'package':
            manifest_file = path_in(root, recipe.get('path')) / 'manifest.json'
            data = load_json(manifest_file)
            need(isinstance(data, dict) and data.get('name') == producer and isinstance(data.get('version'), str)
                 and re.fullmatch(r'[0-9A-Za-z.+_-]+', data['version']), f'{producer}: invalid package identity')
            produced = [f'packages/{producer}-{data["version"]}.buipkg', f'dist/{producer}-{data["version"]}.buipkg']
        targets = strings(recipe.get('targets', ['host']), 'targets')
        profiles = strings(recipe.get('profiles', ['release']), 'profiles')
        if recipe['kind'] == 'package':
            need(profiles == ['release'], f'{producer}: source packages use the release artifact profile')
            modes = [('package', 'release')]
        else:
            modes = list(itertools.product(dict.fromkeys(support.host_target() if t == 'host' else t for t in targets), dict.fromkeys(profiles)))
        for mode_target, mode_profile in modes:
            mode_values = dict(values, target=mode_target, profile=mode_profile)
            mode_values['application-suffix'] = '.app' if mode_target.endswith('darwin') else '.exe' if mode_target.endswith('windows') else ''
            for relative in strings(produced, 'outputs'):
                output = path_in(root, render(relative, mode_values))
                for prior, prior_name in producers:
                    need(output != prior and not output.is_relative_to(prior) and not prior.is_relative_to(output),
                         f'conflicting output producers or target/profile paths: {producer} and {prior_name}')
                producers.append((output, producer))
    protected_inputs = {str(config_path)}
    executor = getattr(args, 'executor', None)
    if executor:
        binary = Path(executor).resolve()
        protected_inputs.add(str(binary))
        for pattern in ('*.so', '*.so.*', '*.dll', '*.dylib'):
            protected_inputs.update(str(p.resolve()) for p in binary.parent.glob(pattern) if p.is_file())
    for name in ordered:
        recipe = recipes[name]
        kind = recipe['kind']
        ownership_target = 'package' if kind == 'package' else target
        timeout = recipe.get('timeout', 600)
        need(type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= 86400,
             f'{name}: invalid timeout')
        profiles = strings(recipe.get('profiles', ['release']), 'profiles')
        need(args.profile in profiles, f'{name}: unsupported profile {args.profile}')
        supported = strings(recipe.get('targets', ['host'] if kind == 'command' else list(support.TARGETS)), 'targets')
        supported = [support.host_target() if x == 'host' else x for x in supported]
        need(all(x in support.TARGETS for x in supported), f'{name}: invalid target list')
        need(target in supported, f'{name}: target {target} is unavailable; this recipe supports {supported}')
        files = [] if args.command == 'clean' else inputs(root, recipe.get('inputs', []))
        protected_inputs.update(files)
        outputs = [render(x, values) for x in strings(recipe.get('outputs', []), 'outputs')]
        if kind == 'package':
            folder = path_in(root, recipe.get('path'))
            manifest = load_json(folder / 'manifest.json')
            need(isinstance(manifest, dict) and manifest.get('name') == name and isinstance(manifest.get('version'), str)
                 and re.fullmatch(r'[0-9A-Za-z.+_-]+', manifest['version']), f'{name}: invalid package identity')
            need(not outputs, f'{name}: package outputs are derived from manifest')
            archive = f'{name}-{manifest["version"]}.buipkg'
            outputs = ['packages/' + archive, 'dist/' + archive]
            need(args.command == 'clean' or (files and str(folder / 'manifest.json') in files), f'{name}: inputs must include package manifest')
            for tree in ('modules', 'resources', 'link'):
                if args.command != 'clean' and (folder / tree).exists():
                    members = list((folder / tree).rglob('*'))
                    for member in members:
                        path_in(root, member.relative_to(root).as_posix())
                        need(member.is_file() or member.is_dir(), f'{name}: unsupported package input: {member}')
                    actual = [str(p) for p in members if p.is_file()]
                    need(set(actual) <= set(files), f'{name}: inputs must include all {tree} files')
            argv = []
            if args.command != 'clean':
                compiler = compiler or resolve_compiler(args.compiler or config.get('compiler'), cwd=Path.cwd() if args.compiler else root)
                packager = packager or resolve_packager(args.packager or config.get('packager'), compiler=compiler, cwd=Path.cwd() if args.packager else root)
                values.update(compiler=compiler, packager=packager)
                argv = base + ['seal', '--root', str(root), '--name', name, '--path', str(folder), '--compiler', compiler, '--packager', packager]
                if 'checks' in recipe:
                    checks = strings(recipe['checks'], 'checks')
                    need(checks, f'{name}: checks must not be empty')
                    for source in checks:
                        need(str(path_in(root, (folder / source).relative_to(root).as_posix())) in files and source.endswith('.bui'), f'{name}: check source is not staged')
                        argv += ['--source', source]
                targets = list(support.TARGETS) if args.all_targets or args.command == 'build' else [target]
                for checked in targets:
                    argv += ['--target', checked]
                # Use the exact declared transitive package closure; no ambient repository archives.
                closure = []
                visited = set()
                def deps(current):
                    if current in visited:
                        return
                    visited.add(current)
                    for dep in recipes[current].get('needs', []):
                        deps(dep)
                        if dep not in closure:
                            closure.append(dep)
                deps(name)
                for dep in closure:
                    if recipes[dep]['kind'] == 'package':
                        data = load_json(path_in(root, recipes[dep]['path']) / 'manifest.json')
                        archive_path = root / 'packages' / f'{dep}-{data["version"]}.buipkg'
                        if args.command == 'check':
                            support.verify_package_sources(path_in(root, recipes[dep]['path']), archive_path)
                        argv += ['--dependency', str(archive_path)]
                    else:
                        for output in recipes[dep].get('outputs', []):
                            if output.startswith('packages/') and output.endswith('.buipkg'):
                                archive_path = root / render(output, values)
                                if args.command == 'check':
                                    for pattern in recipes[dep].get('inputs', []):
                                        if pattern.endswith('/manifest.json') and not any(c in pattern for c in '*?['):
                                            source = path_in(root, pattern).parent
                                            if load_json(source / 'manifest.json').get('name') == dep:
                                                support.verify_package_sources(source, archive_path)
                                argv += ['--dependency', str(archive_path)]
                for bundled in strings(recipe.get('bundled_packages', []), 'bundled_packages'):
                    need(re.fullmatch(r'[a-z][a-z0-9_-]*', bundled), 'invalid bundled package name')
                    archive_path = support.bundled_package(bundled, compiler)
                    protected_inputs.add(str(archive_path))
                    argv += ['--dependency', str(archive_path)]
                if args.command == 'check':
                    argv += ['--check-only']
                    # Dependencies are checked, not rebuilt/published by this command.
                    for index, part in enumerate(argv):
                        if part == '--dependency':
                            need(Path(argv[index + 1]).is_file(), f'{name}: build dependencies before checking: {argv[index + 1]}')
        elif kind == 'command':
            field = 'check_argv' if args.command == 'check' else 'argv'
            if args.command != 'clean':
                need(field in recipe, f'{name}: no check command; build checks are adapter-specific')
            argv = [] if args.command == 'clean' else [render(x, values) for x in strings(recipe.get(field, []), field)]
            if args.command != 'clean':
                need(argv, f'{name}: empty command')
                if Path(argv[0]).is_absolute():
                    executable = argv[0]
                elif '/' in argv[0] or '\\' in argv[0]:
                    executable = str(path_in(root, argv[0].replace('\\', '/')))
                else:
                    search = os.pathsep.join(str(Path(p) if Path(p).is_absolute() else root / p)
                                             for p in os.environ.get('PATH', os.defpath).split(os.pathsep))
                    executable = shutil.which(argv[0], path=search)
                need(executable and Path(executable).is_file(), f'{name}: executable not found: {argv[0]}')
                argv[0] = str(Path(executable).resolve())
                need(not args.all_targets or recipe.get('check_all_targets') is True, f'{name}: adapter cannot check all targets through this interface')
        else:
            need(not outputs, f'{name}: groups cannot own outputs')
            continue
        for relative in outputs:
            output = path_in(root, relative)
            need(len(Path(relative).parts) >= 2 and relative.split('/')[0] in ('dist', 'packages'), 'outputs must be below dist/ or packages/')
            for prior in outputs_seen:
                need(output != prior and not output.is_relative_to(prior) and not prior.is_relative_to(output), f'conflicting output producers: {relative}')
            outputs_seen.append(output)
        if args.command == 'clean':
            argv = base + ['clean', '--root', str(root), '--name', name, '--target', ownership_target, '--profile', args.profile]
            for output in outputs:
                argv += ['--output', output]
        report['actions'].append(dict(name=name, kind=kind, argv=argv, outputs=outputs,
                                      inputs=files, timeout=timeout,
                                      reason='explicit clean of recorded outputs' if args.command == 'clean' else 'conservative rebuild; incremental reuse is disabled'))
        if args.command == 'clean':
            report['actions'][-1]['retained_outputs'] = [p for p in outputs if p.startswith('packages/')]
            report['actions'][-1]['clean_outputs'] = [p for p in outputs if not p.startswith('packages/')]
        if args.command == 'build' and outputs:
            argv = base + ['record', '--root', str(root), '--name', name, '--target', ownership_target, '--profile', args.profile]
            for output in outputs:
                argv += ['--output', output]
            report['actions'][-1]['record_argv'] = argv
            prepare = list(argv)
            prepare[len(base)] = 'invalidate'
            report['actions'][-1]['prepare_argv'] = prepare
            failure = list(argv)
            failure[len(base)] = 'failed'
            report['actions'][-1]['failure_argv'] = failure
    need(not any(p == Path(item) or Path(item).is_relative_to(p) for p in outputs_seen for item in protected_inputs), 'build output overlaps an input')
    for output in outputs_seen:
        if output.is_file():
            for item in protected_inputs:
                source = Path(item)
                need(not source.is_file() or not os.path.samefile(output, source), 'build output aliases an input file')
    if args.json:
        destination = Path(args.json).resolve()
        helper_root = Path(__file__).resolve().parents[1]
        if helper_root.parent.name == 'versions':
            helper_root = helper_root.parent.parent
        need(destination != helper_root and not destination.is_relative_to(helper_root), 'report overlaps build helper runtime')
        control = root / '.buoy'
        need(destination != control and not destination.is_relative_to(control), 'report overlaps internal build state')
        for recipe in recipes.values():
            for pattern in strings(recipe.get('inputs', []), 'inputs'):
                path_in(root, pattern)
                if destination.is_relative_to(root):
                    relative = destination.relative_to(root).as_posix()
                    need(not (fnmatch.fnmatchcase(relative, pattern) or fnmatch.fnmatchcase(relative, pattern.replace('**/', ''))),
                         'report overlaps build inputs')
        need(str(destination) not in protected_inputs and not any(destination == p or destination.is_relative_to(p) or p.is_relative_to(destination) for p, _ in producers), 'report overlaps build inputs or outputs')
    if compiler:
        report['compiler'] = compiler
        report['packager'] = packager
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    planner = sub.add_parser('plan')
    planner.add_argument('command', choices=('build', 'check', 'clean'))
    planner.add_argument('names', nargs='*')
    planner.add_argument('--config', default='buoy.build.json')
    for option in ('target', 'compiler', 'packager', 'json', 'cancel-file', 'deadline'):
        planner.add_argument('--' + option)
    planner.add_argument('--profile', default='release')
    planner.add_argument('--executor', help=argparse.SUPPRESS)
    for switch in ('plan', 'list', 'explain', 'all-targets'):
        planner.add_argument('--' + switch, action='store_true')
    locker = sub.add_parser('lock')
    locker.add_argument('--root', type=Path, required=True)
    locker.add_argument('--pid', type=int, required=True)
    for action in ('seal', 'record', 'clean', 'invalidate', 'failed'):
        command = sub.add_parser(action)
        command.add_argument('--root', type=Path, required=True)
        command.add_argument('--name', required=True)
        command.add_argument('--target', action='append', default=[])
        command.add_argument('--profile', default='release')
        command.add_argument('--output', action='append', default=[])
        if action == 'seal':
            command.add_argument('--path', type=Path, required=True)
            command.add_argument('--compiler', required=True)
            command.add_argument('--packager', required=True)
            command.add_argument('--dependency', action='append', default=[])
            command.add_argument('--check-only', action='store_true')
            command.add_argument('--source', action='append')
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == 'plan':
        args = planner.parse_intermixed_args(arguments[1:])
        args.action = 'plan'
    else:
        args = parser.parse_args(arguments)
    try:
        if args.action == 'plan':
            print(json.dumps(plan(args), ensure_ascii=False))
        elif args.action == 'lock':
            hold_lock(args.root.resolve(), args.pid)
        elif args.action == 'seal':
            manifest = load_json(args.path / 'manifest.json')
            output = args.root / 'packages' / f'{args.name}-{manifest["version"]}.buipkg'
            support.verify_and_seal(args.path, output, args.dependency, args.target,
                                    args.compiler, args.packager, args.check_only, args.source,
                                    mirrors=[args.root / 'dist' / output.name])
        else:
            need(len(args.target) == 1, 'exactly one target required')
            if args.action == 'invalidate':
                invalidate(args.root.resolve(), args.name, args.target[0], args.profile, args.output)
            else:
                operation = {'record': record, 'clean': clean, 'failed': failed}[args.action]
                operation(args.root.resolve(), args.name, args.target[0], args.profile, args.output)
        return 0
    except (ValueError, OSError, RuntimeError) as error:
        print(f'ahoy build: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
