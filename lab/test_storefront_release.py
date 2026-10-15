"""Verify promotion times without changing deployment identity or evidence."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import delivery_promote as promote


class StorefrontRelease(unittest.TestCase):
    def test_first_promotion_time_survives_reverification_and_changes_on_redeployment(self):
        deployment={'fingerprint':'a'*64,'fields':{'software_version':'1.2.0','source_sha':'b'*40,'image':'image@sha256:abc'}}
        with tempfile.TemporaryDirectory() as folder, patch.object(promote,'RECORDS',Path(folder)), patch.object(promote,'apply') as apply, patch.object(promote,'retain',return_value={'sha256':'c'*64,'blob':'retained'}):
            first=promote.save_verification('integration',deployment,{'state':'verified','verified_at':'2026-10-15T18:00:00Z'})
            repeat=promote.save_verification('integration',deployment,{'state':'verified','verified_at':'2026-10-15T19:00:00Z'})
            self.assertEqual(repeat['promoted_at'],first['verified_at'])
            cm=apply.call_args.args[0]
            self.assertEqual(cm['metadata']['namespace'],'lab-delivery-integration')
            self.assertEqual(json.loads(cm['data']['release.json'])['source_sha'],'b'*40)
            next_release={**deployment,'fingerprint':'d'*64}
            next_value=promote.save_verification('integration',next_release,{'state':'verified','verified_at':'2026-10-16T18:00:00Z'})
            self.assertEqual(next_value['promoted_at'],'2026-10-16T18:00:00Z')
            self.assertNotEqual(cm['metadata']['name'],apply.call_args.args[0]['metadata']['name'])

    def test_historical_verification_does_not_invent_promotion_time(self):
        deployment={'fingerprint':'a'*64,'fields':{'source_sha':'b'*40,'image':'old'}}
        with tempfile.TemporaryDirectory() as folder, patch.object(promote,'RECORDS',Path(folder)), patch.object(promote,'apply'), patch.object(promote,'retain',return_value={}):
            (Path(folder)/'integration.json').write_text(json.dumps({'deployment':deployment}))
            result=promote.save_verification('integration',deployment,{'state':'verified','verified_at':'2026-10-15T18:00:00Z'})
            self.assertIsNone(result['promoted_at'])


if __name__=='__main__':unittest.main()
