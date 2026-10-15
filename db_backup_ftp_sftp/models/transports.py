# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

"""SFTP and FTP/FTPS upload adapters.
Usage::

    with config._get_transport() as transport:
        transport.test()
        transport.upload(local_path, remote_path)
        transport.delete(remote_path)

``paramiko`` is imported lazily: the module installs without it and only the
SFTP protocol needs it (add ``paramiko`` to requirements.txt on Odoo.sh).
"""
import errno
import ftplib
import io
import logging
import os
import posixpath

from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BaseTransport:
    def __init__(self, config):
        self.config = config

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *exc):
        try:
            self.close()
        except Exception:
            _logger.debug("Error while closing transport", exc_info=True)

    def open(self):
        raise NotImplementedError

    def close(self):
        pass

    def test(self):
        raise NotImplementedError

    def upload(self, local_path, remote_path):
        raise NotImplementedError

    def delete(self, remote_path):
        raise NotImplementedError


class SftpTransport(BaseTransport):

    def open(self):
        try:
            import paramiko
        except ImportError:
            raise UserError(_(
                "The Python package 'paramiko' is not installed. On Odoo.sh "
                "add a line 'paramiko' to requirements.txt at the root of "
                "your repository and push."))
        c = self.config
        pkey = None
        if c.auth_method == 'key':
            pkey = self._load_key(paramiko, c.private_key,
                                  c.key_passphrase or None)
        self.client = paramiko.SSHClient()
        # Trust on first use, like most backup tools; traffic is encrypted.
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(
            hostname=c.host, port=c.port or 22, username=c.username,
            password=None if pkey else (c.password or None), pkey=pkey,
            look_for_keys=False, allow_agent=False,
            timeout=60, banner_timeout=60, auth_timeout=60)
        self.sftp = self.client.open_sftp()

    @staticmethod
    def _load_key(paramiko, key_text, passphrase):
        if not key_text:
            raise UserError(_("Please paste the private key."))
        key_text = key_text.strip() + '\n'
        errors = []
        for name in ('Ed25519Key', 'ECDSAKey', 'RSAKey', 'DSSKey'):
            key_cls = getattr(paramiko, name, None)
            if not key_cls:
                continue
            try:
                return key_cls.from_private_key(io.StringIO(key_text),
                                                password=passphrase)
            except Exception as error:
                errors.append(f"{name}: {error}")
        raise UserError(_("Could not read the private key. Details: %s",
                          '; '.join(errors)))

    def close(self):
        if getattr(self, 'sftp', None):
            self.sftp.close()
        if getattr(self, 'client', None):
            self.client.close()

    def _makedirs(self, path):
        if not path or path in ('/', '.'):
            return
        current = '/' if path.startswith('/') else ''
        for part in path.strip('/').split('/'):
            current = posixpath.join(current, part) if current else part
            try:
                self.sftp.stat(current)
            except IOError:
                self.sftp.mkdir(current)

    def test(self):
        folder = self.config.remote_folder or '.'
        self._makedirs(folder)
        probe = posixpath.join(folder, '.odoo_backup_write_test')
        with self.sftp.open(probe, 'w') as handle:
            handle.write('ok')
        self.sftp.remove(probe)

    def upload(self, local_path, remote_path):
        self._makedirs(posixpath.dirname(remote_path))
        tmp_path = remote_path + '.part'
        # confirm=True compares the remote size with the local one
        self.sftp.put(local_path, tmp_path, confirm=True)
        try:
            self.sftp.posix_rename(tmp_path, remote_path)
        except IOError:  # server without the posix-rename extension
            try:
                self.sftp.remove(remote_path)
            except IOError:
                pass
            self.sftp.rename(tmp_path, remote_path)

    def delete(self, remote_path):
        try:
            self.sftp.remove(remote_path)
        except IOError as error:
            if getattr(error, 'errno', None) != errno.ENOENT:
                raise


class FtpTransport(BaseTransport):

    def open(self):
        c = self.config
        ftp_cls = ftplib.FTP_TLS if c.ftp_tls else ftplib.FTP
        self.ftp = ftp_cls(timeout=120)
        self.ftp.encoding = 'utf-8'
        self.ftp.connect(c.host, c.port or 21)
        self.ftp.login(c.username or 'anonymous', c.password or '')
        if c.ftp_tls:
            self.ftp.prot_p()
        self.ftp.set_pasv(not c.ftp_active_mode)

    def close(self):
        if getattr(self, 'ftp', None):
            try:
                self.ftp.quit()
            except Exception:
                self.ftp.close()

    def _makedirs(self, path):
        if not path or path in ('/', '.'):
            return
        current = '/' if path.startswith('/') else ''
        for part in path.strip('/').split('/'):
            current = posixpath.join(current, part) if current else part
            try:
                self.ftp.mkd(current)
            except ftplib.error_perm:
                pass

    def test(self):
        folder = self.config.remote_folder or ''
        self._makedirs(folder)
        probe = posixpath.join(folder, '.odoo_backup_write_test') \
            if folder else '.odoo_backup_write_test'
        self.ftp.storbinary(f'STOR {probe}', io.BytesIO(b'ok'))
        self.ftp.delete(probe)

    def upload(self, local_path, remote_path):
        self._makedirs(posixpath.dirname(remote_path))
        tmp_path = remote_path + '.part'
        with open(local_path, 'rb') as stream:
            self.ftp.storbinary(f'STOR {tmp_path}', stream,
                                blocksize=1024 * 1024)
        local_size = os.path.getsize(local_path)
        try:
            self.ftp.voidcmd('TYPE I')
            remote_size = self.ftp.size(tmp_path)
        except ftplib.all_errors:
            remote_size = None  # server does not support SIZE
        if remote_size is not None and remote_size != local_size:
            raise UserError(_(
                "Upload incomplete: %(remote)s bytes on the server instead "
                "of %(local)s.", remote=remote_size, local=local_size))
        try:
            self.ftp.delete(remote_path)
        except ftplib.error_perm:
            pass
        self.ftp.rename(tmp_path, remote_path)

    def delete(self, remote_path):
        try:
            self.ftp.delete(remote_path)
        except ftplib.error_perm as error:
            if not str(error).startswith('550'):  # 550 = not found
                raise

TRANSPORTS = {
    'sftp': SftpTransport,
    'ftp': FtpTransport,
}
