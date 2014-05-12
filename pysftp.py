"""A friendly Python SFTP interface."""

import os
import socket
import tempfile
import paramiko
from paramiko import SSHException   # make available
from paramiko import AuthenticationException   # make available

__version__ = "0.2.4"


class ConnectionException(Exception):
    """Exception raised for connection problems

    Attributes:
        message  -- explanation of the error
    """

    def __init__(self, host, port):
        # Call the base class constructor with the parameters it needs
        Exception.__init__(self, host, port)
        self.message = 'Could not connect to host:port.  %s:%s'

class CredentialException(Exception):
    """Exception raised for credential problems

    Attributes:
        message  -- explanation of the error
    """

    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        Exception.__init__(self, message)
        self.message = message


class Connection(object):
    """Connects and logs into the specified hostname.
    Arguments that are not given are guessed from the environment.

    :param host: The Hostname or IP of the remote machine.
    :type str:
    :param username: Your username at the remote machine.
    :type str:
    :param private_key: Your private key file.
    :type str:
    :param password: Your password at the remote machine.
    :type str:
    :param port: The SSH port of the remote machine.(default: 22)
    :type int:
    :param private_key_pass: password to use, if private_key is encrypted.
    :type str:
    :param log: log connection/handshake details?
    :type bool:
    :returns: a connection to the requested machine
    :raises: ConnectionException, CredentialException, SSHException, AuthenticationException, PasswordRequiredException

    """

    def __init__(self,
                 host,
                 username=None,
                 private_key=None,
                 password=None,
                 port=22,
                 private_key_pass=None,
                 log=False,
                ):
        self._sftp_live = False
        self._sftp = None
        if not username:
            username = os.environ['LOGNAME']


        if log:
            # Log to a temporary file.
            templog = tempfile.mkstemp('.txt', 'ssh-')[1]
            paramiko.util.log_to_file(templog)

        # Begin the SSH transport.
        self._tranport_live = False
        try:
            self._transport = paramiko.Transport((host, port))
            self._tranport_live = True
        except (AttributeError, socket.gaierror):
            # couldn't connect
            raise ConnectionException(host, port)

        # Authenticate the transport. prefer password if given
        if password:
            # Using Password.
            self._transport.connect(username=username, password=password)
        else:
            # Use Private Key.
            if not private_key:
                # Try to use default key.
                if os.path.exists(os.path.expanduser('~/.ssh/id_rsa')):
                    private_key = '~/.ssh/id_rsa'
                elif os.path.exists(os.path.expanduser('~/.ssh/id_dsa')):
                    private_key = '~/.ssh/id_dsa'
                else:
                    raise CredentialException("You have not specified a "\
                                              "password or key.")

            private_key_file = os.path.expanduser(private_key)
            try:  #try rsa
                rsakey = paramiko.RSAKey
                prv_key = rsakey.from_private_key_file(private_key_file,
                                                       private_key_pass)
            except paramiko.SSHException:   #if it fails, try dss
                dsskey = paramiko.DSSKey
                prv_key = dsskey.from_private_key_file(private_key_file,
                                                       private_key_pass)
            self._transport.connect(username=username, pkey=prv_key)

    def _sftp_connect(self):
        """Establish the SFTP connection."""
        if not self._sftp_live:
            self._sftp = paramiko.SFTPClient.from_transport(self._transport)
            self._sftp_live = True

    def get(self, remotepath, localpath=None, callback=None):
        """Copies a file between the remote host and the local host.

        :param remotepath: the remote path and filename, source
        :type str:
        :param localpath: the local path and filename to copy, destination. If not specified, file is copied to local cwd
        :type str:
        :param callback: optional callback function (form: func(int, int)) that accepts the bytes transferred so far and the total bytes to be transferred/
        :type callable:

        :returns: nothing

        :raises: IOError

        """
        if not localpath:
            localpath = os.path.split(remotepath)[1]
        self._sftp_connect()
        self._sftp.get(remotepath, localpath, callback=callback)

    def put(self, localpath, remotepath=None, callback=None, confirm=True):
        """Copies a file between the local host and the remote host.

        :param localpath: the local path and filename
        :type str:
        :param remotepath: the remote path, else the remote cwd() and filename is used.
        :type str:
        :param callback: optional callback function (form: func(int, int)) that accepts the bytes transferred so far and the total bytes to be transferred.
        :type callable:
        :param confirm: whether to do a stat() on the file afterwards to confirm the file size
        :type bool:

        :returns: an SFTPAttributes object containing attributes about the given file

        :raises: IOError, OSError

        """
        if not remotepath:
            remotepath = os.path.split(localpath)[1]
        self._sftp_connect()
        return self._sftp.put(localpath, remotepath, callback=callback,
                              confirm=confirm)

    def execute(self, command):
        """Execute the given commands on a remote machine.  The command is executed without regard to the remote cwd.

        :param command: the command to execute.
        :type str:

        :returns: results

        """
        channel = self._transport.open_session()
        channel.exec_command(command)
        output = channel.makefile('rb', -1).readlines()
        if output:
            return output
        else:
            return channel.makefile_stderr('rb', -1).readlines()

    def chdir(self, remotepath):
        """change the current working directory on the remote

        :param remotepath: the remote path to change to
        :type str:

        :returns: nothing

        :raises: IOError
        """
        self._sftp_connect()
        self._sftp.chdir(remotepath)

    def getcwd(self):
        """return the current working directory on the remote

        :returns: a string representing the current remote path

        """
        self._sftp_connect()
        return self._sftp.getcwd()

    def listdir(self, path='.'):
        """return a list of files for the given path"""
        self._sftp_connect()
        return self._sftp.listdir(path)

    def remove(self, remotefile):
        """remove the file @ remotefile, remotefile may include a path, if no
        path, then cwd is used.  This method only works on files

        :param remotefile: the remote file to delete
        :type str:

        :returns: nothing

        :raises: IOError
        """
        self._sftp_connect()
        self._sftp.remove(remotefile)

    def rename(self, remote_src, remote_dest):
        """rename a file on the remote host.

        :param remote_src: the remote file to rename
        :type str:

        :param remote_dest: the remote file to put it
        :type str:

        :returns: nothing

        :raises: IOError
        """
        self._sftp_connect()
        self._sftp.rename(remote_src, remote_dest)

    def close(self):
        """Closes the connection and cleans up."""
        # Close SFTP Connection.
        if self._sftp_live:
            self._sftp.close()
            self._sftp_live = False
        # Close the SSH Transport.
        if self._tranport_live:
            self._transport.close()
            self._tranport_live = False

    def open(self, remote_file, mode='r', bufsize=-1):
        """Open a file on the remote server.

        See http://paramiko-docs.readthedocs.org/en/latest/api/sftp.html?highlight=open#paramiko.sftp_client.SFTPClient.open for details.

        :param remote_file: name of the file to open.
        :type str:

        :param mode: mode (Python-style) to open file (always assumed binary)
        :type str:

        :param bufsize: desired buffering (-1 = default buffer size)
        :type int:

        :returns: an SFTPFile object representing the open file

        :raises: IOError - if the file could not be opened.

        """
        self._sftp_connect()
        return self._sftp.open(remote_file, mode=mode, bufsize=bufsize)


    def __del__(self):
        """Attempt to clean up if not explicitly closed."""
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, etype, value, traceback):
        self.close()

