# See LICENSE file for full copyright and licensing details.

from .base import GqlDict


class Media(GqlDict):
    """This is an GQL Interface, not a real object."""

    _gid_name = 'Media'
    _body = GqlDict._tmpl.MEDIA_BODY

    @property
    def name(self):
        self.ensure_one()
        return self.src.split('/')[-1]

    @property
    def status(self):
        self.ensure_one()
        return self._env.MediaStatus(self['status'])

    @property
    def src(self):
        self.ensure_one()
        return self._extract(self.to_dict(), 'preview.image.url', '') or ''

    @property
    def content_type(self):
        self.ensure_one()
        return self._env.MediaContentType(self['mediaContentType'])

    @property
    def is_image(self):
        self.ensure_one()
        return self.status.is_ready and self.content_type.is_image


class AbstractMedia(Media):
    """This is an abstract class for media objects such as MediaImage, Video etc."""

    _media_type = None

    def __repr__(self):
        return f'{self._media_type}({self.id})'

    def create_gid(self, *args, **kw) -> str:
        value = super().create_gid(*args, **kw)
        return value.replace('Media', self._media_type)
