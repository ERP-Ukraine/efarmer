# Copyright 2026 VentorTech OU
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

import fnmatch
import html
import logging
import os
import stat
import tarfile
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .transports import TRANSPORTS

_logger = logging.getLogger(__name__)


def human_size(size):
    size = float(size or 0)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if size < 1024 or unit == 'TB':
            return f"{size:.0f} {unit}" if unit == 'B' else f"{size:.1f} {unit}"
        size /= 1024


class DbRemoteBackup(models.Model):
    """Copies the backup files Odoo.sh already creates (~/backup.daily) to an
    SFTP or FTP/FTPS server."""
    _name = 'db.remote.backup'
    _description = 'Copy Odoo.sh Backups to SFTP / FTP'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    # -------------------------------------------------------------- source
    source_path = fields.Char(
        string='Source Folder', required=True, default='~/backup.daily',
        help="Folder in the Odoo.sh container where Odoo.sh keeps its daily "
             "backups. '~' is the home folder of the Odoo process.")
    file_pattern = fields.Char(
        string='File Pattern', default='*',
        help="Only files matching one of these patterns are copied, "
             "separated by commas, e.g. '*.zip, *.dump'. '*' = everything.")
    include_subfolders = fields.Boolean(
        string='Include Subfolders', default=True,
        help="Also copy files that are inside subfolders of the source.")
    pack_folders = fields.Boolean(
        string='Pack Subfolders into Archives',
        help="Pack every first-level subfolder of the source (e.g. a "
             "filestore folder with thousands of files) into one .tar.gz "
             "archive and upload that, instead of file by file.")
    min_file_age = fields.Integer(
        string='Minimum File Age (minutes)', default=30,
        help="Files modified more recently are skipped for now, so a backup "
             "that Odoo.sh is still writing is never copied half-finished.")
    source_preview = fields.Html(string='Files in Source Folder',
                                 compute='_compute_source_preview',
                                 sanitize=False)
    keep_days = fields.Integer(
        string='Keep (days)', default=30,
        help="Files uploaded by this module are deleted from the server "
             "after this many days. 0 = keep forever. Other files in the "
             "folder are never touched.")

    protocol = fields.Selection([('sftp', 'SFTP (SSH)'),
                                 ('ftp', 'FTP / FTPS')],
                                required=True, default='sftp')
    host = fields.Char(required=True)
    port = fields.Integer(default=22)
    username = fields.Char(string='User')
    auth_method = fields.Selection([('password', 'Password'),
                                    ('key', 'Private Key')],
                                   string='Authentication', default='password')
    password = fields.Char(copy=False)
    private_key = fields.Text(string='Private Key (stored)', copy=False)
    private_key_input = fields.Text(
        string='Private Key', compute='_compute_private_key_input',
        inverse='_inverse_private_key_input',
        help="Paste the whole private key (OpenSSH or PEM). It is stored "
             "but never displayed again; paste a new one to replace it.")
    private_key_set = fields.Boolean(compute='_compute_private_key_input')
    key_passphrase = fields.Char(string='Key Passphrase', copy=False)
    ftp_tls = fields.Boolean(
        string='Use FTPS (TLS)', default=True,
        help="Strongly recommended: plain FTP sends the password and the "
             "backups unencrypted.")
    ftp_active_mode = fields.Boolean(
        string='Active Mode',
        help="Leave unchecked (passive mode) unless your server requires it.")
    remote_folder = fields.Char(
        string='Remote Folder', default='odoo-backups',
        help="Each backup goes into a sub-folder named after its date, e.g. "
             "odoo-backups/2026-10-14/<file>. Relative to the login folder, "
             "or absolute when it starts with '/'.")

    notify_on_failure = fields.Boolean(string='Email on Failure', default=True)
    notify_email = fields.Char(
        string='Notification Email',
        help="Comma separated. Empty = email of the administrator.")
    healthcheck_url = fields.Char(
        string='Heartbeat URL',
        help="Optional (e.g. https://hc-ping.com/<uuid> from healthchecks.io)."
             " Called after each successful run, <url>/fail after a failed "
             "one: you also get an alert if the job silently stops.")
    last_run_date = fields.Datetime(string='Last Run', readonly=True,
                                    copy=False)
    last_run_status = fields.Selection([('success', 'Success'),
                                        ('nothing', 'Nothing new'),
                                        ('failed', 'Failed')],
                                       string='Last Status', readonly=True,
                                       copy=False)
    last_run_message = fields.Text(string='Last Run Details', readonly=True,
                                   copy=False)
    last_success_date = fields.Datetime(string='Last Successful Upload',
                                        readonly=True, copy=False)
    last_alert_date = fields.Datetime(readonly=True, copy=False)

    log_ids = fields.One2many('db.remote.backup.log', 'config_id',
                              string='History')
    log_count = fields.Integer(compute='_compute_log_count')

    @api.depends('private_key')
    def _compute_private_key_input(self):
        for rec in self:
            rec.private_key_input = False
            rec.private_key_set = bool(rec.private_key)

    def _inverse_private_key_input(self):
        for rec in self:
            if rec.private_key_input:
                rec.private_key = rec.private_key_input.strip()

    def _compute_log_count(self):
        data = self.env['db.remote.backup.log']._read_group(
            [('config_id', 'in', self.ids)], ['config_id'], ['__count'])
        counts = {config.id: count for config, count in data}
        for rec in self:
            rec.log_count = counts.get(rec.id, 0)

    @api.onchange('protocol')
    def _onchange_protocol(self):
        self.port = 22 if self.protocol == 'sftp' else 21

    @api.depends('source_path', 'file_pattern', 'include_subfolders',
                 'pack_folders', 'min_file_age')
    def _compute_source_preview(self):
        for rec in self:
            rec.source_preview = rec._render_source_preview()

    def _render_source_preview(self):
        esc = html.escape
        try:
            base, items = self._scan_source()
        except UserError as error:
            return (f'<div class="alert alert-warning" role="alert">'
                    f'{esc(str(error))}</div>')
        if not items:
            return (f'<div class="alert alert-info" role="alert">'
                    f'{esc(_("Folder %s exists but no file matches the pattern.", base))}'
                    f'</div>')
        done = self._done_keys()
        now = time.time()
        rows = []
        for item in items[:300]:
            if (item['rel'], item['size'], item['mtime']) in done:
                status = '<span class="badge text-bg-success">%s</span>' % esc(_('Uploaded'))
            elif now - item['mtime'] < (self.min_file_age or 0) * 60:
                status = '<span class="badge text-bg-secondary">%s</span>' % esc(_('Too new, waiting'))
            else:
                status = '<span class="badge text-bg-warning">%s</span>' % esc(_('Pending'))
            modified = datetime.fromtimestamp(item['mtime'], timezone.utc)
            kind = ' <i class="fa fa-folder text-muted"></i>' if item['is_dir'] else ''
            rows.append(
                f"<tr><td>{esc(item['rel'])}{kind}</td>"
                f"<td class='text-end'>{human_size(item['size'])}</td>"
                f"<td>{modified:%Y-%m-%d %H:%M} UTC</td><td>{status}</td></tr>")
        more = (f"<p>… {len(items) - 300} more</p>" if len(items) > 300 else '')
        return (
            f"<p><b>{esc(base)}</b> — {len(items)} item(s)</p>"
            "<table class='table table-sm'><thead><tr>"
            f"<th>{esc(_('File'))}</th><th class='text-end'>{esc(_('Size'))}</th>"
            f"<th>{esc(_('Modified'))}</th><th>{esc(_('Status'))}</th>"
            f"</tr></thead><tbody>{''.join(rows)}</tbody></table>{more}")

    def _source_base(self):
        return os.path.abspath(os.path.expanduser(
            (self.source_path or '~/backup.daily').strip()))

    def _patterns(self):
        raw = (self.file_pattern or '*').replace(';', ',')
        return [p.strip() for p in raw.split(',') if p.strip()] or ['*']

    def _scan_source(self):
        """Return (base_folder, items); an item is a dict with the keys
        path, rel, size, mtime, is_dir. Raise UserError when the folder is
        missing (normal on staging / development builds)."""
        base = self._source_base()
        if not os.path.isdir(base):
            raise UserError(_(
                "Folder %s not found or not readable by the Odoo process. "
                "On Odoo.sh it exists only in the production container, so "
                "this is expected on staging and development builds.", base))
        patterns = self._patterns()

        def matches(name, rel):
            return any(fnmatch.fnmatch(name, p) or fnmatch.fnmatch(rel, p)
                       for p in patterns)

        items = []
        for entry in sorted(os.scandir(base), key=lambda e: e.name):
            try:
                st = entry.stat(follow_symlinks=True)
            except OSError:
                continue
            if stat.S_ISREG(st.st_mode):
                if matches(entry.name, entry.name):
                    items.append({'path': entry.path, 'rel': entry.name,
                                  'size': st.st_size, 'mtime': st.st_mtime,
                                  'is_dir': False})
            elif stat.S_ISDIR(st.st_mode) and self.include_subfolders:
                if self.pack_folders:
                    size, mtime = self._folder_fingerprint(entry.path)
                    items.append({'path': entry.path,
                                  'rel': entry.name + '.tar.gz',
                                  'size': size, 'mtime': mtime,
                                  'is_dir': True})
                else:
                    items.extend(self._walk(base, entry.path, matches))
        return base, items

    @staticmethod
    def _walk(base, folder, matches):
        found = []
        for root, dirs, files in os.walk(folder):
            dirs.sort()
            for name in sorted(files):
                full = os.path.join(root, name)
                rel = os.path.relpath(full, base).replace(os.sep, '/')
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                if stat.S_ISREG(st.st_mode) and matches(name, rel):
                    found.append({'path': full, 'rel': rel,
                                  'size': st.st_size, 'mtime': st.st_mtime,
                                  'is_dir': False})
        return found

    @staticmethod
    def _folder_fingerprint(folder):
        """Total size and newest mtime of a folder: they change whenever a
        file inside changes, so the archive is re-uploaded only then."""
        size, mtime = 0, os.stat(folder).st_mtime
        for root, _dirs, files in os.walk(folder):
            for name in files:
                try:
                    st = os.stat(os.path.join(root, name))
                except OSError:
                    continue
                size += st.st_size
                mtime = max(mtime, st.st_mtime)
        return size, mtime

    def _done_keys(self):
        """Fingerprints (name, size, mtime) of files already uploaded (or
        uploaded and later removed by retention): never uploaded twice."""
        logs = self.env['db.remote.backup.log'].search_read(
            [('config_id', '=', self.id),
             ('state', 'in', ('uploaded', 'deleted'))],
            ['name', 'size', 'mtime'])
        return {(log['name'], int(log['size']), log['mtime']) for log in logs}

    def _remote_path(self, item):
        day = datetime.fromtimestamp(item['mtime'], timezone.utc)
        folder = (self.remote_folder or '').strip()
        parts = [p for p in (folder.strip('/'), f"{day:%Y-%m-%d}", item['rel'])
                 if p]
        prefix = '/' if folder.startswith('/') else ''
        return prefix + '/'.join(parts)

    @staticmethod
    def _notification(title, message, kind='success', sticky=False):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': title, 'message': message, 'type': kind,
                       'sticky': sticky},
        }

    def _get_transport(self):
        self.ensure_one()
        return TRANSPORTS[self.protocol](self)

    def action_test_connection(self):
        self.ensure_one()
        try:
            with self._get_transport() as transport:
                transport.test()
        except Exception as error:
            _logger.info("Backup connection test failed", exc_info=True)
            return self._notification(_("Connection failed"),
                                      str(error) or repr(error), 'danger',
                                      sticky=True)
        return self._notification(
            _("Connection OK"),
            _("Connected and wrote a test file in '%s'.",
              self.remote_folder or '.'))

    def action_run_now(self):
        """Run in the background through the scheduled action: big uploads
        would otherwise hit the HTTP request timeout."""
        self.env.ref('db_backup_ftp_sftp.ir_cron_db_remote_backup') \
            .sudo()._trigger()
        return self._notification(
            _("Copy started"),
            _("The upload runs in the background. Reload this page in a few "
              "minutes and check 'Last Run' and the history."))

    def action_view_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Upload History"),
            'res_model': 'db.remote.backup.log',
            'view_mode': 'list,form',
            'domain': [('config_id', '=', self.id)],
            'context': {'default_config_id': self.id},
        }

    def action_view_cron(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ir.cron',
            'res_id': self.env.ref(
                'db_backup_ftp_sftp.ir_cron_db_remote_backup').id,
            'view_mode': 'form',
        }

    @api.model
    def _cron_run(self):
        for config in self.search([]):
            config._run_sync()

    def _commit(self):
        """Persist progress after every file, so a run stopped by the
        Odoo.sh cron time limit resumes where it stopped."""
        if not getattr(threading.current_thread(), 'testing', False) and \
                not self.env.context.get('db_backup_no_commit'):
            self.env.cr.commit()

    def _run_sync(self):
        self.ensure_one()
        Log = self.env['db.remote.backup.log']
        uploaded, errors = [], []
        try:
            _base, items = self._scan_source()
        except UserError as error:
            self._finish('failed', str(error))
            return
        done = self._done_keys()
        now = time.time()
        min_age = (self.min_file_age or 0) * 60
        pending = [i for i in items
                   if (i['rel'], i['size'], i['mtime']) not in done
                   and now - i['mtime'] >= min_age]
        expired = Log.browse()
        if self.keep_days > 0:
            expired = Log.search([
                ('config_id', '=', self.id), ('state', '=', 'uploaded'),
                ('upload_date', '<', fields.Datetime.now() - timedelta(
                    days=self.keep_days))])
        if not pending and not expired:
            self._finish('nothing', _("No new files in the source folder."))
            return
        try:
            with self._get_transport() as transport:
                for item in pending:
                    error = self._upload_item(transport, item)
                    if error:
                        errors.append(f"{item['rel']}: {error}")
                    else:
                        uploaded.append(item['rel'])
                    self._commit()
                for log in expired:
                    try:
                        transport.delete(log.remote_path)
                        log.write({'state': 'deleted',
                                   'deleted_date': fields.Datetime.now()})
                    except Exception as error:
                        _logger.warning("Backup copy: cannot delete %s",
                                        log.remote_path, exc_info=True)
                        errors.append(_("Delete %(path)s: %(error)s",
                                        path=log.remote_path, error=error))
                    self._commit()
        except Exception as error:
            _logger.exception("Backup copy '%s' failed", self.name)
            errors.append(_("Connection: %s", str(error) or repr(error)))
        lines = []
        if uploaded:
            lines.append(_("Uploaded: %s", ', '.join(uploaded)))
        if expired:
            lines.append(_("Retention: %s old file(s) processed",
                           len(expired)))
        lines += errors
        self._finish('failed' if errors else 'success', '\n'.join(lines),
                     uploaded=bool(uploaded))

    def _upload_item(self, transport, item):
        """Upload one item and log it. Return None or the error text."""
        Log = self.env['db.remote.backup.log']
        remote_path = self._remote_path(item)
        start = time.time()
        tmp_archive = None
        try:
            local_path = item['path']
            if item['is_dir']:
                tmp_archive = self._pack_folder(item['path'])
                local_path = tmp_archive
            size = os.path.getsize(local_path)
            transport.upload(local_path, remote_path)
            Log.create({
                'config_id': self.id, 'name': item['rel'],
                'size': item['size'], 'mtime': item['mtime'],
                'uploaded_size': size, 'remote_path': remote_path,
                'state': 'uploaded', 'upload_date': fields.Datetime.now(),
                'duration': time.time() - start,
            })
            _logger.info("Backup copy: uploaded %s -> %s (%s)", item['rel'],
                         remote_path, human_size(size))
            return None
        except Exception as error:
            _logger.warning("Backup copy: upload of %s failed", item['rel'],
                            exc_info=True)
            Log.create({
                'config_id': self.id, 'name': item['rel'],
                'size': item['size'], 'mtime': item['mtime'],
                'remote_path': remote_path, 'state': 'failed',
                'upload_date': fields.Datetime.now(),
                'duration': time.time() - start,
                'message': str(error) or repr(error),
            })
            return str(error) or repr(error)
        finally:
            if tmp_archive and os.path.exists(tmp_archive):
                os.remove(tmp_archive)

    @staticmethod
    def _pack_folder(folder):
        handle, path = tempfile.mkstemp(suffix='.tar.gz',
                                        prefix='backup_copy_')
        os.close(handle)
        with tarfile.open(path, 'w:gz', compresslevel=1) as tar:
            tar.add(folder, arcname=os.path.basename(folder))
        return path

    def _finish(self, status, message, uploaded=False):
        values = {'last_run_date': fields.Datetime.now(),
                  'last_run_status': status,
                  'last_run_message': message}
        if uploaded and status == 'success':
            values['last_success_date'] = fields.Datetime.now()
        if status == 'failed' and (
                self.last_run_status != 'failed' or not self.last_alert_date
                or self.last_alert_date < fields.Datetime.now()
                - timedelta(hours=23)):
            values['last_alert_date'] = fields.Datetime.now()
            self._send_failure_email(message)
        self.sudo().write(values)
        self._ping_heartbeat(status)
        self._commit()

    def _ping_heartbeat(self, status):
        if not self.healthcheck_url:
            return
        url = self.healthcheck_url.strip().rstrip('/')
        if status == 'failed':
            url += '/fail'
        try:
            requests.get(url, timeout=10)
        except requests.RequestException:
            _logger.warning("Backup heartbeat ping failed", exc_info=True)

    def _send_failure_email(self, message):
        if not self.notify_on_failure:
            return
        email_to = self.notify_email or self.env.ref('base.user_admin').email
        if not email_to:
            return
        self.env['mail.mail'].sudo().create({
            'subject': _("[%(db)s] Copying the Odoo.sh backups failed: "
                         "%(name)s", db=self.env.cr.dbname, name=self.name),
            'email_to': email_to,
            'body_html': (
                f"<p>{html.escape(_('Copying the Odoo.sh backups to SFTP/FTP failed.'))}</p>"
                f"<p><b>{html.escape(self.name)}</b> - "
                f"{html.escape(self.host or '')}</p>"
                f"<pre>{html.escape(message or '')}</pre>"),
            'auto_delete': True,
        })
