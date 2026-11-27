"""Admission persistante : tests sans modèle, réseau ni dépense réelle."""
import tempfile
import threading
import time
import unittest
from pathlib import Path
from arpagona_api.store import Store

def reserve_in_process(path, uid, gate, results):
    store = Store(path)
    try:
        gate.wait(timeout=5)
        results.put(store.budget.reserve('pid-'+str(__import__('os').getpid()), uid, .75, 1, time.time()))
    finally:
        store.close()


class BudgetAdmission(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name)/'test.db')
        self.store = Store(self.path)
        self.uid = self.store.add_user('qa', 'QA', 'synthetique-password-2026')
        self.now = time.time()

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def reserve(self, key, amount=.5, day=1.0):
        return self.store.budget.reserve(key, self.uid, amount, day, self.now)

    def test_reserves_before_cost_is_known(self):
        self.assertEqual(self.reserve('a'), 'ok')
        self.assertEqual(self.reserve('b'), 'ok')
        self.assertEqual(self.reserve('c'), 'limite')

    def test_release_only_after_known_final_cost(self):
        self.reserve('a')
        self.store.budget.settle('a', .1, self.now)
        self.assertEqual(self.reserve('b', .9), 'ok')
        self.assertEqual(self.reserve('c', .01), 'limite')

    def test_unknown_and_invalid_usage_fail_closed(self):
        for bad in (None, float('nan'), float('inf'), -1, 'invalide', True):
            with self.subTest(bad=bad):
                # Une base distincte par cas ne masque pas une transition précédente.
                key = repr(bad)
                self.store._run('DELETE FROM budget_entries')
                self.reserve(key)
                self.store.budget.settle(key, bad, self.now)
                self.assertEqual(self.reserve('next'), 'inconnu')

    def test_reservation_survives_reopen_and_day_boundary(self):
        self.reserve('a', 1)
        self.store.close()
        self.store = Store(self.path)
        self.assertEqual(self.store.budget.reserve('b', self.uid, 1, 1, self.now+172800), 'limite')

    def test_same_key_is_never_admitted_twice(self):
        self.assertEqual(self.reserve('a'), 'ok')
        self.assertEqual(self.reserve('a'), 'existant')

    def test_settlement_cannot_be_rewritten(self):
        self.reserve('a')
        self.store.budget.settle('a', .5, self.now)
        self.store.budget.settle('a', 0, self.now)
        self.assertEqual(self.reserve('b', .6), 'limite')

    def test_unknown_cannot_be_automatically_cleared(self):
        self.reserve('a')
        self.store.budget.settle('a', None, self.now)
        self.store.budget.settle('a', 0, self.now)
        self.assertEqual(self.reserve('b'), 'inconnu')

    def test_completed_cost_expires_but_active_reservation_does_not(self):
        self.reserve('a')
        self.store.budget.settle('a', .5, self.now)
        self.assertEqual(self.store.budget.reserve('b', self.uid, 1, 1, self.now+86401), 'ok')

    def test_invalid_configuration_refused(self):
        for bad in (0, -1, float('nan'), float('inf'), True):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.reserve('bad', amount=bad)

    def test_legacy_unknown_cost_blocks_instead_of_disappearing(self):
        conv = self.store.conversation_for(self.uid)
        mid = self.store.start_mission(self.uid, conv['id'], 'legacy', 'Ancien test')
        self.store.finish_mission(mid, 'terminee', cost_usd=None)
        self.assertEqual(self.reserve('next'), 'inconnu')

    def test_legacy_known_cost_is_included(self):
        conv = self.store.conversation_for(self.uid)
        mid = self.store.start_mission(self.uid, conv['id'], 'legacy', 'Ancien test')
        self.store.finish_mission(mid, 'terminee', cost_usd=.8)
        self.assertEqual(self.reserve('next', .3), 'limite')

    def test_actual_overrun_stops_next_admission(self):
        self.reserve('a')
        self.store.budget.settle('a', 1.2, self.now)
        self.assertEqual(self.reserve('b'), 'limite')

    def test_rounding_never_rounds_limit_up(self):
        self.assertEqual(self.reserve('a', .5000001, 1.0000001), 'ok')
        self.assertEqual(self.reserve('b', .5, 1.0000001), 'limite')

    def test_reconciliation_requires_admin_evidence_and_leaves_audit(self):
        self.reserve('a')
        self.store.budget.settle('a', None, self.now)
        member = self.store.add_user('member', 'Membre', 'synthetique-password-2026')
        with self.assertRaises(PermissionError):
            self.store.budget.reconcile_unknown('a', 0, 'Justificatif fictif de recette', member, self.now)
        with self.assertRaises(ValueError):
            self.store.budget.reconcile_unknown('a', 0, '', self.uid, self.now)
        self.assertEqual(self.reserve('b'), 'inconnu')
        self.store.budget.reconcile_unknown('a', .1, 'Justificatif fictif de recette', self.uid, self.now)
        self.assertEqual(self.reserve('b'), 'ok')
        self.assertTrue(any(r['action']=='budget_rapproche' for r in self.store.audit_rows()))

    def test_cli_requires_confirmation_and_reads_back_receipt(self):
        import subprocess, sys, json
        self.reserve('qa-key')
        self.store.budget.settle('qa-key', None, self.now)
        env = {'ARPAGONA_DB': self.path, 'PYTHONPATH': str(Path(__file__).resolve().parents[1])}
        command = [sys.executable, '-m', 'arpagona_api.manage', 'budget-reconcile', 'qa-key',
                   '--operator', 'qa', '--cost-usd', '.1', '--evidence', 'Justificatif fictif de recette']
        refused = subprocess.run(command, env=env, text=True, capture_output=True, timeout=10)
        self.assertNotEqual(refused.returncode, 0)
        self.assertEqual(self.reserve('next'), 'inconnu')
        accepted = subprocess.run(command+['--confirm'], env=env, text=True, capture_output=True, timeout=10)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        receipt = json.loads(accepted.stdout)
        self.assertEqual(receipt, {'key': 'qa-key', 'state': 'settled', 'actual_micros': 100000})

    def test_export_keeps_financial_holds(self):
        self.reserve('a')
        self.store.budget.settle('a', None, self.now)
        out = self.store.export_data(self.uid)
        self.assertEqual(out['budget'][0]['state'], 'unknown')
        self.assertEqual(out['budget'][0]['key'], 'a')

    def test_legacy_unknown_reconciles_only_with_operator_evidence(self):
        conv = self.store.conversation_for(self.uid)
        mid = self.store.start_mission(self.uid, conv['id'], 'old-qa', 'Ancien test')
        self.store.finish_mission(mid, 'terminee', cost_usd=None)
        self.assertEqual(self.reserve('next'), 'inconnu')
        key = self.store.budget.legacy_unknown()[0]['key']
        self.store.budget.reconcile_unknown(key, .1, 'Facturation fictive de recette vérifiée', self.uid, self.now)
        self.assertEqual(self.store.mission(mid)['cost_usd'], .1)
        self.assertEqual(self.store.budget.snapshot(self.now)['mesure_usd'], .1)
        self.assertEqual(self.reserve('next'), 'ok')

    def test_two_real_processes_cannot_oversubscribe(self):
        import multiprocessing
        ctx = multiprocessing.get_context('spawn')
        gate, results = ctx.Barrier(2), ctx.Queue()
        jobs = [ctx.Process(target=reserve_in_process, args=(self.path, self.uid, gate, results)) for _ in range(2)]
        try:
            for job in jobs: job.start()
            for job in jobs:
                job.join(timeout=10)
                self.assertEqual(job.exitcode, 0)
            self.assertCountEqual([results.get(timeout=2), results.get(timeout=2)], ['ok','limite'])
        finally:
            for job in jobs:
                if job.is_alive(): job.terminate(); job.join(timeout=3)
                job.close()
            results.close()
            results.join_thread()

    def test_two_independent_connections_cannot_oversubscribe(self):
        second = Store(self.path)
        gate = threading.Barrier(2)
        out = []
        def go(store, key):
            gate.wait()
            out.append(store.budget.reserve(key, self.uid, .75, 1, self.now))
        threads = [threading.Thread(target=go,args=(s,k)) for s,k in ((self.store,'a'),(second,'b'))]
        try:
            for t in threads: t.start()
            for t in threads: t.join(timeout=5)
            self.assertTrue(all(not t.is_alive() for t in threads))
            self.assertCountEqual(out, ['ok','limite'])
        finally:
            second.close()

if __name__ == '__main__':
    unittest.main()
