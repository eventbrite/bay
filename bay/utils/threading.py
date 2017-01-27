import sys
import threading


class ExceptionalThread(threading.Thread):
    """
    Thread subclass that allows exceptions to be easily re-raised in the parent.
    """

    def __init__(self, target=None, args=None, kwargs=None, daemon=False):
        threading.Thread.__init__(self, daemon=daemon)
        self.target = target
        self.args = args or tuple()
        self.kwargs = kwargs or {}
        self.__exception = None

    def run_with_exception(self):
        """
        This method should be overriden if you want to subclass this.
        """
        if self.target:
            self.target(*self.args, **self.kwargs)
        else:
            raise NotImplementedError("You must override run_with_exception")

    def run(self):
        """This method should NOT be overriden."""
        try:
            self.run_with_exception()
        except BaseException:
            self.__exception = sys.exc_info()

    def maybe_raise(self):
        if self.__exception is not None:
            raise self.__exception[1]
