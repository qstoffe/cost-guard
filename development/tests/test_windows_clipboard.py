"""Win32 clipboard ownership/failure contracts; never access the real clipboard."""
import ctypes as c
import unittest
from unittest.mock import Mock, call, patch

from src.web.win32_clipboard import copy_text


class ClipboardTests(unittest.TestCase):
    def setUp(self):
        self.user, self.kernel = Mock(), Mock()
        self.allocations = {}
        self.next_handle = 0x100000000
        def allocate(flags, size):
            self.assertEqual(2, flags)
            self.next_handle += 1
            self.allocations[self.next_handle] = c.create_string_buffer(size)
            return self.next_handle
        self.kernel.GlobalAlloc.side_effect = allocate
        self.kernel.GlobalLock.side_effect = lambda handle: c.addressof(self.allocations[handle])
        self.user.OpenClipboard.return_value = True
        self.user.EmptyClipboard.return_value = True
        self.user.SetClipboardData.side_effect = lambda _, handle: handle
        self.user.RegisterClipboardFormatW.side_effect = [49152, 49153]
        self.libraries = patch('src.web.win32_clipboard.c.WinDLL', create=True,
                               side_effect=lambda name, **_: self.user if name == 'user32' else self.kernel)
        self.sleep = patch('src.web.win32_clipboard.time.sleep')
        self.libraries.start()
        self.pause = self.sleep.start()
        self.addCleanup(self.libraries.stop)
        self.addCleanup(self.sleep.stop)

    def test_unicode_complete_url_and_history_exclusions_transfer_allocations_to_os(self):
        url = 'http://127.0.0.1:49123/#bootstrap=synthetic-å-😀'

        copy_text(123, url)

        self.user.OpenClipboard.assert_called_once_with(123)
        self.user.RegisterClipboardFormatW.assert_has_calls([
            call('CanIncludeInClipboardHistory'), call('CanUploadToCloudClipboard')])
        transfers = self.user.SetClipboardData.call_args_list
        self.assertEqual([49152, 49153, 13], [entry.args[0] for entry in transfers])
        self.assertEqual(bytes(4), self.allocations[transfers[0].args[1]].raw)
        self.assertEqual(bytes(4), self.allocations[transfers[1].args[1]].raw)
        self.assertEqual(url.encode('utf-16-le') + b'\0\0', self.allocations[transfers[2].args[1]].raw)
        self.kernel.GlobalFree.assert_not_called()
        self.user.CloseClipboard.assert_called_once()
        self.pause.assert_not_called()
        self.assertEqual(c.c_size_t, self.kernel.GlobalAlloc.argtypes[1])
        self.assertEqual(c.c_void_p, self.kernel.GlobalLock.restype)

    def test_busy_clipboard_is_bounded_preserves_contents_frees_memory_and_can_retry(self):
        self.user.OpenClipboard.return_value = False
        with self.assertRaisesRegex(OSError, '^clipboard_unavailable$'):
            copy_text(123, 'synthetic')
        self.assertEqual(5, self.user.OpenClipboard.call_count)
        self.assertEqual([call(0.02)] * 4, self.pause.call_args_list)
        self.user.EmptyClipboard.assert_not_called()
        self.user.CloseClipboard.assert_not_called()
        self.kernel.GlobalFree.assert_called_once()
        self.user.OpenClipboard.return_value = True
        copy_text(123, 'retry')
        self.user.CloseClipboard.assert_called_once()

    def test_failed_text_transfer_frees_only_untransferred_memory_and_closes(self):
        self.user.SetClipboardData.side_effect = lambda kind, handle: 0 if kind == 13 else handle
        with self.assertRaisesRegex(OSError, '^clipboard_unavailable$'):
            copy_text(123, 'private text not echoed')
        text_handle = self.user.SetClipboardData.call_args.args[1]
        self.kernel.GlobalFree.assert_called_once_with(text_handle)
        self.user.CloseClipboard.assert_called_once()

    def test_failed_history_exclusion_does_not_publish_secret(self):
        self.user.SetClipboardData.side_effect = lambda *_: 0
        with self.assertRaisesRegex(OSError, '^clipboard_unavailable$'):
            copy_text(123, 'private')
        self.assertEqual([49152], [entry.args[0] for entry in self.user.SetClipboardData.call_args_list])
        self.assertEqual(2, self.kernel.GlobalFree.call_count)
        self.user.CloseClipboard.assert_called_once()

    def test_failed_allocation_never_opens_or_frees_clipboard(self):
        self.kernel.GlobalAlloc.side_effect = None
        self.kernel.GlobalAlloc.return_value = 0
        with self.assertRaisesRegex(OSError, '^clipboard_unavailable$'):
            copy_text(123, 'private')
        self.user.OpenClipboard.assert_not_called()
        self.kernel.GlobalFree.assert_not_called()

    def test_failed_lock_releases_allocation_without_opening_clipboard(self):
        self.kernel.GlobalLock.side_effect = None
        self.kernel.GlobalLock.return_value = 0
        with self.assertRaisesRegex(OSError, '^clipboard_unavailable$'):
            copy_text(123, 'private')
        self.kernel.GlobalFree.assert_called_once()
        self.user.OpenClipboard.assert_not_called()

    def test_failed_empty_closes_clipboard_and_releases_allocation(self):
        self.user.EmptyClipboard.return_value = False
        with self.assertRaisesRegex(OSError, '^clipboard_unavailable$'):
            copy_text(123, 'private')
        self.kernel.GlobalFree.assert_called_once()
        self.user.CloseClipboard.assert_called_once()
        self.user.SetClipboardData.assert_not_called()

    def test_failed_format_registration_does_not_publish_secret(self):
        self.user.RegisterClipboardFormatW.side_effect = None
        self.user.RegisterClipboardFormatW.return_value = 0
        with self.assertRaisesRegex(OSError, '^clipboard_unavailable$'):
            copy_text(123, 'private')
        self.kernel.GlobalFree.assert_called_once()
        self.user.CloseClipboard.assert_called_once()
        self.user.SetClipboardData.assert_not_called()


if __name__ == '__main__':
    unittest.main()
