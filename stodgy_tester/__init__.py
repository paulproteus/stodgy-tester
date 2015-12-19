from __future__ import (
    unicode_literals,
    print_function,
    absolute_import,
)
import argparse
import glob
import importlib
import logging
import os
import pexpect
import random
import re
import subprocess
import sys
import helpers

plugin = None


def _run_capture_output(*args, **kwargs):
    kwargs = dict(kwargs)
    kwargs['stdout'] = subprocess.PIPE
    p = subprocess.Popen(*args, **kwargs)
    status = p.wait()
    output = p.communicate()[0]
    assert status == 0, ("subprocess failed: argv=%s, status=%d, output=%s" % (
        args, status, output))
    return output


def _expect(line, current_cmd, do_re_escape=True, do_detect_slow=True,
            strip_comments=True, verbose=True):
    timeout = 2

    slow_text_timeout = int(os.environ.get('SLOW_TEXT_TIMEOUT', 30))
    veryslow_text_timeout = 2 * slow_text_timeout

    if do_detect_slow:
        slow_token = '$[slow]'
        if line.startswith(slow_token):
            helpers.print_info('Slow line...')
            timeout = slow_text_timeout
            line = line.replace(slow_token, '', 1)

        veryslow_token = '$[veryslow]'
        if line.startswith(veryslow_token):
            helpers.print_info('Very slow line...')
            timeout = veryslow_text_timeout
            line = line.replace(veryslow_token, '', 1)

    if verbose:
        helpers.print_info('expecting', line)

    if do_re_escape:
        line = re.escape(line)

    current_cmd.expect(line, timeout=timeout)


RUNNER = helpers.CommandRunner(default_cwd=os.getcwd(), extra_env={
    'VAGRANT_DEFAULT_PROVIDER': 'libvirt'
})


def handle_test_script(vagrant_box_name, lines):
    current_cmd = None

    for line in lines:
        # Figure out what we want to do, given this line.
        if line.startswith('$[run]'):
            arg = line.replace('$[run]', '')
            arg = 'vagrant ssh ' + vagrant_box_name + ' -c "' + arg + '"'
            helpers.print_info('$', arg)
            current_cmd = pexpect.spawn(arg, cwd=os.getcwd())
        elif '$[exitcode]' in line:
            left, right = map(lambda s: s.strip(), line.split('$[exitcode]'))
            # Expect end of file.
            current_cmd.expect(pexpect.EOF, timeout=1)
            current_cmd.close()
            assert current_cmd.exitstatus == int(right)

        elif '$[type]' in line:
            # First, we expect the left side.
            left, right = map(lambda s: s.strip(), line.split('$[type]'))
            _expect(left, current_cmd=current_cmd)

            if right == 'gensym':
                # instead of typing the literal string gensym, we generate
                # a hopefully unique collection of letters and numbers.
                right = ''.join(
                    random.sample('abcdefghijklmnopqrstuvwxyz0123456789', 10))

            # Then we sendline the right side.
            current_cmd.sendline(right)
        else:
            # For now, assume the action is expect.
            _expect(line, current_cmd=current_cmd)


def parse_test_file(headers_list):
    postconditions = []
    cleanups = []
    parsed_headers = {}

    for header in headers_list:
        key, value = map(lambda s: s.strip(), header.split(':'))
        key = key.lower()

        if key == 'vagrant-box':
            parsed_headers['vagrant-box'] = value

        if key == 'title':
            parsed_headers['title'] = value

        if key == 'vagrant-destroy-if-bash':
            if key not in parsed_headers:
                parsed_headers[key] = []
            parsed_headers[key].append(value)

        if key == 'precondition':
            if key not in parsed_headers:
                parsed_headers[key] = []
            parsed_headers[key].append(value)

        if key == 'postcondition':
            postconditions.append([key, value])

        if key == 'cleanup':
            cleanups.append([key, value])

    # Some keys are required.
    #
    # Also uh I should probably be using capnproto for this, hmm.
    for required_key in ['vagrant-box']:
        assert required_key in parsed_headers, "Missing %s" % (required_key,)

    return parsed_headers, postconditions, cleanups


def handle_headers(parsed_headers):
    vagrant_box_name = parsed_headers['vagrant-box']
    vm = helpers.VirtualMachine(name=vagrant_box_name, command_runner=RUNNER)

    # Bring up VM, if needed.
    vm.up_or_resume_if_needed()

    values = parsed_headers.get('vagrant-destroy-if-bash')
    if values:
        for value in values:
            succeeded = False
            try:
                vm.run_command_within_vm(value)
            except:
                succeeded = True
            if not succeeded:
                helpers.print_progress('Destroying this VM...')
                vm.destroy()
                helpers.print_info('Recreating as needed...')
                vm.up_or_resume()

    values = parsed_headers.get('precondition')
    if values:
        for value in values:
            getattr(plugin, value)(vm)


def handle_postconditions(postconditions_list):
    for key, value in postconditions_list:
            evald_value = eval(value)
            assert eval(value), "value of " + value + " was " + str(
                evald_value)


def parse_test_by_filename(filename):
    lines = open(filename).read().split('\n')
    position_of_blank_line = lines.index('')

    headers, test_script = (lines[:position_of_blank_line],
                            lines[position_of_blank_line+1:])

    parsed_headers, postconditions, cleanups = parse_test_file(headers)
    return parsed_headers, postconditions, cleanups, headers, test_script


def run_one_test(filename, box):
    parsed_headers, postconditions, cleanups, headers, test_script = parse_test_by_filename(
        filename)

    # Make the VM etc., if necessary.
    handle_headers(parsed_headers)
    helpers.print_progress("*** Running test from file:", filename)
    helpers.print_info(" -> Extra info:", repr(headers))

    # Run the test script, using pexpect to track its output.
    try:
        handle_test_script(parsed_headers['vagrant-box'], test_script)
    except Exception as e:
        helpers.print_error(str(e))
        raise
        helpers.print_warn('Dazed and confused, but trying to continue.')

    # Run any sanity-checks in the test script, as needed.
    handle_postconditions(postconditions)

    # If the test knows it needs to do some cleanup, e.g. destroying
    # its VM, then do so.
    handle_cleanups(parsed_headers, cleanups, box)


def handle_cleanups(parsed_headers, cleanups, box):
    for key, value in cleanups:
        helpers.print_info('Doing cleanup task', value)
        try:
            getattr(plugin, value)(box)
        except Exception as e:
            helpers.print_error('Ran into error', str(e))
            raise


def import_plugin(plugin_name):
    try:
        return importlib.import_module(plugin_name)
    except ImportError:
        helpers.print_error("You provided a plugin named", plugin_name,
                            "but I cannot seem to import it. Exception details follow.")
        raise


def main():
    parser = argparse.ArgumentParser(description='Run automated tests with the help of Vagrant.')
    parser.add_argument("--plugin", type=str,
                        help="Plugin that defines cleanup etc. for your tests")
    parser.add_argument("--on-vm-start", type=str,
                        help="Name of a Python callable to run when a VM is about to start.",
                        dest='on_vm_start')
    parser.add_argument(
        '--rsync',
        help='Perform `vagrant rsync` to ensure install.sh in the VM is current.',
        action='store_true',
    )
    parser.add_argument(
        '--halt-afterward',
        help='After running the tests, stop the VMs.',
        action='store_true',
    )
    parser.add_argument(
        'testfiles',
        metavar='testfile',
        nargs='*',
        help='A *.t file to run (multiple is OK; empty testfile sequence means run all)',
        default=[],
    )

    args = parser.parse_args()
    # HACK
    global plugin
    plugin = import_plugin(args.plugin)

    testfiles = args.testfiles
    if not testfiles:
        testfiles = sorted(glob.glob('*.t'))

    # Sort testfiles by the Vagrant box they use. That way, we can minimize
    # up/resume/suspend churn.
    testfiles = sorted(testfiles,
                       key=lambda filename: parse_test_by_filename(filename)[0]['vagrant-box'])

    keep_going = True

    boxes_by_name = {}
    boxes_that_have_been_prepared = {}

    box = None
    for filename in testfiles:
        this_vagrant_box_name = parse_test_by_filename(filename)[0]['vagrant-box']
        if this_vagrant_box_name not in boxes_by_name:
            # If this Vagrant box is not yet in boxes_by_name, then we should stop the previous one
            # to conserve RAM.
            if box:
                if args.halt_afterward:
                    box.stop()
                else:
                    box.suspend()

            box = helpers.VirtualMachine(name=this_vagrant_box_name,
                                         command_runner=RUNNER)
            boxes_by_name[this_vagrant_box_name] = box
        else:
            box = boxes_by_name[this_vagrant_box_name]

        if this_vagrant_box_name not in boxes_that_have_been_prepared:
            # If we were told to uninstall first, let's do that.
            if args.on_vm_start:
                getattr(plugin, args.on_vm_start)(box)
            # Same with rsyncing.
            if args.rsync:
                helpers.print_info('** rsync-ing the latest Sandstorm installer etc. to',
                                   this_vagrant_box_name)
                box.rsync()
                # Indicate that no further prep is needed.
                boxes_that_have_been_prepared[this_vagrant_box_name] = True
        try:
            if keep_going:
                run_one_test(filename, box)
        except:
            keep_going = False
            logging.exception("Alas! A test failed!")

    # If we need to stop the VMs, now's a good time to stop
    # them.
    if args.halt_afterward:
        subprocess.check_output(
            ['vagrant', 'halt'],
            cwd=os.getcwd(),
        )

    if not keep_going:
        sys.exit(1)

    sys.exit(0)


if __name__ == '__main__':
    main()
