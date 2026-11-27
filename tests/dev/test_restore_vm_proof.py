"""Garde-fous du contrôleur ; ne remplacent pas la vraie recette Proxmox."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'dev/restore_vm_proof.py'
spec=importlib.util.spec_from_file_location('restore_vm_proof',SCRIPT)
assert spec and spec.loader
proof=importlib.util.module_from_spec(spec)
spec.loader.exec_module(proof)

class RestoreSafety(unittest.TestCase):
    def test_source_never_a_target(self):
        with self.assertRaises(ValueError):proof.target_guard(100,100,{100})

    def test_existing_target_never_overwritten(self):
        with self.assertRaises(ValueError):proof.target_guard(100,101,{100,101})

    def test_fresh_target_and_exact_network_properties(self):
        proof.target_guard(100,101,{100})
        self.assertEqual(proof.network_keys({'net0':'x','net1':'y','networks':'z','onboot':1}),['net0','net1'])

    def test_exact_archive_digest_and_no_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'vzdump-qemu-100-2026_11_27-12_15_21.vma.zst';p.write_bytes(b'fixture sans aucune donnee client')
            expected=hashlib.sha256(p.read_bytes()).hexdigest()
            proof.archive_guard(p,expected,100)
            with self.assertRaises(ValueError):proof.archive_guard(p,expected,101)
            bad=Path(d)/'from-offhost.vma.zst';bad.write_bytes(p.read_bytes())
            with self.assertRaises(ValueError):proof.archive_guard(bad,expected)
            with self.assertRaises(ValueError):proof.archive_guard(p,'0'*64)
            link=Path(d)/'link';link.symlink_to(p)
            with self.assertRaises(ValueError):proof.archive_guard(link,expected)
            with self.assertRaises(ValueError):proof.archive_guard(p,expected.upper())

    def test_dry_run_does_not_require_hypervisor_or_open_files(self):
        result=subprocess.run([sys.executable,str(SCRIPT),'--archive','/nonexistent/archive',
            '--sha256','0'*64,'--target-vmid','101','--data-helper','/nonexistent/helper',
            '--memory-helper','/nonexistent/memory','--expected-data','/nonexistent/data',
            '--expected-memory','/nonexistent/facts','--receipt','/nonexistent/receipt'],
            capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue(json.loads(result.stdout)['dry_run'])

from unittest.mock import patch as mock_patch

class GuestTransport(unittest.TestCase):
    def test_ascii_transport_preserves_utf8_program(self):
        code='import json;print(json.dumps({"preuve":"épreuve"},ensure_ascii=False))'
        wire=proof.wire_program(code)
        self.assertTrue(wire.isascii())
        r=subprocess.run([sys.executable,'-c',wire],capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(r.stdout),{'preuve':'épreuve'})

    def test_one_launch_and_stable_pid_while_polling(self):
        replies=[json.dumps({'pid':42}),json.dumps({'exited':0}),
                 json.dumps({'exited':1,'exitcode':0,'out-data':'{"ok":true}'})]
        with mock_patch.object(proof,'command',side_effect=replies) as call, mock_patch.object(proof.time,'sleep'):
            self.assertEqual(proof.guest(103,'print(1)'),{'ok':True})
        self.assertEqual(call.call_count,3)
        self.assertIn('--synchronous',call.call_args_list[0].args)
        self.assertEqual(call.call_args_list[1].args[-1],'42')
        self.assertEqual(call.call_args_list[2].args[-1],'42')

    def test_uncertain_launch_is_never_replayed(self):
        exc=subprocess.CalledProcessError(255,['qm'],stderr='guest-exec got timeout')
        with mock_patch.object(proof,'command',side_effect=exc) as call:
            with self.assertRaises(proof.GuestError) as caught:proof.guest(103,'print(1)')
        self.assertEqual(call.call_count,1)
        self.assertEqual(caught.exception.details['state'],'uncertain')

    def test_truncated_or_failed_guest_is_not_success(self):
        for result in ({'exited':1,'exitcode':0,'out-data':'{}','out-truncated':1},
                       {'exited':1,'exitcode':1,'err-data':'fixture failure'}):
            with self.subTest(result=result), mock_patch.object(proof,'command',side_effect=[json.dumps({'pid':42}),json.dumps(result)]):
                with self.assertRaises(proof.GuestError):proof.guest(103,'print(1)')

    def test_shared_disk_passthrough_and_network_rejected(self):
        good={'onboot':0,'scsi0':'local-lvm:vm-103-disk-0'}
        proof.isolation_guard(good,103)
        for extra in ({'net0':'virtio'},{'hostpci0':'0000:01:00.0'},
                      {'args':'fixture'},{'onboot':1},{'ide2':'local-lvm:vm-100-cloudinit'}):
            with self.subTest(extra=extra),self.assertRaises(ValueError):proof.isolation_guard(good|extra,103)

if __name__=='__main__':unittest.main()
