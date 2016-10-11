from __future__ import (
    unicode_literals,
    print_function,
    absolute_import,
)
import stodgy_tester.helpers


def uninstall_sandstorm(box):
    stodgy_tester.helpers.print_info('** Uninstalling Sandstorm from', box._name)
    shell_command_list = [
        'sudo pkill -9 sandstorm || true',
        'sudo chattr -i /usr/local/bin',
        'for i in `seq 0 50` ; do if pgrep sandstorm  >/dev/null ; then sleep 0.1 ; fi ; done',
        'sudo rm -rf /opt/sandstorm',
        'sudo rm -rf $HOME/sandstorm',
        'sudo apt-get -y remove --purge postfix',
        'sudo rm -f /etc/sysctl.d/50-sandstorm.conf',
        # Remove any bind-mounting of /proc/sys, if present.
        'if mount | grep -q /proc/sys" " ; then sudo umount /proc/sys ; fi',
        (
            'if [ -e /proc/sys/kernel/unprivileged_userns_clone  ] ; '
            'then echo 0 | sudo dd of=/proc/sys/kernel/unprivileged_userns_clone ; fi'),
        'sudo pkill -9 sudo || true',
        'sudo hostname localhost',
        'sudo modprobe fuse',  # Workaround for issue #858
    ]
    as_text = ' && '.join([('( ' + x + ' )') for x in shell_command_list])
    box.run_command_within_vm(as_text)


def sandstorm_not_installed(box):
    stodgy_tester.helpers.print_info(
        '** Making sure Sandstorm not currently installed on', box._name)
    shell_command_list = [
        'if [ -e ~/sandstorm ] ; then exit 1 ; fi',
        'if [ -e /opt/sandstorm ] ; then exit 1 ; fi',
    ]
    as_text = ' && '.join([('( ' + x + ' )') for x in shell_command_list])
    box.run_command_within_vm(as_text)
