import contextlib
import shutil
import threading
import time

from .colors import CYAN, GREEN, RED, YELLOW
from ..utils.threading import ExceptionalThread


UP_ONE = "\033[A\033[1000D"
CLEAR_LINE = "\033[2K"
INDENT_CHARS = "  "

console_lock = threading.Lock()


class Task:
    """
    Something that can be started (by being created), have progress reported, and then finished.
    It can also have a number of sub-tasks, and arbitary lines of extra information
    that should be shown to the user alongside progress messages or a progress bar.
    """

    FLAVOR_NEUTRAL = "neutral"
    FLAVOR_GOOD = "good"
    FLAVOR_BAD = "bad"
    FLAVOR_WARNING = "warning"

    def __init__(self, name, parent=None):
        self.name = name
        # Any parent tasks to trigger updates in
        self.parent = parent
        with console_lock:
            if self.parent is not None:
                self.parent.subtasks.append(self)
        # Sub tasks to show under this one
        self.subtasks = []
        # The current status message
        self.status = None
        # The current progress from 0 - 1
        self.progress = None
        # The current status flavor (turns into a colour)
        self.status_flavor = self.FLAVOR_NEUTRAL
        # Extra lines of information to show underneath the task
        self.extra_info = []
        # If the task is complete
        self.finished = False
        # Number of lines we had previously cleared
        self.cleared_lines = 0
        # If the output is currently "paused" for other things to write to the console
        self.output_paused = False
        # Run update
        self.update()

    def update(self, status=None, status_flavor=None, progress=None):
        """
        Update either the status message, the progress bar, or both.
        If this is the topmost task, this will trigger a reprint on the console.
        """
        if self.finished:
            raise ValueError("You cannot update() a finished task!")
        with console_lock:
            if status is not None:
                self.status = status
            if progress is not None:
                if len(progress) != 2:
                    raise ValueError("Progress must be a 2-tuple of (count, total)")
                self.progress = progress
            if status_flavor is not None:
                self.status_flavor = status_flavor
        # Look for a parent to potentially trigger update on, or print ourselves
        # if there isn't one
        if self.parent is not None:
            self.parent.update()
        else:
            self.clear_and_output()

    def add_extra_info(self, message):
        """
        Adds a line of extra info and triggers updates
        """
        with console_lock:
            self.extra_info.append(message)
        if self.parent is not None:
            self.parent.update()

    def set_extra_info(self, messages):
        """
        Sets all extra info and triggers updates
        """
        with console_lock:
            self.extra_info = messages
        if self.parent is not None:
            self.parent.update()

    def finish(self, **kwargs):
        """
        Marks the task as finished, meaning it can no longer be mutated.
        Used to optimise terminal output only.
        """
        self.update(**kwargs)
        self.finished = True

    def lines(self):
        """
        Returns the number of console lines this task will need to print itself.
        """
        return 1 + sum(subtask.lines() for subtask in self.subtasks) + len(self.extra_info)

    def make_progress_bar(self, count, total, width=30):
        """
        Helper for making progress bar text.
        """
        progress = min(max(count / total, 0), 1)
        bar_width = width - 2
        bar_size = int(bar_width * progress)
        return "[{}{}] {}/{}".format(
            "=" * bar_size,
            " " * (bar_width - bar_size),
            count,
            total,
        )

    def output(self, indent=0):
        """
        Prints the task out to the console along with its subtasks.
        Assumes that the screen is already cleared and the cursor is in the right
        place.
        """
        # Get terminal width
        terminal_width = shutil.get_terminal_size((80, 20)).columns
        # Work out progress text
        progress_string = ""
        if self.progress is not None:
            progress_string = self.make_progress_bar(*self.progress) + " "
        # Work out status text
        status_string = self.status or ""
        if self.status_flavor == self.FLAVOR_BAD:
            status_string = RED(status_string)
        elif self.status_flavor == self.FLAVOR_GOOD:
            status_string = GREEN(status_string)
        elif self.status_flavor == self.FLAVOR_WARNING:
            status_string = YELLOW(status_string)
        # Print out our line
        indent_string = indent * INDENT_CHARS
        print("{}{}: {}{}".format(
            indent_string,
            CYAN(self.name),
            progress_string,
            status_string,
        ), flush=True)
        # Print out extra info
        indent_string = (indent + 1) * INDENT_CHARS
        for info in self.extra_info:
            print(indent_string + info[:terminal_width - (len(indent_string) + 1)].replace("\n", ""), flush=True)
        # Print out subtasks
        for subtask in self.subtasks:
            subtask.output(indent=indent + 1)

    def clear_and_output(self):
        """
        Clears the terminal up to the right line then outputs the information
        of the task.
        """
        # See if output is paused
        if self.output_paused:
            return
        # OK, print
        with console_lock:
            self.last_output_time = time.time()
            # Scroll the terminal down/up enough for any new lines
            needed_lines = self.lines()
            new_lines = needed_lines - self.cleared_lines
            if new_lines > 0:
                print("\n" * new_lines, flush=True, end="")
            elif new_lines < 0:
                print(
                    (UP_ONE + CLEAR_LINE) * abs(new_lines),
                    flush=True,
                    end="",
                )
            self.cleared_lines = needed_lines
            # Move cursor to top of cleared section
            print(
                (UP_ONE + CLEAR_LINE) * needed_lines,
                flush=True,
                end="",
            )
            self.output()

    def _pause_output(self, pause=True):
        """
        Allows the output to be paused and unpaused by finding the parent and doing it there.
        """
        if self.parent is None:
            self.output_paused = pause
            if not pause:
                # Make the output rewrite from where it is
                self.cleared_lines = 0
                self.clear_and_output()
        else:
            self.parent._pause_output(pause)

    @contextlib.contextmanager
    def paused_output(self):
        """
        Context manager that pauses printing of output until it's exited.
        """
        self._pause_output(True)
        yield
        self._pause_output(False)

    @contextlib.contextmanager
    def rate_limit(self, interval=0.1):
        """
        Context manager that rate-limits updates on tasks
        """
        buffered_changes = {"running": True}

        # Thread loop that flushes every interval
        def flusher():
            while buffered_changes['running']:
                # Do any extra_info calls
                if "set_extra_info" in buffered_changes:
                    self.set_extra_info(buffered_changes['set_extra_info'])
                    del buffered_changes['set_extra_info']
                # Do any update calls
                if "update" in buffered_changes:
                    self.update(**buffered_changes['update'])
                    del buffered_changes['update']
                # Sleep
                time.sleep(interval)

        # Fake task object to provide out
        class BufferedTask(object):
            def set_extra_info(self, extra_info):
                self.buffered_changes['set_extra_info'] = extra_info
            def update(self, **kwargs):
                self.buffered_changes['update'] = kwargs

        # Start thread that flushes every interval
        flush_thread = ExceptionalThread(target=flusher, daemon=True)
        flush_thread.start()

        # Run inner code
        yield BufferedTask()

        # Do one more flush and exit
        buffered_changes['running'] = False
        flush_thread.join()


class RootTask(Task):
    """
    Special task subclass that represents the "root" task, the instance that
    has no output of its own but encapsulates all other tasks in the app in order.
    """

    def __init__(self):
        super(RootTask, self).__init__("__root__")

    def lines(self):
        # We don't have our own line to output
        return super(RootTask, self).lines() - 1

    def output(self):
        for subtask in self.subtasks:
            subtask.output(indent=0)
