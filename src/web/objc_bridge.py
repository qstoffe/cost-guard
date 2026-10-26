"""Narrow, typed Objective-C ABI for the in-box AppKit status item (no PyObjC)."""
import ctypes as C
import sys
from threading import current_thread, main_thread

from .process_identity import InstanceConflict

PTR = C.c_void_p
BOOL = C.c_bool
INTEGER = C.c_long
MASK = C.c_ulonglong
DOUBLE = C.c_double
ACTION = C.CFUNCTYPE(None, PTR, PTR, PTR)

# Registered Objective-C classes outlive instances. Their IMP callbacks must too.
_registered_callbacks = []


def require_main_thread():
    if current_thread() is not main_thread():
        raise InstanceConflict("tray_unavailable")


class ObjC:
    def __init__(self):
        require_main_thread()
        if sys.platform != "darwin" or C.sizeof(PTR) != 8:
            raise InstanceConflict("tray_unavailable")
        self.appkit = C.CDLL("/System/Library/Frameworks/AppKit.framework/AppKit")
        self.lib = C.CDLL("/usr/lib/libobjc.A.dylib")
        signatures = {
            "objc_getClass": (PTR, [C.c_char_p]),
            "sel_registerName": (PTR, [C.c_char_p]),
            "objc_allocateClassPair": (PTR, [PTR, C.c_char_p, C.c_size_t]),
            "class_addMethod": (BOOL, [PTR, PTR, PTR, C.c_char_p]),
            "objc_registerClassPair": (None, [PTR]),
            "objc_disposeClassPair": (None, [PTR]),
        }
        for name, (result, arguments) in signatures.items():
            function = getattr(self.lib, name)
            function.restype, function.argtypes = result, arguments
        self.address = C.cast(self.lib.objc_msgSend, PTR).value
        self.messages = {}

    def cls(self, name):
        value = self.lib.objc_getClass(name.encode("ascii"))
        if not value:
            raise InstanceConflict("tray_unavailable")
        return value

    def selector(self, name):
        return self.lib.sel_registerName(name.encode("ascii"))

    def send(self, receiver, name, result=PTR, *arguments):
        # Separate prototypes avoid global objc_msgSend restype/argtypes races and
        # preserve pointer/NSInteger/double ABI on both arm64 and x86_64 macOS.
        types = tuple(kind for kind, _ in arguments)
        key = (result, types)
        if key not in self.messages:
            self.messages[key] = C.CFUNCTYPE(result, PTR, PTR, *types)(self.address)
        return self.messages[key](receiver, self.selector(name), *(value for _, value in arguments))

    def string(self, text):
        return self.send(self.cls("NSString"), "stringWithUTF8String:", PTR,
                         (C.c_char_p, text.encode("utf-8")))

    def target(self, enqueue, tick, failed):
        import uuid
        target_class = self.lib.objc_allocateClassPair(
            self.cls("NSObject"), ("CostGuardMenu_" + uuid.uuid4().hex).encode("ascii"), 0)
        if not target_class:
            raise InstanceConflict("tray_unavailable")
        callbacks = []
        def invoke(action):
            try:
                action()
            except BaseException as error:
                # ctypes must not print/ignore an unhandled Python callback fault.
                failed(error)
        for selector, action in (("openCostGuard:", lambda: enqueue("open")),
                                 ("exitCostGuard:", lambda: enqueue("exit")),
                                 ("pollOwner:", tick)):
            # Only a queue write in native callbacks; no HTTP/browser/account work.
            callback = ACTION(lambda _self, _cmd, _sender, action=action: invoke(action))
            callbacks.append(callback)
            if not self.lib.class_addMethod(target_class, self.selector(selector),
                                            C.cast(callback, PTR), b"v@:@"):
                self.lib.objc_disposeClassPair(target_class)
                raise InstanceConflict("tray_unavailable")
        self.lib.objc_registerClassPair(target_class)
        _registered_callbacks.append((self, callbacks))
        return self.send(self.send(target_class, "alloc"), "init")
