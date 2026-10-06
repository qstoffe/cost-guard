"""Exercise the actual bounded stdlib bridge with an isolated synthetic CLI."""
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from src.accounts.claude_transport import read_claude_auth, read_claude_usage


FAKE = '''
import json,sys,time
mode,log=sys.argv[1:]
if mode == 'auth':
    print(json.dumps({'loggedIn': True, 'subscriptionType': 'pro', 'email':'fake@example.invalid', 'secret':'SECRET'}))
    sys.exit(0)
for line in sys.stdin:
    value=json.loads(line)
    with open(log,'a') as f:f.write(json.dumps(value)+'\\n')
    assert value['type']=='control_request'
    request=value['request']; subtype=request['subtype']; body={}
    if subtype=='initialize':
        body={'account':{'subscriptionType':'Claude Pro','apiProvider':'firstParty'}}
    elif subtype=='get_usage':
        assert request['skip_behaviors'] is True
        if mode=='timeout':time.sleep(30)
        body={'subscription_type':'pro','rate_limits_available':True,'rate_limits':{},'behaviors':'PRIVATE','session':{'model_usage':{}}}
    response={'subtype':'success','request_id':value['request_id'],'response':body}
    if subtype=='get_usage' and mode in ('missing','auth_failure'):
        response={'subtype':'error','request_id':value['request_id'],'error': 'Unknown control request subtype: get_usage' if mode=='missing' else 'Failed to authenticate: OAuth token revoked SECRET'}
    if subtype=='get_usage' and mode=='format':response['response']=[]
    print(json.dumps({'type':'control_response','response':response}),flush=True)
'''


class ClaudeTransportTests(unittest.TestCase):
    def run_fake(self, mode, timeout=2):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); script = root / 'fake.py'; log = root / 'requests.jsonl'
            script.write_text(FAKE)
            commands = []
            def command(args):
                commands.append(args)
                return [sys.executable, str(script), mode, str(log)]
            with patch('src.accounts.claude_transport._command', side_effect=command):
                result = read_claude_auth() if mode == 'auth' else read_claude_usage(timeout_seconds=timeout)
            requests = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
            return result, commands, requests

    def test_only_two_metadata_requests_no_model_prompt_and_no_persistence(self):
        result, commands, requests = self.run_fake('success')
        self.assertEqual('available', result.availability)
        self.assertNotIn('behaviors', result.usage); self.assertNotIn('session', result.usage)
        self.assertEqual(['initialize', 'get_usage'], [r['request']['subtype'] for r in requests])
        for flag in ('--no-session-persistence','--strict-mcp-config','--no-chrome'):
            self.assertIn(flag, commands[0])
        self.assertIn('{"disableAllHooks":true}', commands[0])

    def test_method_absence_auth_rejection_and_changed_shape_are_safe(self):
        for mode, reason in (('missing','method_missing'), ('auth_failure','auth_failure'), ('format','format_changed')):
            result, _, _ = self.run_fake(mode)
            self.assertEqual(reason, result.reason)
            self.assertNotIn('SECRET', repr(result))
            self.assertIsNone(result.usage)

    def test_timeout_is_bounded_and_helper_is_reaped(self):
        start = time.monotonic()
        result, _, _ = self.run_fake('timeout', timeout=.2)
        self.assertEqual('timeout', result.reason)
        self.assertLess(time.monotonic() - start, 8)
        # TemporaryDirectory removal above also proves closed handles on Windows.

    def test_auth_metadata_allowlist_and_missing_cli(self):
        result, _, _ = self.run_fake('auth')
        self.assertNotIn('secret', result)
        with patch('src.accounts.claude_transport._command', return_value=None):
            self.assertIsNone(read_claude_auth())
            self.assertEqual('cli_missing', read_claude_usage().reason)


if __name__ == '__main__':
    unittest.main()
