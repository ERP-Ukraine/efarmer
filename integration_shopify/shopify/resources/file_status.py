# See LICENSE file for full copyright and licensing details.

from .status_abstract import StatusAbstract


FILE_STATUS_MAP = {
    'FAILED': ('Failed', 'File processing has failed.'),
    'PROCESSING': ('Processing', 'File is being processed.'),
    'READY': ('Ready', 'File is ready to be displayed.'),
    'UPLOADED': ('Uploaded', 'File has been uploaded but hasn\'t been processed.'),
}


class FileStatus(StatusAbstract):

    failed = 'FAILED'
    processing = 'PROCESSING'
    ready = 'READY'
    uploaded = 'UPLOADED'

    @property
    def is_failed(self):
        return self == self.failed

    @property
    def is_processing(self):
        return self == self.processing

    @property
    def is_ready(self):
        return self == self.ready

    @property
    def is_uploaded(self):
        return self == self.uploaded

    @property
    def mapping(self):
        return FILE_STATUS_MAP
