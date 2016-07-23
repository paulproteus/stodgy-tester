# This file contains all sorts of helper classes & functions which make the main function easier to
# understand.
from __future__ import (
    unicode_literals,
    print_function,
    absolute_import,
)
import ansicolor
import datetime
import os
import subprocess


def _make_colored_printer(color):
    def make_print_colored(color=color):
        def print_colored(*args, **kwargs):
            unicode_args = []
            for arg in args:
                if type(arg) is str:
                    unicode_args.append(arg.decode('utf-8'))
                elif isinstance(arg, Exception):
                    unicode_args.append(unicode(arg))
                else:
                    unicode_args.append(arg)
            return print(color(u' '.join(unicode_args)), **kwargs)
        return print_colored
    return make_print_colored(color)

print_info = _make_colored_printer(color=ansicolor.cyan)
print_warn = _make_colored_printer(color=ansicolor.green)
print_progress = _make_colored_printer(color=ansicolor.black)
print_error = _make_colored_printer(color=ansicolor.red)


class CommandRunner(object):
    def __init__(self, default_cwd, extra_env=None, print_cmd=True):
        '''The whole point of this CommandRunner is to encapsulate a default CWD value.'''
        self._default_cwd = default_cwd
        self._default_env = os.environ.copy()
        self._full_env = self._default_env
        self._extra_env = extra_env
        if self._extra_env:
            self._full_env.update(self._extra_env)
        self._should_print_cmd = print_cmd
        self._should_print_cmd_output = True
        self._should_print_timing = True

    def _print_cmd_start(self, argv):
        if not self._should_print_cmd:
            return 0
        msg_strings = ['$']
        env_strings = []
        if self._extra_env:
            for key in self._extra_env:
                env_strings.append(key + '=' + self._extra_env[key])
        msg_strings.extend(env_strings)
        msg_strings.extend(argv)
        msg = ' '.join(msg_strings)
        print_info(msg)

    def _print_cmd_end(self, printed_length, started_time):
        if not self._should_print_cmd:
            return
        now = datetime.datetime.utcnow()
        print_info('  ' + '[%d sec]' % ((now - started_time).seconds,))

    def __call__(self, argv):
        '''Run the command indicated by argv. Raise an exception if it failed to exit 0.

        Depending on the value of self._should_print_cmd, also print the command & how long it took.
        '''
        # TODO(soon): Create log files of each test in a text file, but only print out what seems
        # relevant.
        printed_length = self._print_cmd_start(argv)
        started_time = datetime.datetime.utcnow()
        output = '(Output not known)'
        # Run the process. capturing its output, and printing it if it exited non-zero.
        p = subprocess.Popen(
            argv, cwd=self._default_cwd, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self._default_env,
        )
        output = ''
        for line in p.stdout:
            line = line.rstrip()
            output += unicode(line, 'utf-8') + u'\n'
            if self._should_print_cmd_output:
                if line:
                    print_info(line)
        status = p.wait()
        stderr = p.communicate()[1].decode('utf-8', 'replace')
        self._print_cmd_end(printed_length, started_time)
        if status != 0:
            raise_me = Exception(u"Subprocess failed: argv=%s, stderr=%s" % (argv, stderr))
            raise_me.status = status
            raise_me.output = output
            raise_me.stderr = stderr
            raise_me.argv = argv
            raise raise_me
        return output


class VirtualMachine(object):
    '''Model for a Vagrant VM.'''
    def __init__(self, name, command_runner):
        # Store a name so we can print it
        self._name = name
        # Store a command runner so that someone can configure default_cwd just once.
        self._command_runner = command_runner
        # Store a flag indicating if the VM seems up. If it's not, we auto-start it as needed.
        self._cached_box_seems_up = False

    def suspend(self):
        self._command_runner(['vagrant', 'suspend', self._name])
        self._cached_box_seems_up = False

    def rsync(self):
        self.up_or_resume_if_needed()
        self._command_runner(['vagrant', 'rsync', self._name])

    def run_command_within_vm(self, command_as_str):
        '''Ask Vagrant to run a shell command inside this Linux virtual machine.'''
        self.up_or_resume_if_needed()
        full_bash_cmd = 'set -e; ' + command_as_str
        self._command_runner(['vagrant', 'ssh', self._name, '-c', full_bash_cmd])

    def up_or_resume_if_needed(self):
        "Ask Vagrant to attempt to resume this VM, and if that doesn't work, then boot it fresh."
        if self._cached_box_seems_up:
            return
        # First, try doing vagrant resume.
        try:
            output = self._command_runner(['vagrant', 'resume', self._name])
            if (
                    ('VM not created. Moving on' in output) or
                    ('Domain is not created' in output) or
                    ('Domain is not suspended' in output)):
                pass  # Still need to vagrant up.
            else:
                self._cached_box_seems_up = True
                return output
        except Exception as e:
            print_warn("** Warning: exception during vagrant resume", self._name)
            print_warn("Going to do vagrant up instead.")
            print_warn(e)

        # Then, always do "vagrant up", since it should be a no-up if the VM is already up, and if
        # the VM isn't up, then we bring it up.
        output = self._command_runner(['vagrant', 'up', self._name])
        self._cached_box_seems_up = True
        return output

    def destroy_then_start(self):
        '''Ask Vagrant to remove all stored files on-disk related to this VM, then recreate it.

        Useful if the VM gets into some horrific state. No one should ever need this, yet I need it
        frequently. That's life, I guess.
        '''
        self._command_runner(['vagrant', 'destroy', '-f', self._name])
        self._cached_box_seems_up = False
        return self.up_or_resume_if_needed()
