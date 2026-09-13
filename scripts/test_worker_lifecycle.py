#!/usr/bin/env python3
"""No LLM/GPU: real wrapper, pipes, Linux processes, hooks and watcher in temp repos."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

SRC = Path(__file__).resolve().parents[1]

FAKE_CLAUDE = r'''#!/usr/bin/env python3
import json, os, pathlib, subprocess, sys, time
c = pathlib.Path(os.environ['LAB_CANDIDATE_DIR'])
assert os.environ['CLAUDE_CODE_DISABLE_BACKGROUND_TASKS'] == '1'
assert os.environ['BASH_DEFAULT_TIMEOUT_MS'] == os.environ['BASH_MAX_TIMEOUT_MS'] == '900000'
mode = os.environ['TEST_MODE']
(c/'code').mkdir(exist_ok=True)
(c/'code/run.sh').write_text('echo foreground run\n')
work = """import os, pathlib, signal, time
c = pathlib.Path(os.environ['LAB_CANDIDATE_DIR'])
if os.environ['TEST_MODE'] in ('detached', 'hang', 'failure'):
    os.setsid()
    if os.fork(): os._exit(0)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
(c/'descendant.pid').write_text(str(os.getpid()))
time.sleep(0.15 if os.environ['TEST_MODE'] == 'foreground' else 3)
(c/'out').mkdir(exist_ok=True)
(c/'out/predictions-search.json').write_text('[1]')
(c/'late-marker').write_text('finished')
"""
(c/'code/train.py').write_text(work)
(c/'code/run.sh').write_text('exec python3 "' + str(c/'code/train.py') + '"\n')
p = subprocess.Popen(['bash', str(c/'code/run.sh')])
while not (c/'descendant.pid').exists(): time.sleep(.01)
if mode == 'foreground':
    assert p.wait() == 0
    (c/'summary.md').write_text('Ran synchronously and checked exit/predictions.\n')
if mode == 'hang': time.sleep(30)
if mode == 'failure': sys.exit(1)
print(json.dumps({'result': 'Training finished.' if mode == 'foreground' else 'Training is pending.',
                  'session_id': 'test', 'is_error': False}), flush=True)
'''


class WorkerLifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='lab-lifecycle-')
        self.root = Path(self.tmp.name)
        shutil.copytree(SRC/'tools', self.root/'tools', ignore=shutil.ignore_patterns('__pycache__'))
        self.cdir = self.root/'candidates/c0001'
        self.cdir.mkdir(parents=True)
        (self.root/'task.md').write_text('Synthetic worker lifecycle test; no labels.\n')
        card = dict(candidate='c0001', operator='draft', instructions='Complete the job.',
                    task_file='task.md', seed=42, parents=[], lineage=[], population=[], best=None,
                    contract=dict(may_write='candidates/c0001', may_read=['task.md'],
                                  write='code/run.sh and summary.md', run='code/run.sh',
                                  predictions='out/predictions-search.json', final='Reuse weights', max_turns=40))
        (self.cdir/'job.json').write_text(json.dumps(card))
        bindir = self.root/'bin'
        bindir.mkdir()
        (bindir/'claude').write_text(FAKE_CLAUDE)
        (bindir/'claude').chmod(0o755)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(('LAB_', 'ANTHROPIC_', 'CLAUDE_'))}
        self.env.update(PATH=str(bindir)+':'+os.environ['PATH'], LAB_ROOT=str(self.root),
                        LAB_CANDIDATE_DIR=str(self.cdir), LAB_JOB=str(self.cdir/'job.json'),
                        LAB_PREDICTIONS_OUT=str(self.cdir/'out/predictions-search.json'),
                        LAB_JOB_WALL_CLOCK_SEC='900', LAB_WATCH_POLL_SEC='.05')

    def tearDown(self):
        self.tmp.cleanup()

    def worker(self, mode):
        return subprocess.run([str(self.root/'tools/lab-worker')], env=dict(self.env, TEST_MODE=mode),
                              capture_output=True, text=True, timeout=12)

    def assert_drained(self, late=True):
        pid = int((self.cdir/'descendant.pid').read_text())
        self.assertFalse(Path(f'/proc/{pid}').exists(), f'descendant {pid} survived')
        if late:
            time.sleep(3.1)  # cross the attempted late-write deadline
            self.assertFalse((self.cdir/'late-marker').exists())
            self.assertFalse((self.cdir/'out/predictions-search.json').exists())

    def test_foreground_completes(self):
        cp = self.worker('foreground')
        self.assertEqual(cp.returncode, 0, cp.stderr)
        self.assertIn('contract met', cp.stdout)
        self.assertTrue((self.cdir/'out/predictions-search.json').exists())
        self.assert_drained(late=False)

    def test_successful_cli_return_with_pending_output_is_invalid(self):
        cp = self.worker('early')  # child retains pipeline FDs: must not wait for their EOF
        self.assertEqual(cp.returncode, 2, cp.stderr)
        self.assertIn('live descendants', cp.stderr)
        self.assertIn('Training is pending', (self.cdir/'summary.md').read_text())
        self.assert_drained()

    def test_setsid_double_fork_is_cleaned(self):
        cp = self.worker('detached')
        self.assertEqual(cp.returncode, 2, cp.stderr)
        self.assertIn('lifecycle violation', (self.cdir/'session.stderr').read_text())
        self.assert_drained()

    def test_cli_failure_also_cleans_detached_work(self):
        cp = self.worker('failure')
        self.assertEqual(cp.returncode, 2, cp.stderr)
        self.assertTrue((self.cdir/'summary.md').exists())
        self.assert_drained()

    def watch(self, wid, command, candidate=True, budget=.01):
        wd = self.root/'.lab/watch'
        wd.mkdir(parents=True, exist_ok=True)
        entry = dict(id=wid, cmd=command, log=f'.lab/watch/{wid}.log', budget_min=budget,
                     status='running', started='2026-09-12T00:00:00Z', candidate_dir=str(self.cdir) if candidate else None)
        (wd/f'{wid}.json').write_text(json.dumps(entry))
        return [str(self.root/'tools/lab'), 'watch', '_run', wid]

    def test_watcher_budget_cleans_detached_descendants_before_settlement(self):
        cp = subprocess.run(self.watch('timeout', [str(self.root/'tools/lab-worker')]),
                            env=dict(self.env, TEST_MODE='hang'), capture_output=True, text=True, timeout=12)
        self.assertEqual(cp.returncode, 0, cp.stderr)
        entry = json.loads((self.root/'.lab/watch/timeout.json').read_text())
        self.assertEqual(entry['status'], 'killed')
        self.assertIn('wall-clock', entry['kill_reason'])
        self.assert_drained()

    def test_watcher_signal_request_cleans_and_operator_watch_is_unaffected(self):
        op = self.watch('operator', [sys.executable, '-c', 'import time; time.sleep(5)'], candidate=False, budget=1)
        # These are short foreground test children; the enclosing test has a timeout.
        with subprocess.Popen(op, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as operator:
            command = self.watch('kill', [str(self.root/'tools/lab-worker')], budget=1)
            with subprocess.Popen(command, env=dict(self.env, TEST_MODE='hang'),
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE) as candidate:
                deadline = time.monotonic() + 5
                while not (self.cdir/'descendant.pid').exists() and time.monotonic() < deadline:
                    time.sleep(.02)
                (self.root/'.lab/watch/kill.kill').write_text('synthetic stop request')
                _, err = candidate.communicate(timeout=12)
                self.assertEqual(candidate.returncode, 0, err)
            entry = json.loads((self.root/'.lab/watch/kill.json').read_text())
            self.assertEqual(entry['status'], 'killed')
            self.assertIsNone(operator.poll(), 'unrelated operator watcher was killed')
            self.assert_drained()
            operator.communicate(timeout=12)
            self.assertEqual(operator.returncode, 0)
        self.assertEqual(json.loads((self.root/'.lab/watch/operator.json').read_text())['status'], 'done')

    def test_watcher_normal_exit_also_drains_detached_candidate_work(self):
        code = '''import os, pathlib, signal, time
c = pathlib.Path(os.environ['LAB_CANDIDATE_DIR'])
if os.fork():
    while not (c/'descendant.pid').exists(): time.sleep(.01)
    os._exit(0)
os.setsid()
if os.fork(): os._exit(0)
signal.signal(signal.SIGTERM, signal.SIG_IGN)
(c/'descendant.pid').write_text(str(os.getpid()))
time.sleep(3)
(c/'late-marker').write_text('late')
'''
        cp = subprocess.run(self.watch('early-raw', [sys.executable, '-c', code], budget=1),
                            env=self.env, capture_output=True, text=True, timeout=12)
        self.assertEqual(cp.returncode, 0, cp.stderr)
        entry = json.loads((self.root/'.lab/watch/early-raw.json').read_text())
        self.assertEqual((entry['status'], entry['exit_code']), ('failed', 2))
        self.assert_drained()

    def test_worker_cannot_launch_nested_watch_at_command_boundary(self):
        for subcmd in ('start', '_run'):
            args = ['start', '--op', 'nested', '--budget-min', '1', '--', 'true'] if subcmd == 'start' else ['_run', 'missing']
            cp = subprocess.run([str(self.root/'tools/lab'), 'watch', *args],
                                env=dict(self.env, LAB_ROLE='worker'), capture_output=True, text=True, timeout=5)
            self.assertNotEqual(cp.returncode, 0)
            self.assertIn('nested watchers', cp.stderr)
        self.assertFalse((self.root/'.lab/watch').exists())

    def test_hook_background_guards_and_foreground_allowances(self):
        blocked = [('bash code/run.sh', True), ('bash code/run.sh &', False),
                   ('nohup bash code/run.sh', False), ('setsid bash code/run.sh', False),
                   ('disown', False), ('/usr/bin/setsid bash code/run.sh', False),
                   ("python3 -c '\nx = 1 & 3\nprint(x)\n'", True),
                   ('true; nohup bash code/run.sh', False),
                   ("python3 - <<'PY' &\nprint(1 & 3)\nPY", False),
                   ("nohup python3 - <<'PY'\nprint(1 & 3)\nPY", False),
                   ("python3 - <<'PY'\nprint(1 & 3)\nPY\nbash code/run.sh &", False),
                   ("python3 - <<'PY'\nprint(1 & 3)\nPY\nsetsid bash code/run.sh", False),
                   ("cat <<EOF\nexample\nEOF\ntools/lab watch _run nested", False),
                   ('tools/lab watch start --op train --budget-min 15 -- bash code/run.sh', False)]
        allowed = [('timeout 60 bash code/run.sh', False), ('bash code/run.sh > train.log 2>&1', False),
                   ('bash code/run.sh &> train.log', False),
                   ('bash code/run.sh && test -s out/predictions-search.json', False),
                   ('echo "a & b"', False), ("printf '%s\\n' '&'", False),
                   ("printf '%s\\n' 'Do not use nohup or setsid'", False),
                   ("printf '%s\\n' 'tools/lab watch start --op train'", False),
                   ("python3 - <<'PY'\nprint(1 & 3)\nPY", False),
                   ("python3 -c '\nx = 1 & 3\nprint(x)\n'", False),
                   ('python3 - <<"PY" > train.log 2>&1\nprint(1 & 3)\nPY', False),
                   ("cat <<-EOF\n\tnohup setsid &\n\tEOF", False),
                   ("cat <<A <<'B'\n&\nA\nnohup setsid &\nB", False)]
        for command, background in blocked + allowed:
            with self.subTest(command=command, background=background):
                data = dict(tool_name='Bash', tool_input=dict(command=command, run_in_background=background))
                cp = subprocess.run([str(SRC/'.claude/hooks/guard.sh')], input=json.dumps(data),
                                    env=dict(self.env, LAB_ROLE='worker'), capture_output=True, text=True, timeout=5)
                self.assertEqual(cp.returncode, 2 if (command, background) in blocked else 0, cp.stderr)
        data = dict(tool_name='Bash', tool_input=dict(command=blocked[-1][0]))
        cp = subprocess.run([str(SRC/'.claude/hooks/guard.sh')], input=json.dumps(data), env=self.env,
                            capture_output=True, text=True, timeout=5)
        self.assertEqual(cp.returncode, 0, cp.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
