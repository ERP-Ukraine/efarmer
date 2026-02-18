# See LICENSE file for full copyright and licensing details.

from .status_abstract import StatusAbstract


MEDIA_STATUS_MAP = {
    'FAILED': ('Failed', 'Media processing has failed.'),
    'PROCESSING': ('Processing', 'Media is being processed.'),
    'READY': ('Ready', 'Media is ready to be displayed.'),
    'UPLOADED': ('Uploaded', 'Media has been uploaded but not yet processed.'),
}


class MediaStatus(StatusAbstract):

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
        return MEDIA_STATUS_MAP
