import errno
import os

if os.name == "nt":
    import msvcrt
else:
    import fcntl

BUSY_ERRNOS = (errno.EACCES, errno.EAGAIN, errno.EDEADLK)


def try_lock(handle):
    try:
        if os.name == "nt":
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        if error.errno not in BUSY_ERRNOS:
            raise
        return False
    return True
